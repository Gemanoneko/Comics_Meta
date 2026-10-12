"""No challenge URL (or the comic that hit it) enters the local HTTP API."""
import json
import os
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import app
import browser_search
import lens_verification
import progress_snapshot
from test_worker import scratch_directory

SECRET='https://www.google.com/sorry/index?continue=private-token'


class ApiRedactionTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(app,'live_root',return_value=''))
        self.enterContext(patch.object(lens_verification,'_owner',None))
        lens_verification.initialize()
        (app.DATA/'browser-heartbeat').write_text(json.dumps({'pid':os.getpid(),'timestamp':time.time()}))
        browser_search.legacy_status(human_verification=True,verification_state='required',verification_url=SECRET,
                                     verification_task={'path':'Y:/Comix/private.cbz','size':1,'mtime':2},detail='Fixture detail')

    def get(self,path):
        handler=object.__new__(app.Handler)
        handler.headers={'Host':'127.0.0.1:8765'};handler.server=SimpleNamespace(server_port=8765);handler.path=path
        with patch.object(handler,'respond') as respond:handler.do_GET()
        return respond.call_args.args[0]

    def assert_private_absent(self,value):
        text=json.dumps(value)
        self.assertNotIn('private-token',text);self.assertNotIn('private.cbz',text)
        self.assertNotIn('verification_url',text);self.assertNotIn('verification_task',text)

    def test_browser_verification_endpoint_omits_challenge_url(self):
        result=self.get('/api/browser-verification')
        self.assertTrue(result['cover']['human_verification'])
        self.assertEqual(result['cover']['detail'],'Fixture detail')
        self.assert_private_absent(result)

    def test_progress_endpoint_omits_challenge_url(self):
        result=progress_snapshot.collect(progress_snapshot.Files())
        self.assertTrue(result['browser_search']['human_verification'])
        self.assert_private_absent(result)

    def test_worker_still_reads_the_url_internally(self):
        self.assertEqual(browser_search.legacy_status()['verification_url'],SECRET)


if __name__=='__main__':
    unittest.main()
