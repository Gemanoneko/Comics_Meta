"""Independent, supervised cover-search process. It never writes comic archives."""
import argparse
import json
import os
import threading
import time
from datetime import datetime,timezone
from pathlib import Path
import app
import browser_search as search
import cover_tasks
import storage
import pause_control


def locked():
    app.DATA.mkdir(parents=True,exist_ok=True)
    handle=(app.DATA/'browser-worker.lock').open('a+b')
    handle.seek(0);handle.write(b'0');handle.flush();handle.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        handle.close();return None
    return handle


def process(row,browser,options):
    if pause_control.requested():
        cover_tasks.finish(row,'pending','Paused; search remains queued.');return
    path=Path(row['path'])
    stat=path.stat()
    if [stat.st_size,stat.st_mtime_ns]!=[row['size'],row['mtime']]:
        cover_tasks.finish(row,'stale','Archive changed; waiting for discovery to refresh it.');return
    old=json.loads(row['metadata'])
    import automatic
    if not automatic.language_eligible(row,old):
        cover_tasks.finish(row,'excluded_language','Outside the English-language scope.');return
    with app.db() as con:
        task=con.execute('SELECT state FROM cover_tasks WHERE path=?',(row['path'],)).fetchone()
    if task and task[0]=='not_needed':return
    search.status(state='searching',current=path.name,detail='Searching the cover; candidate links will be verified before any metadata write.')
    data=search.cover_bytes(path);key,leads=search.cached(data)
    provider='cache'
    if leads is None:
        state=search.status()
        provider='browser'
        try:
            if state.get('browser_retry_at',0)>time.time():raise ValueError('Browser search is cooling down.')
            search.reserve('browser',int(options.get('daily_request_limit',100)),datetime.now(timezone.utc).strftime('%Y-%m-%d'))
            leads=browser.search(data)
            search.status(human_verification=False,verification_url='',browser_retry_at=0,browser_error='')
        except pause_control.PauseRequested:
            cover_tasks.finish(row,'pending','Paused; search remains queued.');return
        except search.HumanVerification as exc:
            search.status(human_verification=True,verification_state='required',verification_url=exc.url,browser_retry_at=time.time()+3600)
            leads=None
        except Exception:
            search.status(browser_retry_at=time.time()+3600,browser_error='Browser search could not finish; retrying after a cooldown.')
            leads=None
        if not leads and options.get('serpapi_fallback'):
            if pause_control.requested():
                cover_tasks.finish(row,'pending','Paused; search remains queued.');return
            provider='serpapi'
            try:
                leads=search.serpapi_search(data,options)
                search.status(fallback_detail='')
            except ValueError as exc:search.status(fallback_detail=str(exc))
        if leads:search.save_cache(key,leads)
    # Archive bytes may have changed while the browser was running.
    stat=path.stat()
    if [stat.st_size,stat.st_mtime_ns]!=[row['size'],row['mtime']]:
        cover_tasks.finish(row,'stale','Archive changed during search; results were not applied.');return
    with app.db() as con:
        task=con.execute('SELECT state FROM cover_tasks WHERE path=?',(row['path'],)).fetchone()
    if task and task[0]=='not_needed':return
    if leads:
        cover_tasks.record(row,leads)
        search.status(state='candidates_saved',provider=provider,detail=str(len(leads))+' candidate links saved for automatic identity verification.')
    else:
        cover_tasks.finish(row,'retry_wait','No usable cover-search candidates; retry after one day.')
        search.status(state='waiting',detail='No usable candidates for this cover. Continuing with other comics.')


def wait_for_work(seconds):
    """Interrupt pacing promptly for a user verification request or a pause."""
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if pause_control.requested() or (app.DATA/'browser-resume').exists():return
        time.sleep(min(1,max(0,deadline-time.monotonic())))


def verification_request(browser,options):
    resume=app.DATA/'browser-resume'
    if not resume.exists():return browser
    resume.unlink()
    state=search.status()
    if not state.get('human_verification') or not state.get('verification_url'):return browser
    try:
        search.status(state='opening_verification',verification_state='opening',detail='Opening the verification browser; no further clicks are needed.')
        if not browser:browser=search.LensBrowser(options)
        resolved=browser.human_session(state['verification_url'])
        minimized=browser.minimize() if resolved else False
        search.status(human_verification=not resolved,verification_state='verified' if resolved else 'required',
                      verification_window='minimized' if minimized else 'open' if resolved else 'closed',
                      browser_retry_at=0 if resolved else time.time()+3600,
                      detail=('Verification complete. The browser is minimized; keep it open for automatic searches.' if minimized else 'Verification complete. You can minimize the browser; keep it open for automatic searches.') if resolved else 'Verification did not finish. Request a new window when ready.')
    except Exception:
        search.status(state='needs_human',verification_state='required',detail='Could not complete the verification session. Retry from the dashboard.')
    return browser


def main(once=False):
    handle=locked()
    if not handle:return
    stop=threading.Event()
    def heartbeat():
        while not stop.is_set():
            try:storage.save(app.DATA/'browser-heartbeat',{'pid':os.getpid(),'timestamp':time.time()})
            except OSError:pass
            stop.wait(2)
    threading.Thread(target=heartbeat,daemon=True).start()
    with app.db() as con:
        cover_tasks.table(con)
        con.execute("UPDATE cover_tasks SET state='pending' WHERE state='searching'")
    browser=None
    next_search_at=0
    state=search.status()
    search.status(verification_state='required' if state.get('human_verification') else 'verified',verification_window='closed')
    try:
        while True:
            if pause_control.requested():
                if browser:
                    browser.close();browser=None
                pause_control.checkpoint('browser')
                state=search.status()
                search.status(state='paused',verification_state='required' if state.get('human_verification') else 'verified',verification_window='closed',detail='Paused; cover queue retained.')
                if once:return
                time.sleep(1);continue
            pause_control.checkpoint('browser')
            options=search.settings()
            if not options.get('enabled'):
                search.status(state='disabled',detail='Browser cover research is disabled.')
                if once:return
                time.sleep(5);continue
            browser=verification_request(browser,options)
            if time.monotonic()<next_search_at:
                wait_for_work(next_search_at-time.monotonic());continue
            row=cover_tasks.claim()
            if not row:
                search.status(state='waiting',detail='Watching for unresolved covers.')
                if once:return
                wait_for_work(5);continue
            try:
                if not browser:browser=search.LensBrowser(options)
                process(row,browser,options)
            except Exception:
                # Exceptions from browsers can contain URLs or user data; keep UI errors generic.
                cover_tasks.finish(row,'retry_wait','Cover search failed; a later retry is scheduled.')
                search.status(state='retry_wait',detail='Cover search failed. Continuing with other comics.')
                if browser:
                    try:browser.close()
                    except Exception:pass
                    browser=None
            if once:return
            next_search_at=time.monotonic()+max(30,int(options.get('interval_seconds',60)))
            wait_for_work(next_search_at-time.monotonic())
    finally:
        stop.set()
        if browser:browser.close()
        handle.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true')
    main(parser.parse_args().once)
