"""Host the dashboard outside a terminal/client lifecycle; record child exits."""
import json
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent


def main():
    data = BASE / 'data'
    data.mkdir(exist_ok=True)
    # Keep one bounded tail from the prior run, never an unbounded log archive.
    for name in ('server-output.log', 'server-error.log'):
        path = data / name
        if path.exists():
            with path.open('rb') as previous:
                previous.seek(max(0, path.stat().st_size - 262144))
                path.with_suffix('.previous.log').write_bytes(previous.read())
    with (data / 'server-output.log').open('wb') as output, (data / 'server-error.log').open('wb') as error:
        child = subprocess.Popen([sys.executable, '-u', str(BASE / 'app.py'), '--no-browser'],
                                 cwd=BASE, stdout=output, stderr=error,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        code = child.wait()
    (data / 'server-exit.json').write_text(json.dumps({'timestamp': time.time(), 'exit_code': code}), encoding='utf-8')
    return code


if __name__ == '__main__':
    sys.exit(main())
