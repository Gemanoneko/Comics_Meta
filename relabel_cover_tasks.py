"""One-time v0.1.2 deploy step: requeue Lens searches that never ran.

Before v0.1.2 a Google Lens search that was blocked (cooldown, daily cap or
human check) was saved as an empty result: state 'retry_wait' with the detail
LEGACY_DETAIL, its queue time reset. This returns those tasks to 'pending'
with their 'updated' time kept, so they are searched again in their original
queue order. Genuine empty searches carry the same detail and cannot be told
apart; they simply get one more search.

Every relabelled row is copied to the backup table first, in the same
transaction, so --rollback restores state, detail and updated exactly.

Run from the checkout the service uses, with processing paused
(dashboard: Pause, wait for Paused), before starting v0.1.2:

    python relabel_cover_tasks.py             dry run: counts only, no writes
    python relabel_cover_tasks.py --apply     relabel and record the backup
    python relabel_cover_tasks.py --rollback  restore rows from the backup

--data <folder> points at another data folder (default: this checkout's data/).
"""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

LEGACY_DETAIL='No usable cover-search candidates; retry after one day.'
# The detail every newly queued cover search carries.
QUEUED_DETAIL='Browser reverse-image research queued; no metadata write authorized.'
BACKUP='cover_tasks_relabel_v012'


class Refused(Exception):
    pass


def database(data):
    path=Path(data)/'catalog.sqlite'
    if not path.is_file():raise Refused('No catalog at '+str(path)+'.')
    return path


def connect(path,readonly):
    if readonly:return sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=30)
    con=sqlite3.connect(path,timeout=30)
    con.isolation_level=None  # Explicit BEGIN IMMEDIATE / COMMIT below.
    return con


def has_table(con,name):
    return bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone())


def paused(con):
    """Both workers acknowledged a pause (the dashboard shows Paused)."""
    if not has_table(con,'processing_control'):return False
    row=con.execute('SELECT paused,generation FROM processing_control WHERE id=1').fetchone()
    if not row or not row[0]:return False
    if not has_table(con,'processing_ack'):return False
    acked={r[0] for r in con.execute('SELECT worker FROM processing_ack WHERE generation=?',(row[1],))}
    return {'metadata','browser'}<=acked


def counts(con):
    tasks=has_table(con,'cover_tasks')
    backup=has_table(con,BACKUP)
    result={'paused':paused(con),
            'to_relabel':con.execute("SELECT COUNT(*) FROM cover_tasks WHERE state='retry_wait' AND detail=?",(LEGACY_DETAIL,)).fetchone()[0] if tasks else 0,
            'backup_rows':con.execute('SELECT COUNT(*) FROM '+BACKUP).fetchone()[0] if backup else 0,
            'restorable':0}
    if tasks and backup:
        result['restorable']=con.execute('SELECT COUNT(*) FROM cover_tasks t JOIN '+BACKUP+" b USING(path) WHERE t.state='pending' AND t.detail=? AND t.updated=b.updated",(QUEUED_DETAIL,)).fetchone()[0]
    return result


def require_paused(con):
    if not paused(con):raise Refused('Processing is not paused. Press Pause in the dashboard and wait for Paused, then run again.')


def apply(con):
    con.execute('BEGIN IMMEDIATE')
    try:
        require_paused(con)
        if not has_table(con,'cover_tasks'):raise Refused('No cover_tasks table; nothing to relabel.')
        if has_table(con,BACKUP) and con.execute('SELECT COUNT(*) FROM '+BACKUP).fetchone()[0]:
            raise Refused('A previous relabel is still recorded in '+BACKUP+'. Roll it back first.')
        con.execute('CREATE TABLE IF NOT EXISTS '+BACKUP+'(path TEXT PRIMARY KEY,state TEXT,updated REAL,detail TEXT,relabeled_at REAL)')
        now=time.time()
        backed=con.execute('INSERT INTO '+BACKUP+" SELECT path,state,updated,detail,? FROM cover_tasks WHERE state='retry_wait' AND detail=?",(now,LEGACY_DETAIL)).rowcount
        # Only state and detail change; 'updated' (queue position) is kept.
        changed=con.execute("UPDATE cover_tasks SET state='pending',detail=? WHERE state='retry_wait' AND detail=? AND path IN (SELECT path FROM "+BACKUP+')',(QUEUED_DETAIL,LEGACY_DETAIL)).rowcount
        if changed!=backed:raise Refused('Backup and relabel counts differ (%d, %d); nothing was changed.'%(backed,changed))
        con.execute('COMMIT')
    except BaseException:
        con.execute('ROLLBACK');raise
    return {'relabeled':changed,'backup_rows':backed}


def rollback(con):
    con.execute('BEGIN IMMEDIATE')
    try:
        require_paused(con)
        if not has_table(con,BACKUP):raise Refused('No relabel backup is recorded; nothing to roll back.')
        total=con.execute('SELECT COUNT(*) FROM '+BACKUP).fetchone()[0]
        # A row searched, identified or requeued since the relabel has moved on
        # (its state, detail or updated differs) and is left as it is now.
        restored=con.execute('UPDATE cover_tasks SET state=(SELECT state FROM '+BACKUP+' b WHERE b.path=cover_tasks.path),'
                             'detail=(SELECT detail FROM '+BACKUP+' b WHERE b.path=cover_tasks.path) '
                             "WHERE state='pending' AND detail=? AND updated=(SELECT updated FROM "+BACKUP+' b WHERE b.path=cover_tasks.path)',
                             (QUEUED_DETAIL,)).rowcount
        con.execute('DROP TABLE '+BACKUP)
        con.execute('COMMIT')
    except BaseException:
        con.execute('ROLLBACK');raise
    return {'restored':restored,'left_as_is':total-restored}


def main(argv=None):
    parser=argparse.ArgumentParser(description='Requeue v0.1.1 Lens tasks whose search never ran (reversible).')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--apply',action='store_true',help='relabel and record the backup')
    mode.add_argument('--rollback',action='store_true',help='restore relabelled rows from the backup')
    parser.add_argument('--data',default=str(Path(__file__).resolve().parent/'data'),help='data folder holding catalog.sqlite')
    options=parser.parse_args(argv)
    try:
        path=database(options.data)
        if options.apply or options.rollback:
            con=connect(path,False)
            try:result=apply(con) if options.apply else rollback(con)
            finally:con.close()
            result['mode']='apply' if options.apply else 'rollback'
        else:
            con=connect(path,True)
            try:result=counts(con)
            finally:con.close()
            result['mode']='dry-run'
    except Refused as exc:
        print(json.dumps({'refused':str(exc)}));return 2
    print(json.dumps(result));return 0


if __name__=='__main__':
    sys.exit(main())
