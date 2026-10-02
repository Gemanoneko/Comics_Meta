import json
import unittest
from pathlib import Path
from unittest.mock import patch
import app,discovery_state,cover_tasks,local_model
from test_worker import scratch_directory


class DiscoveryStateTests(unittest.TestCase):
    def test_unicode_migration_happens_once_and_preserves_newer_results(self):
        with scratch_directory() as d,patch.object(app,'DATA',Path(d)):
            folder=Path(d)/'comics';path=folder/'0Ѕ — café.cbz'
            (Path(d)/'automatic.json').write_text(json.dumps({'checked':{str(path):{'outcome':'old'}}},ensure_ascii=False),encoding='utf-8')
            self.assertEqual(discovery_state.load(folder)['checked'][str(path)]['outcome'],'old')
            discovery_state.save_one(path,{'outcome':'new'})
            self.assertEqual(discovery_state.load(folder)['checked'][str(path)]['outcome'],'new')

    def test_large_library_only_loads_current_folder(self):
        with scratch_directory() as d,patch.object(app,'DATA',Path(d)):
            folder=Path(d)/'current';path=folder/'one.cbz'
            discovery_state.save_one(path,{'outcome':'current'})
            with app.db() as con:
                con.executemany('INSERT INTO discovery_records VALUES(?,?)',((str(Path(d)/'elsewhere'/str(i)/'book.cbz'),json.dumps({'outcome':'pending','error':'x'*1000})) for i in range(25000)))
            self.assertEqual(list(discovery_state.load(folder)['checked']),[str(path)])
            self.assertEqual(discovery_state.counts(folder),{'current':1})

    def test_cover_task_is_not_duplicated_until_archive_changes(self):
        with scratch_directory() as d,patch.object(app,'DATA',Path(d)):
            row={'path':str(Path(d)/'comic.cbz'),'size':10,'mtime':1}
            cover_tasks.enqueue(row);cover_tasks.enqueue(row)
            self.assertEqual(cover_tasks.status(),{'pending':1})
            with self.assertRaises(ValueError):cover_tasks.record(row,[{'url':'http://example.org'}])

    def test_reversed_bargain_is_rejected_before_model_review(self):
        source={'url':'https://example.org','text':"Her mother's freedom in exchange for Shi's life."}
        draft={'summary':'A '*24+"Offered Shi's life for her mother's freedom.",'sufficient':True,'narrative':True,'evidence':[source['text']]}
        with patch.object(local_model,'chat',return_value=draft) as chat:
            self.assertIsNone(local_model.sourced_synopsis([source]));self.assertEqual(chat.call_count,1)
