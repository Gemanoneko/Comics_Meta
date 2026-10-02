"""Persistent serial queue for reviewed folder plans; no guessed matches."""
import argparse
import json
import os
import time
import threading
from pathlib import Path
import batch
import app
import storage

QUEUE = app.DATA / 'queue'


def save(path, value):
    storage.save(path,value)


def enqueue(plan_path):
    plan_path = Path(plan_path).resolve()
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    if not plan.get('entries') or not plan.get('folder'):
        raise ValueError('A reviewed folder plan is required.')
    QUEUE.mkdir(parents=True, exist_ok=True)
    target = QUEUE / (plan_path.parent.name + '.json')
    if not target.exists():
        save(target, dict(plan=str(plan_path), folder=plan['folder'], state='pending'))
    return target


def run_one():
    QUEUE.mkdir(parents=True, exist_ok=True)
    for ticket in sorted(QUEUE.glob('*.json')):
        item = json.loads(ticket.read_text(encoding='utf-8'))
        if item['state'] != 'pending':
            continue
        item.update(state='running', started=time.time())
        save(ticket, item)
        try:
            batch.apply(item['plan'], remove_verified_backups=True)
            item.update(state='complete', finished=time.time())
        except Exception as exc:
            # Never retry a partially written plan blindly or remove its backups.
            item.update(state='needs_attention', error=str(exc), finished=time.time())
        save(ticket, item)
        return True
    return False


def main():
    QUEUE.mkdir(parents=True, exist_ok=True)
    lock = (QUEUE / 'worker.lock').open('a+b')
    lock.seek(0); lock.write(b'0'); lock.flush(); lock.seek(0)
    if os.name == 'nt':
        import msvcrt
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return  # Another worker already owns the queue.
    else:
        import fcntl
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return
    # An interrupted write needs inspection, not an automatic replay.
    for ticket in QUEUE.glob('*.json'):
        item = json.loads(ticket.read_text(encoding='utf-8'))
        if item['state'] == 'running':
            item.update(state='needs_attention', error='Interrupted batch; inspect results and retained backups before requeuing.')
            save(ticket, item)
    def heartbeat():
        while True:
            try:save(QUEUE / 'heartbeat', dict(pid=os.getpid(), timestamp=time.time()))
            except OSError:pass  # A brief reader lock must not kill all future heartbeats.
            time.sleep(2)
    threading.Thread(target=heartbeat, daemon=True).start()
    next_discovery = 0
    while True:
        try:
            ran = run_one()
        except OSError:
            # Leave a running ticket for inspection; never blindly replay a partial write.
            try:batch.progress(phase='Automatic lookup waiting',detail='Queue storage is temporarily unavailable; retrying safely.')
            except OSError:pass
            time.sleep(10)
            continue
        if not ran:
            config_path = app.BASE / 'config.json'
            config = json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
            automatic = config.get('automatic', {})
            if automatic.get('enabled') and time.time() >= next_discovery:
                next_discovery = time.time() + 600
                try:
                    import automatic as discovery
                    import scheduler
                    root=automatic.get('library_root',automatic['root'])
                    def inventory_progress(visited,found):
                        batch.progress(phase='Inventorying live folders',current_folder=root,
                                       detail=str(visited)+' directories visited; '+str(found)+' comic folders found. No archives are changed during this step.')
                    folder = scheduler.select(root,on_progress=inventory_progress)
                    if not folder:
                        state=json.loads(scheduler.STATE.read_text(encoding='utf-8'))
                        if state.get('inventory_pending'):
                            next_discovery=0
                            time.sleep(2)
                            continue
                        waiting=[v for v in state.get('folders',{}).values() if v.get('state')=='retry_wait']
                        batch.progress(phase='Automatic lookup waiting' if waiting else 'Waiting for delta scan',detail=(str(len(waiting))+' folders waiting to retry earlier failures.' if waiting else 'Scheduled folder passes finished; watching for new or changed files.'))
                        due=[v.get('next_scan',0) for v in state.get('folders',{}).values()]
                        if due:next_discovery=min(next_discovery,max(time.time()+2,min(due)))
                        time.sleep(2)
                        continue
                    queued = discovery.discover(folder)
                    scheduler.finish(folder,queued=queued)
                    if not queued:
                        batch.progress(phase='Advancing to next folder',detail='Folder pass finished. Unresolved research is retained; selecting the next due folder.')
                    next_discovery = 0
                    if queued:
                        next_discovery = 0
                except Exception as exc:
                    if 'folder' in locals() and folder:
                        try:scheduler.finish(folder,error=str(exc))
                        except OSError:pass
                        next_discovery = 0
                    try:batch.progress(phase='Automatic lookup waiting', detail=str(exc))
                    except OSError:pass
            time.sleep(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--enqueue', nargs='+')
    options = parser.parse_args()
    if options.enqueue:
        for plan in options.enqueue:
            print(enqueue(plan))
    else:
        main()
