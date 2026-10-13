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
import pause_control

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


_complete = {}  # ticket path -> (mtime_ns, size) of a ticket last read as complete


def tickets():
    """(path, ticket) for every queue ticket, in queue order.

    The queue keeps every completed ticket, thousands on a large library, and
    reading them all on each worker loop and catalog probe took about a second.
    A ticket last read as complete is skipped until its file changes; every
    other ticket is always read from disk."""
    result = []
    seen = set()
    if not QUEUE.is_dir():
        return result
    with os.scandir(QUEUE) as entries:
        for entry in entries:
            if not entry.name.endswith('.json') or not entry.is_file():
                continue
            path = Path(entry.path)
            stat = entry.stat()
            key = (stat.st_mtime_ns, stat.st_size)
            seen.add(path)
            if _complete.get(path) == key:
                result.append((path, {'state': 'complete'}))
                continue
            item = json.loads(path.read_text(encoding='utf-8'))
            if item.get('state') == 'complete':
                _complete[path] = key
            else:
                _complete.pop(path, None)
            result.append((path, item))
    for path in [p for p in _complete if p.parent == QUEUE and p not in seen]:
        _complete.pop(path, None)
    return sorted(result, key=lambda pair: pair[0].name)


def run_one():
    if pause_control.requested():return False
    QUEUE.mkdir(parents=True, exist_ok=True)
    for ticket, item in tickets():
        if item['state'] != 'pending':
            continue
        item.update(state='running', started=time.time())
        save(ticket, item)
        try:
            import research_runtime
            with research_runtime.stage('Archive write and verification'):
                batch.apply(item['plan'], remove_verified_backups=True)
            item.update(state='complete', finished=time.time())
        except pause_control.PauseRequested:
            item.update(state='pending',paused=time.time())
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
    import free_search_browser
    free_search_browser.enable_worker_owner()
    import yandex_verification
    yandex_verification.initialize()
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
        if pause_control.requested():
            import free_search_browser
            free_search_browser.close()
            yandex_verification.cancel()
        if pause_control.checkpoint('metadata'):
            time.sleep(1)
            next_discovery=0
            continue
        try:
            if yandex_verification.active() and yandex_verification.service():continue
            import maintenance
            try:maintenance.run()
            except Exception:pass  # Cleanup failures must not stop metadata processing.
            ran = run_one()
        except OSError:
            # Leave a running ticket for inspection; never blindly replay a partial write.
            try:batch.progress(phase='Automatic lookup waiting',detail='Queue storage is temporarily unavailable; retrying safely.')
            except OSError:pass
            time.sleep(10)
            continue
        if not ran:
            if pause_control.requested():continue
            config_path = app.BASE / 'config.json'
            config = json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
            automatic = config.get('automatic', {})
            if automatic.get('enabled') and time.time() >= next_discovery:
                next_discovery = time.time() + 600
                try:
                    import automatic as discovery
                    import scheduler
                    root=automatic.get('library_root') or automatic.get('root')
                    if not root:raise ValueError('Automatic lookup requires library_root or root.')
                    def inventory_progress(visited,found):
                        batch.progress(phase='Inventorying live folders',current_folder=root,
                                       detail=str(visited)+' directories visited; '+str(found)+' comic folders found. No archives are changed during this step.')
                    selection = scheduler.select(root,on_progress=inventory_progress,with_mode=True)
                    folder = selection['folder'] if selection else None
                    if not folder:
                        state=json.loads(scheduler.STATE.read_text(encoding='utf-8'))
                        if state.get('inventory_pending') or state.get('coverage_pending'):
                            if state.get('coverage_pending'):
                                batch.progress(phase='Checking first-update readiness',detail='Checking the next bounded catalog slice before selecting refinement work. Existing source waits are retained.')
                            next_discovery=0
                            time.sleep(2)
                            continue
                        waiting=[v for v in state.get('folders',{}).values() if v.get('state')=='retry_wait']
                        batch.progress(phase='Automatic lookup waiting' if waiting else 'Waiting for delta scan',detail=(str(len(waiting))+' folders waiting to retry earlier failures.' if waiting else 'Scheduled folder passes finished; watching for new or changed files.'))
                        due=[v.get('next_scan',0) for v in state.get('folders',{}).values()]
                        if due:next_discovery=min(next_discovery,max(time.time()+2,min(due)))
                        time.sleep(2)
                        continue
                    queued = discovery.discover(folder,coverage_only=selection['coverage_only'])
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
            pause_control.sleep(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--enqueue', nargs='+')
    options = parser.parse_args()
    if options.enqueue:
        for plan in options.enqueue:
            print(enqueue(plan))
    else:
        try:main()
        finally:
            import free_search_browser
            free_search_browser.close()
