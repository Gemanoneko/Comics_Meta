"""Read-only online backup of the live catalog into scratch. Opens only catalog.sqlite."""
import os, sqlite3, sys, time
from pathlib import Path
src = Path(os.environ['LOCALAPPDATA']) / 'ComicsMeta' / 'data' / 'catalog.sqlite'
dst = Path(sys.argv[1])
assert not dst.exists(), 'snapshot target exists'
t0 = time.time()
with sqlite3.connect('file:' + src.as_posix() + '?mode=ro', uri=True) as s:
    s.execute('PRAGMA query_only=1')
    d = sqlite3.connect(str(dst))
    s.backup(d)
    d.close()
el = time.time() - t0
d = sqlite3.connect(str(dst))
print('snapshot bytes', dst.stat().st_size, 'seconds', round(el, 2), 'quick_check', d.execute('PRAGMA quick_check').fetchone()[0], 'at', time.strftime('%Y-%m-%d %H:%M:%S'))
d.close()
