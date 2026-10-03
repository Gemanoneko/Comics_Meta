import unittest
import zipfile
from pathlib import Path
import reverse_image
from test_worker import scratch_directory

class CoverTests(unittest.TestCase):
    def test_cover_preview_selects_only_requested_image(self):
        with scratch_directory() as root:
            comic=Path(root)/'Comic.cbz'
            with zipfile.ZipFile(comic,'w') as archive:
                archive.writestr('01.jpg',b'cover');archive.writestr('02.png',b'second image')
            self.assertEqual(reverse_image.cover(comic),(b'cover','image/jpeg','.jpg'))
            self.assertEqual(reverse_image.cover(comic,1),(b'second image','image/png','.png'))
            with self.assertRaises(ValueError):reverse_image.cover(comic,2)
