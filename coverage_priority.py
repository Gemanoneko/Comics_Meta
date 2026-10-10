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
    for ticket in worker.QUEUE.glob('*.json'):
        item = json.loads(ticket.read_text(encoding='utf-8'))
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
    return upgrade or source_scheduling.due(previous, signature, version, statuses, new_leads, now), new_leads, upgrade


def order_rows(rows, checked, written, pending, coverage_only=False):
    rows = [row for row in rows if path_key(row['path']) not in pending and
            (not coverage_only or path_key(row['path']) not in written)]
    return sorted(rows, key=lambda row: (
        path_key(row['path']) in written,
        bool(checked.get(row['path'])) and checked[row['path']].get('signature') == [row['size'], row['mtime']],
        checked.get(row['path'], {}).get('outcome') not in ('web_issue_found', 'publisher_issue_found', 'current'),
        row['path']))


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
        # Materialized distinct normalized history avoids a per-comic history
        # lookup and includes legacy Windows extended paths and manual writes.
        rows = con.execute('''WITH written AS (
            SELECT DISTINCT CASE WHEN substr(path,1,8)=? THEN ?||substr(path,9)
                WHEN substr(path,1,4)=? THEN substr(path,5) ELSE path END AS path FROM history)
            SELECT c.*,d.value AS discovery_value FROM comics c
            LEFT JOIN written w ON c.path=w.path COLLATE NOCASE
            LEFT JOIN discovery_records d ON c.path=d.path
            WHERE w.path IS NULL AND c.status NOT IN ('absent','error','corrupted','unsupported')
            AND lower(substr(c.path,-4))='.cbz' AND ''' + scope.replace('path', 'c.path') + '''
            AND c.path>? COLLATE NOCASE ORDER BY c.path COLLATE NOCASE LIMIT ?''',
            ('\\\\?\\UNC\\', '\\\\', '\\\\?\\', *args, state.get('coverage_cursor', ''), PROBE_LIMIT)).fetchall()
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
