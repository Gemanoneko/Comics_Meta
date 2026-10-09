import unittest
from provider_wait import ProviderDeferred,record_failure,retry_time,repair_old_getcomics_error


class ProviderWaitTests(unittest.TestCase):
    def test_global_outage_does_not_accelerate_comic_retries(self):
        waits={}
        errors=record_failure(None,waits,'GetComics',ProviderDeferred('Human verification','getcomics'))
        self.assertIsNone(errors)
        self.assertEqual(waits['getcomics']['retry_at'],0)
        self.assertEqual(retry_time(86400,errors,0),86400)

    def test_real_error_keeps_short_retry_even_with_other_provider_waits(self):
        waits={}
        errors=record_failure(None,waits,'Source',ValueError('Invalid response'))
        errors=record_failure(errors,waits,'GCD',ProviderDeferred('Daily budget','gcd',8000))
        self.assertIn('Invalid response',errors)
        self.assertEqual(retry_time(86400,errors,0),3600)

    def test_existing_outage_only_record_restores_normal_retry(self):
        record={'outcome':'needs_identity_lookup','retry_at':4600,'error':'; GetComics needs human verification or rejected access; automatic requests stopped.'}
        self.assertTrue(repair_old_getcomics_error(record))
        self.assertEqual(record['retry_at'],87400)
        self.assertIsNone(record['error'])
        self.assertFalse(repair_old_getcomics_error(record))

    def test_repair_does_not_hide_other_errors_or_change_their_retry(self):
        record={'retry_at':4600,'error':'Archive problem; GetComics needs human verification or rejected access; automatic requests stopped.'}
        repair_old_getcomics_error(record)
        self.assertEqual(record['error'],'Archive problem')
        self.assertEqual(record['retry_at'],4600)
