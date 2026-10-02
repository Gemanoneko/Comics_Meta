"""Persistent folder-by-folder delta passes; a pass is not a completeness claim."""
import json
import os
import time
from pathlib import Path
import app
import storage

STATE=app.DATA/'folders.json'

def folders(root,on_progress=None):
    root=Path(root).resolve()
    if not root.is_dir():raise ValueError('Library root unavailable.')
    result=[]
    visited=0;last_update=0
    for folder,dirs,files in os.walk(app.filesystem_path(root),followlinks=False):
        visited+=1
        if on_progress and time.time()-last_update>5:
            on_progress(visited,len(result));last_update=time.time()
        dirs[:]=[d for d in dirs if d not in {'.yacreaderlibrary','.comic-metadata-backups'}]
        if not any(Path(f).suffix.lower() in {'.cbz','.cbr','.cb7'} for f in files):continue
        text=folder[4:] if folder.startswith('\\\\?\\') else folder
        path=Path(text).resolve()
        if path.is_relative_to(root):result.append(str(path))
    return sorted(result,key=lambda p:(not ('!Coffin Comics' in Path(p).parts),p.casefold()))

def select(root,now=None,on_progress=None):
    now=time.time() if now is None else now
    state=json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'folders':{}}
    root=Path(root).resolve()
    if not root.is_dir():raise ValueError('Library root unavailable.')
    changed=state.get('root')!=str(root)
    if changed or (not state.get('inventory_pending') and now-state.get('inventoried_at',0)>600):
        prefix=str(root).rstrip('\\/')+os.sep
        state['folders']={p:v for p,v in state['folders'].items() if p.casefold().startswith(prefix.casefold()) or p==str(root)}
        state.update(root=str(root),inventory_pending=[str(root)],inventory_seen=[],inventory_visited=0,inventory_errors=[])
    if state.get('inventory_pending'):
        # Persist a bounded traversal and begin processing found folders immediately.
        # A huge DAS must not finish its entire tree walk before the first write.
        started=time.time()
        for _ in range(50):
            if not state['inventory_pending'] or time.time()-started>10:break
            folder=state['inventory_pending'].pop()
            try:
                with os.scandir(app.filesystem_path(folder)) as entries:items=list(entries)
                children=[];has_comics=False
                for entry in items:
                    if entry.name.lower() in {'.yacreaderlibrary','.comic-metadata-backups','.git'}:continue
                    if entry.is_symlink():continue
                    if entry.is_dir(follow_symlinks=False):
                        if getattr(entry.stat(follow_symlinks=False),'st_file_attributes',0)&0x400:continue
                        children.append(str(Path(folder)/entry.name))
                    elif Path(entry.name).suffix.lower() in {'.cbz','.cbr','.cb7'}:has_comics=True
                state['inventory_pending'].extend(sorted(children,key=str.casefold,reverse=True))
                if has_comics:
                    state['inventory_seen'].append(folder)
                    state['folders'].setdefault(folder,{'next_scan':0})
            except OSError:
                state['inventory_errors'].append(folder)
                state['inventory_errors']=state['inventory_errors'][-100:]
            state['inventory_visited']+=1
        if on_progress:on_progress(state['inventory_visited'],len(state['inventory_seen']))
        if not state['inventory_pending']:
            if not state['inventory_errors']:
                seen=set(state['inventory_seen']);state['folders']={p:v for p,v in state['folders'].items() if p in seen}
            state['inventoried_at']=now
            state.pop('inventory_seen',None)
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
