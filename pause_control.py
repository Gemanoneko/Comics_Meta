"""Durable cooperative pause shared by both workers and manual actions."""
import json
import time
import urllib.request
import app


class PauseRequested(Exception):
    pass


def table(con):
    con.execute('CREATE TABLE IF NOT EXISTS processing_control(id INTEGER PRIMARY KEY,paused INTEGER,generation INTEGER,model_unloaded INTEGER,unload_attempt REAL,error TEXT)')
    con.execute("INSERT OR IGNORE INTO processing_control VALUES(1,0,0,0,0,'')")
    con.execute('CREATE TABLE IF NOT EXISTS processing_ack(worker TEXT PRIMARY KEY,generation INTEGER,timestamp REAL)')


def requested():
    with app.db() as con:
        table(con)
        return bool(con.execute('SELECT paused FROM processing_control WHERE id=1').fetchone()[0])


def change(paused):
    with app.db() as con:
        table(con)
        con.execute("UPDATE processing_control SET paused=?,generation=generation+1,model_unloaded=0,unload_attempt=0,error='' WHERE id=1 AND paused<>?",(int(paused),int(paused)))
    return status()


def status():
    with app.db() as con:
        table(con)
        row=dict(con.execute('SELECT * FROM processing_control WHERE id=1').fetchone())
        ack={r['worker'] for r in con.execute('SELECT worker FROM processing_ack WHERE generation=?',(row['generation'],))}
    phase='running'
    if row['paused']:phase='paused' if {'metadata','browser'}<=ack else 'pausing'
    return {'requested':bool(row['paused']),'phase':phase,'gpu_released':bool(row['model_unloaded']),
            'waiting_for':sorted({'metadata','browser'}-ack) if row['paused'] else [],'error':row['error']}


def unload_model():
    from local_model import MODEL
    body=json.dumps({'model':MODEL,'keep_alive':0,'stream':False}).encode()
    req=urllib.request.Request('http://127.0.0.1:11434/api/generate',data=body,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as response:json.load(response)
    with urllib.request.urlopen('http://127.0.0.1:11434/api/ps',timeout=5) as response:
        if any(m.get('name')==MODEL for m in json.load(response).get('models',[])):
            raise ValueError('Gemma is still loaded.')


def checkpoint(worker):
    """Called only after an in-flight operation has finished safely."""
    now=time.time()
    with app.db() as con:
        table(con)
        row=dict(con.execute('SELECT * FROM processing_control WHERE id=1').fetchone())
        if not row['paused']:
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
            con.execute('UPDATE processing_control SET model_unloaded=?,error=? WHERE id=1 AND generation=? AND paused=1',(success,error,row['generation']))
    return True


def sleep(seconds):
    """Wake promptly for a pause without busy polling during normal pacing."""
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        if requested():return
        time.sleep(min(1,max(0,until-time.monotonic())))
