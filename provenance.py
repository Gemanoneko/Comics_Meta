"""Which values in a comic the in-book tiers wrote and nobody has changed since.

Sergei, 2026-10-13: "Outside sources may now REPLACE in-book values when they
disagree." Only values the in-book tiers wrote, only from a verified external
source, and never values Sergei or another program wrote.

app.write_metadata keeps a write ledger, one row per verified write, in the same
transaction as its history row: the fields that write set, who started it
('automatic' plan or 'manual'), and the archive's [size, mtime] before and after.
A field counts as in-book only when all of these hold:

- the latest app write that set it came from an in-book tier (source 'in-book:...')
  and set exactly the value the archive holds now;
- every app write since then was automatic. A manual write means Sergei worked on
  the comic, so every value it leaves in place counts as his;
- only those writes changed the archive. Each one started from the signature the
  one before left, and the last one left the signature the folder scan has just
  read. If another program saved the archive in between (a tagger, a re-download),
  the chain breaks there, and no value older than the break is replaced, even if
  it still reads the same.

v0.1.3 wrote before the ledger existed. Its verified batch writes are recorded once
from their batch folders (backfill): the plan entry gives the source, the fields and
the starting signature; results.json gives the verified output signature.
"""
import json
from pathlib import Path
import app

IN_BOOK_PREFIX = 'in-book:'
REPLACED_PREFIX = 'replaced-in-book:'
BACKFILL_KEY = 'write_ledger_backfill_v1'
CREATOR_FIELDS = ('Writer', 'Penciller', 'Inker', 'Colorist', 'Letterer', 'CoverArtist', 'Editor')
COLUMNS = 'history_id,path,source,writer,fields,input_size,input_mtime,output_size,output_mtime,origin'
_backfilled = set()


def history_paths(path):
    """The forms a comic's path takes in history: as scanned, and the writer's extended path."""
    return list(dict.fromkeys([str(path), str(app.filesystem_path(path))]))


def _pair(size, mtime):
    return [size, mtime] if size is not None and mtime is not None else None


def chain(row, con=None):
    """The app's own verified writes that made the archive what the scan read, newest first.

    Stops at the first write it cannot place: a history row with no ledger row, a write
    that left a different signature from the one the next write started from (another
    program saved the archive in between), or a write whose starting signature is unknown."""
    if con is None:
        with app.db() as con:
            return chain(row, con)
    paths = history_paths(row['path'])
    ids = [r[0] for r in con.execute('SELECT id FROM history WHERE path IN (%s) ORDER BY id DESC' % ','.join('?' * len(paths)), paths)]
    if not ids:
        return []
    ledger = {}
    for start in range(0, len(ids), 500):
        part = ids[start:start + 500]
        for values in con.execute('SELECT ' + COLUMNS + ' FROM write_ledger WHERE history_id IN (%s)' % ','.join('?' * len(part)), part):
            ledger[values[0]] = dict(zip(COLUMNS.split(','), values))
    links, expected = [], [row['size'], row['mtime']]
    for history_id in ids:
        link = ledger.get(history_id)
        if not link or _pair(link['output_size'], link['output_mtime']) != expected:
            break
        links.append(link)
        expected = _pair(link['input_size'], link['input_mtime'])
        if expected is None:
            break
    return links


def same(a, b):
    return ' '.join(str(a or '').split()) == ' '.join(str(b or '').split())


def in_book_values(row, old, con=None):
    """{field: value} for the fields whose current value the in-book tiers wrote, untouched since."""
    values, seen = {}, set()
    for link in chain(row, con):
        if link['writer'] != 'automatic':
            break  # Sergei worked on the comic here: every value still in place counts as his.
        try:
            fields = json.loads(link['fields'] or '{}')
        except ValueError:
            break
        for field, value in fields.items():
            if field in seen or field == 'Notes':
                continue
            seen.add(field)
            if str(link['source'] or '').startswith(IN_BOOK_PREFIX) and str(old.get(field) or '').strip() and same(old.get(field), value):
                values[field] = old[field]
    return values


def pages_unchanged(row, signature, con=None):
    """The archive read at `signature` became the current one only through the app's own
    verified writes. Those change ComicInfo.xml and never a page, so a cover or credits
    reading taken at `signature` still describes these pages."""
    if not isinstance(signature, (list, tuple)) or len(signature) != 2:
        return False
    if list(signature) == [row['size'], row['mtime']]:
        return True
    return any(_pair(link['input_size'], link['input_mtime']) == list(signature) for link in chain(row, con))


def disagrees(field, current, value):
    """A verified external value says something different from the in-book value, not just
    the same thing written another way ("001" and "1", "Image" and "Image Comics")."""
    import research
    a, b = ' '.join(str(current or '').split()), ' '.join(str(value or '').split())
    if not b or a == b:
        return False
    if field == 'Number':
        return research.issue_number(a) != research.issue_number(b)
    if field == 'Publisher':
        import imprints  # An imprint and its parent are the same house: "Skybound" agrees with "Image Comics".
        return imprints.publisher_key(a) != imprints.publisher_key(b)
    if field in ('Year', 'Month', 'Day'):
        try:
            return int(a) != int(b)
        except ValueError:
            return True
    if field in CREATOR_FIELDS:
        names = lambda v: {' '.join(research.words(n)) for n in research.credit_names(v)} - {''}
        return names(a) != names(b)
    return True  # Series and other text: the verified source's own wording.


def backfill(batches=None):
    """Record v0.1.3's verified batch writes in the ledger. Idempotent; returns counts."""
    batches = Path(batches or getattr(app, 'STATE_ROOT', app.BASE) / 'batches')
    with app.db() as con:
        history = {r[0]: (r[1], r[2]) for r in con.execute('SELECT backup,id,source FROM history WHERE backup IS NOT NULL')}
    rows, counts = [], {'folders': 0, 'results': 0, 'recorded': 0, 'unmatched': 0}
    for folder in sorted(batches.iterdir()) if batches.is_dir() else []:
        try:
            plan = json.loads((folder / 'plan.json').read_text(encoding='utf-8'))
            results = json.loads((folder / 'results.json').read_text(encoding='utf-8')) if (folder / 'results.json').is_file() else []
        except (OSError, ValueError):
            continue
        counts['folders'] += 1
        entries = {e.get('path'): e for e in plan.get('entries', []) if isinstance(e, dict) and e.get('action') == 'write'}
        writer = 'manual' if plan.get('reference') else 'automatic'
        for result in results if isinstance(results, list) else []:
            counts['results'] += 1
            output = result.get('output_signature')
            found = history.get(result.get('backup'))
            entry = entries.get(result.get('path'))
            if not (result.get('metadata_readback_verified') and isinstance(output, list) and len(output) == 2 and found and entry):
                counts['unmatched'] += 1
                continue
            changes = entry.get('changes') or {}
            fields = {k: (changes.get(k) or {}).get('after', '') for k in result.get('fields_updated') or [] if k in changes and k != 'Notes'}
            start = entry.get('signature') if isinstance(entry.get('signature'), list) and len(entry['signature']) == 2 else [None, None]
            rows.append((found[0], result['path'], found[1], writer, json.dumps(fields, ensure_ascii=False), start[0], start[1],
                         output[0], output[1], 'backfill'))
    with app.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS ledger_meta(key TEXT PRIMARY KEY, value TEXT)')
        before = con.execute('SELECT COUNT(*) FROM write_ledger').fetchone()[0]
        con.executemany('INSERT OR IGNORE INTO write_ledger(' + COLUMNS + ') VALUES(?,?,?,?,?,?,?,?,?,?)', rows)
        counts['recorded'] = con.execute('SELECT COUNT(*) FROM write_ledger').fetchone()[0] - before
        con.execute('INSERT OR REPLACE INTO ledger_meta VALUES(?,?)', (BACKFILL_KEY, json.dumps(counts)))
    return counts


def ensure_backfilled():
    """Run the backfill once per catalog. A failure never stops discovery; the next start retries."""
    key = str(Path(app.DATA).resolve())
    if key in _backfilled:
        return
    _backfilled.add(key)
    try:
        with app.db() as con:
            con.execute('CREATE TABLE IF NOT EXISTS ledger_meta(key TEXT PRIMARY KEY, value TEXT)')
            done = con.execute('SELECT 1 FROM ledger_meta WHERE key=?', (BACKFILL_KEY,)).fetchone()
        if not done:
            backfill()
    except Exception as exc:
        # Safe either way: without the backfill, v0.1.3's in-book values are never replaced.
        print('Write ledger backfill not completed:', type(exc).__name__, str(exc)[:300])
