"""The broker (engine_host.py) reports its own closure result by exit code, and Quit always closes the app.

T1 (code review v0.6.6): when its Job still counted a member after termination, the broker raised RuntimeError and
exited with code 1, the code Task Manager and taskkill give a process they end, so the shell overruled the broker's
own evidence. M3: a claim-retirement failure after the Job was proven empty raised too (code 1).
Quit always closes (Sergei 2026-11-18): the broker re-terminates its Job every RETERMINATE_EVERY seconds for up to the
closure wait the shell passes (--closure-wait). A part still running after that is named in
locks/leftover-<owner>.json and the broker exits with CLOSURE_LEFTOVER (124); the shell exits anyway.

Each test runs a copy of the real engine_host.py with a stand-in app.py (the engine) and a stand-in library_lock, as the
shell runs it: the owner pipe on stdin, this process as the parent. Only the Job count can be replaced, because a Job
member that survives termination cannot be made on purpose (Futaba could not produce one either; a debugger holding
the exit leaves the process unsignalled but the Job count drops at once, measured 2026-11-18)."""
import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path
from test_worker import scratch_directory

CODE = Path(__file__).resolve().parents[1]
TOKEN, OWNER = 'c' * 64, 'd' * 64
ENGINE = r'''
import os, time
print("engine up", flush=True)
if os.environ["STUB_ENGINE"] == "exit":
    raise SystemExit(0)
time.sleep(60)
'''
LIBRARY_LOCK = r'''
import os
from pathlib import Path
def retire_engine_claims(owner):
    with open(Path(__file__).with_name("retired.txt"), "a") as record:
        record.write(owner + "\n")
    if os.environ["STUB_RETIRE"] == "fail":
        raise OSError("claims folder unavailable")
'''
DRIVER = r'''
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
import engine_host
engine_host.RETERMINATE_EVERY = float(os.environ["STUB_EVERY"])
count, terminate = engine_host.active_engine, engine_host.terminate_job
terminations = []
def counted_terminate(job, code):
    terminations.append(code)
    if os.environ["STUB_TERMINATE"] == "fail-first" and len(terminations) == 1:
        return 0  # A refused termination: nothing was ended.
    return terminate(job, code)
engine_host.terminate_job = counted_terminate
mode = os.environ["STUB_COUNT"]
if mode == "survivor":  # A member the Job still counts after every termination.
    engine_host.active_engine = lambda job: 1
elif mode == "late":  # A member that outlives the first termination but not the second.
    engine_host.active_engine = lambda job: 1 if len(terminations) < 2 else count(job)
elif mode == "unreadable":
    def unreadable(job):
        raise OSError(5, "Engine descendants")
    engine_host.active_engine = unreadable
if os.environ.get("STUB_MEMBERS"):
    engine_host.job_members = lambda job: json.loads(os.environ["STUB_MEMBERS"])
sys.argv = ["engine_host.py", "--parent-pid", sys.argv[1], "--port", "1", "--closure-wait", os.environ["STUB_WAIT"]]
try:
    code = engine_host.main()
finally:
    print("terminations %d" % len(terminations), file=sys.stderr, flush=True)
raise SystemExit(code)
'''


class BrokerRun:
    """One broker copy in a scratch folder, started the way the shell starts it."""

    def __init__(self, case, folder):
        self.case, self.folder = case, folder
        self.locks = folder / 'locks'
        shutil.copyfile(CODE / 'engine_host.py', folder / 'engine_host.py')
        shutil.copyfile(CODE / 'file_lock.py', folder / 'file_lock.py')
        for name, text in (('app.py', ENGINE), ('library_lock.py', LIBRARY_LOCK), ('drive.py', DRIVER)):
            (folder / name).write_text(text, encoding='utf-8')

    def start(self, *, engine='wait', count='real', retire='ok', wait='0.6', every='0.1', terminate='ok', members=None,
              owner=OWNER):
        env = dict(os.environ, COMICS_META_STATE_ROOT=str(self.folder / 'state'), COMICS_META_SHELL_TOKEN=TOKEN,
                   COMICS_META_CLAIM_OWNER=owner, COMICS_META_LOCK_DIR=str(self.locks), STUB_ENGINE=engine,
                   STUB_COUNT=count, STUB_RETIRE=retire, STUB_WAIT=wait, STUB_EVERY=every, STUB_TERMINATE=terminate,
                   STUB_MEMBERS='' if members is None else json.dumps(members), PYTHONDONTWRITEBYTECODE='1')
        process = subprocess.Popen([sys.executable, '-I', '-B', str(self.folder / 'drive.py'), str(os.getpid())],
                                   cwd=self.folder, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        self.case.addCleanup(lambda: (process.kill(), process.wait(30), process.stdin.close(), process.stdout.close(),
                                      process.stderr.close()))
        process.stdin.write((TOKEN + '\n').encode('ascii'))
        process.stdin.flush()
        return process

    def run(self, *, force=True, **options):
        """(exit code, stderr, owners retired, seconds from the stop to the exit) of one broker run."""
        process = self.start(**options)
        self.case.assertEqual(process.stdout.readline().strip(), b'engine up')
        began = time.monotonic()
        if force:
            process.stdin.write(b'force\n')  # What the shell's forceStop sends.
            process.stdin.flush()
        # The owner pipe stays open until the broker exits: closing it would itself force a stop.
        code = process.wait(60)
        elapsed = time.monotonic() - began
        retired = self.folder / 'retired.txt'
        owners = retired.read_text(encoding='utf-8').split() if retired.exists() else []
        retired.unlink(missing_ok=True)
        return code, process.stderr.read().decode('utf-8', 'replace'), owners, elapsed

    def leftover(self, owner=OWNER):
        path = self.locks / ('leftover-' + owner + '.json')
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


class BrokerClosureTests(unittest.TestCase):
    def broker(self):
        return BrokerRun(self, Path(self.enterContext(scratch_directory())))

    def test_a_forced_stop_with_an_empty_job_returns_125_and_retires_the_claims(self):
        run = self.broker()
        code, err, retired, _ = run.run()  # Positive control: the real Job count.
        self.assertEqual(code, 125, err)
        self.assertEqual(retired, [OWNER])
        self.assertIsNone(run.leftover())

    def test_an_engine_exit_returns_its_own_code(self):
        code, err, retired, _ = self.broker().run(engine='exit', force=False)
        self.assertEqual(code, 0, err)
        self.assertEqual(retired, [OWNER])

    def test_a_member_that_survives_is_terminated_again_every_period_for_the_whole_wait_then_recorded(self):
        for force in (True, False):
            with self.subTest(force=force):
                run = self.broker()
                before = time.time()
                code, err, retired, elapsed = run.run(engine='wait' if force else 'exit', count='survivor',
                                                      force=force, wait='0.6', every='0.1')
                self.assertEqual(code, 124, err)
                self.assertGreaterEqual(elapsed, 0.6)  # The whole closure wait the shell passed ...
                terminations = int(err.split('terminations ')[1].split()[0])
                self.assertGreaterEqual(terminations, 5, err)  # ... re-terminating every 0.1 s (until 0.6.7: twice).
                self.assertIn('Owned engine descendants remain after termination; terminating again.', err)
                self.assertIn('Engine parts still running after the 0.6 s closure wait', err)
                self.assertEqual(retired, [])  # Claims of a Job not proven empty stay for the next claimant.
                record = run.leftover()
                self.assertIsNotNone(record, err)
                self.assertEqual((record['schema'], record['owner']), (1, OWNER))
                self.assertGreaterEqual(record['written'], before)
                self.assertLessEqual(record['written'], time.time())
                self.assertEqual(record['members'], [])  # The real Job is empty; only its count was replaced.

    def test_the_closure_wait_comes_from_the_shell(self):
        code, err, _, elapsed = self.broker().run(count='survivor', wait='1.5', every='0.5')
        self.assertEqual(code, 124, err)
        self.assertGreaterEqual(elapsed, 1.5)
        self.assertIn('after the 1.5 s closure wait', err)

    def test_a_job_count_that_cannot_be_read_is_recorded_as_a_leftover(self):
        run = self.broker()
        code, err, retired, _ = run.run(count='unreadable')
        self.assertEqual(code, 124, err)
        self.assertEqual(retired, [])
        self.assertIsNotNone(run.leftover())

    def test_a_member_gone_after_the_second_termination_is_a_confirmed_forced_stop(self):
        run = self.broker()
        code, err, retired, _ = run.run(count='late')
        self.assertEqual(code, 125, err)
        self.assertIn('terminating again', err)
        self.assertEqual(retired, [OWNER])
        self.assertIsNone(run.leftover())

    def test_a_refused_termination_is_logged_and_the_count_still_decides(self):
        run = self.broker()
        code, err, retired, _ = run.run(terminate='fail-first')
        self.assertIn('Engine Job termination failed (Windows error', err)  # Unchecked until 0.6.7.
        self.assertEqual(code, 125, err)  # Terminated again 0.1 s later; then the Job is empty.
        self.assertEqual(retired, [OWNER])

    def test_a_proven_empty_job_removes_the_shells_provisional_record(self):
        run = self.broker()
        run.locks.mkdir()
        provisional = run.locks / ('leftover-' + OWNER + '.json')
        provisional.write_text(json.dumps({'schema': 1, 'owner': OWNER, 'written': time.time(), 'members': None,
                                           'source': 'shell'}), encoding='utf-8')
        other = run.locks / ('leftover-' + 'e' * 64 + '.json')
        other.write_text('{}', encoding='utf-8')
        code, err, _, _ = run.run()
        self.assertEqual(code, 125, err)
        self.assertFalse(provisional.exists())
        self.assertTrue(other.exists())  # Another engine's record is not this broker's to remove.

    def test_a_claim_retirement_failure_keeps_the_closure_code(self):  # M3
        for force, expected in ((True, 125), (False, 0)):
            with self.subTest(force=force):
                code, err, retired, _ = self.broker().run(engine='wait' if force else 'exit', retire='fail',
                                                          force=force)
                self.assertEqual(code, expected, err)
                self.assertEqual(retired, [OWNER])
                self.assertIn('Engine claims were not retired: OSError claims folder unavailable', err)


if __name__ == '__main__':
    unittest.main()
