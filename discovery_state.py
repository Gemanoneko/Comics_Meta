"""Per-file research state in SQLite, bounded by the folder being processed."""
import json
import time
from pathlib import Path
import app

WRITE_RETRY_SECONDS = 86400  # The ordinary daily research retry; a skipped write waits this long.
WRITE_NOT_DONE = ('write_skipped', 'write_failed')  # Outcomes of a planned write that did not happen.
# v0.1.3 review F29: waits after the 1st to 4th failed write on one unchanged archive.
# The next failure stops automatic retries until the archive changes.
WRITE_FAILED_BACKOFF_DAYS = (1, 2, 4, 7)
WRITE_FAILED_LIMIT = len(WRITE_FAILED_BACKOFF_DAYS) + 1


def initialize(con):
    con.execute('CREATE TABLE IF NOT EXISTS discovery_records(path TEXT PRIMARY KEY,value TEXT NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS discovery_settings(key TEXT PRIMARY KEY,value TEXT)')
    migrated=con.execute("SELECT value FROM discovery_settings WHERE key='legacy_migrated'").fetchone()
    if not migrated:
        legacy=app.DATA/'automatic.json'
        if legacy.exists():
            if legacy.stat().st_size>10*1024*1024:raise ValueError('Legacy research cache needs repair before migration.')
            records=json.loads(legacy.read_text(encoding='utf-8')).get('checked',{})
            con.executemany('INSERT OR IGNORE INTO discovery_records VALUES(?,?)',[(p,json.dumps(v,ensure_ascii=False)) for p,v in records.items()])
        con.execute("INSERT INTO discovery_settings VALUES('legacy_migrated','yes')")
    if not con.execute("SELECT value FROM discovery_settings WHERE key='provider_wait_migrated'").fetchone():
        from provider_wait import repair_old_getcomics_error
        repaired=0
        for row in con.execute("SELECT path,value FROM discovery_records WHERE value LIKE '%GetComics needs human verification or rejected access%'").fetchall():
            record=json.loads(row['value'])
            if repair_old_getcomics_error(record):
                con.execute('UPDATE discovery_records SET value=? WHERE path=?',(json.dumps(record,ensure_ascii=False),row['path']))
                repaired+=1
        con.execute("INSERT INTO discovery_settings VALUES('provider_wait_migrated',?)",(str(repaired),))


def load(folder):
    with app.db() as con:
        initialize(con)
        scope,args=app.scope_filter(folder)
        rows=con.execute('SELECT path,value FROM discovery_records WHERE '+scope,args).fetchall()
    return {'checked':{r['path']:json.loads(r['value']) for r in rows if Path(r['path']).parent==Path(folder)}}


def save_one(path,value):
    with app.db() as con:
        initialize(con)
        value=with_write_failures(con,path,value)
        con.execute('INSERT OR REPLACE INTO discovery_records VALUES(?,?)',(str(path),json.dumps(value,ensure_ascii=False)))


def with_write_failures(con,path,value):
    """F29: a run of failed writes belongs to the archive, not to one pass.

    The record a later pass saves for the same archive (same signature), for example
    when it plans the comic again, keeps the run, so the wait keeps growing and a stop
    holds. A changed archive starts again from nothing."""
    if 'write_failures' in value:return value
    found=con.execute('SELECT value FROM discovery_records WHERE path=?',(str(path),)).fetchone()
    run=json.loads(found['value']).get('write_failures') if found else None
    if isinstance(run,dict) and run.get('signature')==value.get('signature'):
        return dict(value,write_failures=run)
    return value


def write_retries_stopped(record, signature):
    """Automatic write retries for this archive have stopped after repeated failures (F29)."""
    run = record.get('write_failures')
    return isinstance(run, dict) and bool(run.get('stopped')) and run.get('signature') == signature


def failed_write(record, reason, now):
    """F29: the record's retry, failure run and detail after one more failed write.

    A write that fails on an unchanged archive is a property of that file (a page with
    a bad CRC, an encrypted or unsupported entry, a file another program holds open),
    not a search that may answer later. Each further failure on the same archive waits
    longer (WRITE_FAILED_BACKOFF_DAYS); the WRITE_FAILED_LIMIT-th stops automatic
    retries until the archive changes. Research searching has no terminal state; this
    stop is limited to writing one archive, and the detail says so."""
    signature = record.get('signature')
    run = record.get('write_failures')
    run = run if isinstance(run, dict) and run.get('signature') == signature else {}
    count = run.get('count', 0) + 1
    stopped = count >= WRITE_FAILED_LIMIT
    error = ' '.join(str(reason).split())[:300].rstrip('.') + '.'
    if stopped:
        retry_at = 0  # No automatic retry; coverage_priority.write_retry_waiting holds the comic.
        detail = ('Automatic writes stopped after ' + str(count) + ' failed attempts on this unchanged archive. Last error: ' + error
                  + ' The file may be damaged, encrypted or held open by another program. It is tried again once the file changes'
                  ' (repaired, replaced or re-saved).')
    else:
        days = WRITE_FAILED_BACKOFF_DAYS[count - 1]
        retry_at = now + days * 86400
        detail = ('Write failed (attempt ' + str(count) + ' of ' + str(WRITE_FAILED_LIMIT) + ' on this archive): ' + error
                  + ' Nothing was written. Next attempt in ' + str(days) + (' day' if days == 1 else ' days')
                  + ', or at the next pass if the file changes.')
    return {'retry_at': retry_at, 'detail': detail,
            'write_failures': {'signature': signature, 'count': count, 'first_at': run.get('first_at', now),
                               'last_at': now, 'stopped': stopped}}


def write_not_done(path, outcome, reason, now=None):
    """A planned write did not happen, and nothing was written to the archive (v0.1.3 review F22, F23).

    The comic's record keeps its archive signature and research state. Its outcome
    says why. A skipped write is offered again after the ordinary daily retry; a
    failed one after a wait that grows with each failure on the same archive, until
    automatic retries stop (failed_write, F29). Either is offered again on the next
    pass once the archive changes (its signature then differs). A comic with no
    record (a manual reference plan) is left alone. Returns whether a record changed."""
    now = time.time() if now is None else now
    with app.db() as con:
        initialize(con)
        found = con.execute('SELECT value FROM discovery_records WHERE path=?', (str(path),)).fetchone()
        if not found:
            return False
        record = json.loads(found['value'])
        record.update(outcome=outcome, retry_at=now + WRITE_RETRY_SECONDS, write_error=str(reason)[:2000], write_at=now)
        if outcome == 'write_failed':
            record.update(failed_write(record, reason, now))
        con.execute('UPDATE discovery_records SET value=? WHERE path=?', (json.dumps(record, ensure_ascii=False), str(path)))
    return True


def counts(root):
    with app.db() as con:
        initialize(con)
        scope,args=app.scope_filter(root)
        rows=con.execute("SELECT COALESCE(json_extract(value,'$.outcome'),'unknown') outcome,COUNT(*) n FROM discovery_records WHERE "+scope+' GROUP BY outcome',args)
        return {r['outcome']:r['n'] for r in rows}
