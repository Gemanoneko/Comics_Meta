"""Read-only "would write" listing for one Metron matching switch (Sergei 2026-11-17, options 2 and 3; also B3).

    python -B tools/metron_would_write.py --rule collection_label --out C:\\Temp\\cmo-would-write [--limit 200]
        [--max-requests 300] [--floor 1000] [--offline] [--live <state folder>]

What it does:
1. Copies the live catalog through a read-only SQLite backup into <out>/state (with config.json). Metron answers
   it fetches are cached there, never in the app's own catalog.
2. Picks the comics no source has identified (ComicInfo Web/Notes cite none of Metron, GCD and ComicVine) that the
   rule can search and today's defaults cannot (metron_spellings: comics whose Series has another spelling).
3. Runs the app's own Metron lookup with that one switch on, with every identity check and the cover check.
4. Writes <out>/would-write.csv (one row per comic the rule would write, for Futaba's sample) and
   <out>/checked.jsonl (every comic asked, with its outcome).

It writes nothing to any comic and nothing under the live state folder or the library. Metron requests are paced
at least 8 s apart, wait out a nearly used burst minute, stop at --max-requests, stop before Metron's shared daily
remaining falls to --floor (the app needs the rest), and stop at the first Metron error or rate limit.
--offline uses cached Metron answers only (no request, no cover download; the cover stage is then not run).
"""
import argparse
import csv
import json
import os
import random
import re
import sys
import time
from pathlib import Path

RULES = {'collection_label': 'Option 3: "Vol N"/"vNN"/"Book N" plus a year as issue N of a collection series',
         'metron_spellings': 'Option 2: leading "The", "&"/"and", trailing "(YYYY)" in the Series',
         'yearless': 'B3: no year at all (pilot only; switch stays off)'}
CODE = Path(__file__).resolve().parents[1]
CITES = re.compile(r'metron|comics\.org|grand comics database|comicvine', re.I)
MIN_SPACING = 8.0
BURST_KEEP = 10


def check_out_folder(out, live, library):
    """Refuse an output folder inside the live state folder or the library."""
    out = Path(os.path.abspath(out))
    for root, what in ((live, 'the live state folder'), (library, 'the library')):
        if root and (out == Path(os.path.abspath(root)) or Path(os.path.abspath(root)) in out.parents):
            raise SystemExit('--out must not be inside ' + what + ': ' + str(out))
    return None


def snapshot(live, out):
    import shutil
    import sqlite3
    state = out / 'state'
    (state / 'data').mkdir(parents=True, exist_ok=False)
    source = sqlite3.connect('file:' + str(live / 'data' / 'catalog.sqlite').replace('\\', '/') + '?mode=ro', uri=True, timeout=30)
    target = sqlite3.connect(str(state / 'data' / 'catalog.sqlite'))
    try:
        source.backup(target)
    finally:
        source.close()
        target.close()
    shutil.copy2(live / 'config.json', state / 'config.json')
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--rule', required=True, choices=sorted(RULES))
    parser.add_argument('--out', required=True, help='a new, empty folder')
    parser.add_argument('--live', default=str(Path(os.environ.get('LOCALAPPDATA', '')) / 'ComicsMeta'))
    parser.add_argument('--limit', type=int, default=200, help='comics to ask (random sample, fixed seed)')
    parser.add_argument('--max-requests', type=int, default=300)
    parser.add_argument('--floor', type=int, default=1000, help="stop when Metron's daily remaining reaches this")
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args(argv)
    live, out = Path(args.live), Path(args.out)
    config = json.loads((live / 'config.json').read_text(encoding='utf-8'))
    automatic = config.get('automatic') or {}
    check_out_folder(out, live, automatic.get('library_root') or automatic.get('root'))
    if out.exists() and any(out.iterdir()):
        raise SystemExit('--out must be a new, empty folder')
    out.mkdir(parents=True, exist_ok=True)
    state = snapshot(live, out)
    os.environ['COMICS_META_STATE_ROOT'] = str(state)  # Before the app's modules are imported.
    sys.path.insert(0, str(CODE))
    import app, metron, pipeline_config, coverage_priority, source_scheduling
    from provider_wait import ProviderDeferred
    if Path(os.path.abspath(app.STATE_ROOT)) != Path(os.path.abspath(state)):
        raise SystemExit('state root did not move to the snapshot; nothing was asked')

    switches = dict(pipeline_config.MATCHING_DEFAULTS)
    defaults = dict(switches)
    pipeline_config.matching = lambda name: switches[name]

    def applies(row, old):
        switches.update(defaults)
        default = metron.identity(row, old)
        switches[args.rule] = True
        found = metron.identity(row, old)
        if args.rule == 'metron_spellings':
            return bool(found and metron.spelling_variants(found[0]))
        return bool(found and found[3] == args.rule and (not default or default[3] != args.rule))

    with app.db() as con:
        rows = con.execute("SELECT path,series,number,year,metadata FROM comics WHERE status!='absent'").fetchall()
    pool = []
    for r in rows:
        try:
            old = json.loads(r['metadata'] or '{}') or {}
        except ValueError:
            continue
        if not isinstance(old, dict) or CITES.search(str(old.get('Web') or '') + ' ' + str(old.get('Notes') or '')):
            continue
        row = {'path': r['path'], 'series': r['series'], 'number': r['number'], 'year': r['year']}
        if coverage_priority.language_eligible(row, old) and applies(row, old):
            pool.append((row, old))
    switches.update(defaults)
    switches[args.rule] = True
    random.Random(20261117).shuffle(pool)
    sample = pool[:args.limit]

    used = {'requests': 0, 'last': 0.0}
    original = metron.request

    def status():
        found = []
        for path in (state / 'data' / 'metron-status.json', live / 'data' / 'metron-status.json'):
            try:
                found.append(json.loads(path.read_text(encoding='utf-8')))
            except (OSError, ValueError):
                pass
        return max(found, key=lambda s: s.get('checked_at', 0)) if found else {}

    class Offline(Exception):
        pass

    class Stop(Exception):
        pass

    def request(endpoint, **params):
        import urllib.parse
        key = 'metron:https://metron.cloud/api/' + endpoint + '?' + urllib.parse.urlencode(params)
        with app.db() as con:
            hit = con.execute('SELECT 1 FROM cache WHERE key=? AND fetched>?', (key, time.time() - 7 * 86400)).fetchone()
        if not hit:
            if args.offline:
                raise Offline()
            if used['requests'] >= args.max_requests:
                raise Stop('--max-requests reached')
            now = status()
            if (now.get('sustained') or {}).get('remaining', args.floor + 1) <= args.floor:
                raise Stop("Metron's daily remaining is at --floor")
            if (now.get('burst') or {}).get('remaining', BURST_KEEP + 1) <= BURST_KEEP:
                time.sleep(61)  # Metron's minute is rolling: wait it out rather than for its next slot.
            time.sleep(max(0.0, used['last'] + MIN_SPACING - time.time()))
            used['last'] = time.time()
            used['requests'] += 1
        return original(endpoint, **params)

    metron.request = request
    if args.offline:
        metron.verified_cover = lambda path, url: {'comparison': 'not_run', 'page': 0}
    stopped, writes, asked = None, [], 0
    with (out / 'checked.jsonl').open('w', encoding='utf-8') as checked:
        for row, old in sample:
            entry = {'path': row['path'], 'identity': metron.identity(row, old)}
            try:
                result = metron.lookup(row, old)
            except Offline:
                entry['outcome'] = 'needs_metron_request'
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
            # Only a match this rule made counts: a match today's rules make on their own (Metron added the issue
            # since the last ask, or --offline skipped the cover check that refused it) is not this rule's write.
            ours = bool(result) and (result.get('name_spelling') if args.rule == 'metron_spellings' else result.get('match_rule') == args.rule)
            useful = ours and source_scheduling.useful(result, old)
            entry['outcome'] = ('would_write' if useful else 'verified_nothing_new' if ours
                                else 'matched_by_todays_rules' if result else 'no_match')
            if result:
                fields = result['fields']
                entry.update(match_rule=result.get('match_rule'), name_spelling=result.get('name_spelling'),
                             cover_match=result.get('cover_match'), web=fields.get('Web'))
                if useful:
                    writes.append({'path': row['path'], 'match_rule': result.get('match_rule'),
                                   'name_spelling': result.get('name_spelling') or '', 'metron_issue': fields.get('Web'),
                                   'series': fields.get('Series'), 'number': fields.get('Number'), 'year': fields.get('Year'),
                                   'format': fields.get('Format') or '', 'cover_match': json.dumps(result.get('cover_match')),
                                   'fills': ' '.join(sorted(k for k, v in fields.items() if v and not old.get(k)))})
            checked.write(json.dumps(entry, ensure_ascii=False) + '\n')
    with (out / 'would-write.csv').open('w', encoding='utf-8', newline='') as handle:
        columns = ['path', 'match_rule', 'name_spelling', 'metron_issue', 'series', 'number', 'year', 'format', 'cover_match', 'fills']
        writer = csv.DictWriter(handle, columns)
        writer.writeheader()
        writer.writerows(writes)
    summary = {'rule': args.rule, 'pool': len(pool), 'sample': len(sample), 'asked': asked, 'would_write': len(writes),
               'metron_requests': used['requests'], 'stopped': stopped, 'offline': args.offline}
    (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary))
    return summary


if __name__ == '__main__':
    main()
