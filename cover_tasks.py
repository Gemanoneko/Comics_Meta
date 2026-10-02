"""Durable browser-cover research tasks; search results are leads, never facts."""
import json
import time
import urllib.parse
import app


def table(con):
    con.execute('CREATE TABLE IF NOT EXISTS cover_tasks(path TEXT PRIMARY KEY, signature TEXT, state TEXT, updated REAL, detail TEXT)')


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
    # The browser researcher runs serially with discovery; requesting an early retry
    # does not bypass the archive signature or identity checks.
    import scheduler
    if scheduler.STATE.exists():
        state=json.loads(scheduler.STATE.read_text(encoding='utf-8'))
        from pathlib import Path
        folder=str(Path(row['path']).parent)
        if folder in state.get('folders',{}):
            state['folders'][folder]['next_scan']=0;storage.save(scheduler.STATE,state)


def status():
    with app.db() as con:
        table(con)
        return {r['state']:r['n'] for r in con.execute('SELECT state,COUNT(*) n FROM cover_tasks GROUP BY state')}
