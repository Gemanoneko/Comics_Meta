"""Bounded parallel source lookups, aggregate stage timing, verified evidence reuse."""
import hashlib
import json
import time
import zipfile
import sqlite3
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED, CancelledError
from contextlib import contextmanager
from functools import wraps
import app
import pause_control


@contextmanager
def stage(name):
    started=time.monotonic();failed=False
    try:yield
    except BaseException:
        failed=True;raise
    finally:
        elapsed=time.monotonic()-started
        try:
            with app.db() as con:
                con.execute('CREATE TABLE IF NOT EXISTS stage_metrics(stage TEXT PRIMARY KEY,calls INTEGER,seconds REAL,errors INTEGER)')
                con.execute('INSERT INTO stage_metrics VALUES(?,1,?,?) ON CONFLICT(stage) DO UPDATE SET calls=calls+1,seconds=seconds+excluded.seconds,errors=errors+excluded.errors',
                            (name,elapsed,int(failed)))
        except (OSError,sqlite3.Error):
            # Diagnostics must not prevent research or hide its original error.
            pass


def timed(name):
    def decorate(function):
        @wraps(function)
        def wrapped(*args,**kwargs):
            with stage(name):return function(*args,**kwargs)
        return wrapped
    return decorate


def metrics():
    with app.db() as con:
        exists=con.execute("SELECT 1 FROM sqlite_master WHERE name='stage_metrics'").fetchone()
        rows=[dict(r) for r in con.execute('SELECT * FROM stage_metrics ORDER BY seconds DESC')] if exists else []
    return {'stages':rows,'research_concurrency':2,'throughput':throughput()}


def record_check(outcome):
    try:_record_check(outcome)
    except (OSError,sqlite3.Error):pass  # Measurement must not stop enrichment.


def _record_check(outcome):
    now=time.time()
    with app.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS throughput_buckets(minute INTEGER PRIMARY KEY,checks INTEGER,queued INTEGER)')
        con.execute('CREATE TABLE IF NOT EXISTS throughput_settings(key TEXT PRIMARY KEY,value REAL)')
        con.execute("INSERT OR IGNORE INTO throughput_settings VALUES('started_at',?)",(now,))
        con.execute('INSERT INTO throughput_buckets VALUES(?,1,?) ON CONFLICT(minute) DO UPDATE SET checks=checks+1,queued=queued+excluded.queued',
                    (int(now//60),int(outcome=='queued')))
        con.execute('DELETE FROM throughput_buckets WHERE minute<?',(int(now//60)-7*24*60,))


def throughput():
    now=time.time()
    with app.db() as con:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE name='throughput_settings'").fetchone():return None
        setting=con.execute("SELECT value FROM throughput_settings WHERE key='started_at'").fetchone()
        if not setting:return None
        started=setting[0]
        since=max(started,now-3600)
        counts=con.execute('SELECT COALESCE(SUM(checks),0) checks,COALESCE(SUM(queued),0) queued FROM throughput_buckets WHERE minute>=?',(int(since//60),)).fetchone()
        writes=con.execute('SELECT COUNT(*) writes,COUNT(DISTINCT path) comics FROM history WHERE timestamp>=?',(since,)).fetchone()
    return {'window_seconds':max(0,now-since),'checks':counts['checks'],'queued':counts['queued'],
            'writes':writes['writes'],'updated_comics':writes['comics'],'started_at':started}


def first_verified(attempts,row,old,on_result,concurrency=2):
    """At most two independent sources; stop scheduling after a verified match."""
    concurrency=max(1,min(2,int(concurrency)))
    def invoke(name,lookup):
        if pause_control.requested():raise pause_control.PauseRequested()
        with stage(name):return lookup(row,old)
    with ThreadPoolExecutor(max_workers=concurrency,thread_name_prefix='metadata-source') as pool:
        pending={};next_index=0;found={}
        while pending or next_index<len(attempts):
            if not found and not pause_control.requested():
                while len(pending)<concurrency and next_index<len(attempts):
                    name,lookup=attempts[next_index]
                    pending[pool.submit(invoke,name,lookup)]=(next_index,name)
                    next_index+=1
            if not pending:break
            done,_=wait(pending,timeout=1,return_when=FIRST_COMPLETED)
            for future in done:
                index,name=pending.pop(future)
                try:
                    result=future.result()
                    on_result(name,result,None)
                    if result:found[index]=result
                except (pause_control.PauseRequested,CancelledError):
                    pass
                except Exception as exc:on_result(name,None,exc)
            if pause_control.requested():
                for future in pending:future.cancel()
        if pause_control.requested():raise pause_control.PauseRequested()
        return found[min(found)] if found else None


def page_identity(path):
    with zipfile.ZipFile(app.filesystem_path(path)) as archive:
        pages=sorted((i.filename,i.CRC,i.file_size) for i in archive.infolist()
                     if i.filename.lower().endswith(('.jpg','.jpeg','.png','.webp','.gif','.avif','.bmp')))
    if not pages:raise ValueError('No pages available for verified evidence reuse.')
    return hashlib.sha256(json.dumps(pages).encode()).hexdigest()


def identity(row,old):
    import research
    series,number=research.query_identity(row,old)
    return [research.series_key(series),research.issue_number(number),str(old.get('Year') or row.get('year') or ''),old.get('ISBN',''),research.series_key(old.get('Title','')),old.get('Format','')]


def remember(path,row,old,result,version,issue=None):
    import research
    if not result or not result.get('sources'):return
    try:pages=page_identity(path)
    except (OSError,ValueError,zipfile.BadZipFile):return
    expected=dict(old)
    fields=dict(result.get('fields',{}))
    if issue:
        import automatic
        fields.update(automatic.verified_issue_fields(issue))
    for key,value in fields.items():
        if not expected.get(key):expected[key]=value
    research.save_evidence(path,{'verified_evidence':{'pages':pages,'identity':identity(row,old),'written_identity':identity(row,expected),
        'version':version,'verified_at':time.time(),'result':result,'issue':issue}})


def reuse(path,row,old,saved,version):
    record=saved.get('verified_evidence',{})
    if record.get('version')!=version or identity(row,old) not in (record.get('identity'),record.get('written_identity')) or time.time()-record.get('verified_at',0)>30*86400:return None
    try:pages=page_identity(path)
    except (OSError,ValueError,zipfile.BadZipFile):return None
    if record.get('pages')!=pages:return None
    result=record.get('result')
    if not isinstance(result,dict) or not result.get('sources'):return None
    with stage('Verified evidence reused'):pass
    return result
