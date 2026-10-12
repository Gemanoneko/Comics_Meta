"""Non-blocking one-byte OS file locks that end with the owning process.

Byte 0 is the same range the worker leases (queue/worker.lock and
browser-worker.lock) lock, so these helpers can test and hold those leases.
"""
import os


def open_lock(path, create=True):
    """Open a lock file for locking; returns a file descriptor (not inherited by children)."""
    flags = os.O_RDWR | getattr(os, 'O_BINARY', 0) | (os.O_CREAT if create else 0)
    return os.open(path, flags, 0o666)


def try_lock(fd):
    """Take byte 0 for this descriptor; False when another holder has it."""
    os.lseek(fd, 0, os.SEEK_SET)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def unlock(fd):
    os.lseek(fd, 0, os.SEEK_SET)
    if os.name == 'nt':
        import msvcrt
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_UN)
