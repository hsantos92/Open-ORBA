#!/usr/bin/env python3
"""Restricted mount helper for the Orba 3 storage interface only."""
import os,sys,subprocess
from pathlib import Path
MOUNT=Path('/run/orba-studio')
def device():
    found=[]
    for d in Path('/sys/class/block').glob('sd*'):
        if not (d/'partition').exists():continue
        for p in d.resolve().parents:
            try:valid=(p/'idVendor').read_text().strip()=='34b0' and (p/'idProduct').read_text().strip()=='0804'
            except OSError:continue
            if valid:found.append('/dev/'+d.name);break
    if len(found)!=1:raise RuntimeError('No unique Orba 3 storage partition found')
    return found[0]
if __name__=='__main__':
    action=sys.argv[1] if len(sys.argv)==2 else ''
    if action not in ('read','write','unmount'):raise RuntimeError('Invalid action')
    dev=device();MOUNT.mkdir(mode=0o755,exist_ok=True)
    if MOUNT.is_symlink():raise RuntimeError('Unsafe mount directory')
    if MOUNT.is_mount():
        actual=subprocess.check_output(['findmnt','-n','-o','SOURCE','--target',str(MOUNT)],text=True).strip()
        if actual!=dev:raise RuntimeError('Mount belongs to another device')
        subprocess.run(['umount',str(MOUNT)],check=True)
    if action!='unmount':
        uid=int(os.environ.get('PKEXEC_UID',os.getuid()))
        options=f'{"ro" if action=="read" else "rw"},nosuid,nodev,noexec,uid={uid},umask=077'
        subprocess.run(['mount','-t','vfat','-o',options,dev,str(MOUNT)],check=True)
    print('Orba storage:',action,flush=True)
