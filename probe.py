import glob, os, select, time
from protocol import command, decode, MidiParser

def devices():
    result = []
    for path in glob.glob('/proc/asound/card*/midi*'):
        if 'Artiphon Orba 3' in open(path).read():
            card = path.split('/card')[1].split('/')[0]
            result.append('/dev/snd/midiC' + card + 'D' + path.rsplit('midi', 1)[1])
    return result

if __name__ == '__main__':
    for path in devices():
        print('Device:', path, flush=True)
        fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        parser = MidiParser()
        queries = [('active part', [2,1,0,3]), ('tempo', [2,7,0,7]), ('battery', [2,3,0,15]), ('key', [2,3,0,18]), ('scale', [2,3,0,19])]
        for i, (name, payload) in enumerate(queries, 32):
            os.write(fd, command(payload, i))
            until = time.monotonic() + 1
            while time.monotonic() < until:
                if select.select([fd], [], [], .1)[0]:
                    for message in parser.feed(os.read(fd, 4096)):
                        try: print(name, decode(message), flush=True)
                        except ValueError: print('MIDI:', message.hex(), flush=True)
        os.close(fd)
