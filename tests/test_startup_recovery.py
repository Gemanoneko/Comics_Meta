import json
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

import app
import browser_search
import progress_snapshot
from test_worker import scratch_directory


class StartupRecoveryTests(unittest.TestCase):
    def test_corrupt_status_is_read_only_and_shell_status_survives(self):
        with scratch_directory() as folder, patch.object(app, 'DATA', Path(folder)), patch.dict('os.environ', {'COMICS_META_SHELL_TOKEN':'fixture-token'}), patch('setup_state.status', return_value={'configured':False}):
            data=Path(folder); browser=data/'browser-search.json'; heartbeat=data/'browser-heartbeat'
            heartbeat.write_text(json.dumps({'timestamp':time.time()}))
            server=app.LocalServer(('127.0.0.1',0),app.Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
            url='http://127.0.0.1:%d/api/shell/status'%server.server_port
            def status():
                request=urllib.request.Request(url,headers={'X-ComicsMeta-Shell':'fixture-token'})
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=3) as response:return json.load(response)
            self.assertTrue(status()['owned'])
            original=b'\0'*1644;browser.write_bytes(original)
            for _ in range(8):self.assertTrue(status()['owned'])
            self.assertEqual(browser.read_bytes(),original)
            self.assertTrue(browser_search.legacy_status()['status_unavailable'])
            with self.assertRaises(ValueError):browser_search.legacy_status(state='waiting')
            self.assertEqual(browser.read_bytes(),original)
            browser.write_text('{}');self.assertTrue(status()['owned'])
            self.assertNotIn('status_unavailable',browser_search.legacy_status())

    def test_progress_and_folder_corruption_is_reported_without_writes(self):
        with scratch_directory() as folder, patch.object(app,'DATA',Path(folder)):
            root=Path(folder);bad={'progress.json':b'\0'*30283,'folders.json':b'\0'*1659323,'browser-search.json':b'\0'*1644}
            for name,data in bad.items():(root/name).write_bytes(data)
            files=progress_snapshot.Files()
            try:result=progress_snapshot.collect(files)
            finally:files.close()
            self.assertTrue(result['progress_unavailable']);self.assertTrue(result['folders_unavailable'])
            self.assertTrue(result['browser_search']['status_unavailable'])
            for name,data in bad.items():self.assertEqual((root/name).read_bytes(),data)
