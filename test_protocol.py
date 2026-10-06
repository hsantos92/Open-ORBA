import unittest
from protocol import command, decode, MidiParser
from app import midi_file
class Tests(unittest.TestCase):
    def test_captured_packet(self):
        sample = bytes.fromhex('f0 00 02 03 00 03 50 60 40 00 00 06 00 18 0c 1d f7')
        identifier,payload = decode(sample)
        self.assertEqual(command(payload,identifier),sample)
    def test_corruption(self):
        packet=bytearray(command([2,7,0,7],33)); packet[7]^=1
        with self.assertRaises(ValueError): decode(bytes(packet))
    def test_fragmented_running_status(self):
        p=MidiParser()
        self.assertEqual(p.feed(b'\x90\x3c'),[])
        self.assertEqual(p.feed(b'\xf8\x64\x3d\x00'),[b'\x90\x3c\x64',b'\x90\x3d\x00'])
        message=command([2,1,0,3,0],3)
        self.assertEqual(p.feed(message[:5]),[])
        self.assertEqual(p.feed(message[5:]),[message])
    def test_midi_export(self):
        result=midi_file([(0,b'\x90\x3c\x64'),(.5,b'\x80\x3c\x00')])
        self.assertEqual(int.from_bytes(result[18:22],'big'),len(result)-22)
        self.assertIn(b'\x83\x60\x80\x3c\x00',result)
        self.assertTrue(result.endswith(b'\x00\xff\x2f\x00'))
    def test_held_note_cleanup(self):
        self.assertIn(b'\x00\x89\x24\x00',midi_file([(0,b'\x99\x24\x7f')]))
if __name__=='__main__': unittest.main()
