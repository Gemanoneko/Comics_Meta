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
import lens_verification


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
    # A search that never ran is not an empty result. These reasons keep the
    # task in place (same queue position and retry wait) until the hold ends.
    blocked=None;fallback_blocked=None;searched=False;failed=False
    if leads is None:
        state=search.status()
        provider='browser'
        retry_at=state.get('browser_retry_at',0)
        if retry_at>time.time():
            # Observing an existing cooldown is not another failed request.
            blocked=('Google Lens needs human verification.' if state.get('human_verification')
                     else 'Google Lens is cooling down.')
        else:
            try:
                try:search.reserve('browser',int(options.get('daily_request_limit',100)),datetime.now(timezone.utc).strftime('%Y-%m-%d'))
                except ValueError:
                    blocked='Daily Google Lens search limit reached.'
                    raise
                leads=browser.search(data);searched=True
                search.status(human_verification=False,verification_url='',verification_task={},browser_retry_at=0,browser_error='')
            except pause_control.PauseRequested:
                cover_tasks.finish(row,'pending','Paused; search remains queued.');return
            except search.HumanVerification as exc:
                blocked='Google Lens asked for human verification.'
                # The comic whose search hit the check receives the results page
                # Google loads once the check is solved. Never exposed by the API.
                search.status(human_verification=True,verification_state='required',verification_url=exc.url,
                              verification_task={'path':row['path'],'size':row['size'],'mtime':row['mtime']},browser_retry_at=time.time()+3600)
                leads=None
            except Exception:
                # Only a new failure starts the usual wait.
                if not blocked:failed=True
                search.status(browser_retry_at=time.time()+3600,browser_error='Browser search could not finish; retrying after a cooldown.')
                leads=None
        if not leads and options.get('serpapi_fallback'):
            if pause_control.requested():
                cover_tasks.finish(row,'pending','Paused; search remains queued.');return
            provider='serpapi'
            try:
                leads=search.serpapi_search(data,options);searched=True
                search.status(fallback_detail='')
            except ValueError as exc:
                fallback_blocked=str(exc)
                search.status(fallback_detail=str(exc))
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
    elif searched:
        cover_tasks.finish(row,'retry_wait','No usable cover-search candidates; retry after one day.')
        search.status(state='waiting',detail='No usable candidates for this cover. Continuing with other comics.')
    elif failed or not blocked:
        cover_tasks.finish(row,'retry_wait','Cover search could not finish; retry after one day.')
        search.status(state='waiting',detail='Cover search could not finish. Continuing with other comics.')
    else:
        fallback=' SerpApi fallback unavailable: '+fallback_blocked if fallback_blocked else ''
        cover_tasks.release(row,blocked+fallback+' Not searched; kept in its queue place until this clears.')
        search.status(state='waiting',detail=blocked+' Queued covers keep their place; searching resumes when this clears.')
        return max(search.status().get('browser_retry_at',0),time.time())


def wait_for_work(seconds):
    """Interrupt pacing promptly for a user verification request or a pause."""
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if pause_control.requested() or (app.DATA/'browser-resume').exists():return
        time.sleep(min(1,max(0,deadline-time.monotonic())))


def verification_request(browser,options):
    browser=lens_verification.service(browser,options)
    if browser is not None:
        try:harvest_verified_page(browser)
        except Exception:
            # Never let saving optional leads stop the worker; the comic's
            # search stays queued and runs again normally.
            pass
    return browser


def harvest_verified_page(browser):
    """Give the post-check results page to the search that hit the check."""
    leads=getattr(browser,'verified_leads',None)
    if not isinstance(leads,list) or not leads:return 0
    browser.verified_leads=[]
    task=search.legacy_status().get('verification_task') or {}
    search.status(verification_task={})
    saved=cover_tasks.record_verified_page(task,leads)
    if saved:
        search.status(state='candidates_saved',provider='browser',detail=str(saved)+' candidate links saved for automatic identity verification.')
    return saved


def main(once=False):
    handle=locked()
    if not handle:return
    import lens_browser_owner
    lens_browser_owner.enable()
    lens_verification.initialize()
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
                lens_verification.paused()
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
            hold=None
            try:
                if not browser:browser=search.LensBrowser(options)
                hold=process(row,browser,options)
            except Exception:
                # Exceptions from browsers can contain URLs or user data; keep UI errors generic.
                cover_tasks.finish(row,'retry_wait','Cover search failed; a later retry is scheduled.')
                search.status(state='retry_wait',detail='Cover search failed. Continuing with other comics.')
                if browser:
                    try:browser.close()
                    except Exception:pass
                    browser=None
            if once:return
            pacing=max(30,int(options.get('interval_seconds',60)))
            # A blocked search left its task in place; claiming again before the
            # hold ends would only re-read the same queue head. Re-check hourly.
            if hold:pacing=max(pacing,min(hold-time.time(),3600))
            next_search_at=time.monotonic()+pacing
            wait_for_work(next_search_at-time.monotonic())
    finally:
        stop.set()
        if browser:browser.close()
        handle.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true')
    main(parser.parse_args().once)
