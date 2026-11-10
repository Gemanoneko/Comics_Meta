"""Focused source checks: full discovery/isolation, no child processes or live state.

Run from the tool root: python -B tests/run_naming_checks.py --scratch <absolute
owned folder strictly inside this checkout's scratch/>. This is not a build gate.
"""
import argparse
import atexit
import os
from pathlib import Path
import sys
import threading
import time
import unittest


CODE = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--scratch', required=True)
args = parser.parse_args()
scratch = Path(args.scratch)
if not scratch.is_absolute() or not scratch.resolve().is_relative_to(CODE / 'scratch') or scratch.resolve() == CODE / 'scratch':
    parser.error('scratch must be an absolute owned subfolder of this checkout scratch/')
created = not scratch.exists()
if created:
    def remove_empty_owned_root():
        try:
            scratch.rmdir()
        except FileNotFoundError:
            pass
    atexit.register(remove_empty_owned_root)
os.environ['COMICS_META_TEST_SCRATCH'] = str(scratch)
os.chdir(CODE)
sys.path.insert(0, str(CODE))
started = time.monotonic()


def expired():
    print('Source naming checks exceeded 600000ms deadline.', flush=True)
    os._exit(124)


def guard(event, args):
    if event in ('subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn', 'os.spawn'):
        raise PermissionError('Source naming checks may not launch descendants')


timer = threading.Timer(600, expired)
timer.daemon = True
timer.start()
sys.addaudithook(guard)
# Discovery loads test_0_state_isolation before application modules. Filtering
# happens afterwards; the live-state sentinel remains the final selected test.
discovered = unittest.defaultTestLoader.discover('tests')
allowed = {'test_0_state_isolation', 'test_zz_state_isolation', 'test_filename_matching',
           'test_gcd_offline', 'test_metron_year_rules', 'test_v014_review_fixes',
           'test_source_scheduling', 'test_research_runtime', 'test_research', 'test_in_book'}


def cases(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from cases(test)
        else:
            yield test


selected = unittest.TestSuite(t for t in cases(discovered) if t.__class__.__module__ in allowed)
result = unittest.TextTestRunner(verbosity=2).run(selected)
timer.cancel()
print('Source naming checks:', result.testsRun, 'tests;', round(time.monotonic() - started, 3),
      'seconds; descendants forbidden; formal entry/build/native QA not run.', flush=True)
raise SystemExit(not result.wasSuccessful())
