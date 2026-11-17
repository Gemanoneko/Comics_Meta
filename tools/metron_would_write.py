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

--tagged measures precision instead (2026-11-17, options 3 and 4): it asks comics another tool tagged with a ComicVine
issue id (ComicInfo cites neither Metron nor GCD) as bare files, the identity taken from the filename alone, and for
yearless with the year hidden too (filename_year_formats and folder_year off, so the year cannot come back). A match
is right when the Metron issue's cv_id is the tag's ComicVine id. Writes <out>/tagged.jsonl and the counts in
summary.json; yearless counts are split into comics whose name and folder carry no year ("natural") and comics whose
year was hidden ("hidden").

A Metron 429 waits out Metron's own retry time (at most --max-wait seconds) and asks the same comic once more; a
second 429 in a row, a longer wait, or any other Metron error stops the run.
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
OURS = re.compile(r'metron|comics\.org|grand comics database', re.I)
CV_WEB = re.compile(r'comicvine\.gamespot\.com/\S*?4000-(\d+)', re.I)
CV_NOTES = re.compile(r'(?:\bIssue ID\s*:?\s*|CVDB)(\d+)', re.I)
METRON_ISSUE = re.compile(r'metron\.cloud/issue/(\d+)/')
MIN_SPACING = 8.0
BURST_KEEP = 10


def comicvine_id(old):
    """The ComicVine issue id another tool tagged the comic with, or None (never for a Metron- or GCD-written one)."""
    web, notes = str(old.get('Web') or ''), str(old.get('Notes') or '')
    if OURS.search(web + ' ' + notes):
        return None
    found = CV_WEB.search(web)
    if not found and re.search(r'comic\s*vine|CVDB', notes, re.I):
        found = CV_NOTES.search(notes)
    return found.group(1) if found else None


def judge(tag_id, old, detail):
    """right/wrong by Metron's cv_id; without one, right_no_cv_id when the number agrees and the cover year is within
    one year of the tag's Year (the 2026-10-26 fallback), else wrong_no_cv_id."""
    cv = detail.get('cv_id')
    if cv not in (None, '', 0):
        return 'right' if str(cv) == str(tag_id) else 'wrong'
    import research
    year = str(detail.get('cover_date') or '')[:4]
    agrees = (research.issue_number(detail.get('number')) == research.issue_number(old.get('Number') or '')
              and year.isdigit() and str(old.get('Year') or '').isdigit() and abs(int(year) - int(old['Year'])) <= 1)
    return 'right_no_cv_id' if agrees else 'wrong_no_cv_id'


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
    parser.add_argument('--tagged', action='store_true', help='precision on ComicVine-tagged comics asked as bare files')
    parser.add_argument('--max-wait', type=int, default=900, help='longest wait for a 429 retry time, in seconds')
    args = parser.parse_args(argv)
    if args.tagged and args.rule == 'metron_spellings':
        raise SystemExit('--tagged measures collection_label and yearless')
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
    # --tagged yearless hides the year, so the filename-date and folder-year rules must not find it again.
    asked_with = dict(defaults, **{args.rule: True})
    if args.tagged and args.rule == 'yearless':
        asked_with.update(filename_year_formats=False, folder_year=False)

    def applies(row, old):
        switches.update(defaults)
        default = metron.identity(row, old)
        switches[args.rule] = True
        found = metron.identity(row, old)
        if args.rule == 'metron_spellings':
            return bool(found and metron.spelling_variants(found[0]))
        return bool(found and found[3] == args.rule and (not default or default[3] != args.rule))

    def tagged(r, old):
        """A tagged comic as the bare file the rule is for, or None."""
        from filename_identity import parse_name
        import year_hints
        tag = comicvine_id(old)
        if not tag:
            return None
        series, number, year = parse_name(r['path'])
        natural = not (year or year_hints.filename_year(r['path']) or year_hints.folder_year(r['path']))
        row = {'path': r['path'], 'series': series, 'number': number, 'year': '' if args.rule == 'yearless' else year}
        if not coverage_priority.language_eligible(row, old):
            return None
        switches.update(asked_with)
        found = metron.identity(row, {})
        if not found or found[3] != args.rule:
            return None
        return {'row': row, 'old': old, 'ask': {}, 'tag': tag, 'natural': natural}

    with app.db() as con:
        rows = con.execute("SELECT path,series,number,year,metadata FROM comics WHERE status!='absent'").fetchall()
    pool = []
    for r in rows:
        try:
            old = json.loads(r['metadata'] or '{}') or {}
        except ValueError:
            continue
        if not isinstance(old, dict):
            continue
        if args.tagged:
            entry = tagged(r, old)
            if entry:
                pool.append(entry)
            continue
        if CITES.search(str(old.get('Web') or '') + ' ' + str(old.get('Notes') or '')):
            continue
        row = {'path': r['path'], 'series': r['series'], 'number': r['number'], 'year': r['year']}
        if coverage_priority.language_eligible(row, old) and applies(row, old):
            pool.append({'row': row, 'old': old, 'ask': old})
    switches.update(asked_with)
    random.Random(20261117).shuffle(pool)
    if args.tagged and args.rule == 'yearless':
        pool.sort(key=lambda entry: not entry['natural'])  # Comics with no year anywhere first: the rule's own pool.
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
    covers = {'tried': 0}
    if args.offline:
        metron.verified_cover = lambda path, url: {'comparison': 'not_run', 'page': 0}
    else:
        compare = metron.verified_cover

        def verified_cover(path, url):
            covers['tried'] += 1
            return compare(path, url)
        metron.verified_cover = verified_cover

    def ask(row, old):
        """metron.lookup, once more after a 429 once Metron's own retry time has passed."""
        for attempt in (1, 2):
            try:
                return metron.lookup(row, old)
            except ProviderDeferred:
                try:
                    now = json.loads((state / 'data' / 'metron-status.json').read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    raise
                wait = now.get('retry_at', 0) - time.time() + 5
                if now.get('http_status') != 429 or attempt == 2 or wait > args.max_wait:
                    raise
                used['backoffs'] = used.get('backoffs', 0) + 1
                print('429: waiting %d s' % max(wait, 61), flush=True)
                time.sleep(max(wait, 61))  # At least a whole rolling minute.

    stopped, writes, asked, outcomes = None, [], 0, {}
    with (out / ('tagged.jsonl' if args.tagged else 'checked.jsonl')).open('w', encoding='utf-8') as checked:
        for item in sample:
            row, old, ask_old = item['row'], item['old'], item['ask']
            entry = {'path': row['path'], 'identity': metron.identity(row, ask_old)}
            if args.tagged:
                entry.update(tag_cv_id=item['tag'], natural=item['natural'], tag_series=old.get('Series'),
                             tag_number=old.get('Number'), tag_year=old.get('Year'))
            covers['tried'] = 0
            try:
                result = ask(row, ask_old)
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
            entry['covers_compared'] = covers['tried']
            # Only a match this rule made counts: a match today's rules make on their own (Metron added the issue
            # since the last ask, or --offline skipped the cover check that refused it) is not this rule's write.
            ours = bool(result) and (result.get('name_spelling') if args.rule == 'metron_spellings' else result.get('match_rule') == args.rule)
            if args.tagged:
                issue = METRON_ISSUE.search(str(result['fields'].get('Web') or '')) if ours else None
                if issue:
                    detail = request('issue/' + issue.group(1) + '/')  # Cached by the lookup itself.
                    entry.update(outcome=judge(item['tag'], old, detail), metron_cv_id=detail.get('cv_id'),
                                 metron_number=detail.get('number'), metron_cover_date=detail.get('cover_date'),
                                 metron_series=(detail.get('series') or {}).get('name'))
                else:
                    entry['outcome'] = ('matched_by_todays_rules' if result else
                                        'refused_after_cover' if covers['tried'] else 'refused_before_cover')
            else:
                useful = ours and source_scheduling.useful(result, old)
                entry['outcome'] = ('would_write' if useful else 'verified_nothing_new' if ours
                                    else 'matched_by_todays_rules' if result else 'no_match')
            if result:
                fields = result['fields']
                entry.update(match_rule=result.get('match_rule'), name_spelling=result.get('name_spelling'),
                             cover_match=result.get('cover_match'), web=fields.get('Web'))
                if not args.tagged and entry['outcome'] == 'would_write':
                    writes.append({'path': row['path'], 'match_rule': result.get('match_rule'),
                                   'name_spelling': result.get('name_spelling') or '', 'metron_issue': fields.get('Web'),
                                   'series': fields.get('Series'), 'number': fields.get('Number'), 'year': fields.get('Year'),
                                   'format': fields.get('Format') or '', 'cover_match': json.dumps(result.get('cover_match')),
                                   'fills': ' '.join(sorted(k for k, v in fields.items() if v and not old.get(k)))})
            key = entry['outcome'] if not args.tagged or args.rule != 'yearless' else \
                ('natural ' if item['natural'] else 'hidden ') + entry['outcome']
            outcomes[key] = outcomes.get(key, 0) + 1
            checked.write(json.dumps(entry, ensure_ascii=False) + '\n')
            checked.flush()
    if not args.tagged:
        with (out / 'would-write.csv').open('w', encoding='utf-8', newline='') as handle:
            columns = ['path', 'match_rule', 'name_spelling', 'metron_issue', 'series', 'number', 'year', 'format', 'cover_match', 'fills']
            writer = csv.DictWriter(handle, columns)
            writer.writeheader()
            writer.writerows(writes)
    summary = {'rule': args.rule, 'tagged': args.tagged, 'pool': len(pool), 'sample': len(sample), 'asked': asked,
               'outcomes': dict(sorted(outcomes.items())), 'metron_requests': used['requests'],
               'backoffs_429': used.get('backoffs', 0), 'stopped': stopped, 'offline': args.offline}
    if args.tagged:
        summary['natural_in_pool'] = sum(1 for entry in pool if entry['natural'])
    else:
        summary['would_write'] = len(writes)
    (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary))
    return summary


if __name__ == '__main__':
    main()
