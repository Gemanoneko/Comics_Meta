"""Sergei 2026-10-13 (Futaba Q-5): a solved Google check resumes Lens searching after a short
pause, not the rest of the one-hour hold. Unsolved checks keep the hour, the daily cap stays,
and checks that come back soon after a solve back off: 5, 10, 20, 40 minutes, then the hour.

Offline: the real lens_verification.service and browser_worker.lens_attempt with a mocked browser.
"""
import json
import os
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import app
import browser_search as search
import browser_worker
import lens_verification as lens
import pause_control
from test_worker import scratch_directory

HOUR = 3600


class SolvedHoldTests(unittest.TestCase):
    def test_steps_reset_and_never_longer_than_the_running_hold(self):
        now, state, waits = 1_000_000.0, {}, []
        for _ in range(6):
            state = dict(state, browser_retry_at=now + HOUR)  # Google asks: the unsolved hour.
            result = lens.solved_hold(state, now)  # Sergei solves it at once.
            waits.append(result['browser_retry_at'] - now)
            state = result
            now += result['solved_checks']['wait'] + 30  # Google asks again 30 s after the pause.
        self.assertEqual(waits, [300, 600, 1200, 2400, HOUR, HOUR])
        quiet = lens.solved_hold(dict(state, browser_retry_at=now + 3 * HOUR + HOUR), now + 3 * HOUR)
        self.assertEqual(quiet['solved_checks']['count'], 1)  # Two quiet hours start over.
        self.assertEqual(lens.solved_hold({'browser_retry_at': now + 120}, now)['browser_retry_at'], now + 120)  # Never longer.
        self.assertEqual(lens.solved_hold({'browser_retry_at': now - 5}, now)['browser_retry_at'], now - 5)  # An ended hold stays ended.


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.enterContext(patch.object(lens, '_owner', None))
        pause_control.requested()
        lens.initialize()
        (app.DATA / 'browser-heartbeat').write_text(json.dumps({'pid': os.getpid(), 'timestamp': time.time()}))
        self.browser = Mock()
        self.browser.minimize.return_value = True
        self.browser.human_session.side_effect = lambda url, admitted, observation: (admitted(), observation('load'), True)[-1]

    def challenge(self):
        """What lens_attempt saves when Google asks: the check and the one-hour hold."""
        row = {'path': str(self.root / 'Spawn 001.cbz'), 'size': 1, 'mtime': 1}
        browser = Mock()
        browser.search.side_effect = search.HumanVerification('https://www.google.com/sorry/fixture')
        outcome, _ = browser_worker.lens_attempt(row, browser, {}, {'daily_request_limit': 100})
        self.assertIsInstance(outcome, browser_worker.Held)
        self.assertAlmostEqual(search.legacy_status()['browser_retry_at'], time.time() + HOUR, delta=5)  # Unsolved: the hour.

    def solve(self):
        lens.request()
        lens.service(self.browser, {})
        return search.legacy_status()['browser_retry_at'] - time.time()

    def test_solving_shortens_the_hold_and_repeats_back_off(self):
        waits = []
        for _ in range(3):
            search.legacy_status(browser_retry_at=0)  # The short pause has ended.
            self.challenge()
            waits.append(round(self.solve() / 60))
        self.assertEqual(waits, [5, 10, 20])  # Before: 60, 60, 60.
        self.assertFalse(search.legacy_status()['human_verification'])

    def test_an_unsolved_check_keeps_the_hour(self):
        self.challenge()
        lens.request()
        self.browser.human_session.side_effect = None
        self.browser.human_session.return_value = False  # Window closed without solving.
        lens.service(self.browser, {})
        self.assertAlmostEqual(search.legacy_status()['browser_retry_at'], time.time() + HOUR, delta=5)
        self.assertTrue(search.legacy_status()['human_verification'])

    def test_the_daily_cap_survives_a_solve(self):
        self.challenge()  # That search used the day's one allowed search.
        self.solve()
        with patch.object(time, 'time', return_value=time.time() + 400):  # After the short pause.
            outcome, _ = browser_worker.lens_attempt({'path': 'x', 'size': 1, 'mtime': 1}, Mock(), {}, {'daily_request_limit': 1})
        self.assertEqual(outcome.reason, 'Daily Google Lens search limit reached.')

    def test_the_worker_wakes_for_the_shortened_hold(self):
        self.challenge()
        sleeping_until = time.monotonic() + HOUR  # The worker was sleeping out the held search.
        before = browser_worker.solved_at()
        self.assertEqual(browser_worker.after_solve(sleeping_until, before), sleeping_until)  # Nothing solved: unchanged.
        self.solve()
        woke = browser_worker.after_solve(sleeping_until, before)
        self.assertAlmostEqual(woke - time.monotonic(), 300, delta=5)


if __name__ == '__main__':
    unittest.main()
