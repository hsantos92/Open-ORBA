#!/usr/bin/env python3
"""Offline Linux companion for Artiphon Orba 3. Python standard library only."""
import json, os, time, tkinter as tk
from tkinter import ttk, filedialog
from protocol import MidiParser, command, decode
from probe import devices

BG, PANEL, TEXT, MUTED, ACCENT = '#10141e', '#1c2332', '#edf4ff', '#98a9c2', '#69dfba'
PARTS = ['Lead', 'Chord', 'Bass', 'Drum']
COLORS = ['#ee58cd', '#f6a04a', '#4169e1', '#38d5df']
DISPLAY_ORDER = [3, 2, 1, 0]

def vlq(value):
    out = [value & 127]
    while value >> 7:
        value >>= 7; out.insert(0, (value & 127) | 128)
    return bytes(out)

def midi_file(events):
    # Fixed 120 BPM / 480 PPQN makes timestamps independent of device tempo.
    track = bytearray(b'\x00\xff\x51\x03\x07\xa1\x20'); previous = 0
    active = set()
    for seconds, message in events:
        if not message or not 0x80 <= message[0] < 0xf0: continue
        tick = max(previous, round(seconds * 960))
        track += vlq(tick - previous) + message; previous = tick
        if message[0] >> 4 == 9 and message[2]: active.add((message[0] & 15, message[1]))
        elif message[0] >> 4 in (8, 9): active.discard((message[0] & 15, message[1]))
    for channel, note in sorted(active): track += b'\x00' + bytes([0x80 | channel, note, 0])
    track += b'\x00\xff\x2f\x00'
    return b'MThd\x00\x00\x00\x06\x00\x00\x00\x01\x01\xe0MTrk' + len(track).to_bytes(4, 'big') + track

class App:
    def __init__(self, root):
        self.root = root; self.fd = None; self.parser = MidiParser(); self.identifier = 0
        self.pending = {}; self.state = {}; self.events = []; self.recording = False
        self.storage_hold = False
        self.count = 0; self.active = set(); self.last_scan = 0; self.last_refresh = 0
        root.title('Orba Studio · Linux'); root.geometry('1080x860'); root.minsize(1000, 820); root.configure(bg=BG)
        style = ttk.Style(); style.theme_use('clam')
        style.configure('TButton', font=('Sans', 11), padding=9, background=PANEL, foreground=TEXT)
        style.configure('Treeview', background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=28, font=('Sans',11))
        style.configure('Treeview.Heading', background='#28344a', foreground=TEXT, font=('Sans',11,'bold'))
        style.map('Treeview', background=[('selected','#365777')])
        style.map('TButton', background=[('active', '#344359')], foreground=[('disabled', '#637085')])
        top = tk.Frame(root, bg=BG); top.pack(fill='x', padx=32, pady=(25, 12))
        tk.Label(top, text='ORBA STUDIO', bg=BG, fg=TEXT, font=('Sans', 25, 'bold')).pack(anchor='w')
        tk.Label(top, text='A local home for your Orba 3', bg=BG, fg=MUTED, font=('Sans', 12)).pack(anchor='w')
        self.status = tk.StringVar(value='Looking for Orba 3…')
        tk.Label(root, textvariable=self.status, bg=BG, fg=ACCENT, font=('Sans', 11)).pack(anchor='w', padx=32)
        self.metrics = tk.StringVar(value='Waiting for device settings')
        tk.Label(root, textvariable=self.metrics, bg=BG, fg=TEXT, font=('Sans', 13)).pack(anchor='w', padx=32, pady=12)
        self.canvas = tk.Canvas(root, height=235, bg=PANEL, highlightthickness=0); self.canvas.pack(fill='x', padx=32)
        self.circles = {}; self.pad_labels = {}
        for position, i in enumerate(DISPLAY_ORDER):
            x = 120 + position * 230
            self.circles[i] = self.canvas.create_oval(x-68, 25, x+68, 161, fill=BG, outline=COLORS[i], width=2)
            self.pad_labels[i] = self.canvas.create_text(x, 92, text=f'{position+1}  {PARTS[i]}', fill=COLORS[i], font=('Sans', 15, 'bold'))
            self.canvas.tag_bind(self.circles[i], '<Button-1>', lambda event, n=i: self.set_part(n))
            self.canvas.tag_bind(self.pad_labels[i], '<Button-1>', lambda event, n=i: self.set_part(n))
        self.live = self.canvas.create_text(465, 205, text='Play your Orba to see notes and gestures', fill=MUTED, font=('Sans', 12))
        def resize(event):
            for pos, i in enumerate(DISPLAY_ORDER):
                x = (pos+.5)*event.width/4
                self.canvas.coords(self.circles[i],x-68,25,x+68,161); self.canvas.coords(self.pad_labels[i],x,92)
            self.canvas.coords(self.live,event.width/2,205)
        self.canvas.bind('<Configure>',resize)
        controls = tk.Frame(root, bg=BG); controls.pack(fill='x', padx=32, pady=15)
        tk.Label(controls, text='Tempo', bg=BG, fg=TEXT).pack(side='left')
        self.tempo = tk.StringVar(value='112')
        tk.Spinbox(controls, from_=40, to=240, textvariable=self.tempo, width=5, font=('Sans', 13)).pack(side='left', padx=8)
        self.apply = ttk.Button(controls, text='Apply BPM', command=self.set_tempo); self.apply.pack(side='left')
        self.part_buttons = {}
        for pos, i in enumerate(DISPLAY_ORDER):
            style.configure(f'Part{i}.TButton', foreground=COLORS[i])
            b = ttk.Button(controls, text=f'{pos+1} {PARTS[i]}', style=f'Part{i}.TButton', command=lambda n=i: self.set_part(n)); b.pack(side='left', padx=(8,0)); self.part_buttons[i]=b
        bar = tk.Frame(root, bg=BG); bar.pack(fill='x', padx=32)
        self.record_button = ttk.Button(bar, text='● Record MIDI', command=self.record); self.record_button.pack(side='left')
        ttk.Button(bar, text='Save MIDI…', command=self.save_midi).pack(side='left', padx=8)
        ttk.Button(bar, text='Save device report…', command=self.save_report).pack(side='left')
        from workbench import Workbench
        self.workbench = Workbench(self)
        toolsbar = tk.Frame(root, bg=BG); toolsbar.pack(fill='x', padx=32, pady=(10,0))
        ttk.Button(toolsbar, text='Sound library', command=self.workbench.open).pack(side='left')
        self.audio_button = ttk.Button(toolsbar, text='● Record audio WAV', command=self.workbench.toggle_audio); self.audio_button.pack(side='left', padx=8)
        self.record_status = tk.StringVar(value='Record your live performance as MIDI')
        tk.Label(root, textvariable=self.record_status, bg=BG, fg=MUTED).pack(anchor='w', padx=32, pady=10)
        self.log = tk.Text(root, height=6, bg=PANEL, fg=MUTED, relief='flat', font=('Monospace', 10), state='disabled')
        tk.Label(root, text='USB MIDI + stereo audio • Offline sound library • Preview 0.2', bg=BG, fg=MUTED).pack(side='bottom', pady=12)
        self.log.pack(fill='both', expand=True, padx=32)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.tick()
    def message(self, text):
        self.log.configure(state='normal'); self.log.insert('end', time.strftime('%H:%M:%S ') + text + '\n')
        if int(self.log.index('end-1c').split('.')[0]) > 150: self.log.delete('1.0', '30.0')
        self.log.see('end'); self.log.configure(state='disabled')
    def send(self, payload, label):
        if self.fd is None: return
        self.identifier = (self.identifier + 1) % 256
        packet = command(payload, self.identifier)
        try:
            if os.write(self.fd, packet) != len(packet): raise OSError('Incomplete MIDI write')
            if payload[0] == 2:
                self.pending[self.identifier] = (time.monotonic(), label, bytes(payload[:4]))
        except OSError as error: self.message(str(error)); self.disconnect()
    def refresh(self):
        for label, payload in [('part',[2,1,0,3]), ('tempo',[2,7,0,7]), ('battery',[2,3,0,15]), ('key_raw',[2,3,0,18]), ('scale_raw',[2,3,0,19])]: self.send(payload, label)
        self.last_refresh = time.monotonic()
    def set_tempo(self):
        try:
            bpm = float(self.tempo.get())
            if not 40 <= bpm <= 240: raise ValueError()
        except ValueError: self.message('Enter a tempo between 40 and 240 BPM.'); return
        if 'tempo' not in self.state: return
        value = round(bpm*100)
        self.send([3,7,0,7,value>>8,value&255], 'set tempo'); self.root.after(250, self.refresh)
    def set_part(self, part):
        if 'part' in self.state:
            self.send([3,1,0,3,part], 'set part'); self.root.after(250, self.refresh)
    def handle(self, message):
        self.count += 1
        if message[0] == 0xf0:
            try: identifier, payload = decode(message)
            except ValueError as error: self.message(str(error)); return
            pending = self.pending.get(identifier)
            if pending is None or payload[:4] != pending[2]: return
            self.pending.pop(identifier)
            label = pending[1]; value = payload[4:]
            if not value: return
            if label.startswith('selected_'):
                self.state[label]=value.split(b'\0')[0].decode('utf-8',errors='replace')
                self.message('Device preset: '+self.state[label]); return
            if label == 'tempo' and len(value) == 2:
                self.state[label] = int.from_bytes(value,'big') / 100
                if self.root.focus_get() is None or self.root.focus_get().winfo_class() != 'Spinbox': self.tempo.set(str(self.state[label]))
            elif label in ('part','battery','key_raw','scale_raw') and len(value) == 1: self.state[label] = value[0]
            return
        if self.recording: self.events.append((time.monotonic()-self.started, message))
        channel = message[0] & 15; kind = message[0] >> 4
        if kind == 0xc and time.monotonic()-self.last_refresh > .3: self.refresh()
        part = {0:0,15:1,8:2,9:3}.get(channel)
        if kind in (8,9):
            key = (channel,message[1]); on = kind == 9 and message[2] > 0
            if on: self.active.add(key)
            else: self.active.discard(key)
            if on:
                note = ['C','C♯','D','D♯','E','F','F♯','G','G♯','A','A♯','B'][message[1]%12] + str(message[1]//12-1)
                self.canvas.itemconfigure(self.live, text=f'{PARTS[part] if part is not None else "MIDI"} · {note} · velocity {message[2]}')
        elif kind == 0xb:
            self.canvas.itemconfigure(self.live, text=f'Gesture · channel {channel+1} · CC {message[1]} · {message[2]}')
    def disconnect(self):
        if self.fd is not None: os.close(self.fd)
        self.fd = None; self.pending.clear(); self.state.clear(); self.active.clear(); self.parser = MidiParser()
        if self.recording: self.record()
    def tick(self):
        now = time.monotonic()
        if self.fd is None and not self.storage_hold and now-self.last_scan > 2:
            self.last_scan = now
            try:
                found = devices()
                if found:
                    self.fd = os.open(found[0], os.O_RDWR|os.O_NONBLOCK)
                    self.status.set('Connected · Artiphon Orba 3 · ' + found[0]); self.message('USB MIDI connected. Reading settings.'); self.refresh()
                else: self.status.set('Connect your Orba 3 by USB to begin')
            except OSError as error: self.status.set('Connection unavailable: '+str(error))
        if self.fd is not None:
            try:
                for _ in range(16):
                    try: chunk = os.read(self.fd,4096)
                    except BlockingIOError: break
                    if not chunk: raise OSError('Device disconnected')
                    for message in self.parser.feed(chunk): self.handle(message)
                if now-self.last_refresh > 10: self.refresh()
            except OSError as error: self.message(str(error)); self.disconnect(); self.status.set('Disconnected · reconnecting automatically')
        for identifier, (sent,label,_) in list(self.pending.items()):
            if now-sent > 2:
                self.pending.pop(identifier); self.message(label + ': no reply received')
        part = self.state.get('part'); name = PARTS[part] if part in range(4) else '—'
        self.metrics.set(f'PART  {name}     TEMPO  {self.state.get("tempo", "—")} BPM     BATTERY  {self.state.get("battery", "—")}%')
        self.apply.configure(state='normal' if 'tempo' in self.state else 'disabled')
        for i, button in self.part_buttons.items():
            button.configure(state='normal' if 'part' in self.state else 'disabled')
            lit = any({0:0,15:1,8:2,9:3}.get(ch) == i for ch,note in self.active)
            self.canvas.itemconfigure(self.circles[i], fill=COLORS[i] if lit else BG, outline=COLORS[i], width=5 if part == i else 2)
            self.canvas.itemconfigure(self.pad_labels[i], fill=BG if lit else COLORS[i])
        self.record_button.configure(state='normal' if self.fd is not None or self.recording else 'disabled')
        if self.recording: self.record_status.set(f'Recording · {now-self.started:.1f}s · {len(self.events)} MIDI events')
        self.root.after(20,self.tick)
    def record(self):
        if not self.recording:
            if self.events:
                from tkinter import messagebox
                if not messagebox.askyesno('New recording', 'Replace the current in-memory recording? Save MIDI first if you want to keep it.'): return
            self.events=[]; self.started=time.monotonic(); self.recording=True; self.record_button.configure(text='■ Stop recording')
        else:
            self.recording=False; self.record_button.configure(text='● Record MIDI'); self.record_status.set(f'Recording stopped · {len(self.events)} events · ready to save')
    def save_midi(self):
        if self.recording: self.record()
        if not self.events: self.message('Record a performance before saving MIDI.'); return
        path = filedialog.asksaveasfilename(defaultextension='.mid', initialfile='Orba-performance.mid', filetypes=[('MIDI file','*.mid')])
        if path:
            try:
                with open(path,'wb') as f: f.write(midi_file(self.events))
                self.message('Saved MIDI: '+path)
            except OSError as error: self.message(str(error))
    def save_report(self):
        path = filedialog.asksaveasfilename(defaultextension='.json', initialfile='Orba-device-report.json')
        if path:
            try:
                with open(path,'w') as f: json.dump({'device':'Artiphon Orba 3','usb_id':'34b0:0806','connected':self.fd is not None,'settings':self.state,'midi_messages_received':self.count,'note':'key_raw and scale_raw are unverified numeric values'},f,indent=2)
                self.message('Saved report: '+path)
            except OSError as error: self.message(str(error))
    def transfer_preset(self, entry, library):
        self.workbench.send_preset(entry)
    def close(self):
        if self.workbench.busy:
            self.message('Please wait for the current operation to finish.'); return
        if self.workbench.audio.process:
            self.workbench.stop_audio(); self.message('Saving audio; close again when it finishes.'); return
        if self.events:
            from tkinter import messagebox
            if not messagebox.askyesno('Close Orba Studio', 'Close the app? Any recording not saved as MIDI will be lost.'): return
        self.disconnect(); self.root.destroy()

if __name__ == '__main__':
    root=tk.Tk(); App(root); root.mainloop()
