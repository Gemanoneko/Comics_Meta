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
TOKEN, OWNER, OTHER = 'c' * 64, 'd' * 64, 'e' * 64
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

    def run(self, *, force=True, while_running=None, **options):
        """(exit code, stderr, owners retired, seconds from the stop to the exit) of one broker run."""
        process = self.start(**options)
        self.case.assertEqual(process.stdout.readline().strip(), b'engine up')
        if while_running:
            while_running()
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

    def refused(self, *, stop_after=None, engine='exit', **options):
        """(exit code, stderr, stdout, seconds) of a broker start that ends before its engine starts. (Its engine, if it
        does start, exits at once with 0.)"""
        process = self.start(engine=engine, **options)
        began = time.monotonic()
        if stop_after is not None:
            time.sleep(stop_after)
            process.stdin.write(b'force\n')  # Quit or a second start from the shell during the check.
            process.stdin.flush()
        code = process.wait(60)
        return code, process.stderr.read().decode('utf-8', 'replace'), process.stdout.read(), time.monotonic() - began

    def record(self, members, owner=OTHER, written=None, raw=None):
        self.locks.mkdir(exist_ok=True)
        path = self.locks / ('leftover-' + owner + '.json')
        path.write_text(raw if raw is not None else json.dumps(
            {'schema': 1, 'owner': owner, 'written': time.time() if written is None else written, 'members': members}),
            encoding='utf-8')
        return path


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
        other = run.locks / ('leftover-' + OTHER + '.json')
        code, err, _, _ = run.run(while_running=lambda: other.write_text(  # After this broker's own start check.
            json.dumps({'schema': 1, 'owner': OTHER, 'written': time.time(), 'members': None}), encoding='utf-8'))
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


def dummy(case):
    """A live process standing in for an earlier engine's part: (pid, creation time)."""
    import engine_host
    process = subprocess.Popen([sys.executable, '-I', '-B', '-c', 'import time; time.sleep(120)'],
                               creationflags=0x08000000)
    case.addCleanup(lambda: (process.kill(), process.wait(30)))
    handle = engine_host.open_member(process.pid, engine_host.QUERY_LIMITED)
    try:
        created = engine_host.created(handle)
    finally:
        engine_host.close(handle)
    return process, created


def stuck(case, process):
    """Hold `process`'s exit: terminated again, it still runs, as a part finishing a disk operation does."""
    from debug_hold import Hold
    hold = Hold(process.pid)
    case.addCleanup(hold.release)
    return hold


def hold_claim(case, locks, owner):
    """A process holding one of `owner`'s library claims the way library_lock does (file_lock's byte 0)."""
    claims = locks / 'claims'
    claims.mkdir(parents=True, exist_ok=True)
    lock = claims / ('engine-' + owner + '-4242-0123456789ab.lock')
    code = ('import sys;sys.path.insert(0,sys.argv[1]);import file_lock;fd=file_lock.open_lock(sys.argv[2]);'
            'assert file_lock.try_lock(fd);print("locked",flush=True);sys.stdin.read()')
    holder = subprocess.Popen([sys.executable, '-I', '-B', '-c', code, str(CODE), str(lock)], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, creationflags=0x08000000)
    case.addCleanup(lambda: (holder.kill(), holder.wait(30), holder.stdin.close(), holder.stdout.close()))
    case.assertEqual(holder.stdout.readline().strip(), b'locked')
    return holder


class PreviousSessionTests(unittest.TestCase):
    """At start the broker checks every leftover record before it starts anything (Sergei 2026-11-18): a part still
    running after it is terminated again refuses the start with PREVIOUS_CLOSING (123); otherwise the record goes."""

    def broker(self):
        return BrokerRun(self, Path(self.enterContext(scratch_directory())))

    def test_a_part_still_running_after_it_is_terminated_again_refuses_the_start_with_123(self):
        run = self.broker()
        part, created = dummy(self)
        hold = stuck(self, part)
        path = run.record([[part.pid, created]], written=time.time() - 75)
        code, err, out, _ = run.refused(every='0.3')
        self.assertEqual(code, 123, err)
        self.assertEqual(out, b'')  # The engine never started.
        self.assertIn('pid %d alive, terminated again' % part.pid, err)  # Its members, alive or not ...
        self.assertRegex(err, r'\(age 7[5-9] s\)')  # ... and the record's age are logged (R4 item 7).
        self.assertIn('still running 0.3 s later (pid %d); this start waits for it.' % part.pid, err)
        self.assertTrue(path.exists())
        self.assertTrue(hold.exit_held.is_set())  # The broker did terminate it; only its exit is still pending.
        hold.release()  # The part finishes its operation and ends.
        part.wait(10)
        code, err, _, _ = run.run(every='0.3')  # The next start: a normal start, and the record is gone.
        self.assertEqual(code, 125, err)
        self.assertIn('pid %d ended' % part.pid, err)
        self.assertIn('nothing of that session is left; record removed.', err)
        self.assertFalse(path.exists())

    def test_a_pid_that_now_names_another_process_is_left_alone_and_the_record_goes(self):
        run = self.broker()
        part, created = dummy(self)
        path = run.record([[part.pid, created + 1]])  # Same PID, another creation time: PID reuse.
        code, err, _, _ = run.run()
        self.assertEqual(code, 125, err)
        self.assertIn('pid %d ended (its PID now names another process)' % part.pid, err)
        self.assertIsNone(part.poll())  # Not terminated.
        self.assertFalse(path.exists())

    def test_a_record_whose_parts_have_ended_goes_as_after_a_reboot(self):
        run = self.broker()
        ended = subprocess.Popen([sys.executable, '-I', '-B', '-c', ''], creationflags=0x08000000)
        ended.wait(30)
        path = run.record([[ended.pid, 1], [999999996, 2]])
        code, err, _, _ = run.run()
        self.assertEqual(code, 125, err)
        self.assertFalse(path.exists())

    def test_a_record_without_a_process_list_or_unreadable_is_checked_by_its_engine_claims(self):
        for name, write in (('no process list', lambda run: run.record(None)),
                            ('unreadable', lambda run: run.record(None, raw='\x00\x00 not json'))):
            with self.subTest(name):
                run = self.broker()
                path = write(run)
                holder = hold_claim(self, run.locks, OTHER)
                code, err, _, _ = run.refused(every='0.3')
                self.assertEqual(code, 123, err)
                self.assertIn('so its engine claims are checked: 1 held', err)
                holder.stdin.close()  # The old engine's claim holder ends.
                holder.wait(30)
                code, err, _, _ = run.run()
                self.assertEqual(code, 125, err)
                self.assertIn('0 held', err)
                self.assertFalse(path.exists())

    def test_a_record_that_names_no_engine_never_blocks(self):
        run = self.broker()
        path = run.record(None, owner='', raw='garbage')
        self.assertEqual(path.name, 'leftover-.json')
        code, err, _, _ = run.run()
        self.assertEqual(code, 125, err)
        self.assertFalse(path.exists())

    def test_quit_during_the_check_ends_the_broker_at_once(self):
        run = self.broker()
        part, created = dummy(self)
        stuck(self, part)
        run.record([[part.pid, created]])
        code, err, out, elapsed = run.refused(every='20', stop_after=0.5)
        self.assertEqual(code, 123, err)
        self.assertLess(elapsed, 3)  # Not the 20 s re-check period.
        self.assertIn('the shell stopped this start during the check.', err)
        self.assertEqual(out, b'')

    def test_a_part_left_by_one_broker_refuses_the_next_start_until_it_ends(self):
        run = self.broker()
        part, created = dummy(self)
        hold = stuck(self, part)
        code, err, _, _ = run.run(count='survivor', members=[[part.pid, created]])
        self.assertEqual(code, 124, err)
        self.assertEqual(run.leftover()['members'], [[part.pid, created]])
        code, err, _, _ = run.refused(owner=OTHER, every='0.3')  # The next shell, with a new engine identity.
        self.assertEqual(code, 123, err)
        hold.release()
        code, err, _, _ = run.run(owner=OTHER)
        self.assertEqual(code, 125, err)
        self.assertIsNone(run.leftover())

    def test_futabas_harness_holds_a_part_and_writes_its_record(self):
        """tests/debug_hold.py --write-record, as Futaba runs it for the startup screen's checks."""
        run = self.broker()
        part, _ = dummy(self)
        harness = subprocess.Popen([sys.executable, '-B', '-I', str(CODE / 'tests' / 'debug_hold.py'), '--pid', str(part.pid),
                                    '--write-record', str(run.locks), '--age', '180', '--seconds', '60'],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, creationflags=0x08000000)
        self.addCleanup(lambda: (harness.kill(), harness.wait(30), harness.stdin.close(), harness.stdout.close()))
        self.assertEqual(harness.stdout.readline().strip(), b'held %d' % part.pid)
        record = Path(harness.stdout.readline().decode().strip().split(' ', 1)[1])
        code, err, _, _ = run.refused(every='0.3')
        self.assertEqual(code, 123, err)
        self.assertRegex(err, r'\(age 18[0-9] s\): pid %d alive, terminated again' % part.pid)
        harness.stdin.close()  # Release: the part ends.
        self.assertEqual(harness.stdout.readline().strip(), b'released %d' % part.pid)
        part.wait(10)
        code, err, _, _ = run.run()
        self.assertEqual(code, 125, err)
        self.assertFalse(record.exists())


if __name__ == '__main__':
    unittest.main()
