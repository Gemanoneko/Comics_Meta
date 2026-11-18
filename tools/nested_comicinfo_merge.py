"""One-off merge of nested ComicInfo into the root copy, then removal of the nested copy (Sergei 2026-11-18, option d).

    Dry run (the default; writes nothing to any comic, the catalog or the config):
        python -B tools/nested_comicinfo_merge.py --report <folder>/<name>.md [--library <folder>] [--live <state folder>]
    Apply (only after Futaba sampled the dry run and Sergei gave the final OK):
        python -B tools/nested_comicinfo_merge.py --apply <name>.json --out <new empty folder> [--engine <folder>] [--live <state folder>]

Which archives: a root ComicInfo.xml and exactly one ComicInfo.xml inside a folder. Archives with several nested or
several root copies are listed, never planned. (Nested-only archives need no tool: the app reads the nested copy and
moves it to the root at its next write.)

The merge is the app's own (app.merge_comicinfo): fill-empty, element by element. Every tag the nested copy fills and
the root copy does not is copied (repeated tags, Pages and other structured elements included); where both fill a
tag the root copy wins and the nested value is dropped. Each dropped nested value is listed. Then the nested entry is
removed, so the archive keeps one ComicInfo.

Held for Sergei, never planned: the two copies name a different Series or Number; the merge would put a nested
Month or Day beside a root date that disagrees with the nested one (pure fill-empty would mix two dates); either
copy cannot be read (removing an unreadable nested copy would lose it).

The dry run reads the library with read-only handles that let other programs rename, replace or delete the file
meanwhile; it skips the app's backup, conversion-staging and YACReader folders and any archive the app is writing
now (its .metadata-tmp exists), and opens no catalog. It writes <name>.md (summary and one line per archive),
<name>.csv (one row per field filled or nested value dropped, with the value) and <name>.json (the plan the apply
takes). Per archive it also records the nested entry that would be removed and the ZIP order of the two copies:
YACReader reads the first ComicInfo.xml in ZIP order, at any depth (Makoto, 2026-11-18).

Apply uses the app's own write path and locks, not a pause: app.write_metadata(merge_nested=...) from the installed
app's engine (--engine; it must be a version with the nested merge) against the live state folder. So it takes the
same library claim as the running app and the same per-archive write lock as its worker and dashboard; it checks the
archive against the catalog's signature, the nested entry's name, CRC and size and the root fields the plan relies
on before any backup; keeps a backup; rewrites through a temporary archive; proves every other entry unchanged with
exactly the nested entry gone; reads the result back; and records history and the write ledger with writer
'manual', so the app treats the values as Sergei's and never replaces them. The app may keep running: a pause stops
only the worker, not the dashboard, so the locks are needed either way, and a comic the worker planned before this
write is refused by its own signature check and planned again. An archive is written only while it still matches
the plan (the same fields filled, the same nested values dropped); anything else is skipped and listed. Backups are
kept. Results go to <out>/results.jsonl and <out>/summary.json.
"""
import argparse
import copy
import csv
import inspect as introspect
import json
import os
import re
import sys
import time
import zipfile
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]
PLAN_KIND = 'nested-comicinfo-merge'
PLAN_VERSION = 2
SKIP_DIRS = {'.yacreaderlibrary', '.comic-metadata-backups'}
DATE = ('Year', 'Month', 'Day')
HISTORY_SOURCE = 'nested-comicinfo-merge'
_kernel = None


def default_live():
    return Path(os.environ.get('LOCALAPPDATA', '')) / 'ComicsMeta'


def default_engine():
    return Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'comic-metadata' / 'resources' / 'engine'


def open_shared(path):
    """Read-only handle that lets other programs rename, replace or delete the file meanwhile (as
    reverse_image.open_shared: Python's open() omits FILE_SHARE_DELETE on Windows)."""
    if os.name != 'nt':
        return open(path, 'rb')
    global _kernel
    import ctypes, msvcrt
    from ctypes import wintypes
    if _kernel is None:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        _kernel = kernel
    # GENERIC_READ; share read, write and delete; OPEN_EXISTING; not inheritable.
    handle = _kernel.CreateFileW(str(path), 0x80000000, 0x7, None, 3, 0x80, None)
    if handle is None or handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        _kernel.CloseHandle(handle)
        raise
    return os.fdopen(descriptor, 'rb')


def is_comicinfo(name):
    return name.replace('\\', '/').split('/')[-1].lower() == 'comicinfo.xml'


def is_root(name):
    return name.lower() == 'comicinfo.xml'


def parse(app, archive, name):
    """The app's own parse of one ComicInfo entry (size limit, entity refusal, repairs, root tag)."""
    if archive.getinfo(name).file_size > 2_000_000:
        raise ValueError('over 2 MB')
    xml = app.metadata_xml(archive.read(name))
    if xml.tag != 'ComicInfo':
        raise ValueError('root element is not ComicInfo')
    return xml


def text(value):
    return ' '.join(str(value or '').split())


def series_key(value):
    return re.sub(r'[\W_]+', '', text(value).casefold())


def number_key(value):
    value = text(value).lstrip('#')
    try:
        return str(Decimal(value).normalize())
    except InvalidOperation:
        return value.casefold()


def date_key(value):
    value = text(value)
    return str(int(value)) if value.isdigit() else value


def element_key(element):
    """An element's content, spacing collapsed: two copies that say the same thing compare equal."""
    return (element.tag, sorted(element.attrib.items()), text(element.text), [element_key(c) for c in element])


def describe(elements):
    """One value for the report: the text, texts joined by ' | ' for a repeated tag, or a short note for structure."""
    if all(not len(e) for e in elements):
        return ' | '.join(e.text or '' for e in elements)
    return '<%s: %d element(s), %d child element(s)>' % (elements[0].tag, len(elements), sum(len(e) for e in elements))


def plan_merge(app, root, nested):
    """(fills, dropped, hold) for one archive, from the app's own merge on a copy of the root.

    fills: {tag: value} the merge copies into the root copy; dropped: {tag: nested value} both copies fill
    differently (the root value stays and the nested one goes with the nested entry); hold: a reason the archive is
    held for Sergei, or ''."""
    merged = copy.deepcopy(root)
    tags = app.merge_comicinfo(merged, nested)
    fills = {tag: describe([e for e in nested if e.tag == tag]) for tag in tags}
    dropped = {}
    for tag in dict.fromkeys(child.tag for child in nested):
        if tag in tags:
            continue
        donors = [e for e in nested if e.tag == tag and app.comicinfo_filled(e)]
        current = [e for e in root if e.tag == tag and app.comicinfo_filled(e)]
        if donors and current and [element_key(e) for e in donors] != [element_key(e) for e in current]:
            dropped[tag] = describe(donors)
    holds = []
    root_series, nested_series = root.findtext('Series'), nested.findtext('Series')
    root_number, nested_number = root.findtext('Number'), nested.findtext('Number')
    if text(root_series) and text(nested_series) and series_key(root_series) != series_key(nested_series):
        holds.append('the copies name a different Series')
    if text(root_number) and text(nested_number) and number_key(root_number) != number_key(nested_number):
        holds.append('the copies name a different Number')
    if any(part in tags for part in DATE):
        both = [p for p in DATE if text(root.findtext(p)) and text(nested.findtext(p))]
        if any(date_key(root.findtext(p)) != date_key(nested.findtext(p)) for p in both):
            holds.append('the merge would add a nested date part to a root date that differs')
    return fills, dropped, '; '.join(holds)


def inspect(app, path):
    """What one archive holds: layout, ZIP order of its ComicInfo copies, and (root + one nested) the merge."""
    record = {'path': str(path)}
    stat = os.stat(app.filesystem_path(path))
    record['size'], record['mtime'] = stat.st_size, stat.st_mtime_ns
    with open_shared(app.filesystem_path(path)) as handle:
        if handle.read(8).startswith((b'7z\xbc\xaf\x27\x1c', b'Rar!')):
            record['layout'] = 'not_zip'
            return record
        handle.seek(0)
        with zipfile.ZipFile(handle) as archive:
            infos = archive.infolist()
            copies = [info for info in infos if is_comicinfo(info.filename)]
            roots = [info.filename for info in copies if is_root(info.filename)]
            nested = [info for info in copies if not is_root(info.filename)]
            record['roots'], record['nested'] = roots, [info.filename for info in nested]
            if len(roots) > 1:
                record['layout'] = 'several_root'
            elif roots and len(nested) == 1:
                record['layout'] = 'root_and_nested'
            elif roots and nested:
                record['layout'] = 'root_and_several_nested'
            elif roots:
                record['layout'] = 'root_only'
            elif len(nested) == 1:
                record['layout'] = 'nested_only'
            elif nested:
                record['layout'] = 'several_nested'
            else:
                record['layout'] = 'none'
            if copies:
                # YACReader reads the first ComicInfo.xml in ZIP order (the central directory), at any depth.
                record['first_in_zip'] = 'root' if is_root(copies[0].filename) else 'nested'
                by_offset = min(copies, key=lambda info: info.header_offset).filename
                record['first_by_offset'] = 'root' if is_root(by_offset) else 'nested'
                record['root_is_last_entry'] = bool(roots) and infos[-1].filename == roots[0]
            if record['layout'] == 'nested_only':
                try:
                    parse(app, archive, nested[0].filename)
                except Exception as exc:
                    record['nested_error'] = str(exc)[:200] or type(exc).__name__
            if record['layout'] != 'root_and_nested':
                return record
            record['remove'] = {'name': nested[0].filename, 'crc': nested[0].CRC, 'size': nested[0].file_size}
            try:
                root_xml = parse(app, archive, roots[0])
            except Exception as exc:
                record['action'], record['reason'] = 'hold', 'root copy unreadable: ' + (str(exc)[:200] or type(exc).__name__)
                return record
            try:
                nested_xml = parse(app, archive, nested[0].filename)
            except Exception as exc:
                record['action'], record['reason'] = 'hold', 'nested copy unreadable: ' + (str(exc)[:200] or type(exc).__name__)
                return record
    fills, dropped, hold = plan_merge(app, root_xml, nested_xml)
    record.update(fills=fills, dropped=dropped, action='hold' if hold else 'merge', reason=hold,
                  root_fields={tag: root_xml.findtext(tag) or '' for tag in ('Series', 'Number') + DATE},
                  nested_series=text(nested_xml.findtext('Series')), nested_number=text(nested_xml.findtext('Number')))
    return record


def walk(app, library):
    """CBZ files under the library as the app's folder scan spells them, and whether the app is writing one now."""
    for folder, dirs, files in os.walk(app.filesystem_path(library)):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith('.comic-metadata-convert-'))
        native = folder
        if native.startswith('\\\\?\\UNC\\'):
            native = '\\\\' + native[8:]
        elif native.startswith('\\\\?\\'):
            native = native[4:]
        names = set(files)
        for name in sorted(files):
            if Path(name).suffix.lower() != '.cbz':
                continue
            yield Path(native) / name, name + '.metadata-tmp' in names


def live_library(live):
    config = json.loads((live / 'config.json').read_text(encoding='utf-8'))  # Read only; nothing else is used.
    automatic = config.get('automatic', {})
    return automatic.get('library_root') or automatic.get('root') or ''


def dry_run(app, library, report, progress=None):
    library = Path(library).resolve()
    if not library.is_dir():
        raise SystemExit('Library folder is unavailable: ' + str(library))
    records, started = [], time.time()
    for path, busy in walk(app, library):
        if busy:
            records.append({'path': str(path), 'layout': 'busy'})
        else:
            try:
                records.append(inspect(app, path))
            except Exception as exc:
                records.append({'path': str(path), 'layout': 'unreadable', 'error': str(exc)[:200] or type(exc).__name__})
        if progress and len(records) % 2000 == 0:
            progress(len(records))
    write_outputs(library, records, Path(report), time.time() - started)
    return records


def relative(library, path):
    try:
        return str(Path(path).relative_to(library))
    except ValueError:
        return str(path)


def write_outputs(library, records, report, seconds):
    stem = report.with_suffix('')
    plan = {'kind': PLAN_KIND, 'version': PLAN_VERSION, 'created': time.strftime('%Y-%m-%d %H:%M:%S'),
            'library': str(library), 'entries': [r for r in records if r.get('layout') == 'root_and_nested']}
    stem.with_suffix('.json').write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding='utf-8')
    with open(stem.with_suffix('.csv'), 'w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['archive', 'action', 'change', 'field', 'value', 'nested entry removed', 'first in ZIP order'])
        for record in plan['entries']:
            name = relative(library, record['path'])
            removed = (record.get('remove') or {}).get('name', '') if record.get('action') == 'merge' else ''
            rows = [('fill', f, v) for f, v in (record.get('fills') or {}).items()]
            rows += [('nested value dropped (root wins)', f, v) for f, v in (record.get('dropped') or {}).items()]
            for change, field, value in rows or [('nothing to fill', '', '')]:
                writer.writerow([name, record.get('action'), change, field, value, removed, record.get('first_in_zip')])
    report.write_text(summary_markdown(library, records, plan, seconds, stem), encoding='utf-8')


def summary_markdown(library, records, plan, seconds, stem):
    layouts = Counter(r.get('layout') for r in records)
    merge = plan['entries']
    planned = [r for r in merge if r.get('action') == 'merge']
    holds = [r for r in merge if r.get('action') == 'hold']
    fields = Counter(f for r in planned for f in r['fills'])
    dropped = Counter(f for r in planned for f in r.get('dropped', {}))
    first = Counter((r.get('layout'), r.get('first_in_zip')) for r in records if r.get('first_in_zip'))
    order_split = [r for r in records if r.get('first_in_zip') and r.get('first_in_zip') != r.get('first_by_offset')]
    nested_only = [r for r in records if r.get('layout') == 'nested_only']
    unreadable_nested = [r for r in nested_only if r.get('nested_error')]
    backup_bytes = sum(r['size'] for r in planned)
    names = {'none': 'No ComicInfo', 'root_only': 'Root copy only',
             'nested_only': 'One nested copy, no root (Part 1: read, moved to the root at the next write)',
             'several_nested': 'Several nested copies, no root (ignored, kept)', 'root_and_nested': 'Root + one nested (this merge)',
             'root_and_several_nested': 'Root + several nested (not planned)', 'several_root': 'Several root copies (the app refuses these)',
             'not_zip': 'RAR/7-Zip named .cbz', 'unreadable': 'Could not be read', 'busy': 'Being written by the app (skipped)'}
    lines = ['# Comics Meta Organizer - nested ComicInfo merge (option d), dry run', '',
             'Date: %s. Tool: `tools/nested_comicinfo_merge.py` (dry run). Library: `%s`. Took %d s.' % (plan['created'], library, seconds), '',
             'Read-only: each archive opened with a read-only handle that lets the app rename, replace or delete it '
             'meanwhile; the app\'s backup (`.comic-metadata-backups`), conversion-staging (`.comic-metadata-convert-*`) '
             'and `.yacreaderlibrary` folders skipped; any archive with a `.metadata-tmp` beside it (a write under way) '
             'skipped; no catalog opened. Nothing written to any comic, the catalog or the config.', '',
             'Beside this file: `%s.csv` (one row per field filled or nested value dropped, with the value, and the nested '
             'entry removed) and `%s.json` (the plan the apply mode takes).' % (stem.name, stem.name), '',
             'Rule: fill-empty from the nested copy into the root copy, element by element (the app\'s `merge_comicinfo`); '
             'where both copies hold a value the root wins; then the nested entry is removed, so one ComicInfo remains.', '',
             '## Library', '', '| Layout | Archives |', '|---|---:|']
    lines += ['| %s | %d |' % (names[key], layouts[key]) for key in names if layouts.get(key)]
    lines += ['| **CBZ files** | **%d** |' % len(records), '',
              'One nested copy, no root: %d, of which %d readable and %d unreadable (ignored and kept, as before).'
              % (len(nested_only), len(nested_only) - len(unreadable_nested), len(unreadable_nested)), '',
              '## Merge set (root + one nested copy)', '', '| Outcome | Archives |', '|---|---:|',
              '| Merge, then remove the nested entry | %d |' % len(planned),
              '| - of which fill at least one field | %d |' % sum(1 for r in planned if r['fills']),
              '| - of which fill nothing (the root holds it all; only the nested entry goes) | %d |' % sum(1 for r in planned if not r['fills']),
              '| Held for Sergei (see below) | %d |' % len(holds), '',
              'Fields filled in all: %d. Nested values dropped because the root holds another value: %d, in %d archives. '
              'Backups the apply keeps: %.1f GB (one full copy of each archive written).'
              % (sum(len(r['fills']) for r in planned), sum(len(r.get('dropped', {})) for r in planned),
                 sum(1 for r in planned if r.get('dropped')), backup_bytes / 1e9), '',
              '### Fields filled, per type (archives)', '', '| Field | Archives |', '|---|---:|']
    lines += ['| %s | %d |' % item for item in fields.most_common()] or ['| (none) | 0 |']
    lines += ['', '### Nested values dropped (the root holds a different value), per type', '', '| Field | Archives |', '|---|---:|']
    lines += ['| %s | %d |' % item for item in dropped.most_common()] or ['| (none) | 0 |']
    lines += ['', '## ZIP order (YACReader reads the first ComicInfo.xml in ZIP order, at any depth)', '',
              '| Layout | First copy in ZIP order | Archives |', '|---|---|---:|']
    for (layout, which), n in sorted(first.items()):
        if layout in ('root_and_nested', 'root_and_several_nested'):
            lines.append('| %s | %s | %d |' % (names[layout], which, n))
    lines += ['', 'Merge set: the root copy is the last entry of the archive in %d of %d (the app always writes its copy last).'
              % (sum(1 for r in merge if r.get('root_is_last_entry')), len(merge)),
              'Central-directory order and local-header order disagree on the first copy in %d archive(s).' % len(order_split),
              '', '## Held archives', '']
    lines += ['- `%s`: %s. Root: %s #%s, %s; nested: %s #%s.' % (
        relative(library, r['path']), r.get('reason'), text((r.get('root_fields') or {}).get('Series')) or '-',
        text((r.get('root_fields') or {}).get('Number')) or '-',
        '-'.join(text((r.get('root_fields') or {}).get(p)) for p in DATE if text((r.get('root_fields') or {}).get(p))) or 'no date',
        r.get('nested_series') or '-', r.get('nested_number') or '-') for r in holds] or ['(none)']
    odd = [r for r in records if r.get('layout') in ('unreadable', 'several_root', 'root_and_several_nested', 'several_nested')]
    odd += [r for r in nested_only if r.get('nested_error')]
    lines += ['', '## Other oddities', '']
    lines += ['- `%s`: %s%s' % (relative(library, r['path']), names.get(r['layout'], r['layout']),
              (': ' + (r.get('error') or r.get('nested_error'))) if r.get('error') or r.get('nested_error') else '') for r in odd] or ['(none)']
    lines += ['', '## Per archive (merge set)', '',
              'Fields filled, nested values dropped, the nested entry removed, and which copy YACReader reads today.', '',
              '| Archive | Outcome | Fields filled | Nested values dropped | Nested entry removed | YACReader reads today |',
              '|---|---|---|---|---|---|']
    for r in merge:
        cell = lambda value: str(value).replace('|', '\\|')
        lines.append('| %s | %s | %s | %s | %s | %s |' % (
            cell(relative(library, r['path'])), r.get('action'), cell(', '.join(r.get('fills') or {}) or '-'),
            cell(', '.join(r.get('dropped') or {}) or '-'),
            cell((r.get('remove') or {}).get('name')) if r.get('action') == 'merge' else '- (held)', r.get('first_in_zip') or '-'))
    lines += ['', '## Apply (only after Futaba\'s sample and Sergei\'s final OK)', '',
              'Needs the installed app to be a version with the nested merge (the tool refuses an older engine).', '',
              '```', apply_command(stem), '```', '']
    return '\n'.join(lines)


def apply_command(stem):
    python = default_engine().parent / 'runtime' / 'python' / 'python.exe'
    return '"%s" -B "%s" --apply "%s" --out "<new empty folder>"' % (python, CODE / 'tools' / 'nested_comicinfo_merge.py', stem.with_suffix('.json'))


# Apply ----------------------------------------------------------------------------------------------------------

def merge(app, entry, current):
    """Option d: the app's write path fills the root copy from the nested one and removes the nested entry.
    Returns (outcome, details)."""
    if (current.get('fills'), current.get('dropped'), current.get('remove')) != (entry.get('fills'), entry.get('dropped'), entry.get('remove')):
        return 'skipped', {'reason': 'changed since the dry run; run the dry run again'}
    with app.db() as con:
        row = con.execute('SELECT * FROM comics WHERE path=?', (entry['path'],)).fetchone()
    if row is None:
        return 'skipped', {'reason': 'not in the catalog yet'}
    row, attempt = dict(row), {}
    # What the plan relied on in the root copy, checked again under the write lock before any backup.
    expected = dict(entry['root_fields'])
    expected.update({tag: '' for tag in entry['fills'] if tag != 'Pages'})
    try:
        backup = app.write_metadata(row, {}, merge_nested=dict(entry['remove'], tags=list(entry['fills'])), expected=expected,
                                    history_source=HISTORY_SOURCE, writer='manual', verify_readback=True, attempt=attempt)
    except app.ArchiveChanged as exc:
        return 'skipped', {'reason': str(exc)}
    except Exception as exc:
        try:
            stat = os.stat(app.filesystem_path(entry['path']))
            changed = (stat.st_size, stat.st_mtime_ns) != (row['size'], row['mtime'])
        except OSError:
            changed = True
        return 'stopped' if changed else 'failed', {'reason': str(exc)[:500] or type(exc).__name__, 'backup': attempt.get('backup')}
    return 'written', {'fields': list(entry['fills']), 'removed': entry['remove']['name'], 'backup': backup}


ACTIONS = {'merge': merge}


def check_out_folder(out):
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise SystemExit('--out must be a new or empty folder.')
    out.mkdir(parents=True, exist_ok=True)


def apply(plan_path, out, engine, live):
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    if plan.get('kind') != PLAN_KIND or plan.get('version') != PLAN_VERSION:
        raise SystemExit('Not a nested ComicInfo merge plan of this version.')
    out = Path(out)
    check_out_folder(out)
    os.environ['COMICS_META_STATE_ROOT'] = str(live)  # Before the app's modules are imported.
    sys.path.insert(0, str(engine))
    import app
    if Path(os.path.abspath(app.STATE_ROOT)) != Path(os.path.abspath(live)) or Path(app.__file__).resolve().parent != Path(engine).resolve():
        raise SystemExit('The app modules did not load from the engine and live state given.')
    if not hasattr(app, 'merge_comicinfo') or 'merge_nested' not in introspect.signature(app.write_metadata).parameters:
        raise SystemExit('This app version has no nested merge. Install the version that has it, then apply.')
    import library_lock
    if library_lock.identity(app.live_root() or '') != library_lock.identity(plan['library']):
        raise SystemExit('The plan was made for another library than the app is using.')
    counts = Counter()
    with open(out / 'results.jsonl', 'a', encoding='utf-8') as results:
        for entry in plan['entries']:
            action = ACTIONS.get(entry.get('action'))
            if action is None:
                counts['held'] += 1  # Held in the dry run: never written.
                continue
            path = Path(entry['path'])
            if path.with_name(path.name + '.metadata-tmp').exists():
                outcome, details = 'skipped', {'reason': 'the app is writing this comic now'}
            else:
                try:
                    current = inspect(app, path)
                except Exception as exc:
                    current = {'layout': 'unreadable', 'error': str(exc)[:200]}
                if current.get('layout') != 'root_and_nested' or current.get('action') != entry['action']:
                    outcome, details = 'skipped', {'reason': 'no longer one root and one nested copy, or now held'}
                else:
                    outcome, details = action(app, entry, current)
            counts[outcome] += 1
            results.write(json.dumps({'path': entry['path'], 'action': entry['action'], 'outcome': outcome, **details},
                                     ensure_ascii=False) + '\n')
            results.flush()
            print(outcome, path.name, flush=True)
            if outcome == 'stopped':
                break  # The archive may have been written but did not verify: stop for inspection, backup kept.
    (out / 'summary.json').write_text(json.dumps(dict(counts), indent=1), encoding='utf-8')
    print('Done:', dict(counts))
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--report', help='dry run: the .md to write (the .csv and .json go beside it)')
    parser.add_argument('--library', help='dry run: library folder (default: the live config\'s)')
    parser.add_argument('--apply', help='apply this plan (.json from a dry run)')
    parser.add_argument('--out', help='apply: a new or empty folder for the results')
    parser.add_argument('--engine', default=str(default_engine()), help='apply: the app engine folder (default: the installed app)')
    parser.add_argument('--live', default=str(default_live()), help='the live state folder (default: %%LOCALAPPDATA%%\\ComicsMeta)')
    args = parser.parse_args(argv)
    if args.apply:
        if not args.out:
            parser.error('--apply needs --out')
        apply(args.apply, args.out, Path(args.engine), Path(args.live))
        return
    if not args.report:
        parser.error('give --report for a dry run, or --apply with --out')
    sys.path.insert(0, str(CODE))
    import app  # This checkout's merge rule and parser; the dry run opens no catalog.
    library = args.library or live_library(Path(args.live))
    if not library:
        raise SystemExit('No library folder configured; give --library.')
    dry_run(app, library, args.report, progress=lambda n: print('checked', n, file=sys.stderr, flush=True))


if __name__ == '__main__':
    main()
