"""Per-comic problem reasons for the dashboard (Judy's failure-filter spec, Sergei 2026-10-13).

Every reason comes from the comic's discovery record, never from batch files or free text,
and counts only while the record still applies: its signature equals the comic's current
[size, mtime]. One reason per comic, the first that matches:

    write_stopped > write_failed > conflict > dead_link > held

write_stopped and held use the predicates the processing code itself uses
(discovery_state.write_retries_stopped, automatic.held_before).
"""
import json
import time
import threading
import app
import discovery_state

CODES = ('write_stopped', 'dead_link', 'conflict', 'write_failed', 'held')  # The page's filter order.
HELP = ('write_stopped', 'dead_link', 'conflict')
RETRYING = ('write_failed', 'held')
CONFLICT_FALLBACK = "ComicVine's series or issue number for this link differs from the file's."


def text(value):
    return ' '.join(str(value if value is not None else '').split())


def conflict_parts(record):
    """(issue id, ComicVine series, ComicVine number, file series, file number), each '' when unknown."""
    issue = record.get('conflict_issue') if isinstance(record.get('conflict_issue'), dict) else {}
    found = record.get('conflict_file') if isinstance(record.get('conflict_file'), dict) else {}
    volume = issue.get('volume') if isinstance(issue.get('volume'), dict) else {}
    return (text(issue.get('id')), text(volume.get('name')), text(issue.get('issue_number')),
            text(found.get('series')), text(found.get('number')))


def conflict_sentence(record):
    """Spec R3: the record's detail for a conflict, word for word the row's first sentence."""
    issue_id, cv_series, cv_number, series, number = conflict_parts(record)
    if all((issue_id, cv_series, cv_number, series, number)):
        return 'ComicVine issue ' + issue_id + ' is ' + cv_series + ' #' + cv_number + '; the file says ' + series + ' #' + number + '.'
    return CONFLICT_FALLBACK


def classify(record, signature):
    """The comic's one problem, as the page's `problem` object, or None."""
    signature = list(signature)
    if not isinstance(record, dict) or record.get('signature') != signature:
        return None  # Changed since: due again at the next pass, so no longer true.
    outcome = record.get('outcome')
    run = record.get('write_failures') if isinstance(record.get('write_failures'), dict) else {}
    count = run.get('count') if run.get('signature') == signature else None
    error = text(record.get('write_error'))[:300]
    if outcome in discovery_state.WRITE_NOT_DONE and discovery_state.write_retries_stopped(record, signature):
        return compact(code='write_stopped', count=count, limit=discovery_state.WRITE_FAILED_LIMIT, last_error=error)
    if outcome == 'write_failed':
        return compact(code='write_failed', count=count, limit=discovery_state.WRITE_FAILED_LIMIT, retry_at=record.get('retry_at') or 0,
                       last_error=error)
    if outcome == 'identity_conflict':
        issue_id, cv_series, cv_number, series, number = conflict_parts(record)
        return compact(code='conflict', issue_id=issue_id, cv_series=cv_series, cv_number=cv_number,
                       file_series=series, file_number=number)
    if record.get('dead_link'):
        return compact(code='dead_link', issue_id=text(record['dead_link']))
    import automatic
    if automatic.held_before(record, signature):
        hold = record['hold']
        return compact(code='held', retry_at=hold.get('next_try_at') or 0, cause=hold.get('cause'))
    return None


def compact(**values):
    return {key: value for key, value in values.items() if value not in (None, '')}


def candidates(con, root, search=''):
    """(path, record, signature) for live comics whose record may hold a problem."""
    discovery_state.initialize(con)
    scope, args = app.scope_filter(root)
    rows = con.execute('''SELECT c.path, c.size, c.mtime, d.value FROM comics c JOIN discovery_records d ON d.path=c.path
        WHERE c.status<>'absent' AND ''' + scope.replace('path', 'c.path') + ''' AND c.path LIKE ?
        AND (json_extract(d.value,'$.outcome') IN ('write_failed','write_skipped','identity_conflict')
             OR json_extract(d.value,'$.hold') IS NOT NULL OR json_extract(d.value,'$.dead_link') IS NOT NULL)''',
                       (*args, '%' + search + '%'))
    for path, size, mtime, value in rows:
        try:
            yield path, json.loads(value), [size, mtime]
        except ValueError:
            continue


def counts(root, connection=None):
    """Spec section 9.1: one count per code for the live root, plus the failure limit."""
    found = dict.fromkeys(CODES, 0)
    def scan(con):
        for _, record, signature in candidates(con, root):
            problem = classify(record, signature)
            if problem:
                found[problem['code']] += 1
    if connection is None:
        with app.db() as con:scan(con)
    else:
        scan(connection)
    found['limit'] = discovery_state.WRITE_FAILED_LIMIT
    return found


class CountsCache:
    """Reuse counts until another connection commits to this catalog.

    SQLite data_version is only comparable on the same connection. Keep that read
    connection across snapshot refreshes; serialize it because refresh threads rotate.
    A transaction gives the version check and scan a consistent database snapshot.
    """
    def __init__(self):
        self.connection=None;self.path=None;self.key=None;self.value=None;self.closed=False
        self.lock=threading.Lock()

    def get(self,root):
        with self.lock:
            if self.closed:raise RuntimeError('Problem count cache is closed.')
            path=(app.DATA/'catalog.sqlite').resolve()
            if self.connection is None or self.path!=path:
                if self.connection is not None:self.connection.close()
                # Snapshot refreshes run on successive threads; the lock owns access.
                import sqlite3
                with app.db() as con:discovery_state.initialize(con)
                self.connection=sqlite3.connect(path,check_same_thread=False,timeout=30)
                self.connection.row_factory=sqlite3.Row
                self.path=path;self.key=None
            con=self.connection
            con.execute('BEGIN')
            try:
                key=(str(root),con.execute('PRAGMA data_version').fetchone()[0])
                if self.key!=key:
                    self.value=counts(root,con)
                    self.key=key
                return dict(self.value)
            finally:
                con.rollback()

    def close(self):
        with self.lock:
            if self.connection is not None:self.connection.close()
            self.connection=None;self.key=None;self.closed=True


def paths_with(con, root, code, search=''):
    return [path for path, record, signature in candidates(con, root, search)
            if (classify(record, signature) or {}).get('code') == code]


def for_rows(con, rows):
    """{path: problem} for the catalog rows on one page of the list."""
    paths = [row['path'] for row in rows]
    if not paths:
        return {}
    discovery_state.initialize(con)
    records = {path: value for path, value in con.execute(
        'SELECT path,value FROM discovery_records WHERE path IN (%s)' % ','.join('?' * len(paths)), paths)}
    found = {}
    for row in rows:
        try:
            record = json.loads(records[row['path']]) if row['path'] in records else None
        except ValueError:
            record = None
        problem = classify(record, [row['size'], row['mtime']]) if record else None
        if problem:
            found[row['path']] = problem
    return found


def try_again(comic_id, now=None):
    """Spec R4: one more automatic write attempt for a comic whose writes stopped.

    Only while its record still applies and is stopped: the stop is cleared and the retry is
    due now; the failure count is kept, so one more failure stops it again. Otherwise nothing
    changes. Returns (changed, the comic's problem now)."""
    now = time.time() if now is None else now
    row = app.comic(comic_id)
    signature = [row['size'], row['mtime']]
    with app.db() as con:
        discovery_state.initialize(con)
        con.execute('BEGIN IMMEDIATE')
        found = con.execute('SELECT value FROM discovery_records WHERE path=?', (row['path'],)).fetchone()
        record = json.loads(found[0]) if found else None
        problem = classify(record, signature) if record else None
        if not problem or problem['code'] != 'write_stopped':
            return False, problem
        run = dict(record['write_failures'], stopped=False, try_again_at=now)
        record.update(write_failures=run, retry_at=now,
                      detail=('Try again requested after ' + str(run.get('count')) + ' failed attempts; one more attempt follows at the next pass.'
                              ' If it fails, automatic writes stop again until the file changes.'))
        con.execute('UPDATE discovery_records SET value=? WHERE path=?', (json.dumps(record, ensure_ascii=False), row['path']))
    return True, classify(record, signature)
