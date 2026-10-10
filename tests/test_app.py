import json
import os
import sys
import shutil
import uuid
import unittest
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


class LibraryTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[1] / 'work' / 'test-runs'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp_path = scratch / str(uuid.uuid4())
        self.root = self.temp_path / 'comics'
        self.root.mkdir(parents=True)
        self.previous_data = app.DATA
        app.DATA = self.temp_path / 'catalog'

    def tearDown(self):
        app.DATA = self.previous_data
        intended = Path(__file__).resolve().parents[1] / 'work' / 'test-runs'
        assert self.temp_path.resolve().parent == intended.resolve()
        shutil.rmtree(self.temp_path)

    def make(self, name='Example 001 (2024).cbz', xml=None):
        path = self.root / name
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('001.jpg', b'pretend cover bytes')
            archive.writestr('002.jpg', b'pretend page bytes' * 1000)
            archive.comment = b'preserve me'
            if xml:
                archive.writestr('ComicInfo.xml', xml)
        return path

    def scan(self):
        app.JOB.update(running=True, changed=0, visited=0, errors=0)
        app.scan([str(self.root)])

    def row(self, path):
        with app.db() as con:
            return dict(con.execute('SELECT * FROM comics WHERE path=?', (str(path),)).fetchone())

    def test_delta_new_changed_and_unchanged(self):
        first = self.make()
        self.scan()
        self.assertEqual(app.JOB['changed'], 1)
        self.assertEqual(self.row(first)['number'], '1')
        self.scan()
        self.assertEqual(app.JOB['changed'], 0)
        self.make('Other 002 (2023).cbz')
        self.scan()
        self.assertEqual(app.JOB['changed'], 1)
        with zipfile.ZipFile(first, 'a') as archive:
            archive.writestr('003.jpg', b'new page')
        self.scan()
        self.assertEqual(app.JOB['changed'], 1)

    def test_backup_archive_and_xml_preservation(self):
        path = self.make(xml='<ComicInfo><Title>Keep title</Title><Notes>Custom</Notes><Pages><Page Image="0" Type="FrontCover"/></Pages></ComicInfo>')
        original = path.read_bytes()
        self.scan()
        backup = app.write_metadata(self.row(path), {'Title': 'Replace?', 'Writer': 'Test Writer', 'Series': 'Example'})
        self.assertEqual(Path(backup).read_bytes(), original)

        with zipfile.ZipFile(path) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.comment, b'preserve me')
            self.assertEqual(archive.read('001.jpg'), b'pretend cover bytes')
            xml = ET.fromstring(archive.read('ComicInfo.xml'))
            self.assertEqual(xml.findtext('Title'), 'Keep title')
            self.assertEqual(xml.findtext('Writer'), 'Test Writer')
            self.assertEqual(xml.findtext('Notes'), 'Custom')
            self.assertEqual(xml.find('Pages/Page').get('Type'), 'FrontCover')
        self.scan()
        self.assertEqual(app.JOB['changed'], 0)
        self.assertEqual(self.row(path)['status'], 'tagged')

    def test_synopsis_windows_line_breaks_survive_exact_readback(self):
        import batch,pause_control
        path=self.make()
        (self.temp_path/'data').mkdir()
        summary='A visitor arrives.\r\n\r\nA strange bargain awaits.\rLast line & more.'
        plan=self.temp_path/'batch'/'plan.json';plan.parent.mkdir()
        plan.write_text(json.dumps({'folder':str(self.root),'entries':[{'path':str(path),'action':'write','sha256':batch.digest(path),'changes':{'Summary':{'before':'','after':summary}},'fields':{'Summary':summary}}]}))
        with patch.object(app,'BASE',self.temp_path),patch.object(pause_control,'requested',return_value=False):
            batch.apply(plan,remove_verified_backups=True)
        self.assertEqual(app.read_metadata(path)[0]['Summary'],summary)
        results=json.loads((plan.parent/'results.json').read_text())
        self.assertTrue(results[0]['metadata_readback_verified'])
        self.assertFalse((self.root/'.comic-metadata-backups').exists())
        with zipfile.ZipFile(path) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.read('001.jpg'),b'pretend cover bytes')

    def test_changed_file_is_not_written(self):
        path = self.make()
        self.scan()
        row = self.row(path)
        with zipfile.ZipFile(path, 'a') as archive:
            archive.writestr('extra.jpg', b'extra')
        with self.assertRaisesRegex(ValueError, 'changed'):
            app.write_metadata(row, {'Title': 'No'})
        self.assertFalse((self.root / '.comic-metadata-backups').exists())

    def test_failed_temporary_metadata_readback_preserves_original(self):
        path=self.make();original=path.read_bytes();self.scan()
        with patch.object(app,'metadata_xml',return_value=ET.fromstring('<ComicInfo><Summary>Wrong</Summary></ComicInfo>')):
            with self.assertRaisesRegex(ValueError,'Temporary archive metadata verification failed'):
                app.write_metadata(self.row(path),{'Summary':'Verified teaser'})
        self.assertEqual(path.read_bytes(),original)
        self.assertFalse(path.with_name(path.name+'.metadata-tmp').exists())
        with app.db() as con:
            self.assertEqual(con.execute('SELECT count(*) FROM history').fetchone()[0],0)

    def test_reviewed_corrections_preserve_personal_fields(self):
        path = self.make(xml='<ComicInfo><Writer>Wrong credit</Writer><Notes>Personal note</Notes><Review>My review</Review></ComicInfo>')
        self.scan()
        app.write_metadata(self.row(path), {'Writer':'Verified writer','Notes':'Source evidence'},
                           overwrite_fields={'Writer'}, append_notes=True)
        metadata,_,_=app.read_metadata(path)
        self.assertEqual(metadata['Writer'],'Verified writer')
        self.assertEqual(metadata['Notes'],'Personal note\n\nSource evidence')
        self.assertEqual(metadata['Review'],'My review')

    def test_missing_root_does_not_mark_files_absent(self):
        path = self.make()
        self.scan()
        app.scan([str(self.root / 'offline')])
        self.assertEqual(self.row(path)['status'], 'missing')

    def test_absent_reappearing_file_recovers_status(self):
        path = self.make()
        self.scan()
        moved = path.with_suffix('.hold')
        path.rename(moved)
        self.scan()
        self.assertEqual(self.row(path)['status'], 'absent')
        moved.rename(path)
        self.scan()
        self.assertEqual(self.row(path)['status'], 'missing')

    def test_unsupported_and_corrupt_files(self):
        unsupported = self.root / 'Rare.cbr'
        unsupported.write_bytes(b'rar')
        corrupt = self.root / 'Corrupt.cbz'
        corrupt.write_bytes(b'not a zip')
        self.scan()
        self.assertEqual(self.row(unsupported)['status'], 'unsupported')
        self.assertEqual(self.row(corrupt)['status'], 'error')

    def test_parent_only_scan_does_not_hide_existing_subfolder_comics(self):
        child=self.root/'child';child.mkdir()
        path=self.make('child/Example 001.cbz')
        self.scan()
        app.scan([str(self.root)],recursive=False)
        self.assertEqual(self.row(path)['status'],'missing')
        path.unlink()
        app.scan([str(self.root)],recursive=False)
        self.assertEqual(self.row(path)['status'],'missing')
        self.scan()
        self.assertEqual(self.row(path)['status'],'absent')

    def test_absent_tagged_archive_retains_write_history_status(self):
        path=self.make(xml='<ComicInfo><Title>Verified</Title></ComicInfo>')
        self.scan()
        with app.db() as con:
            con.execute("UPDATE comics SET status='absent' WHERE path=?",(str(path),))
            con.execute('INSERT INTO history(path,backup,source,timestamp) VALUES(?,?,?,?)',(str(app.filesystem_path(path)),'','',0))
        self.scan()
        self.assertEqual(self.row(path)['status'],'tagged')

    def test_metadata_mapping_uses_credits_and_date(self):
        result = app.metadata_from_issue({'volume': {'name': 'Series'}, 'issue_number': '2',
            'cover_date': '2024-01-02', 'description': '<p>A &amp; B</p>',
            'person_credits': [{'name': 'Person', 'role': 'writer, penciler'}]})
        self.assertEqual(result['Writer'], 'Person')
        self.assertEqual(result['Penciller'], 'Person')
        self.assertEqual(result['Summary'], 'A & B')
        self.assertEqual(result['Year'], '2024')

    def test_bare_ampersand_metadata_recovery_preserves_cdata(self):
        path=self.make(xml='<ComicInfo><Publisher>A & B</Publisher><Summary><![CDATA[A &amp; B]]></Summary></ComicInfo>')
        metadata,status,_=app.read_metadata(path)
        self.assertEqual(status,'embedded')
        self.assertEqual(metadata['Publisher'],'A & B')
        self.assertEqual(metadata['Summary'],'A &amp; B')
        self.scan()
        app.write_metadata(self.row(path),{'Title':'Verified title'})
        self.assertEqual(app.read_metadata(path)[0]['Publisher'],'A & B')

    def test_broken_zip_container_is_separate_from_metadata_errors(self):
        path=self.root/'Damaged.cbz';path.write_bytes(b'PK\x03\x04broken zip container')
        self.scan()
        self.assertEqual(self.row(path)['status'],'corrupted')

    def test_nonzip_cbz_is_other_format_not_corrupted(self):
        path=self.root/'Readable.cbz';path.write_bytes(b'7z\xbc\xaf\x27\x1c\x00\x04')
        self.assertEqual(app.read_metadata(path)[1],'unsupported')

    def test_illegal_xml_controls_repaired_without_changing_story_text(self):
        path=self.make(xml='<ComicInfo><Summary>Premise.\x01\x01Next paragraph.</Summary><Title>Example</Title></ComicInfo>')
        self.scan()
        row=self.row(path)
        self.assertEqual(json.loads(row['metadata'])['Summary'],'Premise.\n\nNext paragraph.')
        app.write_metadata(row,{})
        with zipfile.ZipFile(path) as archive:
            xml=ET.fromstring(archive.read('ComicInfo.xml'))
            self.assertEqual(xml.findtext('Summary'),'Premise.\n\nNext paragraph.')

    def test_synopsis_filter_includes_existing_and_tagged_metadata_only(self):
        existing=self.make('Existing.cbz','<ComicInfo><Title>Existing</Title></ComicInfo>')
        tagged=self.make('Tagged.cbz','<ComicInfo><Title>Tagged</Title><Summary> </Summary></ComicInfo>')
        self.make('Complete.cbz','<ComicInfo><Title>Complete</Title><Summary>Verified premise.</Summary></ComicInfo>')
        synopsis_only=self.make('SynopsisOnly.cbz','<ComicInfo><Summary>Verified premise.</Summary><Notes>Provenance</Notes><PageCount>20</PageCount></ComicInfo>')
        self.make('Missing.cbz')
        self.scan()
        with app.db() as con:con.execute("UPDATE comics SET status='tagged' WHERE path=?",(str(tagged),))
        handler=object.__new__(app.Handler)
        from types import SimpleNamespace
        handler.headers={'Host':'127.0.0.1:8765'}
        handler.server=SimpleNamespace(server_port=8765)
        handler.path='/api/comics?status=needs_synopsis'
        with patch.object(app,'live_root',return_value=''),patch.object(handler,'respond') as respond:
            handler.do_GET()
        result=respond.call_args.args[0]
        self.assertEqual(result['total'],2)
        self.assertEqual({r['path'] for r in result['rows']},{str(existing),str(tagged)})
        self.assertTrue(all(not r['has_synopsis'] for r in result['rows']))
        handler.path='/api/comics?status=metadata_complete'
        with patch.object(app,'live_root',return_value=''),patch.object(handler,'respond') as respond:
            handler.do_GET()
        result=respond.call_args.args[0]
        self.assertEqual(result['total'],1)
        self.assertTrue(result['rows'][0]['has_synopsis'])
        handler.path='/api/comics?status=synopsis_only'
        with patch.object(app,'live_root',return_value=''),patch.object(handler,'respond') as respond:
            handler.do_GET()
        result=respond.call_args.args[0]
        self.assertEqual(result['total'],1)
        self.assertEqual(result['rows'][0]['path'],str(synopsis_only))
        self.assertFalse(result['rows'][0]['has_metadata'])

    def test_rate_reservations_persist_and_pace_attempts(self):
        self.assertEqual(app.reserve_request(10000), 0)
        self.assertEqual(app.reserve_request(10001), 19)
        self.assertEqual(app.reserve_request(10020), 0)
        with app.db() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM api_requests').fetchone()[0], 2)
            con.execute('UPDATE api_state SET blocked_until=11000 WHERE id=1')
        with self.assertRaisesRegex(ValueError, 'cooling down'):
            app.reserve_request(10021)

    def test_hourly_budget_and_expiry(self):
        with app.db() as con:
            con.executemany('INSERT INTO api_requests VALUES(?)', [(10000,)] * 180)
        with self.assertRaisesRegex(ValueError, 'budget'):
            app.reserve_request(11000)
        self.assertEqual(app.reserve_request(13601), 0)


if __name__ == '__main__':
    unittest.main()
