"""Runs last in discovery: no test reached the live state, even where code swallowed the refusal."""
import unittest
import test_0_state_isolation as isolation


class LiveStateUntouchedTests(unittest.TestCase):
    def test_no_test_reached_live_state(self):
        self.assertEqual(isolation.VIOLATIONS, [])
