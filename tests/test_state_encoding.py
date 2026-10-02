import unittest
from unittest.mock import patch
from pathlib import Path
import automatic,storage
from test_worker import scratch_directory

class StateEncodingTests(unittest.TestCase):
    def test_unicode_paths_survive_repeated_saves_on_non_utf8_windows(self):
        with scratch_directory() as d:
            target=Path(d)/'automatic.json'
            key='Y:\\Comix\\Blacklands 0Ѕ — café.cbz'
            original=Path.read_text
            def windows_read(path,encoding=None,**kwargs):return original(path,encoding=encoding or 'cp1251',**kwargs)
            with patch.object(automatic,'STATE',target),patch.object(Path,'read_text',autospec=True,side_effect=windows_read):
                storage.save(target,{'checked':{key:{'signature':[1,2]}}})
                initial=target.stat().st_size
                for _ in range(30):
                    state=automatic.load_state()
                    self.assertEqual(list(state['checked']),[key])
                    storage.save(target,state)
                self.assertEqual(target.stat().st_size,initial)
