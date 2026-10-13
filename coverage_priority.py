"""Bounded first-write priority; source eligibility and write verification stay unchanged."""
import hashlib
import json
import re
from pathlib import Path
import app
import discovery_state
import research
import source_scheduling

PROBE_LIMIT = 256


def path_key(path):
    text = str(path)
    if text.startswith('\\\\?\\UNC\\'):
        text = '\\\\' + text[8:]
    elif text.startswith('\\\\?\\'):
        text = text[4:]
    return text.casefold()


def written_paths(con):
    # History is inserted after verified temporary XML/pages/CRC, replacement
    # and final readable metadata. Catalog status alone is not write history.
    return {path_key(row[0]) for row in con.execute('SELECT DISTINCT path FROM history')}


def pending_paths():
    import worker
    paths = set()
    for _, item in worker.tickets():
        if item.get('state') not in ('pending', 'running', 'needs_attention'):
            continue
        plan = json.loads(Path(item['plan']).read_text(encoding='utf-8'))
        paths.update(path_key(entry['path']) for entry in plan['entries'] if entry.get('action') == 'write')
    return paths


def language_eligible(row, old):
    language = str(old.get('LanguageISO') or '').strip().lower().replace('_', '-').split('-')[0]
    if language and language not in ('en', 'eng', 'english'):
        return False
    return not re.search(r'\((?:fr|french|de|german|es|spanish|it|italian|ru|russian|jp|japanese)\)', Path(row['path']).name, re.I)


def saved_evidence(path):
    evidence = research.CACHE / ('evidence-' + hashlib.sha256(str(path).encode()).hexdigest() + '.json')
    return json.loads(evidence.read_text(encoding='utf-8')) if evidence.exists() else {}


def lookup_flags(row, previous, statuses, version, saved, now):
    signature = [row['size'], row['mtime']]
    new_leads = saved.get('reverse_image_signature') == signature and previous.get('cover_leads') != saved.get('reverse_image_matches')
    metron = (saved.get('verified_evidence') or {}).get('result', {})
    upgrade = metron.get('provider') == 'Metron' and metron.get('metadata_version', 0) < 2 and previous.get('metron_metadata_version', 0) < 2
    if write_retry_waiting(previous, signature, now):
        return False, new_leads, upgrade
    import in_book
    # F24: a comic held for its ComicVine check on this archive and matcher is passed
    # again only to ask ComicVine (automatic.discover wait_only; Metron too when its own
    # schedule allows). Source entries carried from its first held pass are never re-run
    # there, so an old error would make it due at every folder pass. Its hold retry,
    # ComicVine answering and new cover leads still make it due.
    schedule = previous
    if isinstance(previous.get('hold'), dict) and previous.get('signature') == signature and previous.get('version') == version:
        schedule = {key: value for key, value in previous.items() if key != 'source_schedule'}
    # A saved cover reading that agrees with the filename writes without waiting
    # for the comic's ordinary research retry.
    due = (upgrade or in_book.ready(row, saved, previous) or comicvine_answered_since_hold(previous, statuses, now)
           or source_scheduling.due(schedule, signature, version, statuses, new_leads, now))
    return due, new_leads, upgrade


def write_retry_waiting(previous, signature, now):
    """F23: a planned write to this unchanged archive did not happen (it failed, or the
    archive's ComicInfo had changed); the comic waits for its retry instead of being
    planned again, and failing again, at every folder pass. F29: after repeated failed
    writes the wait grows, then automatic retries stop until the archive changes."""
    if previous.get('outcome') not in discovery_state.WRITE_NOT_DONE or previous.get('signature') != signature:
        return False
    return previous.get('retry_at', 0) > now or discovery_state.write_retries_stopped(previous, signature)


def comicvine_answered_since_hold(previous, statuses, now):
    """F18: a comic held for its ComicVine check is due once ComicVine has answered
    any request after that hold, instead of waiting out its growing hold interval.

    Only after the comic's own ComicVine wait has ended: a comic whose own request
    failed (an hour's wait) must not re-trigger the shared pause on every success.
    A hold with no known end (an empty answer, which is cached, or a missing key)
    keeps its daily retry rather than being re-run after every answer."""
    hold = previous.get('hold')
    comicvine = (statuses or {}).get('comicvine') or {}
    return (isinstance(hold, dict) and 0 < hold.get('wait_end', 0) <= now and comicvine.get('status') == 'available'
            and comicvine.get('checked_at', 0) > hold.get('at', float('inf')))


def metron_untried(row, previous):
    """Metron can search this comic (series, number, year) and has not tried this archive yet."""
    try:
        old = json.loads(row.get('metadata') or '{}')
    except ValueError:
        return False
    old = old if isinstance(old, dict) else {}
    series, number = research.query_identity(row, old)
    if not (series and number and (old.get('Year') or row.get('year'))):
        return False
    same = previous.get('signature') == [row['size'], row['mtime']]
    return not (same and 'Metron' in (previous.get('source_schedule') or {}))


def order_rows(rows, checked, written, pending, coverage_only=False, evidence=None):
    """Highest yield first: first updates; then comics the in-book tier can write
    now; then comics Metron can search but has not tried; missing metadata before
    already-tagged; then the earlier research-state order."""
    import in_book
    rows = [row for row in rows if path_key(row['path']) not in pending and
            (not coverage_only or path_key(row['path']) not in written)]
    evidence = evidence or (lambda path: saved_evidence(Path(path)))
    def rank(row):
        previous = checked.get(row['path'], {})
        return (path_key(row['path']) in written,
                not in_book.ready(row, evidence(row['path']), previous),
                not metron_untried(row, previous),
                row.get('status') != 'missing',
                bool(previous) and previous.get('signature') == [row['size'], row['mtime']],
                previous.get('outcome') not in ('web_issue_found', 'publisher_issue_found', 'current'),
                row['path'])
    return sorted(rows, key=rank)


_indexed = set()


def prepare_probe(con):
    """Indexed lookups for the bounded catalog probe.

    The probe used to join every comic against a materialized history list with
    no index (13.8 s per 256-row probe on a 60,000-comic test catalog). History
    paths, normalized as before, now go into a keyed temporary table, and an
    additive case-insensitive path index serves the cursor order (0.02 s)."""
    if str(app.DATA) not in _indexed:
        con.execute('CREATE INDEX IF NOT EXISTS comics_path_nocase ON comics(path COLLATE NOCASE)')
        _indexed.add(str(app.DATA))
    con.execute('CREATE TEMP TABLE IF NOT EXISTS written_history(path TEXT PRIMARY KEY COLLATE NOCASE)')
    con.execute('DELETE FROM temp.written_history')
    con.execute('''INSERT OR IGNORE INTO temp.written_history SELECT CASE WHEN substr(path,1,8)=? THEN ?||substr(path,9)
        WHEN substr(path,1,4)=? THEN substr(path,5) ELSE path END FROM history''', ('\\\\?\\UNC\\', '\\\\', '\\\\?\\'))


def firstpass_folder(root, due, state, statuses, version, now):
    """Probe existing catalog rows only; checkpoint waiting rows before refining."""
    pending = pending_paths()
    with app.db() as con:
        discovery_state.initialize(con)
        key = {'history':con.execute('SELECT MAX(id) FROM history').fetchone()[0],
               'catalog':con.execute('SELECT MAX(id) FROM comics').fetchone()[0],
               'due':hashlib.sha256(json.dumps(sorted(due)).encode()).hexdigest(),
               'pending':sorted(pending),
               'inventory':[state.get('root'),state.get('inventoried_at'),len(state.get('folders',{}))],
               'cover_leads':state.get('coverage_cover_epoch'),
               'providers':{name:[value.get('status'),value.get('retry_at',0)] for name,value in statuses.items()}}
        if state.get('coverage_snapshot') == key and state.get('coverage_recheck_at',0) > now:
            state['coverage_pending'] = False
            return None
        if not state.get('coverage_cursor'):
            state['coverage_probe_key'] = key
            state['coverage_retry_at'] = now + 60
        written = written_paths(con)
        scope, args = app.scope_filter(root)
        # Normalized history (legacy Windows extended paths and manual writes
        # included) is a keyed table, so each comic is one indexed lookup.
        prepare_probe(con)
        rows = con.execute('''SELECT c.*,d.value AS discovery_value FROM comics c
            LEFT JOIN discovery_records d ON c.path=d.path
            WHERE NOT EXISTS(SELECT 1 FROM temp.written_history w WHERE w.path=c.path)
            AND c.status NOT IN ('absent','error','corrupted','unsupported')
            AND lower(substr(c.path,-4))='.cbz' AND ''' + scope.replace('path', 'c.path') + '''
            AND c.path>? COLLATE NOCASE ORDER BY c.path COLLATE NOCASE LIMIT ?''',
            (*args, state.get('coverage_cursor', ''), PROBE_LIMIT)).fetchall()
    cursor = state.get('coverage_cursor', '')
    for record in rows:
        row = dict(record)
        path = Path(row['path'])
        if str(path.parent) in due and path_key(path) not in pending and path_key(path) not in written:
            previous = json.loads(row['discovery_value']) if row['discovery_value'] else {}
            retries = [previous.get('retry_at',0), *(a.get('next_at',0) for a in previous.get('source_schedule',{}).values())]
            state['coverage_retry_at'] = min([state.get('coverage_retry_at',now+60), *(t for t in retries if t > now)])
            old = json.loads(row['metadata'])
            if language_eligible(row, old):
                saved = saved_evidence(path)
                if lookup_flags(row, previous, statuses, version, saved, now)[0]:
                    # Leave the candidate in the probe until discovery either
                    # writes it or records its normal retry window.
                    state.update(coverage_cursor=cursor, coverage_pending=False)
                    return str(path.parent)
        cursor = row['path']
    state['coverage_pending'] = len(rows) == PROBE_LIMIT
    if state['coverage_pending']:
        state['coverage_cursor'] = cursor
    else:
        state.pop('coverage_cursor', None)
        if state.get('coverage_probe_key') != key:
            # Keep advancing while inventory grows; restart only at the end
            # so a new folder before the cursor cannot be missed or starve it.
            state['coverage_pending'] = True
        else:
            state['coverage_snapshot'] = key
            state['coverage_recheck_at'] = state.get('coverage_retry_at',now+60)
    return None
