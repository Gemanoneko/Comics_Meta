"""Persistent folder-by-folder delta passes; a pass is not a completeness claim."""
import json
import os
import time
from pathlib import Path
import app
import storage

STATE=app.DATA/'folders.json'

def folders(root):
    root=Path(root).resolve()
    if not root.is_dir():raise ValueError('Library root unavailable.')
    result=[]
    for folder,dirs,files in os.walk(app.filesystem_path(root),followlinks=False):
        dirs[:]=[d for d in dirs if d not in {'.yacreaderlibrary','.comic-metadata-backups'}]
        if not any(Path(f).suffix.lower() in {'.cbz','.cbr','.cb7'} for f in files):continue
        text=folder[4:] if folder.startswith('\\\\?\\') else folder
        path=Path(text).resolve()
        if path.is_relative_to(root):result.append(str(path))
    return sorted(result,key=lambda p:(not ('!Coffin Comics' in Path(p).parts),p.casefold()))

def select(root,now=None):
    now=time.time() if now is None else now
    state=json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'folders':{}}
    if state.get('root')!=str(Path(root).resolve()) or now-state.get('inventoried_at',0)>600:
        current=folders(root)
        state['folders']={p:state['folders'].get(p,{'next_scan':0}) for p in current}
        state.update(root=str(Path(root).resolve()),inventoried_at=now)
        save(state)
    due=[p for p,v in state['folders'].items() if v.get('next_scan',0)<=now]
    if not due:return None
    return min(due,key=lambda p:(state['folders'][p].get('next_scan',0),p.casefold()))

def save(state):
    storage.save(STATE,state)

def finish(folder,queued=False,error=None):
    state=json.loads(STATE.read_text(encoding='utf-8'))
    state['folders'][str(folder)]={'next_scan':0 if queued else time.time()+(3600 if error else 600),
        'last_pass':time.time(),'state':'writing' if queued else 'retry_wait' if error else 'pass_complete',
        'error':error}
    save(state)
