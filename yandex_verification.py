"""One explicit Yandex verification intent, owned by the serial metadata worker.

State is transactional, separate from Lens and normal retry holds. No URL/profile
is accepted from the dashboard. A restart or pause generation cancels intent.
"""
import json
import os
import time
import uuid
import app

_owner = None
PENDING = {'queued','opening','open'}


def read(con):
    exists=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='yandex_verification'").fetchone()
    row=con.execute('SELECT value FROM yandex_verification WHERE id=1').fetchone() if exists else None
    return json.loads(row[0]) if row else {'phase':'idle','human_verification':False,'window':'closed'}


def save(con,state):
    state=dict(state,updated=time.time())
    con.execute('INSERT OR REPLACE INTO yandex_verification VALUES(1,?)',(json.dumps(state),))


def control(con):
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='processing_control'").fetchone():return False,0
    row=con.execute('SELECT paused,generation FROM processing_control WHERE id=1').fetchone()
    return (bool(row[0]),row[1]) if row else (False,0)


def owner_alive(state):
    try:
        heartbeat=json.loads((app.DATA/'queue/heartbeat').read_text(encoding='utf-8'))
        return bool(state.get('owner')) and heartbeat['pid']==state.get('owner_pid') and 0<=time.time()-heartbeat['timestamp']<15
    except (OSError,ValueError,KeyError,TypeError):return False


def initialize():
    global _owner
    _owner=uuid.uuid4().hex
    with app.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS yandex_verification(id INTEGER PRIMARY KEY,value TEXT NOT NULL)')
        con.execute('BEGIN IMMEDIATE')
        state=read(con)
        state.update(owner=_owner,owner_pid=os.getpid(),request=None,window='closed',
                     phase='required' if state.get('human_verification') else 'idle')
        save(con,state)


def server_started():
    """A successfully bound replacement server invalidates surviving intent."""
    with app.db() as con:
        con.execute('BEGIN IMMEDIATE');state=read(con)
        if state.get('phase') in PENDING:
            state.update(phase='pausing' if state['phase'] in {'opening','open'} else 'required',request=None)
            save(con,state)


def gate(con,now):
    """Same shared reservation ledger, lower configured cap/longer spacing kept."""
    import web_search
    limit,interval=web_search.free_policy()
    tables={row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    hold=con.execute('SELECT blocked_until FROM web_state WHERE id=4').fetchone() if 'web_state' in tables else None
    retry=hold[0] if hold else 0
    reason='cooldown_wait' if retry>now else 'available'
    navigation_at=web_search.navigation_retry(con,now)
    if navigation_at>max(now,retry):retry=navigation_at;reason='pacing_wait'
    if 'web_requests' in tables:
        count,first=con.execute('SELECT COUNT(*),MIN(timestamp) FROM web_requests WHERE timestamp>?',(now-86400,)).fetchone()
        last=con.execute('SELECT MAX(timestamp) FROM web_requests').fetchone()[0]
        if last is not None and last+interval>max(now,retry):retry=last+interval;reason='pacing_wait'
        if count>=limit:retry=max(retry,first+86400);reason='daily_budget_wait'
    return reason,retry if retry>now else 0


def status():
    with app.db() as con:
        state=read(con);paused,generation=control(con);reason,retry=gate(con,time.time())
    alive=owner_alive(state)
    phase=state['phase']
    if phase in PENDING|{'pausing'} and (not alive or state.get('generation')!=generation):phase='required' if state.get('human_verification') else 'idle'
    if paused:phase='pausing' if alive and state.get('phase') in {'opening','open'} else 'paused'
    return {'engine':'yandex','phase':phase,'human_verification':bool(state.get('human_verification')),
            'verification_pending':phase in PENDING,'window':state.get('window','closed') if phase in PENDING|{'pausing'} else 'closed',
            'availability':reason,'retry_at':retry,'alive':alive,'failure':state.get('failure','')}


def required(url,query):
    import free_search_browser
    if not free_search_browser.yandex_url(url) or not query or len(query)>500:
        raise ValueError('Invalid Yandex challenge state.')
    with app.db() as con:
        con.execute('BEGIN IMMEDIATE');state=read(con)
        if not _owner or state.get('owner')!=_owner:raise ValueError('Yandex challenge owner unavailable.')
        state.update(human_verification=True,url=url,query=query,phase='required',window='closed',request=None,failure='')
        save(con,state)


def search_phase(phase):
    with app.db() as con:
        con.execute('BEGIN IMMEDIATE');state=read(con)
        if _owner and state.get('owner')==_owner and not state.get('human_verification') and state.get('phase') not in PENDING:
            state.update(phase=phase,window='closed');save(con,state)


def request(body):
    if body!={'engine':'yandex'}:raise ValueError('An explicit Yandex request is required.')
    with app.db() as con:
        con.execute('BEGIN IMMEDIATE');state=read(con);paused,generation=control(con)
        if paused:raise ValueError('Processing is paused.')
        if not owner_alive(state):raise ValueError('The metadata worker is unavailable.')
        if not state.get('human_verification'):raise ValueError('No Yandex verification is pending.')
        if state.get('phase') in PENDING and state.get('generation')==generation:
            return {'ok':True,'state':'already_requested','engine':'yandex'}
        state.update(phase='queued',request=uuid.uuid4().hex,generation=generation,window='closed',failure='')
        save(con,state)
    return {'ok':True,'state':'queued','engine':'yandex'}


def cancel():
    with app.db() as con:
        con.execute('BEGIN IMMEDIATE');state=read(con)
        if state.get('owner')==_owner and state.get('phase') in PENDING:
            state.update(phase='required' if state.get('human_verification') else 'idle',request=None,window='closed')
            save(con,state)


def service():
    """Run only between metadata operations, never from the HTTP thread."""
    import free_search_browser
    import pause_control
    with app.db() as con:
        con.execute('BEGIN IMMEDIATE');state=read(con);paused,generation=control(con)
        if not _owner or state.get('owner')!=_owner:raise ValueError('Yandex owner changed.')
        if state.get('phase')!='queued':return False
        if paused or generation!=state.get('generation'):
            state.update(phase='required',request=None,window='closed');save(con,state);return False
        if gate(con,time.time())[1]:return False
        # Validate retained input again before a paid-in-ledger browser attempt.
        if not state.get('human_verification') or not free_search_browser.yandex_url(state.get('url','')):
            state.update(phase='failed',request=None,failure='open');save(con,state);return False
        con.execute('CREATE TABLE IF NOT EXISTS web_requests(timestamp REAL)')
        con.execute('INSERT INTO web_requests VALUES(?)',(time.time(),))
        state.update(phase='opening',window='closed');save(con,state)
    request_id=state['request']
    opened=False
    def admitted():
        with app.db() as con:
            current=read(con);paused,generation=control(con)
        if paused or generation!=state['generation'] or current.get('owner')!=_owner or current.get('request')!=request_id or current.get('phase') not in {'opening','open'}:
            raise pause_control.PauseRequested()
    def on_open():
        nonlocal opened
        admitted()
        opened=True
        with app.db() as con:
            con.execute('BEGIN IMMEDIATE');current=read(con)
            if current.get('owner')!=_owner or current.get('request')!=request_id:raise ValueError('Yandex request changed.')
            current.update(phase='open',window='open');save(con,current)
    success=False;failure='unfinished'
    try:
        success=free_search_browser.verify_yandex(state['url'],state['query'],on_open,admitted)
    except pause_control.PauseRequested:
        failure='paused'
    except Exception:
        failure='unfinished' if opened else 'open'
    # Return through verified profile/descendant closure before success/pause.
    free_search_browser.close()
    with app.db() as con:
        con.execute('BEGIN IMMEDIATE');current=read(con);paused,generation=control(con)
        if current.get('owner')!=_owner:return True
        if current.get('request')!=request_id:
            if current.get('request') is None:
                current.update(phase='required' if current.get('human_verification') else 'idle',window='closed');save(con,current)
            return True
        if paused or generation!=current.get('generation') or failure=='paused':success=False;failure='paused'
        current.update(phase='verified' if success else 'required' if failure=='paused' else 'failed',
                       human_verification=not success,window='closed',request=None,failure='' if success else failure)
        if success:current.pop('url',None);current.pop('query',None)
        save(con,current)
    return True


def active():
    """Yandex is searched only while it is one of the regular engines (removed 2026-10-12).

    While it is not, no verification window opens and the dashboard shows no Yandex row;
    the saved state, hold and dedicated profile are kept unchanged."""
    import web_search
    return 'yandex' in web_search.FREE_ENGINES
