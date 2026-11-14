import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import app
import archive_conversion
from test_app import LibraryTests


class ConversionReconcileTests(LibraryTests):
    def request(self,path,body=None,root=None):
        handler=object.__new__(app.Handler);handler.server=SimpleNamespace(server_port=8765);handler.path=path
        handler.headers={'Host':'127.0.0.1:8765'}
        if body is not None:
            raw=json.dumps(body).encode();handler.rfile=io.BytesIO(raw)
            handler.headers.update({'Origin':'http://127.0.0.1:8765','Content-Length':str(len(raw))})
        replies=[];handler.respond=lambda data,status=200,mime='application/json':replies.append((status,data))
        with patch.object(app,'live_root',return_value=str(self.root) if root is None else root):
            (handler.do_POST if body is not None else handler.do_GET)()
        return replies[-1]

    def add_cbr(self,folder,name):
        folder.mkdir(parents=True,exist_ok=True);path=folder/name;path.write_bytes(b'fixture rar');return path

    def test_nonrecursive_reconciles_ancestor_scanned_row_and_preserves_history(self):
        folder=self.root/'Folder';old=self.add_cbr(folder,'Book.cbr');self.scan()
        with app.db() as con:con.execute('INSERT INTO history(path,backup,source,timestamp) VALUES(?,?,?,?)',(str(old),'','fixture',1))
        old.unlink();new=self.make('Folder/Book.cbz');app.scan([str(folder)],recursive=False)
        self.assertEqual(self.row(old)['status'],'absent');self.assertEqual(self.row(new)['status'],'missing')
        with app.db() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM history WHERE path=?',(str(old),)).fetchone()[0],1)
            counts=dict(con.execute('SELECT status,COUNT(*) FROM comics GROUP BY status').fetchall())
        self.assertEqual(app.inventory_totals(counts)['conversion'],0)

    def test_on_open_rechecks_all_unsupported_and_keeps_search_and_absent_filter(self):
        first=self.add_cbr(self.root/'A','gone.cbr');second=self.add_cbr(self.root/'B','keep.cbr');self.scan();first.unlink()
        status,before=self.request('/api/comics?status=unsupported');self.assertEqual((status,before['total']),(200,2))
        status,result=self.request('/api/conversion/recheck',{});self.assertEqual((status,result['uncertain']),(200,0))
        self.assertEqual(self.row(first)['status'],'absent');self.assertEqual(self.row(second)['status'],'unsupported')
        _,filtered=self.request('/api/comics?status=unsupported&q=nomatch');self.assertEqual((filtered['total'],filtered['conversion_total']),(0,1))
        _,absent=self.request('/api/comics?status=absent&q=gone');self.assertEqual(absent['total'],1)
        _,all_rows=self.request('/api/comics');self.assertEqual(all_rows['total'],2)  # Existing All-files behavior retained.

    def test_offline_parent_and_stat_errors_never_retire(self):
        old=self.add_cbr(self.root/'A','gone.cbr');self.scan();old.unlink()
        with patch('app.os.scandir',side_effect=PermissionError('offline')):
            status,result=self.request('/api/conversion/recheck',{})
        self.assertEqual((status,result['uncertain']),(200,1));self.assertEqual(self.row(old)['status'],'unsupported')
        real=app.filesystem_path
        class Refused:
            def stat(self):raise PermissionError('offline')
        with patch.object(app,'filesystem_path',side_effect=lambda p:Refused() if Path(p)==old else real(p)):
            status,result=self.request('/api/conversion/recheck',{})
        self.assertEqual((status,result['uncertain']),(200,1));self.assertEqual(self.row(old)['status'],'unsupported')

    def test_no_configured_root_does_not_check_or_change_rows(self):
        old=self.add_cbr(self.root,'gone.cbr');self.scan();old.unlink()
        with patch('app.os.scandir') as scandir:status,_=self.request('/api/conversion/recheck',{},root='')
        self.assertEqual(status,400);scandir.assert_not_called();self.assertEqual(self.row(old)['status'],'unsupported')

    def test_failed_walk_and_excluded_folders_never_mark_absent(self):
        old=self.add_cbr(self.root/'A','gone.cbr');self.scan();old.unlink()
        def interrupted(*args,**kwargs):
            yield str(self.root),[],[]
            raise OSError('fixture walk failed')
        with patch('app.os.walk',side_effect=interrupted):app.scan([str(self.root)])
        self.assertEqual(self.row(old)['status'],'unsupported')
        excluded=self.root/'.yacreaderlibrary';excluded.mkdir();hidden=self.add_cbr(excluded,'hidden.cbr')
        app.scan([str(excluded)]);hidden.unlink();app.scan([str(self.root)])
        self.assertEqual(self.row(hidden)['status'],'unsupported')

    def test_concurrent_changed_row_is_not_overwritten(self):
        old=self.add_cbr(self.root,'gone.cbr');self.scan();old.unlink()
        with app.db() as con:
            snapshot=con.execute('SELECT id,path,status,size,mtime,seen FROM comics WHERE path=?',(str(old),)).fetchall()
            con.execute('UPDATE comics SET seen=seen+1 WHERE path=?',(str(old),))
            self.assertEqual(app.reconcile_missing(con,snapshot),1)
        self.assertEqual(self.row(old)['status'],'unsupported')

    def test_conversion_worker_skips_missing_and_changed_sources(self):
        old=self.add_cbr(self.root,'gone.cbr');self.scan();old.unlink()
        with patch.object(archive_conversion,'convert') as convert:
            self.assertFalse(archive_conversion.one(self.root));convert.assert_not_called()
        self.assertEqual(self.row(old)['status'],'unsupported')
        old.write_bytes(b'changed fixture')
        with patch.object(archive_conversion,'convert') as convert:
            self.assertFalse(archive_conversion.one(self.root));convert.assert_not_called()
