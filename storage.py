"""Atomic, durable JSON replacement with short Windows reader-lock retries.

save() writes the new file beside the old one, puts its bytes on the disk (flush and fsync), and only then renames
it over the old one with MOVEFILE_WRITE_THROUGH, as setup_state's save already did. A stop at any moment leaves the
complete old file or the complete new one. Before 2026-11-17 the rename could reach the disk before the bytes: after
the unclean stop of 2026-11-13, progress.json, folders.json and browser-search.json came back full size and all
zeros (Docs/ComicsMetaOrganizer_ZeroFillDiagnosis_2026-11-17.md).
"""
import ctypes
import json
import os
import time
import uuid
from pathlib import Path

MOVEFILE_REPLACE_EXISTING = 0x1
MOVEFILE_WRITE_THROUGH = 0x8
_move_file = None


def _move(source, destination):
    """Rename source over destination. On Windows the rename reaches the disk before this returns."""
    global _move_file
    if os.name != 'nt':
        os.replace(source, destination)
        return
    if _move_file is None:
        from ctypes import wintypes
        move = ctypes.WinDLL('kernel32', use_last_error=True).MoveFileExW
        move.argtypes, move.restype = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD], wintypes.BOOL
        _move_file = move
    if not _move_file(str(source), str(destination), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH):
        raise ctypes.WinError(ctypes.get_last_error())  # Access denied or a sharing violation is a PermissionError.


def _write(path, data):
    """Replace path with data (bytes), durably."""
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with open(temporary, 'xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(20):
            try:
                _move(temporary, path)
                return
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(.05)
    finally:
        if temporary.exists():
            temporary.unlink()


def save(path, value):
    path = Path(path)
    # Text-mode line ends, as Path.write_text wrote them before.
    _write(path, json.dumps(value, ensure_ascii=False, indent=2).replace('\n', os.linesep).encode('utf-8'))


def read_text(path):
    """Text of a status, heartbeat or lease file that save() may be replacing right now.

    While the replace runs, Windows briefly refuses a plain open with
    PermissionError (errno 13), in the writer's own process too. Retried with
    the writer's bound; a refusal that outlasts it is raised. Other errors,
    including a missing file, are raised at once.
    """
    for attempt in range(20):
        try:
            return Path(path).read_text(encoding='utf-8')
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(.05)
