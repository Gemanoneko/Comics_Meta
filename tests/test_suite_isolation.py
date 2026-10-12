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
        checkout=Path(app.BASE).resolve()
        self.assertNotEqual(data,checkout/'data')
        self.assertTrue(data.is_relative_to(checkout/'work'/'test-runs'),data)

    def test_conversion_pipeline_and_evidence_tests_use_an_isolated_catalog(self):
        import test_conversion,test_pipeline,test_lead_verification,test_unnumbered_any_publisher
        for case in (test_conversion.ConversionTests('test_existing_cbz_is_never_overwritten'),
                     test_lead_verification.LeadVerificationTests('test_fractional_issue_is_not_issue_five'),
                     test_unnumbered_any_publisher.UnnumberedAnyPublisherTests('test_filename_has_no_issue_number'),
                     test_pipeline.PipelineTests('test_public_url_validation')):
            data,cache=self.setup_only(case)
            self.assert_isolated(data)
        self.assert_isolated(cache)
        self.assertEqual(Path(app.DATA).resolve(),Path(app.BASE).resolve()/'data')  # Patches are undone.

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
