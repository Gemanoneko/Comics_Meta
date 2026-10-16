"""Offline recovery regressions. No real provider, library or credential access."""
import contextlib
from pathlib import Path
import copy
import time
import unittest
from unittest.mock import MagicMock, patch
import comic_recovery as recovery

class RecoveryPlanTests(unittest.TestCase):
    def setUp(self):
        self.old = {'Series': 'Good', 'Number': '1', 'Year': '2000', 'Publisher': 'Keep',
                    'Summary': 'Keep synopsis', 'Web': 'https://example.test/page; https://comicvine.gamespot.com/old/4000-123/; https://other.test/'}
        self.source = {'issue_id': 456, 'url': recovery.canonical(456), 'fields':
                       {'Series': 'Another Series', 'Number': '7', 'Year': '2001', 'Month': '2', 'Day': '3'},
                       'revision': 'trusted', 'checked_at': time.time()}

    def test_removal_preserves_other_links_and_fields(self):
        before = copy.deepcopy(self.old)
        fields = recovery.plan_fields(self.old, 'remove_link', target=123)
        self.assertEqual(set(fields), {'Web'})
        self.assertEqual(fields['Web'], 'https://example.test/page; https://other.test/')  # Not '; ;' (Futaba 0.2.3 m2).
        self.assertEqual(self.old, before)

    def test_removal_keeps_no_stray_separator_at_either_end_or_alone(self):
        link = 'https://comicvine.gamespot.com/old/4000-123/'
        for web, after in ((link + '; https://other.test/', 'https://other.test/'), ('https://a.test/; ' + link, 'https://a.test/'),
                           (link, ''), ('https://a.test/\n' + link + '\nhttps://b.test/', 'https://a.test/\nhttps://b.test/'),
                           ('https://a.test/, ' + link + ' ,https://b.test/', 'https://a.test/, https://b.test/')):
            with self.subTest(web=web):
                self.assertEqual(recovery.plan_fields({'Web': web}, 'remove_link', target=123), {'Web': after})

    def test_provider_identity_only(self):
        fields = recovery.plan_fields(self.old, 'use_provider', self.source, 123)
        self.assertEqual(set(fields), {'Series', 'Number', 'Year', 'Month', 'Day', 'Web'})
        self.assertNotIn('Publisher', fields)
        self.assertNotIn('Summary', fields)
        self.assertIn('https://other.test/', fields['Web'])

    def test_keep_file_rejects_substantive_conflict(self):
        with self.assertRaises(recovery.RecoveryError) as caught:
            recovery.plan_fields(self.old, 'keep_file', self.source, 123)
        self.assertEqual(caught.exception.code, 'conflict')

    def test_keep_file_rejects_date_conflict(self):
        self.source['fields'].update(Series='Good', Number='1')
        with self.assertRaises(recovery.RecoveryError):
            recovery.plan_fields(self.old, 'keep_file', self.source, 123)

    def test_case_punctuation_number_format_keep_existing(self):
        self.old.update(Series='BATMAN - Year One', Number='001', Year='2001')
        self.source['fields'].update(Series='Batman: Year One', Number='1')
        fields = recovery.plan_fields(self.old, 'use_provider', self.source, 123)
        self.assertNotIn('Series', fields)
        self.assertNotIn('Number', fields)
        self.assertNotIn('Year', fields)

    def test_keep_file_changes_only_link(self):
        self.source['fields'].update(Series='Good', Number='1', Year='2000')
        self.assertEqual(set(recovery.plan_fields(self.old, 'keep_file', self.source, 123)), {'Web'})

    def test_ambiguous_duplicate_target_rejected(self):
        self.old['Web'] += ' https://comicvine.gamespot.com/second/4000-123/'
        with self.assertRaises(recovery.RecoveryError):
            recovery.plan_fields(self.old, 'remove_link', target=123)

    def test_supported_links_only(self):
        self.assertEqual(recovery.issue_id('https://comicvine.gamespot.com/title/4000-123/'),123)
        for value in ['https://evil.test/4000-123/', 'https://comicvine.gamespot.com@evil.test/4000-123/',
                      'file:///4000-123/', 'https://comicvine.gamespot.com:443/title/4000-123/',
                      'https://comicvine.gamespot.com/4000-123/?x=1', 'https://comicvine.gamespot.com:bad/4000-123/', 'https://comicvine.gamespot.com/4000-123abc/', True, 0]:
            with self.subTest(value=value), self.assertRaises((recovery.RecoveryError, ValueError)):
                recovery.issue_id(value)

    def test_partial_issue_id_in_web_is_not_a_removal_target(self):
        self.old['Web']='https://comicvine.gamespot.com/title/4000-123abc/'
        with self.assertRaises(recovery.RecoveryError):
            recovery.plan_fields(self.old,'remove_link',target=123)

    def test_invalid_port_is_typed_invalid_link(self):
        with self.assertRaises(recovery.RecoveryError) as caught:
            recovery.issue_id('https://comicvine.gamespot.com:bad/4000-123/')
        self.assertEqual(caught.exception.code,'invalid_link')

    def test_provider_malformed_identity_or_image_fails_before_cache_access(self):
        valid={'id':456,'volume':{'name':'Good','id':8},'issue_number':'1','image':None}
        for changed in [{'volume':[]},{'volume':{'name':{'nested':'bad'}}},{'issue_number':[]},
                        {'image':['bad']},{'image':{'small_url':{'nested':'bad'}}},
                        {'image':{'small_url':'https://user:secret@example.test/image.png'}},
                        {'image':{'small_url':'javascript:alert(1)'}},{'cover_date':[]}]:
            with self.subTest(changed=changed), patch.object(recovery.app,'api',return_value=dict(valid,**changed)), patch.object(recovery.app,'db') as database:
                with self.assertRaises(recovery.RecoveryError):recovery.provider(456)
                database.assert_not_called()

class RecoveryConfirmationTests(unittest.TestCase):
    def setUp(self):
        recovery._PLANS.clear()
        self.row={'id':1,'path':'isolated.cbz','size':10,'mtime':20}
        self.old={'Series':'Good','Number':'1','Web':'https://comicvine.gamespot.com/title/4000-123/'}
        self.record={'signature':[10,20],'outcome':'identity_conflict'}
        self.plan={'comic':1,'action':'remove_link','row':dict(self.row),'old':dict(self.old),
                   'record_revision':recovery.digest(self.record),'source':None,'fields':{'Web':''},'created':time.time()}
        recovery._PLANS['token']=self.plan

    def tearDown(self):
        recovery._PLANS.clear()

    def test_requires_explicit_boolean_confirmation(self):
        with self.assertRaises(recovery.RecoveryError):
            recovery.confirm('token','true')
        self.assertIn('token',recovery._PLANS)

    def test_expired_plan_cannot_write(self):
        self.plan['created']=time.time()-recovery.TTL-1
        with patch.object(recovery.app,'write_metadata') as writer:
            with self.assertRaises(recovery.RecoveryError):recovery.confirm('token',True)
            writer.assert_not_called()

    def test_changed_full_metadata_rejects_before_write(self):
        with patch.object(recovery.app,'comic_write_guard',create=True,return_value=contextlib.nullcontext()), \
             patch('pause_control.requested',return_value=False), \
             patch.object(recovery,'snapshot',return_value=(self.row,dict(self.old,Summary='changed'),self.record,{'issue_id':'123'})), \
             patch.object(recovery.app,'write_metadata') as writer:
            with self.assertRaises(recovery.RecoveryError):recovery.confirm('token',True)
            writer.assert_not_called()
        self.assertNotIn('token',recovery._PLANS)

    def test_provider_revision_changed_revokes_confirmation(self):
        self.plan['source']={'issue_id':456,'revision':'old'}
        with patch.object(recovery.app,'comic_write_guard',create=True,return_value=contextlib.nullcontext()), \
             patch('pause_control.requested',return_value=False), \
             patch.object(recovery,'snapshot',return_value=(self.row,self.old,self.record,{'issue_id':'123'})), \
             patch.object(recovery,'provider',return_value={'revision':'new'}), \
             patch.object(recovery.app,'write_metadata') as writer:
            with self.assertRaises(recovery.RecoveryError) as caught:recovery.confirm('token',True)
            self.assertEqual(caught.exception.code,'stale')
            writer.assert_not_called()
        self.assertNotIn('token',recovery._PLANS)

    def test_pause_never_resumes_or_writes(self):
        with patch.object(recovery.app,'comic_write_guard',create=True,return_value=contextlib.nullcontext()), \
             patch('pause_control.requested',return_value=True), \
             patch.object(recovery.app,'write_metadata') as writer:
            with self.assertRaises(recovery.RecoveryError):recovery.confirm('token',True)
            writer.assert_not_called()

    def write(self,*args,**kwargs):
        self.assertEqual(kwargs['expected_snapshot'],self.old)
        self.assertTrue(kwargs['verify_readback'])
        self.assertTrue(kwargs['guard_held'])
        self.assertEqual(kwargs['writer'],'manual')
        self.assertFalse(kwargs.get('remove_verified_backups',False))  # Removal waits for the full-snapshot check.
        kwargs['attempt']['backup']='owned-backup'
        return 'owned-backup'

    def no_record(self):
        con=MagicMock()
        con.execute.return_value.fetchone.return_value=None
        return con

    def confirm_with(self,after,remove=None):
        with patch.object(recovery.app,'comic_write_guard',create=True,return_value=contextlib.nullcontext()), \
             patch('pause_control.requested',return_value=False), \
             patch.object(recovery,'snapshot',return_value=(self.row,self.old,self.record,{'issue_id':'123'})), \
             patch.object(recovery,'archive_sha256',return_value='original-sha'), \
             patch.object(recovery.app,'write_metadata',side_effect=self.write), \
             patch.object(recovery.app,'read_metadata',return_value=(after,'embedded','')), \
             patch.object(recovery.app,'remove_verified_backup',side_effect=remove) as remover, \
             patch.object(recovery.app,'comic',return_value=self.row), \
             patch.object(recovery.app,'db',return_value=contextlib.nullcontext(self.no_record())), \
             patch('discovery_state.initialize'):
            return recovery.confirm('token',True),remover

    def test_postwrite_mismatch_reports_retained_recovery_not_success(self):
        result,remover=self.confirm_with(dict(self.old,Web='unexpected'))
        self.assertFalse(result['verified'])
        self.assertEqual(result['backup'],'owned-backup')
        self.assertEqual(result['message'],recovery.NOT_VERIFIED)
        self.assertRegex(result['backup_id'],'^[0-9a-f]{32}$')  # The page shows this backup's location.
        remover.assert_not_called()  # Control: a failed verification never removes the backup.
        with self.assertRaises(recovery.RecoveryError):recovery.confirm('token',True)

    def test_verified_save_removes_its_backup_with_the_original_digest(self):
        result,remover=self.confirm_with(dict(self.old,Web=''))
        self.assertTrue(result['verified'])
        remover.assert_called_once_with('isolated.cbz','owned-backup','original-sha')
        self.assertEqual((result['backup_retained'],result['backup_removed_after_verification']),(False,True))
        self.assertEqual(result['message'],'Change saved and verified.')
        self.assertNotIn('backup_id',result)  # A deleted backup has no location to show.

    def test_refused_backup_removal_keeps_backup_and_still_reports_verified(self):
        result,remover=self.confirm_with(dict(self.old,Web=''),remove=ValueError('Backup verification failed.'))
        remover.assert_called_once()
        self.assertTrue(result['verified'])
        self.assertEqual((result['backup_retained'],result['backup_removed_after_verification']),(True,False))
        self.assertEqual(result['message'],'Change saved and verified. The recovery backup could not be deleted and was retained.')
        self.assertRegex(result['backup_id'],'^[0-9a-f]{32}$')

    def test_failure_before_the_backup_copy_says_no_backup_was_made(self):
        def refuse(*args,**kwargs):
            raise recovery.app.ArchiveChanged('ComicInfo changed since this preview; nothing written.')
        self.write=refuse
        result,_=self.confirm_with(self.old)
        self.assertEqual((result['verified'],result['backup']),(False,None))
        self.assertEqual(result['message'],'The change was not verified. No recovery backup was made. Check the file before trying again.')
        self.assertNotIn('backup_id',result)

class RecoveryBackupFileTests(unittest.TestCase):
    """Real archive, real write_metadata and real backup removal through confirm() (0.2.3)."""
    WEB = 'https://comicvine.gamespot.com/title/4000-123/ https://other.test/'

    def setUp(self):
        import os, shutil, uuid
        from test_app import scratch_parent
        self.shutil = shutil
        scratch = scratch_parent()
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp_path = scratch / str(uuid.uuid4())
        self.root = self.temp_path / 'comics'
        self.root.mkdir(parents=True)
        self.previous_data = recovery.app.DATA
        recovery.app.DATA = self.temp_path / 'catalog'
        recovery._PLANS.clear()
        self.path = self.root / 'Good 001 (2000).cbz'
        self.archive('<ComicInfo><Series>Good</Series><Number>1</Number><Web>' + self.WEB + '</Web></ComicInfo>')
        self.original = self.path.read_bytes()
        recovery.app.JOB.update(running=True, changed=0, visited=0, errors=0)
        recovery.app.scan([str(self.root)])
        with recovery.app.db() as con:
            self.row = dict(con.execute('SELECT * FROM comics WHERE path=?', (str(self.path),)).fetchone())
        self.old = recovery.app.read_metadata(self.path)[0]
        recovery._PLANS['token'] = {'comic': self.row['id'], 'action': 'remove_link', 'row': dict(self.row),
            'old': dict(self.old), 'record_revision': recovery.digest({}), 'source': None,
            'fields': recovery.plan_fields(self.old, 'remove_link', target=123), 'created': time.time()}

    def tearDown(self):
        recovery._PLANS.clear()
        recovery.app.DATA = self.previous_data
        from test_app import scratch_parent
        from test_worker import prune_scratch
        intended = scratch_parent()
        assert self.temp_path.resolve().parent == intended.resolve()
        self.shutil.rmtree(self.temp_path)
        prune_scratch(intended)

    def archive(self, xml):
        import zipfile
        with zipfile.ZipFile(self.path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('001.jpg', b'pretend cover bytes')
            archive.writestr('002.jpg', b'pretend page bytes' * 1000)
            archive.writestr('ComicInfo.xml', xml)

    def backups(self):
        folder = self.root / '.comic-metadata-backups'
        return sorted(folder.iterdir()) if folder.exists() else []

    def confirm(self, write=None):
        with patch('library_lock.require'), patch('pause_control.requested', return_value=False), \
             patch.object(recovery, 'snapshot', return_value=(self.row, dict(self.old), {}, {'issue_id': '123'})), \
             patch.object(recovery.app, 'write_metadata', side_effect=write or recovery.app.write_metadata):
            return recovery.confirm('token', True)

    def test_verified_recovery_save_removes_its_backup(self):
        result = self.confirm()
        self.assertTrue(result['verified'])
        self.assertEqual(result['message'], 'Change saved and verified.')
        self.assertEqual((result['backup_retained'], result['backup_removed_after_verification']), (False, True))
        self.assertEqual(recovery.app.read_metadata(self.path)[0]['Web'], 'https://other.test/')
        self.assertFalse(recovery.app.filesystem_path(result['backup']).exists())
        self.assertEqual(self.backups(), [])
        self.assertFalse((self.root / '.comic-metadata-backups').exists())  # The emptied folder goes too.

    def test_failed_verification_keeps_the_original_as_backup(self):
        real = recovery.app.write_metadata
        def write_then_changed_elsewhere(*args, **kwargs):
            backup = real(*args, **kwargs)
            # Another program edits a field the preview never showed; the full-snapshot check must fail.
            self.archive('<ComicInfo><Series>Edited elsewhere</Series><Number>1</Number><Web> https://other.test/</Web></ComicInfo>')
            return backup
        result = self.confirm(write_then_changed_elsewhere)
        self.assertFalse(result['verified'])
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.backups()[0].name, Path(result['backup']).name)
        self.assertEqual(self.backups()[0].read_bytes(), self.original)
        self.assertEqual(result['message'], recovery.NOT_VERIFIED)  # Changed elsewhere: never 'not changed'.

    def kept_reasons(self):
        with recovery.app.db() as con:
            import kept_backups
            kept_backups._table(con)
            return [row[0] for row in con.execute('SELECT reason FROM kept_backups')]

    @unittest.skipUnless(__import__('os').name == 'nt', 'Windows refuses to replace a read-only file')
    def test_read_only_comic_says_not_saved_and_not_changed(self):
        import os, stat
        os.chmod(self.path, stat.S_IREAD)
        def writable():
            for path in (self.path, *self.backups()):
                os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
        try:  # tearDown removes the folder before cleanups run, so read-only is undone here.
            result = self.confirm()
            self.assertFalse(result['verified'])
            self.assertEqual(result['message'], "The change was not saved because this comic file is read-only. The file was not changed. Turn off Read-only in the file's Properties, then try again.")
            self.assertEqual(self.path.read_bytes(), self.original)  # Measured: nothing was written.
            self.assertEqual([p.name for p in self.backups()], [Path(result['backup']).name])
            self.assertRegex(result['backup_id'], '^[0-9a-f]{32}$')
            self.assertEqual(self.kept_reasons(), ['save_not_verified'])
        finally:
            writable()

if __name__ == '__main__':
    unittest.main()
