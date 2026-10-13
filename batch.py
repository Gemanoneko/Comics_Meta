"""Reviewed folder batches. Reference mode requires identical archive page content."""
import argparse
import hashlib
import json
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import app
import discovery_state
import storage
import pause_control


def progress(**updates):
    target=app.BASE/'data'/'progress.json'
    current=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    current.update(updates)
    current['timestamp']=datetime.now(timezone.utc).isoformat()
    storage.save(target,current)


RECENT_BATCHES = 200


def keep_recent_batches(completed):
    """progress.json is rewritten on every progress step; keep its batch list short.

    Older batch summaries move, in order and unchanged, to data/progress-history.jsonl.
    Write history itself is in the catalog and each batch's results.json."""
    if len(completed)<=RECENT_BATCHES:return completed
    older,recent=completed[:-RECENT_BATCHES],completed[-RECENT_BATCHES:]
    app.DATA.mkdir(parents=True,exist_ok=True)
    with (app.DATA/'progress-history.jsonl').open('a',encoding='utf-8') as archive:
        for item in older:archive.write(json.dumps(item,ensure_ascii=False)+'\n')
    return recent


def digest(path):
    with app.filesystem_path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def page_signatures(path):
    with zipfile.ZipFile(app.filesystem_path(path)) as archive:
        return sorted((i.filename,i.CRC,i.file_size) for i in archive.infolist()
                      if i.filename.lower().endswith(('.jpg','.jpeg','.png','.webp')))


def prepare(folder, reference):
    folder=Path(folder).resolve()
    reference=Path(reference).resolve()
    fields,_,_=app.read_metadata(reference)
    if not fields:
        raise ValueError('Reference must already contain reviewed metadata.')
    expected=page_signatures(reference)
    if not expected:
        raise ValueError('Reference contains no pages.')
    entries=[]
    for path in sorted(folder.iterdir()):
        if path.suffix.lower()!='.cbz' or not path.is_file():
            continue
        if page_signatures(path)!=expected:
            entries.append({'path':str(path),'action':'review','reason':'Page content differs from reviewed reference.'})
            continue
        old,_,_=app.read_metadata(path)
        changes={k:{'before':old.get(k,''),'after':v} for k,v in fields.items()
                 if v and k!='Notes' and old.get(k,'')!=v}
        stat=path.stat()
        entries.append({'path':str(path),'action':'write' if changes else 'unchanged',
                        'size':stat.st_size,'mtime':stat.st_mtime_ns,'sha256':digest(path),
                        'changes':changes,'fields':fields})
    output=app.BASE/'batches'/str(time.time_ns())
    output.mkdir(parents=True)
    plan={'folder':str(folder),'reference':str(reference),'entries':entries,
          'method':'Exact page names, CRCs and sizes match the manually reviewed pilot reference.'}
    (output/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Live folder batch plan','',f'Folder: `{folder}`','',plan['method'],'']
    for entry in entries:
        lines += [f"## {Path(entry['path']).name}",'',f"Action: {entry['action']}",'']
        for key,change in entry.get('changes',{}).items():
            lines += [f"- {key}: {change['before'] or '(empty)'} → {change['after']}"]
    (output/'PLAN.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Plan:',str(output/'plan.json'))
    print('Actions:',[(Path(e['path']).name,e['action'],len(e.get('changes',{}))) for e in entries])


def catalog_row(path,folder):
    """The planned archive's catalog row, rescanning its folder only when the row is stale.

    write_metadata compares the row with the file on disk, so an up-to-date row
    needs no scan. A stale or missing row gets the same non-recursive folder scan
    discovery uses; the planned file is always in that folder."""
    stat=app.filesystem_path(path).stat()
    def lookup():
        with app.db() as con:
            row=con.execute('SELECT * FROM comics WHERE path=?',(str(path),)).fetchone()
        return dict(row) if row else None
    row=lookup()
    if row is None or [row['size'],row['mtime']]!=[stat.st_size,stat.st_mtime_ns]:
        app.JOB.update(running=True,visited=0,changed=0,errors=0)
        app.scan([folder],recursive=False)
        row=lookup()
    if row is None:
        raise ValueError('File was not successfully inventoried.')
    return row


def changed_since_planning(path,entry):
    """Why the entry's archive is no longer the one planned, or '' (F22).

    The digest is taken when the comic joins the plan; the signature, when present,
    is the archive's [size, mtime] at the folder scan whose metadata decided the plan."""
    if not app.filesystem_path(path).is_file():
        return 'Archive no longer present; nothing written.'
    if digest(path)!=entry['sha256']:
        return 'Source changed after planning; nothing written.'
    signature=entry.get('signature')
    if signature:
        stat=app.filesystem_path(path).stat()
        if [stat.st_size,stat.st_mtime_ns]!=list(signature):
            return 'Archive changed after the folder scan that planned it; nothing written.'
    return ''


def unchanged(path,sha256):
    """The archive still holds exactly the planned bytes."""
    try:
        return digest(path)==sha256
    except OSError:
        return False


def apply(plan_path, remove_verified_backups=False):
    """Write a reviewed plan, one comic at a time, each with its own checks.

    - A comic whose archive changed since planning (F22) is skipped (skipped.json).
    - A comic whose write failed with its archive untouched (F23) is recorded
      (failed.json) and offered again after the daily retry; the rest are written.
    - An archive that may have been written but did not verify stops the plan; the
      ticket needs attention, and its backup is kept.
    Nothing is written to a skipped or failed comic, and no backup is removed for one."""
    plan_path=Path(plan_path).resolve()
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    result_path=plan_path.parent/'results.json'
    results=json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else []
    finished={r['path']:r for r in results if r.get('metadata_readback_verified')}
    skipped=[]
    failed=[]
    def not_written(path,outcome,reason):
        """Record a comic left unwritten; its discovery record waits for the daily retry."""
        items,name=(skipped,'skipped.json') if outcome=='write_skipped' else (failed,'failed.json')
        items.append({'path':str(path),'reason':reason,'at':time.time()})
        storage.save(plan_path.parent/name,items)
        discovery_state.write_not_done(path,outcome,reason)
        print('Skipped, changed since planning:' if outcome=='write_skipped' else 'Not written, retried later:',path.name,'-',reason)
    progress(phase='Writing and verifying metadata',current_folder=Path(plan['folder']).name,
             total=len(plan['entries']),checked=len(plan['entries']),updated=len(results),
             detail='Each comic is checked after writing; its backup is removed only after verification.')
    for entry in plan['entries']:
        if entry['action']!='write':
            continue
        if pause_control.requested():raise pause_control.PauseRequested('Paused safely between archive writes.')
        path=Path(entry['path']).resolve()
        if path.parent!=Path(plan['folder']).resolve():
            raise ValueError('Target must stay in the planned folder.')
        if str(path) in finished:
            stat=path.stat()
            if finished[str(path)].get('output_signature')!=[stat.st_size,stat.st_mtime_ns]:
                raise ValueError('A completed archive changed before batch resume; inspect it before retrying.')
            continue
        writing=False  # Set once write_metadata may have touched the archive.
        changed=''
        try:
            # A plan can hold several comics, so one comic changed since planning is
            # skipped rather than blocking the others; its new signature makes the next
            # folder pass plan it again from what it holds now.
            changed=changed_since_planning(path,entry)
            if not changed:
                row=catalog_row(path,plan['folder'])
                writing=True
                # F22: the archive's ComicInfo must still hold each planned field's "before"
                # value when it is read for this write; an edit made since the scan is kept.
                # Provenance for writes without a Web URL (e.g. 'in-book:cover') goes into
                # the write history in the same transaction (F27).
                backup=app.write_metadata(row,entry['fields'],append_notes=True,overwrite_fields=set(entry['changes']),
                                          expected={k:c.get('before','') for k,c in entry['changes'].items()},
                                          history_source=entry.get('source'))
        except pause_control.PauseRequested:
            raise
        except app.ArchiveChanged as exc:
            changed=str(exc)
        except Exception as exc:
            if writing and not unchanged(path,entry['sha256']):
                raise  # The archive may have been replaced: keep the ticket and its backups for inspection.
            # F23: nothing was written to this archive (duplicate ZIP entries, a leftover
            # temporary file, a failed temporary-archive check). The other comics are
            # still written; this one is offered again after the daily retry.
            not_written(path,'write_failed',str(exc)[:1000] or type(exc).__name__)
            continue
        if changed:
            not_written(path,'write_skipped',changed)
            continue
        actual,_,_=app.read_metadata(path)
        for key,change in entry['changes'].items():
            if actual.get(key)!=change['after']:
                raise ValueError('Readback verification failed for '+key)
        if digest(backup)!=entry['sha256']:
            raise ValueError('Backup verification failed.')
        removed=False
        if remove_verified_backups:
            app.remove_verified_backup(path, backup, entry['sha256'])
            removed=True
        stat=path.stat()
        results.append({'path':str(path),'backup':backup,'fields_updated':list(entry['changes']),
                        'output_signature':[stat.st_size,stat.st_mtime_ns],
                        'backup_sha256_verified':True,'metadata_readback_verified':True,
                        'backup_removed_after_verification':removed})
        storage.save(result_path,results)
        print('Updated and verified:',path.name)
        progress(updated=len(results),detail='Verified: '+path.name)
    app.JOB.update(running=True,visited=0,changed=0,errors=0)
    app.scan([plan['folder']],recursive=False)  # Subfolders are inventoried by their own passes.
    print('Repeat scan:',app.JOB)
    status=json.loads((app.BASE/'data'/'progress.json').read_text(encoding='utf-8'))
    completed=[b for b in status.get('completed',[]) if b.get('batch')!=plan_path.parent.name]
    completed.append({'batch':plan_path.parent.name,'folder':Path(plan['folder']).name,'updated':len(results),
                      'review':sum(e['action']=='review' for e in plan['entries'])})
    completed=keep_recent_batches(completed)
    progress(phase='Folder complete',completed=completed,
             detail='Metadata readback and backup checks passed. Repeat scan completed.')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    commands=parser.add_subparsers(dest='command',required=True)
    prep=commands.add_parser('prepare')
    prep.add_argument('--folder',required=True)
    prep.add_argument('--reference',required=True)
    run=commands.add_parser('apply')
    run.add_argument('plan')
    run.add_argument('--remove-verified-backups',action='store_true')
    args=parser.parse_args()
    if args.command=='prepare':
        prepare(args.folder,args.reference)
    else:
        apply(args.plan,args.remove_verified_backups)
