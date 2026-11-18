"""Read-only "would write" listing for VerseDB (2026-11-18), for Futaba's sample before the source goes on.

    python -B tools/versedb_would_write.py --out <new empty folder> [--limit 150] [--max-requests 150]
        [--offline] [--tagged] [--live <state folder>]

What it does (as tools/comicvine_would_write.py):
1. Copies the live catalog through a read-only SQLite backup into <out>/state (with config.json). VerseDB answers it
   fetches are cached there and its requests counted in that copy's ledger, never in the app's own catalog. The
   token (VERSEDB_TOKEN) is read from the live state and never printed or written.
2. Picks the comics the app would ask (versedb.lookup's own order): ComicInfo cites none of Metron, GCD, ComicVine
   and VerseDB, the language gate passes, the identity is one of VerseDB's rules (no-year only under `!BD`), and the
   comic's discovery record says Metron, GCD offline and the ComicVine name search (where switched on) found nothing.
3. Runs the app's own lookup on a seeded random sample, with every check including the cover.
4. Writes <out>/would-write.csv (one row per comic it would write, for Futaba's sample), <out>/checked.jsonl and
   <out>/summary.json.

--tagged measures precision instead: comics whose ComicInfo holds a Series and Number from Metron, GCD or ComicVine
(not VerseDB) are asked as bare files, the identity read from the filename alone. VerseDB has no other source's ids,
so a match is 'right' when its series name and number agree with the tag and 'check_by_hand' otherwise (an edition
or a renamed series); every accept is listed in tagged.jsonl for a look by eye.

Nothing is written to any comic, the live state folder or the library. Requests go through VerseDB's own pacing
(12 s apart, its rolling hourly allowance) and stop at --max-requests or at the first refusal, rate limit or error.
--offline uses cached answers only (no request, no cover download; the cover stage is reported as not run). Run it
while the app's VerseDB source is off (the default): the app does not see this copy's ledger, and both share
VerseDB's 300 an hour. Delete <out> afterwards: it holds a copy of the catalog.
"""
import argparse
import csv
import importlib.util
import json
import os
import random
import re
import sys
import time
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]
TRUTH = re.compile(r'metron|comics\.org|grand comics database|comic\s*vine|cvdb', re.I)
SEED = 20261118


def metron_tool():
    """tools/metron_would_write.py: its snapshot and output-folder check are reused."""
    spec = importlib.util.spec_from_file_location('metron_would_write', CODE / 'tools' / 'metron_would_write.py')
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def known_identity(old):
    """(Series, Number) another verified source wrote, or None (never one VerseDB wrote)."""
    cited = str(old.get('Web') or '') + ' ' + str(old.get('Notes') or '')
    if re.search(r'versedb', cited, re.I) or not TRUTH.search(cited):
        return None
    series, number = str(old.get('Series') or '').strip(), str(old.get('Number') or '').strip()
    return (series, number) if series and number else None


def judge(tag, fields):
    """'right' when VerseDB's series name and number agree with the tag; otherwise 'check_by_hand'."""
    import research, versedb
    same_series = versedb.fold_key(tag[0]) == versedb.fold_key(fields.get('Series'))
    same_number = research.issue_number(tag[1]) == research.issue_number(fields.get('Number') or '')
    return 'right' if same_series and same_number else 'check_by_hand'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--out', required=True, help='a new, empty folder')
    parser.add_argument('--live', default=str(Path(os.environ.get('LOCALAPPDATA', '')) / 'ComicsMeta'))
    parser.add_argument('--limit', type=int, default=150, help='comics to ask (random sample, fixed seed)')
    parser.add_argument('--max-requests', type=int, default=150, help='VerseDB API requests (covers not counted)')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--tagged', action='store_true', help='precision on comics with a known identity, asked as bare files')
    args = parser.parse_args(argv)
    shared = metron_tool()
    live, out = Path(args.live), Path(args.out)
    shared.check_out_folder(out, live, None)  # Before anything is read.
    live_config = json.loads((live / 'config.json').read_text(encoding='utf-8'))
    automatic_config = live_config.get('automatic') or {}
    shared.check_out_folder(out, live, automatic_config.get('library_root') or automatic_config.get('root'))
    if out.exists() and any(out.iterdir()):
        raise SystemExit('--out must be a new, empty folder')
    out.mkdir(parents=True, exist_ok=True)
    state = shared.snapshot(live, out)
    os.environ['COMICS_META_STATE_ROOT'] = str(state)  # Before the app's modules are imported.
    sys.path.insert(0, str(CODE))
    import app, coverage_priority, credential_store, source_scheduling, versedb
    from filename_identity import parse_name
    from provider_wait import ProviderDeferred
    if Path(os.path.abspath(app.STATE_ROOT)) != Path(os.path.abspath(state)):
        raise SystemExit('state root did not move to the snapshot; nothing was asked')

    snapshot_root = app.STATE_ROOT
    app.STATE_ROOT = live  # Only while the token is read (env files are resolved from the live state).
    try:
        secret = credential_store.setting(versedb.TOKEN, config=live_config)
    finally:
        app.STATE_ROOT = snapshot_root
    versedb.token = lambda: secret
    if not secret and not args.offline:
        raise SystemExit('no VERSEDB_TOKEN in the live state; nothing was asked')

    with app.db() as con:
        rows = con.execute("SELECT path,series,number,year,metadata FROM comics WHERE status!='absent'").fetchall()
        records = {r['path']: r['value'] for r in con.execute('SELECT path,value FROM discovery_records')}
    pool = []
    for r in rows:
        try:
            old = json.loads(r['metadata'] or '{}') or {}
        except ValueError:
            continue
        if not isinstance(old, dict):
            continue
        if args.tagged:
            tag = known_identity(old)
            if not tag:
                continue
            series, number, year = parse_name(r['path'])
            row = {'path': r['path'], 'series': series, 'number': number, 'year': year}
            if versedb.identity(row, {}) and coverage_priority.language_eligible(row, old):
                pool.append({'row': row, 'old': old, 'ask': {}, 'schedule': None, 'tag': tag})
            continue
        row = {'path': r['path'], 'series': r['series'], 'number': r['number'], 'year': r['year']}
        if versedb.cites(old) or not coverage_priority.language_eligible(row, old) or not versedb.identity(row, old):
            continue
        try:
            record = json.loads(records.get(str(Path(r['path']).resolve())) or records.get(r['path']) or '{}')
        except ValueError:
            continue
        schedule = record.get('source_schedule') or {}
        if versedb.after_misses(schedule) == 'asked':
            pool.append({'row': row, 'old': old, 'ask': old, 'schedule': schedule})
    random.Random(SEED).shuffle(pool)
    sample = pool[:args.limit]

    used = {'requests': 0, 'covers': 0}
    original_request, original_cover = versedb.request, versedb.verified_cover

    class Offline(Exception):
        pass

    class Stop(Exception):
        pass

    def request(path, **params):
        if versedb.cached(versedb.cache_key(path, params)) is versedb._MISSING:
            if args.offline:
                raise Offline()
            if used['requests'] >= args.max_requests:
                raise Stop('--max-requests reached')
            used['requests'] += 1
        return original_request(path, **params)

    def verified_cover(path, url):
        used['covers'] += 1
        if args.offline:
            return {'comparison': 'not_run', 'page': 0}
        return original_cover(path, url)

    versedb.request = request
    versedb.verified_cover = verified_cover

    stopped, writes, asked, outcomes = None, [], 0, {}
    with (out / ('tagged.jsonl' if args.tagged else 'checked.jsonl')).open('w', encoding='utf-8') as checked:
        for item in sample:
            row, old = item['row'], item['old']
            entry = {'path': row['path'], 'identity': versedb.identity(row, item['ask'])}
            if args.tagged:
                entry.update(tag_series=item['tag'][0], tag_number=item['tag'][1], tag_year=old.get('Year'), tag_web=old.get('Web'))
            covers_before = used['covers']
            try:
                result = versedb.lookup(row, item['ask'], item['schedule'])
            except Offline:
                entry['outcome'] = 'needs_versedb_request'
                checked.write(json.dumps(entry, ensure_ascii=False) + '\n')
                continue
            except (Stop, ProviderDeferred) as exc:
                stopped = str(exc)
                break
            except Exception as exc:  # One unreadable archive does not end the listing.
                entry.update(outcome='error', error=type(exc).__name__)
                checked.write(json.dumps(entry, ensure_ascii=False) + '\n')
                continue
            asked += 1
            entry['covers_compared'] = used['covers'] - covers_before
            if result:
                fields = result['fields']
                entry.update(match_rule=result['match_rule'], cover_match=result['cover_match'], web=fields.get('Web'),
                             fields=fields, name_search=result['name_search'])
            if args.tagged:
                entry['outcome'] = (judge(item['tag'], result['fields']) if result
                                    else 'refused_after_cover' if entry['covers_compared'] else 'refused_before_cover')
            else:
                useful = bool(result) and source_scheduling.useful(result, old)
                entry['outcome'] = 'would_write' if useful else 'verified_nothing_new' if result else 'no_match'
                if useful:
                    fields, search = result['fields'], result['name_search']
                    writes.append({'path': row['path'], 'match_rule': result['match_rule'], 'versedb_issue': fields.get('Web'),
                                   'series': fields.get('Series'), 'number': fields.get('Number'), 'year': fields.get('Year') or '',
                                   'title': fields.get('Title') or '', 'publisher': fields.get('Publisher') or '',
                                   'language': search.get('language') or '', 'matched_by': search.get('matched_by'),
                                   'cover_match': json.dumps(result['cover_match']),
                                   'fills': ' '.join(sorted(k for k, v in fields.items() if v and not old.get(k)))})
            outcomes[entry['outcome']] = outcomes.get(entry['outcome'], 0) + 1
            checked.write(json.dumps(entry, ensure_ascii=False) + '\n')
            checked.flush()
    if not args.tagged:
        with (out / 'would-write.csv').open('w', encoding='utf-8', newline='') as handle:
            columns = ['path', 'match_rule', 'versedb_issue', 'series', 'number', 'year', 'title', 'publisher', 'language',
                       'matched_by', 'cover_match', 'fills']
            writer = csv.DictWriter(handle, columns)
            writer.writeheader()
            writer.writerows(writes)
    summary = {'tagged': args.tagged, 'pool': len(pool), 'sample': len(sample), 'asked': asked,
               'outcomes': dict(sorted(outcomes.items())), 'versedb_requests': used['requests'],
               'covers_compared': used['covers'], 'stopped': stopped, 'offline': args.offline,
               'finished_at': time.strftime('%Y-%m-%d %H:%M:%S')}
    if not args.tagged:
        summary['would_write'] = len(writes)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary))
    return summary


if __name__ == '__main__':
    main()
