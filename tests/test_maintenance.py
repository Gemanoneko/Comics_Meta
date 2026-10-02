import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import maintenance
from test_worker import scratch_directory

class MaintenanceTests(unittest.TestCase):
    def test_expired_caches_removed_but_evidence_and_fresh_temps_retained(self):
        with scratch_directory() as root,patch.object(app,'DATA',Path(root)/'data'),patch.object(app,'BASE',Path(root)):
            with app.db() as con:
                con.execute('INSERT INTO cache VALUES(?,?,?)',('old','{}',0))
                con.execute('INSERT INTO cache VALUES(?,?,?)',('recent','{}',time.time()))
            research=app.DATA/'research';research.mkdir()
            cached=research/('a'*64+'.json');cached.write_text('{}');os.utime(cached,(0,0))
            evidence=research/'evidence-important.json';evidence.write_text('{}');os.utime(evidence,(0,0))
            fresh=app.DATA/'active.tmp';fresh.write_text('keep')
            old=app.DATA/'old.tmp';old.write_text('discard');os.utime(old,(0,0))
            result=maintenance.run(True)
            self.assertFalse(cached.exists());self.assertFalse(old.exists())
            self.assertTrue(evidence.exists());self.assertTrue(fresh.exists())
            self.assertEqual(result['expired_cache_entries'],1)
            with app.db() as con:self.assertEqual(con.execute('SELECT key FROM cache').fetchone()[0],'recent')

    def test_browser_cache_cleanup_preserves_cookies_and_profile_state(self):
        with scratch_directory() as root:
            profile=Path(root)/'profile';cache=profile/'Default/Cache';cache.mkdir(parents=True)
            (cache/'cached').write_bytes(b'garbage')
            cookies=profile/'Default/Cookies';cookies.write_text('keep session')
            self.assertEqual(maintenance.browser_cache(profile),7)
            self.assertFalse(cache.exists());self.assertTrue(cookies.exists())

    def test_cleanup_cannot_escape_owned_directory(self):
        with scratch_directory() as root:
            owned=Path(root)/'owned';owned.mkdir()
            sibling=Path(root)/'keep';sibling.mkdir()
            with self.assertRaises(ValueError):maintenance.remove_tree(sibling,owned)
            self.assertTrue(sibling.exists())
