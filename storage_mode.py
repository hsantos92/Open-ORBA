#!/usr/bin/env python3
"""One-purpose helper: switch the attached Orba 3 to USB storage mode.
May run through polkit because Linux restricts the CDC serial interface.
Never accepts paths or arbitrary serial commands.
"""
from pathlib import Path
import os, termios, time

def serial_port():
    for candidate in Path('/sys/class/tty').glob('ttyACM*'):
        for parent in (candidate/'device').resolve().parents:
            try:
                if (parent/'idVendor').read_text().strip()=='34b0' and (parent/'idProduct').read_text().strip()=='0806':
                    return '/dev/'+candidate.name
            except OSError: pass
    raise RuntimeError('No Orba 3 USB serial interface found')

def enter():
    path=serial_port();fd=os.open(path,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
    try:
        attrs=termios.tcgetattr(fd); attrs[0]=0;attrs[1]=0;attrs[2]=termios.CS8|termios.CREAD|termios.CLOCAL;attrs[3]=0
        attrs[4]=termios.B115200;attrs[5]=termios.B115200;attrs[6][termios.VMIN]=0;attrs[6][termios.VTIME]=5
        termios.tcsetattr(fd,termios.TCSANOW,attrs)
        os.write(fd,b'M');termios.tcdrain(fd)
    finally:os.close(fd)
    print('Storage mode requested for Orba 3',flush=True)
if __name__=='__main__':enter()
