"""Capture only the Orba's own USB input via the desktop audio server."""
import json, subprocess, time
from pathlib import Path

def orba_source():
    sources=json.loads(subprocess.check_output(['pactl','-f','json','list','sources'],text=True,timeout=5))
    candidates=[s for s in sources if s['name'].startswith('alsa_input.') and 'Artiphon_Orba_3' in s['name']]
    if len(candidates)!=1: raise RuntimeError('Connect the Orba USB audio input; no unique Orba input was found.')
    return candidates[0]['name']

class AudioCapture:
    def __init__(self): self.process=None; self.path=None; self.log=None
    def start(self,path):
        if self.process: raise RuntimeError('A recording is already active')
        source=orba_source(); self.path=Path(path)
        # Reserve the destination exclusively, even if it was chosen moments ago.
        with self.path.open('xb'): pass
        self.log=self.path.with_suffix(self.path.suffix+'.log').open('w+')
        try:
            self.process=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','pulse','-i',source,'-ar','48000','-ac','2','-c:a','pcm_s24le',str(self.path)],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=self.log)
            self.started=time.monotonic()
        except Exception:
            self.log.close(); self.path.unlink(missing_ok=True); raise
    def stop(self):
        if not self.process: return
        process=self.process
        try:
            if process.poll() is None:
                process.communicate(b'q\n',timeout=8)
        except subprocess.TimeoutExpired:
            process.terminate(); process.wait(timeout=3)
        finally:
            self.process=None; self.log.flush(); self.log.seek(0); error=self.log.read(); self.log.close()
        if process.returncode!=0: raise RuntimeError(error[-1500:] or 'Audio recording failed')
        self.path.with_suffix(self.path.suffix+'.log').unlink(missing_ok=True)
        if self.path.stat().st_size<=100: raise RuntimeError('No audio was captured')
        return self.path
