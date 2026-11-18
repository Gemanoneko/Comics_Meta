"""The broker (engine_host.py) reports its own closure result by exit code (code review v0.6.6 T1 and M3).

T1: when its Job still counted a member after termination, the broker raised RuntimeError and exited with code 1, the
code Task Manager and taskkill give a process they end. From 0.6.6 the shell confirms closure itself after code 1, so it
overruled the broker's own evidence. The broker now returns CLOSURE_UNCONFIRMED (124), which the shell never confirms.
M3: a claim-retirement failure after the Job was proven empty raised too (code 1), hiding the closure code.

Each test runs a copy of the real engine_host.py with a stand-in app.py (the engine) and a stand-in library_lock, as the
shell runs it: the owner pipe on stdin, this process as the parent. Only the Job count can be replaced, because a Job
member that survives termination cannot be made on purpose (Futaba could not produce one either)."""
import os
import shutil
import subprocess
import sys
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
import os, sys
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
import engine_host
engine_host.CLOSURE_WAIT = 0.3
count, terminate = engine_host.active_engine, engine_host.terminate_job
terminations = []
def counted_terminate(job, code):
    terminations.append(code)
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
sys.argv = ["engine_host.py", "--parent-pid", sys.argv[1], "--port", "1"]
raise SystemExit(engine_host.main())
'''


class BrokerClosureTests(unittest.TestCase):
    def broker(self, *, engine='wait', count='real', retire='ok', force=True):
        """(exit code, stderr, owners retired) of one broker run that is forced to stop or whose engine exits."""
        folder = Path(self.enterContext(scratch_directory()))
        shutil.copyfile(CODE / 'engine_host.py', folder / 'engine_host.py')
        for name, text in (('app.py', ENGINE), ('library_lock.py', LIBRARY_LOCK), ('drive.py', DRIVER)):
            (folder / name).write_text(text, encoding='utf-8')
        env = dict(os.environ, COMICS_META_STATE_ROOT=str(folder / 'state'), COMICS_META_SHELL_TOKEN=TOKEN,
                   COMICS_META_CLAIM_OWNER=OWNER, STUB_ENGINE=engine, STUB_COUNT=count, STUB_RETIRE=retire,
                   PYTHONDONTWRITEBYTECODE='1')
        process = subprocess.Popen([sys.executable, '-I', '-B', str(folder / 'drive.py'), str(os.getpid())],
                                   cwd=folder, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        self.addCleanup(lambda: (process.kill(), process.wait(30), process.stdin.close(), process.stdout.close(),
                                 process.stderr.close()))
        process.stdin.write((TOKEN + '\n').encode('ascii'))
        process.stdin.flush()
        self.assertEqual(process.stdout.readline().strip(), b'engine up')
        if force:
            process.stdin.write(b'force\n')  # What the shell's forceStop sends.
            process.stdin.flush()
        # The owner pipe stays open until the broker exits: closing it would itself force a stop.
        code = process.wait(60)
        retired = folder / 'retired.txt'
        owners = retired.read_text(encoding='utf-8').split() if retired.exists() else []
        return code, process.stderr.read().decode('utf-8', 'replace'), owners

    def test_a_forced_stop_with_an_empty_job_returns_125_and_retires_the_claims(self):
        code, err, retired = self.broker()  # Positive control: the real Job count.
        self.assertEqual(code, 125, err)
        self.assertEqual(retired, [OWNER])
        self.assertNotIn('unconfirmed', err)

    def test_an_engine_exit_returns_its_own_code(self):
        code, err, retired = self.broker(engine='exit', force=False)
        self.assertEqual(code, 0, err)
        self.assertEqual(retired, [OWNER])

    def test_a_member_that_survives_termination_is_reported_as_124_not_1(self):
        for force in (True, False):
            with self.subTest(force=force):
                code, err, retired = self.broker(engine='wait' if force else 'exit', count='survivor', force=force)
                self.assertEqual(code, 124, err)
                self.assertIn('Engine descendant closure unconfirmed', err)
                self.assertEqual(retired, [])  # Claims of a Job not proven empty stay for the next claimant.

    def test_a_job_count_that_cannot_be_read_is_reported_as_124(self):
        code, err, retired = self.broker(count='unreadable')
        self.assertEqual(code, 124, err)
        self.assertEqual(retired, [])

    def test_a_member_gone_after_the_second_termination_is_a_confirmed_forced_stop(self):
        code, err, retired = self.broker(count='late')
        self.assertEqual(code, 125, err)
        self.assertIn('terminating again', err)
        self.assertEqual(retired, [OWNER])

    def test_a_claim_retirement_failure_keeps_the_closure_code(self):  # M3
        for force, expected in ((True, 125), (False, 0)):
            with self.subTest(force=force):
                code, err, retired = self.broker(engine='wait' if force else 'exit', retire='fail', force=force)
                self.assertEqual(code, expected, err)
                self.assertEqual(retired, [OWNER])
                self.assertIn('Engine claims were not retired: OSError claims folder unavailable', err)


if __name__ == '__main__':
    unittest.main()
