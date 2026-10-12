import json
import os
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import app
import browser_worker
import file_lock
import library_lock
import pause_control
import supervisor
import worker
from test_worker import scratch_directory


def hold_like_a_worker(path):
    """Take a lease exactly the way worker.py and browser_worker.py do."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open('a+b')
    handle.seek(0);handle.write(b'0');handle.flush();handle.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise
    return handle


class QuitFixture(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'STATE_ROOT', self.root))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.enterContext(patch.object(pause_control, '_stop_baseline', None))
        self.enterContext(patch.dict(os.environ, {library_lock.LOCK_DIR_ENV: str(self.root / 'locks')}))
        os.environ.pop(pause_control.STOP_BASELINE_ENV, None)
        held = []
        self.enterContext(patch.object(library_lock, '_held', held))
        self.addCleanup(lambda: [claim.release() for claim in list(held)])

    def close_leases(self, leases):
        for fd in leases.values():
            os.close(fd)


class QuitStateTests(QuitFixture):
    def test_quit_is_not_saved_for_the_next_launch(self):
        pause_control.begin_run()
        pause_control.request_stop()
        self.assertTrue(pause_control.stop_requested())
        self.assertTrue(pause_control.requested())  # Every pause checkpoint also ends the step.
        status = pause_control.status()
        self.assertTrue(status['stopping'])
        self.assertFalse(status['requested'])  # The saved Pause setting was not touched.
        pause_control.begin_run()  # Next launch.
        self.assertFalse(pause_control.stop_requested())
        self.assertFalse(pause_control.requested())
        self.assertFalse(pause_control.status()['stopping'])

    def test_quit_while_paused_keeps_pause_saved(self):
        pause_control.change(True)
        pause_control.begin_run()
        pause_control.request_stop()
        pause_control.begin_run()  # Next launch.
        self.assertFalse(pause_control.stop_requested())
        self.assertTrue(pause_control.requested())
        self.assertTrue(pause_control.status()['requested'])

    def test_worker_launched_just_before_quit_still_sees_it(self):
        # The supervisor read generation 0, then the Quit landed before the worker started.
        pause_control.request_stop()
        with patch.dict(os.environ, {pause_control.STOP_BASELINE_ENV: '0'}):
            self.assertEqual(pause_control.begin_run(), 0)
        self.assertTrue(pause_control.stop_requested())
        with patch.dict(os.environ, {pause_control.STOP_BASELINE_ENV: 'not a number'}):
            self.assertEqual(pause_control.begin_run(), 1)  # Falls back to the current generation.
        self.assertFalse(pause_control.stop_requested())

    def test_processes_that_never_began_a_run_ignore_quit(self):
        pause_control.request_stop()
        self.assertFalse(pause_control.stop_requested())
        self.assertFalse(pause_control.requested())


class SupervisorQuitTests(unittest.TestCase):
    def test_launch_carries_the_generation_read_before_launch(self):
        stop = threading.Event()
        launch = Mock(side_effect=lambda *args, **kwargs: stop.set() or Mock())
        supervisor.supervise(Path('project'), stop, launch, baseline=lambda: 7)
        self.assertEqual(launch.call_args.kwargs['env'][pause_control.STOP_BASELINE_ENV], '7')

    def test_quit_during_launch_starts_no_worker(self):
        stop = threading.Event()
        launch = Mock()
        supervisor.supervise(Path('project'), stop, launch, baseline=lambda: stop.set() or 0)
        launch.assert_not_called()


class LeaseTests(QuitFixture):
    def test_waits_for_a_running_worker_then_holds_both_leases(self):
        leases = pause_control.worker_leases()
        running = hold_like_a_worker(leases['metadata'])
        with self.assertRaises(TimeoutError) as caught:
            pause_control.hold_worker_leases(timeout=0.3, poll=0.05)
        self.assertIn('metadata', str(caught.exception))
        late = file_lock.open_lock(leases['browser'])  # A failed wait releases what it took.
        self.assertTrue(file_lock.try_lock(late))
        file_lock.unlock(late);os.close(late)
        running.close()  # The worker exits.
        held = pause_control.hold_worker_leases(timeout=5, poll=0.05)
        self.addCleanup(self.close_leases, held)
        self.assertEqual(set(held), {'metadata', 'browser'})
        with self.assertRaises(OSError):
            hold_like_a_worker(leases['metadata'])  # No late worker can start.


class ServerQuitTests(QuitFixture):
    def setUp(self):
        super().setUp()
        self.server = app.LocalServer(('127.0.0.1', 0), app.Handler)
        self.server.supervisor_stop = threading.Event()
        self.addCleanup(self.server.server_close)
        self.addCleanup(lambda: self.close_leases(self.server.worker_leases))
        self.serving = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.serving.start()
        self.addCleanup(lambda: self.serving.is_alive() and self.server.shutdown())

    def post(self, path):
        port = self.server.server_port
        request = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=b'{}', method='POST',
                                         headers={'Origin': f'http://127.0.0.1:{port}', 'Content-Type': 'application/json'})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=10) as response:
            return json.load(response)

    def test_quit_endpoint_works_while_paused_and_keeps_the_pause(self):
        pause_control.change(True)
        self.assertEqual(self.post('/api/quit'), {'ok': True, 'stopping': True})
        self.serving.join(10)
        self.assertFalse(self.serving.is_alive())
        self.assertTrue(self.server.supervisor_stop.is_set())
        self.assertEqual(pause_control.stop_generation(), 1)
        self.assertTrue(pause_control.status()['requested'])

    def test_quit_waits_for_a_manual_write_and_running_workers(self):
        worker_running = hold_like_a_worker(pause_control.worker_leases()['metadata'])
        app.LOCK.acquire()  # A manual write is in flight.
        try:
            self.server.begin_quit()
            self.assertEqual(self.server.begin_quit(), {'ok': True, 'stopping': True})  # Repeat is harmless.
            deadline = time.monotonic() + 5
            while pause_control.stop_generation() < 1 and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertEqual(pause_control.stop_generation(), 1)  # Workers were asked once.
            time.sleep(0.5)
            self.assertTrue(self.serving.is_alive())
        finally:
            app.LOCK.release()
        time.sleep(0.5)
        self.assertTrue(self.serving.is_alive())  # The worker is still finishing its step.
        worker_running.close()
        self.serving.join(10)
        self.assertFalse(self.serving.is_alive())


class WorkerQuitTests(QuitFixture):
    def run_bounded(self, target):
        """A worker that ignores Quit reaches its next pause checkpoint, which raises here."""
        outcome = {}

        def run():
            try:
                outcome['value'] = target()
            except BaseException as exc:
                outcome['error'] = exc
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join(10)
        self.assertFalse(thread.is_alive(), 'Worker still running after Quit')
        if 'error' in outcome:
            raise outcome['error']
        return outcome.get('value')

    def test_metadata_worker_leaves_at_the_next_step_boundary(self):
        pause_control.request_stop()
        with patch.dict(os.environ, {pause_control.STOP_BASELINE_ENV: '0'}), \
                patch.object(worker, 'QUEUE', self.root / 'data' / 'queue'), \
                patch.object(worker, 'threading', SimpleNamespace(Thread=Mock())), \
                patch.object(pause_control, 'checkpoint', side_effect=AssertionError('Kept working after Quit')), \
                patch('free_search_browser.enable_worker_owner'), patch('free_search_browser.close') as close, \
                patch('yandex_verification.initialize'), patch('yandex_verification.cancel') as cancel:
            self.run_bounded(worker.main)
        close.assert_called()
        cancel.assert_called()
        self.assertFalse(pause_control.status()['requested'])

    def test_cover_worker_closes_its_browser_and_leaves(self):
        pause_control.request_stop()
        statuses = []
        with patch.dict(os.environ, {pause_control.STOP_BASELINE_ENV: '0'}), \
                patch.object(browser_worker, 'threading', SimpleNamespace(Thread=Mock(), Event=threading.Event)), \
                patch.object(pause_control, 'checkpoint', side_effect=AssertionError('Kept working after Quit')), \
                patch('lens_browser_owner.enable'), patch.object(browser_worker.lens_verification, 'initialize'), \
                patch.object(browser_worker.lens_verification, 'paused') as closed, \
                patch.object(browser_worker.search, 'status', side_effect=lambda **kw: statuses.append(kw) or {}):
            self.run_bounded(browser_worker.main)
        closed.assert_called_once()
        self.assertNotIn('paused', [kw.get('state') for kw in statuses])  # Nothing is saved as paused.
        fd = file_lock.open_lock(app.DATA / 'browser-worker.lock')
        self.addCleanup(os.close, fd)
        self.assertTrue(file_lock.try_lock(fd))  # Its lease was released on exit.


if __name__ == '__main__':
    unittest.main()
