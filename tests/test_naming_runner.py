"""The focused filter must not turn broken or absent test modules into success."""
import io
from pathlib import Path
import sys
import unittest

import run_naming_checks
from test_worker import scratch_directory


class NamingRunnerTests(unittest.TestCase):
    def run_fixture(self, broken=False, missing=False):
        with scratch_directory() as directory:
            root = Path(directory)
            good = 'test_naming_good_fixture'
            bad = 'test_naming_broken_fixture'
            (root / (good + '.py')).write_text('import unittest\nclass Good(unittest.TestCase):\n def test_good(self): pass\n', encoding='utf-8')
            if broken:
                (root / (bad + '.py')).write_text("raise RuntimeError('deliberate requested-module import failure')\n", encoding='utf-8')
            try:
                discovered = unittest.TestLoader().discover(str(root), top_level_dir=str(root))
                requested = {good, bad} if broken or missing else {good}
                output = io.StringIO()
                result = unittest.TextTestRunner(stream=output).run(run_naming_checks.focused_suite(discovered, requested))
                return result, output.getvalue()
            finally:
                sys.path[:] = [entry for entry in sys.path if entry != str(root)]
                sys.modules.pop(good, None)
                sys.modules.pop(bad, None)

    def test_good_discovery_control_passes(self):
        result, _ = self.run_fixture()
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)

    def test_requested_import_failure_is_retained_alongside_good_control(self):
        result, output = self.run_fixture(broken=True)
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(result.testsRun, 2)
        self.assertEqual(len(result.errors), 1)
        self.assertIn('deliberate requested-module import failure', output)

    def test_absent_requested_module_fails_closed(self):
        result, output = self.run_fixture(missing=True)
        self.assertFalse(result.wasSuccessful())
        self.assertIn('Requested test modules absent or empty', output)
