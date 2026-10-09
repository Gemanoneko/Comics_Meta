"""Per-file research state in SQLite, bounded by the folder being processed."""
import json
from pathlib import Path
import app


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


def counts(root):
    with app.db() as con:
        initialize(con)
        scope,args=app.scope_filter(root)
        rows=con.execute("SELECT COALESCE(json_extract(value,'$.outcome'),'unknown') outcome,COUNT(*) n FROM discovery_records WHERE "+scope+' GROUP BY outcome',args)
        return {r['outcome']:r['n'] for r in rows}
