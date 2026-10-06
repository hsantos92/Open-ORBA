"""Local sound catalog and portable, dependency-preserving preset bundles."""
from pathlib import Path, PurePosixPath
import hashlib, json, shutil, zipfile, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parent/'library'
MODES={'Drums':'Drum','Drum':'Drum','Bass':'Bass','Chords':'Chord','Chord':'Chord','Lead':'Lead'}

class Library:
    def __init__(self,root=ROOT): self.root=Path(root); self.entries=[]; self.files={}; self.scan()
    def scan(self):
        self.entries=[]; self.files={}; self.errors=[]; seen=set()
        for p in sorted(self.root.rglob('*')):
            if not p.is_file() or p.is_symlink(): continue
            self.files.setdefault(p.name,[]).append(p)
            if p.suffix not in ('.artipreset','.artisong'): continue
            try:
                raw=p.read_bytes()
                if len(raw)>8*1024*1024: continue
                tree=ET.fromstring(raw); digest=hashlib.sha256(raw).hexdigest()
                if digest in seen: continue
                seen.add(digest)
                self.entries.append({'name':tree.get('name',p.stem),'part':MODES.get(tree.get('mode'),'Song'),'description':tree.get('description',''),'path':p,'tree':tree,'digest':digest})
            except (OSError,ET.ParseError) as error: self.errors.append((str(p),str(error)))
        self.entries.sort(key=lambda e:(e['part'],e['name'].lower()))
    def resolve(self,name,origin):
        name=PurePosixPath(name.replace('\\','/'))
        if name.is_absolute() or '..' in name.parts: raise ValueError('Unsafe referenced path')
        candidates=self.files.get(name.name,[])
        if not candidates: return None
        # Prefer the containing imported/recovered package to avoid mixing versions.
        def affinity(p):
            return len(__import__('os').path.commonpath([str(p),str(origin)]).split('/'))
        return max(candidates,key=affinity)
    def dependencies(self,entry):
        found={}; missing=set(); queue=[entry['path']]
        while queue:
            path=queue.pop()
            if path in found: continue
            found[path]=True
            if path.suffix not in ('.artipreset','.artisong','.artistem'): continue
            tree=ET.parse(path).getroot()
            for node in tree.iter():
                for key,value in node.attrib.items():
                    if not value.lower().endswith(('.wav','.artipreset','.artistem','.png')): continue
                    target=self.resolve(value,path)
                    # Artwork is optional for sound playback, preserve when available.
                    if target: queue.append(target)
                    elif not value.lower().endswith('.png'): missing.add(value)
        return list(found),sorted(missing)
    def export(self,entry,destination):
        files,missing=self.dependencies(entry)
        if missing: raise ValueError('Missing sound dependencies: '+', '.join(missing[:5]))
        # Own format, not advertised as an Artiphon artibundle.
        with zipfile.ZipFile(destination,'x',zipfile.ZIP_DEFLATED) as z:
            manifest=[]
            for p in files:
                arc=str(p.relative_to(self.root)); z.write(p,arc); manifest.append(arc)
            z.writestr('orba-studio-manifest.json',json.dumps({'version':1,'name':entry['name'],'files':manifest}))
    def import_paths(self,paths):
        imported=0
        for source in map(Path,paths):
            digest=hashlib.sha256(source.read_bytes()).hexdigest()[:16]
            target=self.root/'imported'/digest
            if target.exists(): continue
            staging=self.root/'imported'/('.'+digest+'.partial'); staging.mkdir(parents=True,exist_ok=True)
            try:
                if zipfile.is_zipfile(source):
                    with zipfile.ZipFile(source) as z:
                        if sum(i.file_size for i in z.infolist())>1024**3: raise ValueError('Bundle exceeds 1 GB')
                        for info in z.infolist():
                            name=PurePosixPath(info.filename.replace('\\','/'))
                            if name.is_absolute() or '..' in name.parts: raise ValueError('Unsafe bundle path')
                            if info.is_dir(): continue
                            if name.suffix.lower() not in ('.artipreset','.artisong','.artistem','.wav','.png','.json'): continue
                            p=staging/str(name); p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(z.read(info))
                elif source.suffix in ('.artipreset','.artisong'):
                    ET.parse(source); shutil.copy2(source,staging/source.name)
                else: raise ValueError('Choose an Artiphon preset/song or a ZIP bundle')
                if not any(staging.rglob('*.artipreset')) and not any(staging.rglob('*.artisong')): raise ValueError('No presets or songs found')
                staging.rename(target); imported+=1
            except Exception:
                shutil.rmtree(staging); raise
        self.scan(); return imported
