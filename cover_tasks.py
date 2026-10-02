"""Durable browser-cover research tasks; search results are leads, never facts."""
import json
import time
import urllib.parse
import app


def table(con):
    con.execute('CREATE TABLE IF NOT EXISTS cover_tasks(path TEXT PRIMARY KEY, signature TEXT, state TEXT, updated REAL, detail TEXT)')
    con.execute('CREATE TABLE IF NOT EXISTS cover_retries(folder TEXT PRIMARY KEY)')


def enqueue(row):
    signature=json.dumps([row['size'],row['mtime']])
    with app.db() as con:
        table(con)
        previous=con.execute('SELECT signature FROM cover_tasks WHERE path=?',(row['path'],)).fetchone()
        if previous and previous[0]==signature:return
        con.execute('INSERT OR REPLACE INTO cover_tasks VALUES(?,?,?,?,?)',(row['path'],signature,'pending',time.time(),'Browser reverse-image research queued; no metadata write authorized.'))


def record(row,leads):
    import research,storage
    safe=[]
    for lead in leads[:10]:
        url=lead.get('url','');p=urllib.parse.urlparse(url)
        if p.scheme!='https' or not p.hostname or p.username or p.password:continue
        safe.append({'url':url,'title':str(lead.get('title',''))[:300]})
    if not safe:raise ValueError('At least one public HTTPS candidate is required.')
    research.save_evidence(row['path'],{'reverse_image_matches':safe,'reverse_image_status':'candidate_needs_verification','reverse_image_signature':[row['size'],row['mtime']]})
    with app.db() as con:
        table(con)
        con.execute('INSERT OR REPLACE INTO cover_tasks VALUES(?,?,?,?,?)',(row['path'],json.dumps([row['size'],row['mtime']]),'leads_found',time.time(),'Search candidates saved; automatic identity verification pending.'))
    # Discovery owns folders.json. The separate browser process requests a retry
    # through SQLite rather than racing a whole-file scheduler update.
    from pathlib import Path
    with app.db() as con:
        table(con)
        con.execute('INSERT OR IGNORE INTO cover_retries VALUES(?)',(str(Path(row['path']).parent),))


def claim(now=None):
    now=time.time() if now is None else now
    with app.db() as con:
        table(con);con.execute('BEGIN IMMEDIATE')
        scope,args=app.scope_filter(app.live_root())
        rows=con.execute("SELECT comics.*,cover_tasks.signature AS task_signature FROM comics JOIN cover_tasks USING(path) WHERE "+scope+" AND comics.status NOT IN ('absent','error','unsupported') AND (cover_tasks.state='pending' OR (cover_tasks.state='retry_wait' AND cover_tasks.updated<?)) ORDER BY cover_tasks.updated LIMIT 20",(*args,now-86400)).fetchall()
        import discovery_state
        discovery_state.initialize(con)
        for row in rows:
            row=dict(row);signature=[row['size'],row['mtime']]
            if json.loads(row.pop('task_signature'))!=signature:
                con.execute("UPDATE cover_tasks SET state='stale',updated=?,detail='Archive changed since this search was queued.' WHERE path=?",(now,row['path']))
                continue
            known=con.execute('SELECT value FROM discovery_records WHERE path=?',(row['path'],)).fetchone()
            known=json.loads(known[0]) if known else {}
            if known.get('signature')==signature and known.get('outcome') in {'current','queued','publisher_issue_found','web_issue_found'}:
                con.execute("UPDATE cover_tasks SET state='not_needed',updated=?,detail='Identity already found through another source.' WHERE path=?",(now,row['path']))
                continue
            con.execute("UPDATE cover_tasks SET state='searching',updated=?,detail='Searching cover in browser' WHERE path=?",(now,row['path']))
            return row
        return None


def identified(row):
    """Cancel an outstanding search after another source verifies issue identity."""
    with app.db() as con:
        table(con)
        con.execute("UPDATE cover_tasks SET state='not_needed',updated=?,detail='Identity verified through another source; reverse search is unnecessary.' WHERE path=? AND state IN ('pending','retry_wait','searching')",(time.time(),row['path']))


def finish(row,state,detail):
    with app.db() as con:
        table(con)
        con.execute('UPDATE cover_tasks SET state=?,updated=?,detail=? WHERE path=?',(state,time.time(),detail[:1000],row['path']))


def status():
    with app.db() as con:
        table(con)
        return {r['state']:r['n'] for r in con.execute('SELECT state,COUNT(*) n FROM cover_tasks GROUP BY state')}
