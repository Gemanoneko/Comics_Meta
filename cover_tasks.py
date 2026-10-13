"""Durable browser-cover research tasks; search results are leads, never facts."""
import json
import time
import urllib.parse
import app

# A genuine empty search is retried after a day (empty results are not cached).
# Leads that failed identity verification are searched again only after the
# 30-day cover-search cache expires; an earlier repeat returns the same leads.
RETRY_SECONDS=86400
UNVERIFIED_RETRY_SECONDS=30*86400


def table(con):
    con.execute('CREATE TABLE IF NOT EXISTS cover_tasks(path TEXT PRIMARY KEY, signature TEXT, state TEXT, updated REAL, detail TEXT)')
    con.execute('CREATE TABLE IF NOT EXISTS cover_retries(folder TEXT PRIMARY KEY)')


def enqueue(row):
    signature=json.dumps([row['size'],row['mtime']])
    with app.db() as con:
        table(con)
        previous=con.execute('SELECT signature,state FROM cover_tasks WHERE path=?',(row['path'],)).fetchone()
        if previous and previous[0]==signature:
            # Discovery only re-enqueues after every source, including the saved
            # cover leads, failed to verify. Saved leads are never a final state.
            if previous[1]=='leads_found':
                con.execute("UPDATE cover_tasks SET state='leads_unverified',updated=?,detail=? WHERE path=? AND state='leads_found'",
                            (time.time(),'Cover-search leads did not verify; another cover search is scheduled after the 30-day result cache expires.',row['path']))
            return
        con.execute('INSERT OR REPLACE INTO cover_tasks VALUES(?,?,?,?,?)',(row['path'],signature,'pending',time.time(),'Browser reverse-image research queued; no metadata write authorized.'))


def record(row,leads,states=None,merge=False):
    """Save search leads as unverified evidence and mark the task leads_found.

    With states, the task's current state and archive signature are checked in
    the same transaction as the write, so a task another source resolved in the
    meantime is never overwritten (returns 0). merge keeps earlier leads saved
    for the same archive instead of replacing them.
    """
    import research
    from pathlib import Path
    safe=[]
    for lead in leads[:10]:
        url=lead.get('url','');p=urllib.parse.urlparse(url)
        if p.scheme!='https' or not p.hostname or p.username or p.password:continue
        safe.append({'url':url,'title':str(lead.get('title',''))[:300]})
    if not safe:raise ValueError('At least one public HTTPS candidate is required.')
    signature=[row['size'],row['mtime']]
    with app.db() as con:
        table(con);con.execute('BEGIN IMMEDIATE')
        if states is not None:
            current=con.execute('SELECT signature,state FROM cover_tasks WHERE path=?',(row['path'],)).fetchone()
            if not current or json.loads(current[0])!=signature or current[1] not in states:return 0
        matches=safe
        if merge:
            previous=research.read_evidence(row['path'])
            if previous.get('reverse_image_signature')==signature:
                seen={lead['url'] for lead in safe}
                matches=safe+[lead for lead in previous.get('reverse_image_matches') or [] if isinstance(lead,dict) and lead.get('url') not in seen]
                matches=matches[:10]
        # Evidence and task are written under one lock (save_evidence's lock).
        research.merge_evidence(row['path'],{'reverse_image_matches':matches,'reverse_image_status':'candidate_needs_verification','reverse_image_signature':signature})
        con.execute('INSERT OR REPLACE INTO cover_tasks VALUES(?,?,?,?,?)',(row['path'],json.dumps(signature),'leads_found',time.time(),'Search candidates saved; automatic identity verification pending.'))
        # Discovery owns folders.json. The separate browser process requests a retry
        # through SQLite rather than racing a whole-file scheduler update.
        con.execute('INSERT OR IGNORE INTO cover_retries VALUES(?)',(str(Path(row['path']).parent),))
    return len(safe)


def claim(now=None):
    now=time.time() if now is None else now
    with app.db() as con:
        table(con);con.execute('BEGIN IMMEDIATE')
        scope,args=app.scope_filter(app.live_root())
        rows=con.execute("SELECT comics.*,cover_tasks.signature AS task_signature,cover_tasks.state AS task_state,cover_tasks.updated AS task_updated FROM comics JOIN cover_tasks USING(path) WHERE "+scope+" AND comics.status NOT IN ('absent','error','unsupported') AND (cover_tasks.state='pending' OR (cover_tasks.state='retry_wait' AND cover_tasks.updated<?) OR (cover_tasks.state='leads_unverified' AND cover_tasks.updated<?)) ORDER BY cover_tasks.updated LIMIT 20",(*args,now-RETRY_SECONDS,now-UNVERIFIED_RETRY_SECONDS)).fetchall()
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
        con.execute("UPDATE cover_tasks SET state='not_needed',updated=?,detail='Identity verified through another source; reverse search is unnecessary.' WHERE path=? AND state IN ('pending','retry_wait','searching','leads_unverified')",(time.time(),row['path']))


def finish(row,state,detail):
    with app.db() as con:
        table(con)
        con.execute('UPDATE cover_tasks SET state=?,updated=?,detail=? WHERE path=?',(state,time.time(),detail[:1000],row['path']))


def release(row,detail):
    """Return a claimed task unsearched: same state, same queue position and wait.

    A blocked provider (cooldown, daily cap, human check, fallback cap) is not
    a search result, so it must neither reset a retry wait nor requeue at the back.
    """
    state=row.get('task_state') or 'pending'
    if state not in ('pending','retry_wait','leads_unverified'):state='pending'
    updated=row.get('task_updated')
    if updated is None:updated=time.time()
    with app.db() as con:
        table(con)
        con.execute("UPDATE cover_tasks SET state=?,updated=?,detail=? WHERE path=? AND state='searching'",(state,updated,detail[:1000],row['path']))


def record_verified_page(task,leads):
    """Save leads read from the results page Google loads after a solved check.

    Only the task that hit the check receives them, and only while its archive
    and queued search are unchanged. They remain unverified leads.
    """
    from pathlib import Path
    try:
        key=task['path'];signature=[int(task['size']),int(task['mtime'])]
        if not isinstance(key,str) or not key:return 0
        stat=Path(key).stat()
    except (KeyError,TypeError,ValueError,OSError):return 0
    if [stat.st_size,stat.st_mtime_ns]!=signature:return 0
    # Checked and written in one transaction; earlier leads for this archive
    # are kept, so a late or stale results page never replaces them.
    try:return record({'path':key,'size':signature[0],'mtime':signature[1]},leads,
                      states=('pending','retry_wait','leads_unverified'),merge=True)
    except ValueError:return 0


def status():
    with app.db() as con:
        table(con)
        return {r['state']:r['n'] for r in con.execute('SELECT state,COUNT(*) n FROM cover_tasks GROUP BY state')}
