"""Durable cooperative pause shared by both workers and manual actions.

Quit is a separate, transient stop: workers finish their current safe step and
exit, and nothing is saved for the next launch. The saved Pause setting is left
exactly as it was.
"""
import json
import os
import time
import urllib.request
import app
import file_lock
import qa_runtime

STOP_BASELINE_ENV = 'COMICS_META_STOP_BASELINE'
_stop_baseline = None  # Quit generation this process already outlived; None: never stops.


class PauseRequested(Exception):
    pass


def table(con):
    con.execute('CREATE TABLE IF NOT EXISTS processing_control(id INTEGER PRIMARY KEY,paused INTEGER,generation INTEGER,model_unloaded INTEGER,unload_attempt REAL,error TEXT)')
    con.execute("INSERT OR IGNORE INTO processing_control VALUES(1,0,0,0,0,'')")
    con.execute('CREATE TABLE IF NOT EXISTS processing_ack(worker TEXT PRIMARY KEY,generation INTEGER,timestamp REAL)')
    con.execute('CREATE TABLE IF NOT EXISTS processing_shell_pause(id INTEGER PRIMARY KEY,until REAL NOT NULL)')


def _effective(con):
    """A short renewed shell lease pauses workers without changing the user's choice.

    Monotonic time is shared across Windows processes. Expired/crashed shells
    cannot leave the next launch durably paused."""
    row = con.execute('SELECT until FROM processing_shell_pause WHERE id=1').fetchone()
    user = bool(con.execute('SELECT paused FROM processing_control WHERE id=1').fetchone()[0])
    if row and row[0] <= time.monotonic():
        con.execute('DELETE FROM processing_shell_pause WHERE id=1')
        if not user:
            con.execute("UPDATE processing_control SET generation=generation+1,model_unloaded=0,unload_attempt=0,error='' WHERE id=1")
        row = None
    return user or bool(row)


def shell_pause(paused):
    """The authenticated owning shell renews its temporary pause every three seconds."""
    with app.db() as con:
        table(con)
        before = _effective(con)
        if paused:
            con.execute('INSERT OR REPLACE INTO processing_shell_pause VALUES(1,?)', (time.monotonic()+15,))
        else:
            con.execute('DELETE FROM processing_shell_pause WHERE id=1')
        if before != _effective(con):
            con.execute("UPDATE processing_control SET generation=generation+1,model_unloaded=0,unload_attempt=0,error='' WHERE id=1")
    return status()


def requested():
    """Pause is saved, or this process has been asked to quit."""
    with app.db() as con:
        table(con)
        return _effective(con) or _stopping(con)


def _stop_generation(con):
    # Read-only: the table appears with the first Quit.
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name='processing_stop'").fetchone():return 0
    row=con.execute('SELECT generation FROM processing_stop WHERE id=1').fetchone()
    return row[0] if row else 0


def _stopping(con):
    return _stop_baseline is not None and _stop_generation(con)>_stop_baseline


def stop_generation():
    with app.db() as con:return _stop_generation(con)


def begin_run(baseline=None):
    """Record which Quit requests this process has already outlived.

    The supervisor passes the generation it read before launching a worker, so a
    Quit that lands while the worker is still starting is not missed."""
    global _stop_baseline
    if baseline is None:
        value=os.environ.get(STOP_BASELINE_ENV,'').strip()
        baseline=int(value) if value.isdigit() else stop_generation()
    _stop_baseline=int(baseline)
    return _stop_baseline


def stop_requested():
    if _stop_baseline is None:return False
    with app.db() as con:return _stopping(con)


def request_stop():
    """Quit: running workers of this state root finish their current safe step and exit.

    Only processes started before this call stop, so the next launch runs normally
    and the saved Pause setting is untouched."""
    with app.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS processing_stop(id INTEGER PRIMARY KEY,generation INTEGER NOT NULL,requested REAL NOT NULL)')
        con.execute('INSERT OR IGNORE INTO processing_stop VALUES(1,0,0)')
        con.execute('UPDATE processing_stop SET generation=generation+1,requested=? WHERE id=1',(time.time(),))
        return _stop_generation(con)


def worker_leases():
    return {'metadata':app.DATA/'queue'/'worker.lock','browser':app.DATA/'browser-worker.lock'}


def hold_worker_leases(timeout=None,poll=0.5):
    """Wait until no worker of this state root is running, then hold both leases.

    A worker keeps its lease for its whole life, so a free lease proves that worker
    has exited, including one left over from an earlier launch. Holding the leases
    keeps a late worker from starting until this process exits."""
    held={}
    deadline=None if timeout is None else time.monotonic()+timeout
    try:
        while True:
            for name,path in worker_leases().items():
                if name in held:continue
                path.parent.mkdir(parents=True,exist_ok=True)
                fd=file_lock.open_lock(path)
                if file_lock.try_lock(fd):held[name]=fd
                else:os.close(fd)
            if len(held)==len(worker_leases()):return held
            if deadline is not None and time.monotonic()>=deadline:
                raise TimeoutError('Workers still running: '+', '.join(sorted(set(worker_leases())-set(held))))
            time.sleep(poll)
    except BaseException:
        for fd in held.values():os.close(fd)
        raise


def change(paused):
    with app.db() as con:
        table(con)
        con.execute("UPDATE processing_control SET paused=?,generation=generation+1,model_unloaded=0,unload_attempt=0,error='' WHERE id=1 AND paused<>?",(int(paused),int(paused)))
    return status()


def status():
    with app.db() as con:
        table(con)
        effective = _effective(con)
        row=dict(con.execute('SELECT * FROM processing_control WHERE id=1').fetchone())
        ack={r['worker'] for r in con.execute('SELECT worker FROM processing_ack WHERE generation=?',(row['generation'],))}
        stopping=_stopping(con)
    phase='running'
    if effective:phase='paused' if {'metadata','browser'}<=ack else 'pausing'
    return {'requested':effective,'user_requested':bool(row['paused']),'phase':phase,'gpu_released':bool(row['model_unloaded']),
            'waiting_for':sorted({'metadata','browser'}-ack) if effective else [],'error':row['error'],
            'stopping':stopping}


def unload_model():
    from local_model import MODEL
    body=json.dumps({'model':MODEL,'keep_alive':0,'stream':False}).encode()
    req=qa_runtime.model_request('/api/generate',data=body,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as response:json.load(response)
    with urllib.request.urlopen(qa_runtime.model_request('/api/ps'),timeout=5) as response:
        if any(m.get('name')==MODEL for m in json.load(response).get('models',[])):
            raise ValueError('Gemma is still loaded.')


def checkpoint(worker):
    """Called only after an in-flight operation has finished safely."""
    now=time.time()
    with app.db() as con:
        table(con)
        effective = _effective(con)
        row=dict(con.execute('SELECT * FROM processing_control WHERE id=1').fetchone())
        if not effective:
            con.execute('DELETE FROM processing_ack WHERE worker=?',(worker,))
            return False
        con.execute('INSERT OR REPLACE INTO processing_ack VALUES(?,?,?)',(worker,row['generation'],now))
        attempt=worker=='metadata' and not row['model_unloaded'] and now-row['unload_attempt']>10
        if attempt:con.execute('UPDATE processing_control SET unload_attempt=? WHERE id=1',(now,))
    if attempt:
        try:
            unload_model();success=1;error=''
        except Exception:
            success=0;error='Workers paused, but Gemma GPU release could not be confirmed. Retrying.'
        with app.db() as con:
            if _effective(con):
                con.execute('UPDATE processing_control SET model_unloaded=?,error=? WHERE id=1 AND generation=?',(success,error,row['generation']))
    return True


def sleep(seconds):
    """Wake promptly for a pause without busy polling during normal pacing."""
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        if requested():return
        time.sleep(min(1,max(0,until-time.monotonic())))
