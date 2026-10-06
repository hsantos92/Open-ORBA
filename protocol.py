"""Artiphon framing, independently implemented from the community protocol spec.
Reference: https://github.com/holofermes/orba-protocol (MIT / CC BY 4.0).
"""
def crc(data):
    result = 0
    for byte in data:
        result ^= byte
        for _ in range(8):
            result = (result >> 1) ^ (0xA001 if result & 1 else 0)
    return result

def pack(data, width_in, width_out):
    result = []; accumulator = bits = 0
    for byte in data:
        accumulator |= byte << bits; bits += width_in
        while bits >= width_out:
            result.append(accumulator & ((1 << width_out) - 1))
            accumulator >>= width_out; bits -= width_out
    if bits and width_out == 7:
        result.append(accumulator)
    return bytes(result)

def command(payload, identifier):
    body = bytes([0x82, 1, identifier]) + len(payload).to_bytes(2, 'big') + bytes(payload)
    return b'\xf0\x00' + pack(body + crc(body).to_bytes(2, 'big'), 8, 7) + b'\xf7'

def decode(message):
    if not message.startswith(b'\xf0\x00') or not message.endswith(b'\xf7'):
        raise ValueError('Not an Artiphon message')
    body = pack(message[2:-1], 7, 8)
    if len(body) < 7 or body[:2] != b'\x82\x01' or len(body) != int.from_bytes(body[3:5], 'big') + 7:
        raise ValueError('Invalid packet length or header')
    if crc(body[:-2]) != int.from_bytes(body[-2:], 'big'):
        raise ValueError('Invalid checksum')
    return body[2], body[5:-2]

class MidiParser:
    def __init__(self):
        self.status = None; self.data = []; self.sysex = None
    def feed(self, chunk):
        messages = []
        for b in chunk:
            if b >= 0xf8:
                continue
            if b == 0xf0:
                self.sysex = bytearray([b]); self.status = None; self.data = []; continue
            if self.sysex is not None:
                if b == 0xf7:
                    self.sysex.append(b); messages.append(bytes(self.sysex)); self.sysex = None
                elif b & 0x80 or len(self.sysex) > 65536:
                    self.sysex = None
                else:
                    self.sysex.append(b)
                continue
            if b & 0x80:
                self.status = b if b < 0xf0 else None; self.data = []; continue
            if self.status is not None:
                self.data.append(b)
                count = 1 if self.status >> 4 in (0xc, 0xd) else 2
                if len(self.data) == count:
                    messages.append(bytes([self.status] + self.data)); self.data = []
        return messages
