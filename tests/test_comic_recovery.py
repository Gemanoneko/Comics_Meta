"""Offline recovery regressions. No real provider, library or credential access."""
import contextlib
import copy
import time
import unittest
from unittest.mock import patch
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
        self.assertEqual(fields['Web'], 'https://example.test/page; ; https://other.test/')
        self.assertEqual(self.old, before)

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

    def test_postwrite_mismatch_reports_retained_recovery_not_success(self):
        def write(*args,**kwargs):
            self.assertEqual(kwargs['expected_snapshot'],self.old)
            self.assertTrue(kwargs['verify_readback'])
            self.assertTrue(kwargs['guard_held'])
            self.assertEqual(kwargs['writer'],'manual')
            kwargs['attempt']['backup']='owned-backup'
            return 'owned-backup'
        with patch.object(recovery.app,'comic_write_guard',create=True,return_value=contextlib.nullcontext()), \
             patch('pause_control.requested',return_value=False), \
             patch.object(recovery,'snapshot',return_value=(self.row,self.old,self.record,{'issue_id':'123'})), \
             patch.object(recovery.app,'write_metadata',side_effect=write), \
             patch.object(recovery.app,'read_metadata',return_value=(dict(self.old,Web='unexpected'),'embedded','')):
            result=recovery.confirm('token',True)
        self.assertFalse(result['verified'])
        self.assertEqual(result['backup'],'owned-backup')
        with self.assertRaises(recovery.RecoveryError):recovery.confirm('token',True)

if __name__ == '__main__':
    unittest.main()
