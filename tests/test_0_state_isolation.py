"""Suite-wide isolation from the live service.

Discovery imports this module first ('0' sorts before every other test
module), so it runs before anything imports app:

* the state root (config.json, .env, data/, batches/, work/) and the library
  lock folder point into one throwaway folder for the whole run;
* an audit hook refuses any access to the live state beside the code and to the
  real per-user ComicsMeta folder, so a test that escapes isolation fails
  instead of touching the running service. test_zz_state_isolation checks at
  the end that no refusal was swallowed.

COMICS_META_TEST_SCRATCH moves the throwaway folders out of the checkout.
"""
import atexit
import os
import shutil
import sqlite3
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

if 'app' in sys.modules:
    raise RuntimeError('State isolation must load before app. Run: python -m unittest discover -s tests')

CODE = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get('COMICS_META_TEST_SCRATCH') or CODE / 'work' / 'test-runs') / str(uuid.uuid4())
STATE = ROOT / 'state'
LOCKS = ROOT / 'locks'
STATE.mkdir(parents=True)
LOCKS.mkdir()
atexit.register(shutil.rmtree, ROOT, True)  # Registered first, so it runs after every other exit hook.
os.environ['COMICS_META_STATE_ROOT'] = str(STATE)
os.environ['COMICS_META_LOCK_DIR'] = str(LOCKS)
os.environ.pop('COMICS_META_STOP_BASELINE', None)


def _normal(path):
    text = os.fsdecode(os.fspath(path))
    if text.startswith('\\\\?\\UNC\\'):
        text = '\\\\' + text[8:]
    elif text.startswith('\\\\?\\'):
        text = text[4:]
    return os.path.normcase(os.path.abspath(text))


_local = os.environ.get('LOCALAPPDATA')
PROTECTED = [CODE / 'data', CODE / 'batches', CODE / 'config.json', CODE / '.env']
if _local:
    PROTECTED.append(Path(_local) / 'ComicsMeta')  # Real lock folder and packaged state root.
_PROTECTED = [_normal(path) for path in PROTECTED]
VIOLATIONS = []
_expected = []
_EVENTS = {'open', 'sqlite3.connect', 'os.remove', 'os.rename', 'os.mkdir', 'os.rmdir', 'shutil.rmtree',
           'os.scandir', 'os.listdir', 'shutil.copyfile', 'shutil.move', 'os.utime', 'os.chmod'}


def _guard(event, args):
    if event not in _EVENTS:
        return
    for value in args[:2]:
        if isinstance(value, int) or value is None:
            continue
        try:
            target = _normal(value)
        except (TypeError, ValueError):
            continue
        for protected in _PROTECTED:
            if target == protected or target.startswith(protected.rstrip(os.sep) + os.sep):
                if not _expected:
                    VIOLATIONS.append((event, target))
                raise PermissionError('Test isolation refused ' + event + ' on live state: ' + target)


sys.addaudithook(_guard)


@contextmanager
def expected_refusal():
    _expected.append(True)
    try:
        yield
    finally:
        _expected.pop()


class StateIsolationTests(unittest.TestCase):
    def test_state_and_locks_point_at_the_throwaway_folder(self):
        import app, library_lock, server_host, worker
        self.assertEqual(app.STATE_ROOT, STATE)
        self.assertNotEqual(app.STATE_ROOT, app.BASE)
        self.assertEqual(app.DATA, STATE / 'data')
        self.assertEqual(worker.QUEUE, STATE / 'data' / 'queue')
        self.assertEqual(server_host.STATE_ROOT, STATE)
        self.assertEqual(library_lock.lock_dir(), LOCKS)

    def test_live_state_access_is_refused_before_it_happens(self):
        # The audit event fires before the OS call, so these never reach the files.
        for target in (CODE / 'data' / 'catalog.sqlite', CODE / 'config.json', CODE / 'batches' / 'x' / 'plan.json'):
            with self.subTest(target=target), expected_refusal(), self.assertRaises(PermissionError):
                open(target, 'rb')
        with expected_refusal(), self.assertRaises(PermissionError):
            sqlite3.connect(CODE / 'data' / 'catalog.sqlite')
        with expected_refusal(), self.assertRaises(PermissionError):
            os.listdir(CODE / 'data')
        # Neighbours with similar names are not refused.
        self.assertEqual(_normal(CODE / 'config.example.json') in _PROTECTED, False)
        (STATE / 'probe.txt').write_text('ok')
        self.assertEqual((STATE / 'probe.txt').read_text(), 'ok')
