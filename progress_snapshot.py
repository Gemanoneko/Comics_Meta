"""One progress aggregation at a time, with backwards-compatible data.

The payload lists the PAYLOAD_BATCHES most recent write batches; completed_total
counts every batch in progress.json. Only immutable parsed values are cached. File identity detects atomic replace;
removed queue files are evicted. No history, queue, plan or archive is rewritten.
"""
import copy
import hashlib
import json
import threading
import time
import app

PAYLOAD_BATCHES = 100


class Files:
    def __init__(self):self.values={}

    def read(self,path,default):
        try:stat=path.stat()
        except FileNotFoundError:
            self.values.pop(path,None);return default
        key=(stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)
        previous=self.values.get(path)
        if previous is not None and previous[0]==key:return previous[1]
        value=json.loads(path.read_text(encoding='utf-8'))
        self.values[path]=(key,value)
        return value

    def queue(self,path):
        paths=set(path.glob('*.json'))
        for old in list(self.values):
            if old.parent==path and old not in paths:self.values.pop(old,None)
        return [self.read(item,{}) for item in paths]


def collect(files):
    import pause_control,discovery_state,cover_tasks,browser_search,providers,research_runtime
    result=dict(files.read(app.DATA/'progress.json',{'phase':'Ready','current_folder':'','completed':[]}))
    completed=result.get('completed',[])
    # The dashboard lists recent batches; older summaries stay on disk, not in every poll.
    result['completed_total']=len(completed)
    completed=result['completed']=completed[-PAYLOAD_BATCHES:]
    result['completed_revision']=hashlib.sha256(json.dumps(completed,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    queue_dir=app.DATA/'queue';tickets=files.queue(queue_dir)
    heartbeat=files.read(queue_dir/'heartbeat',{})
    result['queue']={'alive':0<=time.time()-heartbeat.get('timestamp',0)<15,
                    **{state:sum(t.get('state')==state for t in tickets) for state in ('pending','running','complete')},
                    'attention':[{'folder':t['folder'],'error':t.get('error','')} for t in tickets if t.get('state')=='needs_attention']}
    result['live_root']=app.live_root()
    result['research']=discovery_state.counts(result['live_root'])
    result['control']=pause_control.status()
    result['cover_research']=cover_tasks.status()
    result['browser_search']=browser_search.public(browser_search.status())
    result['providers']=providers.statuses()
    result['performance']=research_runtime.metrics()
    folder_state=files.read(app.DATA/'folders.json',None)
    if folder_state is not None:
        scheduled=folder_state.get('folders',{})
        result['folders']={'total':len(scheduled),'scanned':sum(bool(v.get('last_pass')) and not v.get('error') for v in scheduled.values()),
                           'passes_complete':sum(v.get('state')=='pass_complete' for v in scheduled.values()),
                           'retry_wait':sum(v.get('state')=='retry_wait' for v in scheduled.values()),
                           'next_scan_at':min((v.get('next_scan',0) for v in scheduled.values()),default=None),
                           'inventory_pending':bool(folder_state.get('inventory_pending')),'directories_visited':folder_state.get('inventory_visited',0)}
    return result


class Snapshot:
    def __init__(self,collector=collect,interval=2):
        self.collector=collector;self.interval=interval;self.files=Files()
        self.lock=threading.Lock();self.value=None;self.refreshing=False;self.last=0;self.closed=False;self.error=''

    def refresh(self):
        try:value=self.collector(self.files)
        except Exception as exc:
            with self.lock:self.error=type(exc).__name__
        else:
            with self.lock:self.value=value;self.error=''
        finally:
            with self.lock:self.last=time.monotonic();self.refreshing=False

    def get(self,revision=None):
        with self.lock:
            if not self.closed and not self.refreshing and (self.value is None or time.monotonic()-self.last>=self.interval):
                self.refreshing=True;threading.Thread(target=self.refresh,daemon=True,name='progress-snapshot').start()
            if self.value is None:raise ValueError('Progress snapshot is preparing. Retry shortly.')
            # Shallow copy first; unchanged completed history is omitted only on
            # explicit revision opt-in. All legacy callers receive every row.
            value=dict(self.value)
            if revision and revision==value.get('completed_revision'):value.pop('completed',None)
            value=copy.deepcopy(value)
            value['snapshot_at']=self.last;value['snapshot_stale']=bool(self.refreshing or self.error)
            return value

    def close(self):
        with self.lock:self.closed=True
