"""Durable explicit Lens intent; only the leased browser worker may service it.

The legacy cover status remains provider state. Request receipts are separate so
ordinary cover progress cannot erase an opening failure. No URL enters the API.
"""
import json
import os
import time
import uuid
import app
import storage

_owner = None
PENDING = {'queued', 'opening', 'open', 'closing'}


def read(con):
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name='lens_verification'").fetchone():return {}
    row=con.execute('SELECT value FROM lens_verification WHERE id=1').fetchone()
    return json.loads(row[0]) if row else {}


def save(con,state):
    state=dict(state,updated=time.time())
    con.execute('INSERT OR REPLACE INTO lens_verification VALUES(1,?)',(json.dumps(state),))
    receipt={key:state.get(key) for key in ('request_id','owner','owner_pid','generation','phase','stage','failure','error_class','window','updated')}
    con.execute('INSERT INTO lens_verification_events(timestamp,value) VALUES(?,?)',(state['updated'],json.dumps(receipt)))


def control(con):
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name='processing_control'").fetchone():return False,0
    row=con.execute('SELECT paused,generation FROM processing_control WHERE id=1').fetchone()
    return (bool(row[0]),row[1]) if row else (False,0)


def alive(state):
    try:
        beat=json.loads((app.DATA/'browser-heartbeat').read_text(encoding='utf-8'))
        return bool(state.get('owner')) and beat['pid']==state.get('owner_pid') and 0<=time.time()-beat['timestamp']<15
    except (OSError,ValueError,KeyError,TypeError):return False


def initialize():
    global _owner
    _owner=uuid.uuid4().hex
    with app.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS lens_verification(id INTEGER PRIMARY KEY,value TEXT NOT NULL)')
        con.execute('CREATE TABLE IF NOT EXISTS lens_verification_events(id INTEGER PRIMARY KEY,timestamp REAL,value TEXT NOT NULL)')
        con.execute('BEGIN IMMEDIATE');state=read(con)
        interrupted=state.get('phase') in PENDING or (app.DATA/'browser-resume').exists()
        state.update(owner=_owner,owner_pid=os.getpid(),window='closed')
        if interrupted:state.update(phase='failed',failure='interrupted',stage='worker_start',error_class='',finished_at=time.time())
        else:state.setdefault('phase','idle')
        save(con,state)
    # A stale legacy wake marker is never authorization to replay a window.
    (app.DATA/'browser-resume').unlink(missing_ok=True)


def server_started():
    with app.db() as con:
        con.execute('BEGIN IMMEDIATE');state=read(con)
        if state.get('phase') in PENDING:
            state.update(phase='closing' if state['phase'] in {'opening','open','closing'} or state.get('window') in {'open','minimized'} else 'failed',
                         failure='interrupted',stage='server_start',finished_at=time.time())
            if state['phase']=='failed':state['window']='closed'
            save(con,state)
            if state['phase']=='failed':(app.DATA/'browser-resume').unlink(missing_ok=True)


def status():
    import browser_search
    legacy=browser_search.legacy_status()
    with app.db() as con:state=read(con);paused,generation=control(con)
    current_alive=alive(state);phase=state.get('phase','idle');window=state.get('window','closed')
    invalid=phase in PENDING and (not current_alive or state.get('generation')!=generation)
    failure=state.get('failure','')
    if invalid:phase='failed';failure='interrupted'
    if not current_alive and window in {'open','minimized'}:window='unknown'
    if paused:phase='paused'
    human=bool(legacy.get('human_verification'))
    if phase in {'idle','verified'} and human:phase='required'
    return {'engine':'google_lens','phase':phase,'human_verification':human,'window':window,
            'alive':current_alive,'paused':paused,'failure':failure,'verification_pending':phase in PENDING,
            **{key:state.get(key) for key in ('request_id','requested_at','started_at','opened_at','finished_at','updated')}}


def request():
    import browser_search
    with app.db() as con:
        con.execute('BEGIN IMMEDIATE');state=read(con);paused,generation=control(con)
        if paused:raise ValueError('Processing is paused.')
        if not alive(state):raise ValueError('The Google Lens worker is unavailable.')
        if state.get('window')=='unknown':raise ValueError('Google Lens window closure is not confirmed.')
        if not browser_search.legacy_status().get('human_verification'):raise ValueError('No Google Lens verification is pending.')
        if state.get('phase') in PENDING:
            return {'ok':True,'state':'already_requested','engine':'google_lens','request_id':state.get('request_id')}
        state.update(phase='queued',request_id=uuid.uuid4().hex,generation=generation,window=state.get('window','closed'),
                     requested_at=time.time(),started_at=None,opened_at=None,finished_at=None,
                     stage='queued',failure='',error_class='')
        save(con,state)
        storage.save(app.DATA/'browser-resume',{'requested':state['requested_at'],'request_id':state['request_id']})
    return {'ok':True,'state':'queued','engine':'google_lens','request_id':state['request_id']}


def pending():
    with app.db() as con:return read(con).get('phase') in PENDING


def paused():
    """Called only after the worker has verified its browser closure."""
    with app.db() as con:
        con.execute('BEGIN IMMEDIATE');state=read(con)
        if state.get('owner')==_owner and (state.get('phase') in PENDING or state.get('window')!='closed'):
            state.update(phase='failed' if state.get('phase') in PENDING else state['phase'],window='closed',
                         failure='interrupted',stage='paused',finished_at=time.time());save(con,state)
    (app.DATA/'browser-resume').unlink(missing_ok=True)


def service(browser,options):
    import browser_search as search
    import pause_control
    # A rapid Pause->Resume is still a cancellation of a retained session.
    with app.db() as con:
        previous=read(con);is_paused,generation=control(con)
    if (previous.get('owner')==_owner and previous.get('window') in {'open','minimized'}
            and (is_paused or generation!=previous.get('generation') or previous.get('phase')=='closing')):
        if browser is not None:browser.close();browser=None
        paused()
    with app.db() as con:
        con.execute('BEGIN IMMEDIATE');state=read(con);is_paused,generation=control(con)
        if not _owner or state.get('owner')!=_owner:raise ValueError('Google Lens request owner changed.')
        if state.get('phase')!='queued':return browser
        if is_paused or generation!=state.get('generation'):
            state.update(phase='failed',failure='interrupted',stage='admission',finished_at=time.time());save(con,state)
            (app.DATA/'browser-resume').unlink(missing_ok=True)
            return browser
        state.update(phase='opening',stage='launch',started_at=time.time());save(con,state)
    (app.DATA/'browser-resume').unlink(missing_ok=True)
    request_id=state['request_id'];stage='launch';opened=False
    def admitted():
        with app.db() as con:current=read(con);is_paused,generation=control(con)
        if (is_paused or generation!=state['generation'] or current.get('owner')!=_owner
                or current.get('request_id')!=request_id or current.get('phase') not in {'opening','open'}):
            raise pause_control.PauseRequested()
    def observation(value):
        nonlocal stage,opened
        admitted();stage=value
        with app.db() as con:
            con.execute('BEGIN IMMEDIATE');current=read(con)
            if current.get('owner')!=_owner or current.get('request_id')!=request_id or current.get('phase') not in {'opening','open'}:
                raise pause_control.PauseRequested()
            current['stage']=value
            if value=='load':
                opened=True;current.update(phase='open',window='open',opened_at=time.time())
            save(con,current)
    success=False;failure='unfinished';error_class='';fatal=None;window='closed'
    try:
        admitted()
        retained=search.legacy_status()
        if not retained.get('human_verification'):raise ValueError('Challenge no longer pending.')
        if browser is None:browser=search.LensBrowser(options)
        success=browser.human_session(retained.get('verification_url',''),admitted,observation)
        admitted()
        if success:window='minimized' if browser.minimize() else 'open'
    except pause_control.PauseRequested:success=False;failure='interrupted'
    except BaseException as exc:
        success=False;error_class=type(exc).__name__;failure='load' if stage=='load' else 'unfinished' if opened else 'open'
        if not isinstance(exc,Exception):fatal=exc
    # Commit the keep-session decision under the same lock as pause/restart.
    # Cancellation discovered here still goes through closure below.
    if success:
        with app.db() as con:
            con.execute('BEGIN IMMEDIATE');current=read(con);is_paused,generation=control(con)
            if (is_paused or generation!=state['generation'] or current.get('owner')!=_owner
                    or current.get('request_id')!=request_id or current.get('phase') not in {'opening','open'}):
                success=False;failure='interrupted'
            else:
                current.update(phase='verified',window=window,stage=stage,failure='',error_class='',finished_at=time.time())
                save(con,current)
    if not success:
        try:
            if browser is not None:browser.close()
            browser=None;window='closed'
        except BaseException as exc:
            # Never claim closure or allow a second lease when descendants are unknown.
            window='unknown';stage='closure';error_class=type(exc).__name__;fatal=exc
    if not success:
        with app.db() as con:
            con.execute('BEGIN IMMEDIATE');current=read(con)
            if current.get('owner')==_owner and current.get('request_id')==request_id:
                current.update(phase='failed',window=window,stage=stage,failure=failure,error_class=error_class,finished_at=time.time())
                save(con,current)
    if success:
        # A verified human session clears its challenge, never its quota/backoff.
        search.status(human_verification=False,verification_state='verified',verification_window=window)
    if fatal is not None:raise fatal
    return browser


def session_closed():
    """Successful worker-owned closure, including ordinary-search failures."""
    with app.db() as con:
        con.execute('BEGIN IMMEDIATE');state=read(con)
        if state.get('owner')==_owner and state.get('window')!='closed':
            state.update(window='closed');save(con,state)
