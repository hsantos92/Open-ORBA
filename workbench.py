"""Library and audio tools for the Orba Studio desktop interface."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import subprocess, threading, queue, time, os
from storage import VOLUME, validate_volume, transfer_plan, copy_new, backup
from library import Library
from audio import AudioCapture

class Workbench:
    def __init__(self,app):
        self.app=app; self.audio=AudioCapture(); self.window=None; self.library=Library(); self.jobs=queue.Queue(); self.busy=False; self.pending_preset=None
        app.root.after(100,self.poll)
    def poll(self):
        try:
            while True:
                fn=self.jobs.get_nowait(); fn()
        except queue.Empty: pass
        if self.audio.process and self.audio.process.poll() is not None:
            self.stop_audio()
        self.app.root.after(100,self.poll)
    def task(self,fn,done):
        if self.busy: return
        self.busy=True
        def run():
            try:
                result=fn(); self.jobs.put(lambda: done(result))
            except Exception as error:
                message=str(error); self.jobs.put(lambda: self.report_error(message))
            finally: self.jobs.put(lambda: setattr(self,'busy',False))
        threading.Thread(target=run,daemon=True).start()
    def report_error(self,message):
        if not VOLUME.is_mount(): self.app.storage_hold=False
        self.app.message(message)
        messagebox.showerror('Orba Studio',message,parent=self.window if self.window and self.window.winfo_exists() else self.app.root)
    def toggle_audio(self):
        if self.audio.process: self.stop_audio(); return
        path=filedialog.asksaveasfilename(title='Record Orba audio to WAV',defaultextension='.wav',initialfile=time.strftime('Orba-%Y-%m-%d-%H%M%S.wav'),filetypes=[('WAV audio','*.wav')])
        if not path:return
        if Path(path).exists(): messagebox.showinfo('Choose a new filename','Choose a new filename so your existing recording is preserved.'); return
        try:
            self.audio.start(path); self.app.audio_button.configure(text='■ Stop & save WAV'); self.app.message('Recording the Orba USB audio input to '+path)
        except Exception as error: self.app.message(str(error))
    def stop_audio(self):
        if self.busy:return
        self.app.audio_button.configure(state='disabled',text='Saving WAV…')
        def done(path):
            self.app.message('Saved WAV: '+str(path))
        def stop():
            try:return self.audio.stop()
            finally:self.jobs.put(lambda:self.app.audio_button.configure(state='normal',text='● Record audio WAV'))
        self.task(stop,done)
    def open(self):
        if self.window and self.window.winfo_exists():self.window.lift();return
        w=self.window=tk.Toplevel(self.app.root); w.title('Orba Studio · Sound library'); w.geometry('1100x740'); w.configure(bg='#10141e')
        header=tk.Frame(w,bg='#10141e'); header.pack(fill='x',padx=20,pady=15)
        tk.Label(header,text='SOUND LIBRARY',font=('Sans',20,'bold'),fg='#edf4ff',bg='#10141e').pack(side='left')
        ttk.Button(header,text='Import…',command=self.import_files).pack(side='right')
        self.query=tk.StringVar(); self.filter=tk.StringVar(value='All')
        ttk.Entry(header,textvariable=self.query,width=25).pack(side='right',padx=12)
        ttk.Combobox(header,textvariable=self.filter,values=['All','Drum','Bass','Chord','Lead','Song'],state='readonly',width=10).pack(side='right')
        self.query.trace_add('write',lambda *_:self.populate()); self.filter.trace_add('write',lambda *_:self.populate())
        listframe=tk.Frame(w,bg='#10141e');listframe.pack(fill='both',expand=True,padx=20)
        self.tree=ttk.Treeview(listframe,columns=('part','status'),show='tree headings',selectmode='browse')
        self.tree.heading('#0',text='Sound / song'); self.tree.heading('part',text='Part'); self.tree.heading('status',text='Local files')
        self.tree.column('#0',width=400); self.tree.column('part',width=90); self.tree.column('status',width=240)
        scroll=ttk.Scrollbar(listframe,orient='vertical',command=self.tree.yview);scroll.pack(side='right',fill='y')
        self.tree.configure(yscrollcommand=scroll.set);self.tree.pack(side='left',fill='both',expand=True); self.tree.bind('<<TreeviewSelect>>',self.details)
        self.detail=tk.StringVar(value='Select a sound to inspect its files.')
        tk.Label(w,textvariable=self.detail,wraplength=1030,justify='left',fg='#98a9c2',bg='#10141e').pack(fill='x',padx=20,pady=12)
        storagebar=tk.Frame(w,bg='#10141e');storagebar.pack(fill='x',padx=20,pady=(0,10))
        ttk.Button(storagebar,text='Connect storage',command=self.connect_storage).pack(side='left')
        ttk.Button(storagebar,text='Back up Orba…',command=self.backup_orba).pack(side='left',padx=8)
        ttk.Button(storagebar,text='Eject storage',command=self.eject).pack(side='left')
        ttk.Label(storagebar,text='Sound activation: awaiting device verification').pack(side='right')
        bar=tk.Frame(w,bg='#10141e');bar.pack(fill='x',padx=20,pady=(0,15))
        ttk.Button(bar,text='Export sound bundle…',command=self.export).pack(side='left')
        ttk.Button(bar,text='Preview sample',command=self.preview).pack(side='left',padx=8)
        self.transfer_button=ttk.Button(bar,text='Copy to Orba storage',command=self.transfer);self.transfer_button.pack(side='left')
        ttk.Button(bar,text='Open library folder',command=lambda:subprocess.Popen(['xdg-open',str(self.library.root)])).pack(side='right')
        self.populate()
        self.detail.set(f'{len(self.library.entries)} sounds and songs · {len(self.library.errors)} invalid files skipped. Select a sound to inspect its files.')
    def populate(self):
        if not self.window or not self.window.winfo_exists():return
        self.tree.delete(*self.tree.get_children()); self.rows={}
        for i,e in enumerate(self.library.entries):
            if self.filter.get() not in ('All',e['part']):continue
            if self.query.get().lower() not in (e['name']+' '+e['description']).lower():continue
            files,missing=self.library.dependencies(e); iid=str(i);self.rows[iid]=e
            self.tree.insert('','end',iid=iid,text=e['name'],values=(e['part'],f'Missing {len(missing)} file(s)' if missing else 'Ready'))
    def selected(self):
        selected=self.tree.selection();return self.rows.get(selected[0]) if selected else None
    def details(self,*_):
        e=self.selected()
        if not e:return
        files,missing=self.library.dependencies(e)
        self.detail.set(e['description']+'\n'+str(len(files))+' local files'+(' · Missing: '+', '.join(missing[:3]) if missing else ' · All referenced sound files available'))
    def import_files(self):
        paths=filedialog.askopenfilenames(filetypes=[('Artiphon sounds and bundles','*.artipreset *.artisong *.artibundle *.zip')])
        if not paths:return
        try:self.library.import_paths(paths);self.populate();self.app.message('Imported sound library files.')
        except Exception as error:messagebox.showerror('Import failed',str(error))
    def export(self):
        e=self.selected()
        if not e:return
        destination=filedialog.asksaveasfilename(defaultextension='.zip',initialfile=e['name']+'-Orba-Studio.zip')
        if destination:
            try:self.library.export(e,destination);self.app.message('Exported bundle: '+destination)
            except Exception as error:messagebox.showerror('Export failed',str(error))
    def preview(self):
        e=self.selected()
        if not e:return
        files,_=self.library.dependencies(e);sample=next((p for p in files if p.suffix=='.wav'),None)
        if sample:subprocess.Popen(['ffplay','-nodisp','-autoexit','-loglevel','error',str(sample)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        else:messagebox.showinfo('Synth preset','This preset has no local audio sample to preview. Its sound is generated by the Orba.')
    def transfer(self):
        e=self.selected()
        if e:self.app.transfer_preset(e,self.library)

    def helper(self,script,*args):
        result=subprocess.run(['pkexec','/usr/bin/python',str(Path(__file__).parent/script),*args],capture_output=True,text=True,timeout=120)
        if result.returncode:raise RuntimeError(result.stderr.strip() or 'Desktop authentication was cancelled')
    def connect_storage(self):
        if self.busy:return
        if self.app.recording or self.audio.process:
            messagebox.showinfo('Stop recording','Stop and save your recording before switching to storage mode.');return
        self.app.storage_hold=True;self.app.disconnect()
        self.app.status.set('Opening Orba storage · desktop authentication may be required')
        def connect():
            if not VOLUME.is_mount():
                from storage_mount import device
                try:device()
                except RuntimeError:
                    self.helper('storage_mode.py')
                    for _ in range(40):
                        time.sleep(.25)
                        try:device();break
                        except RuntimeError:pass
                    else:raise RuntimeError('Orba storage did not appear. Reconnect USB and try again.')
            self.helper('storage_mount.py','write');validate_volume()
            return 'Storage connected. Choose a sound and Copy to Orba storage. Eject when finished.'
        def done(result):self.app.status.set('Orba storage connected · performance controls paused');self.app.message(result)
        self.task(connect,done)
    def send_preset(self,entry):
        if self.busy:return
        try:validate_volume(); plan=transfer_plan(entry,self.library)
        except Exception as error:messagebox.showinfo('Storage connection',str(error));return
        if not os.access(VOLUME,os.W_OK):
            messagebox.showinfo('Read-only storage','Use Connect storage to enable file copying.');return
        self.pending_preset=entry
        self.task(lambda:copy_new(plan,progress=lambda s:self.jobs.put(lambda text=s:self.app.message(text))),lambda result:self.app.message(f'Copied {len(result["copied"])} files; verified {result["already_present"]} existing files. Eject storage and restart Orba. Sound activation remains unverified.'))
    def backup_orba(self):
        if self.busy:return
        try:validate_volume()
        except Exception as error:messagebox.showinfo('Connect storage',str(error));return
        parent=filedialog.askdirectory(title='Choose a folder for the Orba backup')
        if not parent:return
        destination=Path(parent)/time.strftime('Orba3-backup-%Y%m%d-%H%M%S')
        self.task(lambda:backup(destination,progress=lambda s:self.jobs.put(lambda text=s:self.app.message(text))),lambda path:self.app.message('Verified complete backup: '+str(path)))
    def eject(self):
        if self.busy:return
        def work():self.helper('storage_mount.py','unmount')
        def done(_):
            self.app.storage_hold=False
            self.app.status.set('Storage ejected · unplug USB, restart Orba, and reconnect')
            self.app.message('Safe to unplug USB. Hold Volume Down (−) and Power together for 15 seconds, release, then power on and reconnect USB.')
        self.task(work,done)
    def load_selected(self):
        entry=self.selected()
        if not entry:return
        if self.app.fd is None:messagebox.showinfo('Reconnect Orba','Eject storage, restart your Orba and reconnect USB first.');return
        if entry['part']=='Song':
            messagebox.showinfo('Song preserved','Song files can be copied and backed up. Song loading is not enabled because it replaces the current device session.');return
        name=entry['path'].name.encode('utf-8')
        if len(name)>128:messagebox.showerror('Filename too long','The Orba accepts filenames up to 128 bytes.');return
        address={'Drum':0x26,'Bass':0x27,'Chord':0x28,'Lead':0x29}[entry['part']]
        self.app.send(bytes([3,3,0,address])+name.ljust(129,b'\0'),'select preset')
        self.app.root.after(150,lambda:self.app.send([3,3,0,0x22,0],'commit preset'))
        self.app.root.after(700,lambda:self.app.send([2,3,0,address],'selected_'+entry['part']))
        self.app.message('Requested sound: '+entry['name']+'; waiting for device filename readback.')
