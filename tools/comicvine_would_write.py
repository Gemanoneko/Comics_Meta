"""Read-only "would write" listing for the ComicVine name search (2026-11-18), for Futaba's sample before it goes on.

    python -B tools/comicvine_would_write.py --out <new empty folder> [--limit 200] [--max-requests 150]
        [--offline] [--tagged] [--live <state folder>]

What it does:
1. Copies the live catalog through a read-only SQLite backup into <out>/state (with config.json), as
   tools/metron_would_write.py does. ComicVine answers it fetches are cached there and its requests are counted in
   that copy's ledger, never in the app's own catalog. The ComicVine key is read from the live state and never
   printed or written.
2. Picks the comics the app would ask (comicvine_search.lookup's own order): ComicInfo cites none of Metron, GCD and
   ComicVine, the language gate passes, the identity is one of the name search's rules, and the comic's discovery
   record says Metron and GCD offline (where switched on) answered it with no match.
3. Runs the app's own lookup on a seeded random sample: every identity check, the single-candidate rule, the cover
   check and the detail checks.
4. Writes <out>/would-write.csv (one row per comic it would write, for Futaba's sample), <out>/checked.jsonl (every
   comic asked, with its outcome) and <out>/summary.json.

--tagged measures precision instead: comics another tool tagged with a ComicVine issue id (ComicInfo cites neither
Metron nor GCD, and the tag is not one of this app's own ComicVine writes) are asked as bare files, the identity
read from the filename alone, and a match is right when its ComicVine issue id is the tag's. Writes
<out>/tagged.jsonl and the counts in summary.json.

It writes nothing to any comic and nothing under the live state folder or the library. Requests go through the
name search's own pacing (10 s apart, its hourly allowance per resource) and stop at --max-requests or at the first
refusal, rate limit or connection error. --offline uses cached answers only (no request, no cover download; the
cover stage is then reported as not run). Run it while the app's ComicVine name search is off (the default): the
app does not see this copy's ledger.
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
OWN_WRITES = re.compile(r'Automatic verified lookup: ComicVine|Automatic match: unique exact series', re.I)
SEED = 20261118


def metron_tool():
    """tools/metron_would_write.py: its snapshot, output-folder check and ComicVine tag reader are reused."""
    spec = importlib.util.spec_from_file_location('metron_would_write', CODE / 'tools' / 'metron_would_write.py')
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def tag_id(old, shared):
    """The ComicVine issue id another tool tagged the comic with, or None (never one of this app's own writes)."""
    if OWN_WRITES.search(str(old.get('Notes') or '')):
        return None
    return shared.comicvine_id(old)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--out', required=True, help='a new, empty folder')
    parser.add_argument('--live', default=str(Path(os.environ.get('LOCALAPPDATA', '')) / 'ComicsMeta'))
    parser.add_argument('--limit', type=int, default=200, help='comics to ask (random sample, fixed seed)')
    parser.add_argument('--max-requests', type=int, default=150, help='ComicVine API requests (covers not counted)')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--tagged', action='store_true', help='precision on ComicVine-tagged comics asked as bare files')
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
    import app, comicvine_search, coverage_priority, credential_store, source_scheduling
    from filename_identity import parse_name
    from provider_wait import ProviderDeferred
    if Path(os.path.abspath(app.STATE_ROOT)) != Path(os.path.abspath(state)):
        raise SystemExit('state root did not move to the snapshot; nothing was asked')

    snapshot_root = app.STATE_ROOT
    app.STATE_ROOT = live  # Only while the key is read (saved keys and env files are resolved from the live state).
    try:
        key = credential_store.setting('COMICVINE_API_KEY', config=live_config)
    finally:
        app.STATE_ROOT = snapshot_root
    app.api_key = lambda: key
    if not key and not args.offline:
        raise SystemExit('no ComicVine key in the live state; nothing was asked')

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
            tag = tag_id(old, shared)
            if not tag:
                continue
            series, number, year = parse_name(r['path'])
            row = {'path': r['path'], 'series': series, 'number': number, 'year': year}
            found = comicvine_search.identity(row, {})
            if found and found[3] in comicvine_search.RULES and coverage_priority.language_eligible(row, old):
                pool.append({'row': row, 'old': old, 'ask': {}, 'schedule': None, 'tag': tag})
            continue
        row = {'path': r['path'], 'series': r['series'], 'number': r['number'], 'year': r['year']}
        if comicvine_search.cites(old) or not coverage_priority.language_eligible(row, old):
            continue
        found = comicvine_search.identity(row, old)
        if not found or found[3] not in comicvine_search.RULES:
            continue
        try:
            record = json.loads(records.get(str(Path(r['path']).resolve())) or records.get(r['path']) or '{}')
        except ValueError:
            continue
        schedule = record.get('source_schedule') or {}
        if comicvine_search.after_misses(schedule) == 'asked':
            pool.append({'row': row, 'old': old, 'ask': old, 'schedule': schedule})
    random.Random(SEED).shuffle(pool)
    sample = pool[:args.limit]

    used = {'requests': 0, 'covers': 0}
    original_request, original_cover = comicvine_search.request, comicvine_search.verified_cover

    class Offline(Exception):
        pass

    class Stop(Exception):
        pass

    def request(resource, **params):
        import urllib.parse
        key_params = dict(params, format='json')
        try:
            hit = comicvine_search.cached(resource + '?' + urllib.parse.urlencode(sorted(key_params.items())))
        except app.ComicVineNotFound:
            hit = None
        if hit is comicvine_search._MISSING:
            if args.offline:
                raise Offline()
            if used['requests'] >= args.max_requests:
                raise Stop('--max-requests reached')
            used['requests'] += 1
        return original_request(resource, **params)

    def verified_cover(path, url):
        used['covers'] += 1
        if args.offline:
            return {'comparison': 'not_run', 'page': 0}
        return original_cover(path, url)

    comicvine_search.request = request
    comicvine_search.verified_cover = verified_cover

    stopped, writes, asked, outcomes = None, [], 0, {}
    with (out / ('tagged.jsonl' if args.tagged else 'checked.jsonl')).open('w', encoding='utf-8') as checked:
        for item in sample:
            row, old = item['row'], item['old']
            entry = {'path': row['path'], 'identity': comicvine_search.identity(row, item['ask'])}
            if args.tagged:
                entry.update(tag_cv_id=item['tag'], tag_series=old.get('Series'), tag_number=old.get('Number'), tag_year=old.get('Year'))
            covers_before = used['covers']
            try:
                result = comicvine_search.lookup(row, item['ask'], item['schedule'])
            except Offline:
                entry['outcome'] = 'needs_comicvine_request'
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
                             name_search=result['name_search'])
            if args.tagged:
                entry['outcome'] = (('right' if str(result['name_search']['issue_id']) == str(item['tag']) else 'wrong') if result
                                    else 'refused_after_cover' if entry['covers_compared'] else 'refused_before_cover')
            else:
                useful = bool(result) and source_scheduling.useful(result, old)
                entry['outcome'] = 'would_write' if useful else 'verified_nothing_new' if result else 'no_match'
                if useful:
                    fields = result['fields']
                    search = result['name_search']
                    writes.append({'path': row['path'], 'match_rule': result['match_rule'], 'comicvine_issue': fields.get('Web'),
                                   'series': fields.get('Series'), 'number': fields.get('Number'), 'year': fields.get('Year'),
                                   'volume': search.get('volume'), 'start_year': search.get('start_year'),
                                   'publisher': fields.get('Publisher') or '', 'cover_match': json.dumps(result['cover_match']),
                                   'fills': ' '.join(sorted(k for k, v in fields.items() if v and not old.get(k)))})
            outcomes[entry['outcome']] = outcomes.get(entry['outcome'], 0) + 1
            checked.write(json.dumps(entry, ensure_ascii=False) + '\n')
            checked.flush()
    if not args.tagged:
        with (out / 'would-write.csv').open('w', encoding='utf-8', newline='') as handle:
            columns = ['path', 'match_rule', 'comicvine_issue', 'series', 'number', 'year', 'volume', 'start_year',
                       'publisher', 'cover_match', 'fills']
            writer = csv.DictWriter(handle, columns)
            writer.writeheader()
            writer.writerows(writes)
    summary = {'tagged': args.tagged, 'pool': len(pool), 'sample': len(sample), 'asked': asked,
               'outcomes': dict(sorted(outcomes.items())), 'comicvine_requests': used['requests'],
               'covers_compared': used['covers'], 'stopped': stopped, 'offline': args.offline,
               'finished_at': time.strftime('%Y-%m-%d %H:%M:%S')}
    if not args.tagged:
        summary['would_write'] = len(writes)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary))
    return summary


if __name__ == '__main__':
    main()
