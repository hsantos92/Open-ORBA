"""Verified file copying for the mounted Orba volume; no overwrites or firmware writes."""
import hashlib,json,os,shutil,time
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET
from protocol import crc
from library import MODES
VOLUME=Path('/run/orba-studio')

def safe_relative(value):
    p=PurePosixPath(value.replace('\\','/'))
    if p.is_absolute() or '..' in p.parts or not p.parts:raise ValueError('Unsafe sound path: '+value)
    return Path(*p.parts)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def validate_volume(root=VOLUME):
    root=Path(root)
    if not root.is_mount() or not (root/'PersistentState.xml').is_file() or not (root/'sriracha_factory_content_version.txt').is_file():
        raise RuntimeError('Orba 3 storage is not mounted. Use Connect storage first.')
    return root

def transfer_plan(entry,library):
    files,missing=library.dependencies(entry)
    if missing:raise ValueError('Missing dependencies: '+', '.join(missing[:5]))
    plan={}
    def add(source,relative):
        relative=safe_relative(str(relative))
        if relative in plan and sha(plan[relative])!=sha(source):raise ValueError('Conflicting bundle files: '+str(relative))
        plan[relative]=source
    for p in files:
        if p.suffix not in ('.artipreset','.artisong','.artistem'):continue
        root=ET.parse(p).getroot()
        if p.suffix=='.artipreset':
            part=MODES.get(root.get('mode'))
            if not part:raise ValueError('Unknown preset instrument')
            add(p,Path('Presets')/part/p.name)
        elif p.suffix=='.artisong':add(p,Path('Songs')/p.name)
        else:
            # Stems require the original Stems hierarchy to retain sample references.
            parts=p.parts
            if 'Stems' not in parts:raise ValueError('Stem bundle is missing its original Stems folder structure')
            add(p,Path(*parts[parts.index('Stems'):]))
        for node in root.iter():
            name=node.get('fileName','')
            if name.lower().endswith('.wav'):
                sample=library.resolve(name,p)
                if not sample:raise ValueError('Missing sample '+name)
                if node.get('pool'):
                    rel=Path('SamplePools')/safe_relative(node.get('pool'))
                    if node.get('subdirectory'):rel/=safe_relative(node.get('subdirectory'))
                    add(sample,rel/safe_relative(name))
                elif 'Stems' in sample.parts:add(sample,Path(*sample.parts[sample.parts.index('Stems'):]))
                else:raise ValueError('Sample has no verified device destination: '+name)
    return plan

def copy_new(plan,root=VOLUME,progress=lambda text:None):
    root=validate_volume(root);required=0; todo=[]
    for relative,source in plan.items():
        target=root/safe_relative(str(relative))
        if not target.resolve().is_relative_to(root.resolve()):raise ValueError('Unsafe target')
        if target.exists():
            if sha(target)!=sha(source):raise ValueError('Existing device file differs; preserved: '+str(relative))
        else:todo.append((relative,source));required+=source.stat().st_size+4096
    if shutil.disk_usage(root).free<required+4*1024*1024:raise ValueError('Not enough free space on Orba')
    # Samples first; publish presets last so interruption cannot expose an incomplete sound.
    todo.sort(key=lambda pair: pair[0].suffix in ('.artipreset','.artisong'))
    created=[]
    for i,(relative,source) in enumerate(todo):
        target=root/relative;target.parent.mkdir(parents=True,exist_ok=True)
        progress(f'Copying {i+1}/{len(todo)}: {source.name}')
        # Exclusive create prevents races and overwrites. Remove partial files on failure.
        created_here=False
        try:
            with source.open('rb') as src,target.open('xb') as dst:
                created_here=True
                shutil.copyfileobj(src,dst,1024*1024);dst.flush();os.fsync(dst.fileno())
            if sha(target)!=sha(source):raise IOError('Copy verification failed: '+str(relative))
        except Exception:
            # Never unlink an existing file if exclusive creation failed.
            if created_here:target.unlink()
            raise
        created.append(str(relative))
        sidecar=target.with_suffix('.crc')
        if not sidecar.exists():
            checksum=0
            with target.open('rb') as src:
                # crc() has zero initialization; file sizes are bounded by local sound library.
                checksum=crc(src.read())
            with sidecar.open('x') as f:f.write(f'{checksum:04x}');f.flush();os.fsync(f.fileno())
    os.sync()
    return {'copied':created,'already_present':len(plan)-len(todo)}

def backup(destination,root=VOLUME,progress=lambda text:None):
    root=validate_volume(root); destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=False);manifest={}
    for i,source in enumerate(root.rglob('*')):
        if not source.is_file():continue
        relative=source.relative_to(root);target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target);digest=sha(target)
        if digest!=sha(source):raise IOError('Backup verification failed: '+str(relative))
        manifest[str(relative)]=digest
        if i%50==0:progress(f'Backed up {len(manifest)} files')
    (destination/'backup-sha256.json').write_text(json.dumps(manifest,indent=2))
    return destination
