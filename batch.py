"""Reviewed folder batches. Reference mode requires identical archive page content."""
import argparse
import hashlib
import json
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import app
import storage


def progress(**updates):
    target=app.BASE/'data'/'progress.json'
    current=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    current.update(updates)
    current['timestamp']=datetime.now(timezone.utc).isoformat()
    storage.save(target,current)


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


def apply(plan_path, remove_verified_backups=False):
    plan_path=Path(plan_path).resolve()
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    results=[]
    progress(phase='Writing and verifying metadata',current_folder=Path(plan['folder']).name,
             total=len(plan['entries']),checked=len(plan['entries']),updated=0,
             detail='Each comic is checked after writing; its backup is removed only after verification.')
    for entry in plan['entries']:
        if entry['action']!='write':
            continue
        path=Path(entry['path']).resolve()
        if path.parent!=Path(plan['folder']).resolve():
            raise ValueError('Target must stay in the planned folder.')
        if digest(path)!=entry['sha256']:
            raise ValueError('Source changed after planning; regenerate plan.')
        app.JOB.update(running=True,visited=0,changed=0,errors=0)
        app.scan([plan['folder']])
        with app.db() as con:
            row=con.execute('SELECT * FROM comics WHERE path=?',(str(path),)).fetchone()
            if row is None:
                raise ValueError('File was not successfully inventoried.')
            row=dict(row)
        backup=app.write_metadata(row,entry['fields'],append_notes=True,
                                  overwrite_fields=set(entry['changes']))
        actual,_,_=app.read_metadata(path)
        for key,change in entry['changes'].items():
            if actual.get(key)!=change['after']:
                raise ValueError('Readback verification failed for '+key)
        if digest(backup)!=entry['sha256']:
            raise ValueError('Backup verification failed.')
        removed=False
        if remove_verified_backups:
            backup_path=app.filesystem_path(backup)
            intended=app.filesystem_path(path.parent / '.comic-metadata-backups')
            if backup_path.parent != intended or not backup_path.name.startswith(path.name + '.') or backup_path.suffix!='.bak':
                raise ValueError('Backup cleanup target is outside the expected folder.')
            backup_path.unlink()
            removed=True
        results.append({'path':str(path),'backup':backup,'fields_updated':list(entry['changes']),
                        'backup_sha256_verified':True,'metadata_readback_verified':True,
                        'backup_removed_after_verification':removed})
        (plan_path.parent/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Updated and verified:',path.name)
        progress(updated=len(results),detail='Verified: '+path.name)
    app.JOB.update(running=True,visited=0,changed=0,errors=0)
    app.scan([plan['folder']])
    print('Repeat scan:',app.JOB)
    status=json.loads((app.BASE/'data'/'progress.json').read_text(encoding='utf-8'))
    completed=[b for b in status.get('completed',[]) if b.get('batch')!=plan_path.parent.name]
    completed.append({'batch':plan_path.parent.name,'folder':Path(plan['folder']).name,'updated':len(results),
                      'review':sum(e['action']=='review' for e in plan['entries'])})
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
