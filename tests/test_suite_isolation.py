"""Futaba Q-8: the suite never writes the checkout's data/ or leaves fixtures behind.

Run from the main checkout, the old tests touched the live catalog.
"""
import unittest
from pathlib import Path
import app
import research


class SuiteIsolationTests(unittest.TestCase):
    def setup_only(self,case):
        case.setUp()
        try:return Path(app.DATA).resolve(),Path(research.CACHE).resolve()
        finally:case.doCleanups()

    def assert_isolated(self,data):
        import test_worker
        checkout=Path(app.BASE).resolve()
        self.assertNotEqual(data,checkout/'data')
        self.assertTrue(data.is_relative_to(test_worker.scratch_parent().resolve()),data)

    def test_scratch_folders_leave_no_empty_work_folder_behind(self):
        # Before v0.1.3 every run left <checkout>/work/test-runs behind.
        import os,shutil,tempfile,test_worker
        from unittest.mock import patch
        outside=Path(tempfile.mkdtemp(prefix='cmo-scratch-check-'))
        self.addCleanup(shutil.rmtree,outside,ignore_errors=True)
        default=outside/'checkout'/'work'/'test-runs'
        with patch.dict(os.environ,{'COMICS_META_TEST_SCRATCH':''}),patch.object(test_worker,'scratch_parent',return_value=default):
            with test_worker.scratch_directory() as first:
                with test_worker.scratch_directory():pass
                self.assertTrue(Path(first).is_dir())  # A folder still in use is never pruned.
        self.assertFalse((outside/'checkout'/'work').exists())
        self.assertTrue((outside/'checkout').is_dir())  # Only the empty work/test-runs pair is removed.
        named=outside/'named';named.mkdir()
        with patch.dict(os.environ,{'COMICS_META_TEST_SCRATCH':str(named)}):
            with test_worker.scratch_directory():pass
        self.assertTrue(named.is_dir())  # An explicitly named scratch folder is left alone.

    def test_conversion_pipeline_and_evidence_tests_use_an_isolated_catalog(self):
        import test_conversion,test_pipeline,test_lead_verification,test_unnumbered_any_publisher
        for case in (test_conversion.ConversionTests('test_existing_cbz_is_never_overwritten'),
                     test_lead_verification.LeadVerificationTests('test_fractional_issue_is_not_issue_five'),
                     test_unnumbered_any_publisher.UnnumberedAnyPublisherTests('test_filename_has_no_issue_number'),
                     test_pipeline.PipelineTests('test_public_url_validation')):
            data,cache=self.setup_only(case)
            self.assert_isolated(data)
        self.assert_isolated(cache)
        self.assertEqual(Path(app.DATA).resolve(),Path(app.STATE_ROOT).resolve()/'data')  # Patches restore the suite's isolated state root.

    def test_coverage_priority_fixtures_are_removed(self):
        import test_coverage_priority
        case=test_coverage_priority.CoveragePriorityTests('test_history_including_extended_paths_overrides_transient_catalog_status')
        case.setUp()
        fixture=case.fixture
        self.assertTrue(fixture.exists())
        case.doCleanups()
        self.assertFalse(fixture.exists())  # Before: left in <checkout>/scratch/ on every run.
        self.assertFalse(fixture.resolve().is_relative_to(Path(app.BASE).resolve()/'scratch'))


if __name__=='__main__':
    unittest.main()
