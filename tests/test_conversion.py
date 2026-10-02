import subprocess
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import archive_conversion as conversion
from test_worker import scratch_directory


@unittest.skipUnless(conversion.SEVEN_ZIP.exists(),'7-Zip unavailable')
class ConversionTests(unittest.TestCase):
    def fixture(self,root):
        folder=Path(root)/'input';folder.mkdir()
        Image.new('RGB',(20,20),'red').save(folder/'001.png')
        (folder/'ComicInfo.xml').write_text('<ComicInfo><Title>Example</Title></ComicInfo>')
        original=Path(root)/'Example.cb7'
        subprocess.run([str(conversion.SEVEN_ZIP),'a','-t7z',str(original),'001.png','ComicInfo.xml'],cwd=folder,capture_output=True,check=True)
        return original

    def test_verified_conversion_removes_original_and_temporary_files(self):
        with scratch_directory() as root,patch.object(conversion.pause_control,'requested',return_value=False):
            original=self.fixture(root)
            result=conversion.convert(original)
            self.assertFalse(original.exists())
            self.assertTrue(result['original_removed'])
            with zipfile.ZipFile(original.with_suffix('.cbz')) as archive:
                self.assertEqual(archive.read('001.png'),(Path(root)/'input/001.png').read_bytes())
            self.assertFalse(list(Path(root).glob('.comic-metadata-convert-*')))

    def test_verification_failure_retains_original_and_cleans_staging(self):
        with scratch_directory() as root,patch.object(conversion.pause_control,'requested',return_value=False):
            original=self.fixture(root);before=original.read_bytes()
            with patch.object(conversion,'verify',side_effect=ValueError('verification failed')):
                with self.assertRaises(ValueError):conversion.convert(original)
            self.assertEqual(original.read_bytes(),before)
            self.assertFalse(original.with_suffix('.cbz').exists())
            self.assertFalse(list(Path(root).glob('.comic-metadata-convert-*')))

    def test_cbz_named_7zip_is_replaced_only_after_verification(self):
        with scratch_directory() as root,patch.object(conversion.pause_control,'requested',return_value=False):
            original=self.fixture(root);named=original.with_suffix('.cbz');original.rename(named)
            conversion.convert(named)
            self.assertTrue(zipfile.is_zipfile(named))
            self.assertFalse(list(Path(root).glob('*.conversion-original')))

    def test_existing_cbz_is_never_overwritten(self):
        with scratch_directory() as root,patch.object(conversion.pause_control,'requested',return_value=False):
            original=self.fixture(root);target=original.with_suffix('.cbz');target.write_bytes(b'keep this file')
            with self.assertRaises(ValueError):conversion.convert(original)
            self.assertTrue(original.exists());self.assertEqual(target.read_bytes(),b'keep this file')

    def test_final_readback_failure_restores_same_name_original(self):
        with scratch_directory() as root,patch.object(conversion.pause_control,'requested',return_value=False):
            original=self.fixture(root);named=original.with_suffix('.cbz');original.rename(named);before=named.read_bytes()
            with patch.object(conversion,'verify',side_effect=[None,ValueError('readback failed')]):
                with self.assertRaises(ValueError):conversion.convert(named)
            self.assertEqual(named.read_bytes(),before)
