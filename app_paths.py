"""Where the code lives and where the state lives.

Code (this folder): the Python modules, static/ and VERSION.
State (the state root): config.json, .env, data/, batches/ and work/.

COMICS_META_STATE_ROOT selects the state root. The packaged app sets it to
%LOCALAPPDATA%\\ComicsMeta. Unset or blank, state stays beside the code, which
is where the WIP checkout has always kept it.
"""
import os
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parent
STATE_ROOT_ENV = 'COMICS_META_STATE_ROOT'


def state_root(environ=None):
    value = (os.environ if environ is None else environ).get(STATE_ROOT_ENV, '').strip()
    if not value:
        return CODE_ROOT
    path = Path(value)
    if not path.is_absolute():
        # A relative root would follow whatever folder a process started in.
        raise ValueError(STATE_ROOT_ENV + ' must be an absolute folder path.')
    return Path(os.path.abspath(path))
