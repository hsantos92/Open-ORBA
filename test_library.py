import tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from library import Library
from storage import safe_relative,transfer_plan,copy_new
class LibraryTests(unittest.TestCase):
 def test_traversal_rejected(self):
  for path in ['../bad','/bad','a/../../bad','a\\..\\..\\bad']:
   with self.assertRaises(ValueError):safe_relative(path)
 def test_bundle_and_dependencies(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'library';root.mkdir()
   (root/'bass.artipreset').write_text('<PresetEntry name="Bass" mode="Bass"><SampledSound fileName="tone.wav" pool="User" subdirectory="Test"/></PresetEntry>')
   (root/'tone.wav').write_bytes(b'test-audio')
   library=Library(root);entry=library.entries[0]
   self.assertEqual(library.dependencies(entry)[1],[])
   plan=transfer_plan(entry,library)
   self.assertIn(Path('SamplePools/User/Test/tone.wav'),plan)
   exported=Path(temp)/'sound.zip';library.export(entry,exported)
   other=Library(Path(temp)/'other');other.import_paths([exported])
   self.assertEqual(len(other.entries),1);self.assertEqual(other.dependencies(other.entries[0])[1],[])
 def test_missing_dependency(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'p.artipreset').write_text('<PresetEntry mode="Lead"><SampledSound fileName="missing.wav" pool="User"/></PresetEntry>')
   lib=Library(root)
   with self.assertRaises(ValueError):transfer_plan(lib.entries[0],lib)
 def test_no_overwrite(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);src=root/'source';src.write_bytes(b'new');device=root/'device';device.mkdir();(device/'target').write_bytes(b'old')
   with patch('storage.validate_volume',return_value=device):
    with self.assertRaises(ValueError):copy_new({Path('target'):src},device)
   self.assertEqual((device/'target').read_bytes(),b'old')
 def test_copy_readback(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);src=root/'source';src.write_bytes(b'new');device=root/'device';device.mkdir()
   with patch('storage.validate_volume',return_value=device):
    result=copy_new({Path('Presets/Bass/test.artipreset'):src},device)
   self.assertEqual(len(result['copied']),1);self.assertEqual((device/'Presets/Bass/test.artipreset').read_bytes(),b'new')
if __name__=='__main__':unittest.main()
