"""Per-file research state in SQLite, bounded by the folder being processed."""
import json
import time
from pathlib import Path
import app

WRITE_RETRY_SECONDS = 86400  # The ordinary daily research retry.
WRITE_NOT_DONE = ('write_skipped', 'write_failed')  # Outcomes of a planned write that did not happen.


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
        con.execute('INSERT OR REPLACE INTO discovery_records VALUES(?,?)',(str(path),json.dumps(value,ensure_ascii=False)))


def write_not_done(path, outcome, reason, now=None):
    """A planned write did not happen, and nothing was written to the archive (v0.1.3 review F22, F23).

    The comic's record keeps its archive signature and research state. Its outcome
    says why, and it is offered again after the ordinary daily retry, or on the next
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
        con.execute('UPDATE discovery_records SET value=? WHERE path=?', (json.dumps(record, ensure_ascii=False), str(path)))
    return True


def counts(root):
    with app.db() as con:
        initialize(con)
        scope,args=app.scope_filter(root)
        rows=con.execute("SELECT COALESCE(json_extract(value,'$.outcome'),'unknown') outcome,COUNT(*) n FROM discovery_records WHERE "+scope+' GROUP BY outcome',args)
        return {r['outcome']:r['n'] for r in rows}
