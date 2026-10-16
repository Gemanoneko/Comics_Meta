"""Machine-wide single-writer claim on a comic library.

Every process that can change a library (the dashboard server, the metadata
worker, the cover-search worker and the batch command) holds a claim on the
library folder for as long as it runs. A claim records the state root of the
copy that made it. A live claim from a different state root on the same
folder, a parent or a child refuses the new claim, so an installed copy and a
WIP checkout, including a worker left over from either, never both write one
library. Processes of one copy share a state root and never block each other;
their per-state worker leases still stop duplicate workers.

Claims are OS byte locks, so they end with the process. A crash or a killed
worker never leaves a lock to clear by hand.

Layout (per Windows user; every copy runs as the same user):
  %LOCALAPPDATA%\\ComicsMeta\\locks\\gate.lock          one check-and-claim at a time
  %LOCALAPPDATA%\\ComicsMeta\\locks\\claims\\<id>.lock  held while the claimant lives
  %LOCALAPPDATA%\\ComicsMeta\\locks\\claims\\<id>.json  who holds it
COMICS_META_LOCK_DIR moves the folder (tests only).
"""
import atexit
import json
import os
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
import app
import file_lock
import storage

LOCK_DIR_ENV = 'COMICS_META_LOCK_DIR'
EXIT_LIBRARY_BUSY = 75  # Dashboard exit code: another copy owns the library.
GATE_TIMEOUT = 30

_held = []
_mutex = threading.Lock()
_role = None


class LibraryBusy(Exception):
    """This copy may not change the library. Nothing was written."""

    def __init__(self, message, library='', owner=None):
        super().__init__(message)
        self.library = str(library)
        self.owner = owner or {}


def lock_dir():
    value = os.environ.get(LOCK_DIR_ENV, '').strip()
    if value:
        return Path(value)
    local = os.environ.get('LOCALAPPDATA')
    return (Path(local) if local else Path.home() / '.local' / 'state') / 'ComicsMeta' / 'locks'


def identity(path):
    """One spelling per folder: absolute, links and mapped drives resolved, case folded."""
    text = os.fspath(path)
    if text.startswith('\\\\?\\UNC\\'):
        text = '\\\\' + text[8:]
    elif text.startswith('\\\\?\\'):
        text = text[4:]
    text = os.path.abspath(text)
    try:
        text = os.path.realpath(text)
    except OSError:
        pass  # An unreachable network drive keeps its spelling; nothing can be written there anyway.
    return os.path.normcase(text)


def contains(parent, child):
    try:
        return os.path.commonpath([parent, child]) == parent
    except ValueError:  # Different drives.
        return False


def overlaps(first, second):
    return contains(first, second) or contains(second, first)


def _remove(*paths):
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass  # Retried by the next claimant's stale-claim sweep.


@contextmanager
def _gate(timeout):
    folder = lock_dir()
    folder.mkdir(parents=True, exist_ok=True)
    fd = file_lock.open_lock(folder / 'gate.lock')
    try:
        deadline = time.monotonic() + timeout
        while not file_lock.try_lock(fd):
            if time.monotonic() >= deadline:
                raise LibraryBusy('The library lock is busy. Nothing was changed; try again shortly.')
            time.sleep(0.05)
        try:
            claims = folder / 'claims'
            claims.mkdir(exist_ok=True)
            yield claims
        finally:
            file_lock.unlock(fd)
    finally:
        os.close(fd)


def _overlapping_owner(claims, library_id, state_id):
    """The record of a live claim from another state root on an overlapping folder, else None."""
    for lock_path in sorted(claims.glob('*.lock')):
        record_path = lock_path.with_suffix('.json')
        try:
            fd = file_lock.open_lock(lock_path, create=False)
        except FileNotFoundError:
            continue
        except OSError:
            live = True  # Unopenable is not proof that its owner has gone.
        else:
            live = not file_lock.try_lock(fd)
            if not live:
                file_lock.unlock(fd)
            os.close(fd)
        if not live:
            _remove(lock_path, record_path)  # Its process has ended.
            continue
        try:
            owner = json.loads(storage.read_text(record_path))
            state, library = owner['state_identity'], owner['library_identity']
        except (OSError, ValueError, KeyError, TypeError):
            state = library = None
        if not (isinstance(state, str) and isinstance(library, str)):
            # A held claim that cannot be read is not proof the library is free.
            return {'state_root': 'unknown', 'claim': lock_path.name}
        if state != state_id and overlaps(library, library_id):
            return owner
    for record_path in claims.glob('*.json'):
        if not record_path.with_suffix('.lock').exists():
            _remove(record_path)
    return None


class Claim:
    def __init__(self, library, library_id, fd, lock_path, record_path):
        self.library, self.identity = library, library_id
        self._fd, self._lock_path, self._record_path = fd, lock_path, record_path

    @property
    def held(self):
        return self._fd is not None

    def covers(self, target_id):
        return self.held and contains(self.identity, target_id)

    def release(self):
        """Give the library up. A busy gate only delays removing the files, never the release."""
        if not self.held:
            return
        try:
            with _gate(2):
                self._close()
                _remove(self._lock_path, self._record_path)
        except (LibraryBusy, OSError):
            self._close()

    def _close(self):
        fd, self._fd = self._fd, None
        if fd is not None:
            try:
                file_lock.unlock(fd)
            except OSError:
                pass
            os.close(fd)


def _default_role():
    return _role or Path(sys.argv[0] or 'python').stem or 'python'


def acquire(library, role=None):
    """Claim `library` for this process until it exits or releases; raises LibraryBusy."""
    library = os.fspath(library)
    library_id = identity(library)
    state_root = os.fspath(app.STATE_ROOT)
    state_id = identity(state_root)
    try:
        with _gate(GATE_TIMEOUT) as claims:
            owner = _overlapping_owner(claims, library_id, state_id)
            if owner is not None:
                raise LibraryBusy('Another Comics Meta copy is using this library (state folder: '
                                  + str(owner.get('state_root') or 'unknown')
                                  + '). This copy will not change it.', library, owner)
            name = '%d-%s' % (os.getpid(), uuid.uuid4().hex[:12])
            lock_path, record_path = claims / (name + '.lock'), claims / (name + '.json')
            fd = file_lock.open_lock(lock_path)
            try:
                if not file_lock.try_lock(fd):
                    raise LibraryBusy('A new library claim could not be locked. Nothing was changed.', library)
                storage.save(record_path, {
                    'state_root': state_root, 'state_identity': state_id,
                    'library': library, 'library_identity': library_id,
                    'code_root': os.fspath(app.BASE), 'role': role or _default_role(),
                    'pid': os.getpid(), 'claimed_at': time.time()})
            except BaseException:
                os.close(fd)
                _remove(lock_path, record_path)
                raise
    except OSError as exc:
        # Fail closed: without a working lock folder no copy may assume it owns a library.
        raise LibraryBusy('The library lock folder is unavailable (' + exc.__class__.__name__
                          + '), so this copy will not change the library.', library) from None
    return Claim(library, library_id, fd, lock_path, record_path)


def _hold(library, library_id, role=None):
    with _mutex:
        for claim in _held:
            if claim.covers(library_id):
                return claim
        claim = acquire(library, role)
        _held.append(claim)
        return claim


def adopt(claim):
    """Retain an existing process-owned claim across setup request threads.

    No gate/reacquisition occurs: the original byte lock stays held throughout
    the durable config commit and dashboard activation.
    """
    if not isinstance(claim,Claim) or not claim.held:
        raise ValueError('Only a live library claim can be retained')
    with _mutex:
        if claim not in _held:_held.append(claim)
    return claim


def claim_configured(role):
    """Claim the configured library when a process starts; None when no library is configured."""
    global _role
    _role = role
    root = app.live_root()
    return _hold(root, identity(root), role) if root else None


def require(path, root=None):
    """Hold a claim covering `path` before changing it; raises LibraryBusy.

    The claim is on the configured library when `path` is inside it, else on
    `root` (the folder the comic was scanned from), else on the comic's folder."""
    target = identity(path)
    with _mutex:
        for claim in _held:
            if claim.covers(target):
                return claim
    for candidate in (app.live_root(), root):
        if candidate and contains(identity(candidate), target):
            return _hold(os.fspath(candidate), identity(candidate))
    folder = os.path.dirname(os.path.abspath(os.fspath(path)))
    return _hold(folder, identity(folder))


def release_all():
    with _mutex:
        while _held:
            _held.pop().release()


atexit.register(release_all)
