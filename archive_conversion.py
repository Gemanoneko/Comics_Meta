"""Verified local archive conversion; retain originals until content checks pass."""
import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
import zipfile
from pathlib import Path,PurePosixPath
import app
import pause_control

SEVEN_ZIP=Path('C:/Program Files/7-Zip/7z.exe')

class ArchiveDamage(ValueError):
    pass


def run(arguments):
    result=subprocess.run([str(SEVEN_ZIP),*arguments],capture_output=True,timeout=600)
    if result.returncode:
        error=(result.stdout+result.stderr).decode('utf-8',errors='replace')
        if arguments[0]=='t' and any(text in error for text in ('CRC Failed','Data Error','Unexpected end of archive','Headers Error')):
            raise ArchiveDamage('Original archive integrity check failed; needs reacquiring.')
        raise ValueError('7-Zip could not verify or extract this archive. Original retained.')
    return result.stdout.decode('utf-8',errors='strict')


def members(source):
    listing=run(['l','-slt','-ba','-sccUTF-8',str(source)])
    files=[]
    for block in listing.replace('\r\n','\n').split('\n\n'):
        fields=dict(line.split(' = ',1) for line in block.splitlines() if ' = ' in line)
        if not fields.get('Path'):continue
        name=fields['Path'].replace('\\','/')
        parts=PurePosixPath(name).parts
        if name.startswith('/') or not parts or any(part in ('..','.') or ':' in part for part in parts):
            raise ValueError('Unsafe archive member path; original retained.')
        if fields.get('Symbolic Link') or fields.get('Hard Link') or 'L' in fields.get('Attributes',''):
            raise ValueError('Archive links are not convertible; original retained.')
        if fields.get('Encrypted')=='+':raise ValueError('Encrypted archive; original retained.')
        if fields.get('Folder')=='+' or fields.get('Attributes','').startswith('D'):continue
        files.append((name,int(fields['Size'])))
    if not files or len({name.casefold() for name,_ in files})!=len(files):
        raise ValueError('Empty or ambiguous archive member names; original retained.')
    return files


def signature(path):
    stat=path.stat();return [stat.st_size,stat.st_mtime_ns]


def checksum(handle):
    digest=hashlib.sha256()
    for part in iter(lambda:handle.read(1024*1024),b''):digest.update(part)
    return digest.hexdigest()


def verify(target,manifest):
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:raise ValueError('Converted archive integrity failed; original retained.')
        if set(archive.namelist())!=set(manifest):raise ValueError('Converted member list differs; original retained.')
        for name,(size,digest) in manifest.items():
            if archive.getinfo(name).file_size!=size:raise ValueError('Converted file size differs; original retained.')
            with archive.open(name) as handle:
                if checksum(handle)!=digest:raise ValueError('Converted file content differs; original retained.')
    app.read_metadata(target)  # Metadata must also be readable by this app.


def convert(path):
    source=app.filesystem_path(path)
    if source.suffix.lower()=='.cbz' and zipfile.is_zipfile(source):return None
    if not SEVEN_ZIP.is_file():raise ValueError('7-Zip is required for conversion.')
    if pause_control.requested():raise pause_control.PauseRequested()
    original_signature=signature(source)
    final=source.with_suffix('.cbz')
    same=final==source
    if not same and final.exists():raise ValueError('A CBZ with this name already exists; original retained.')
    records=members(source)
    if not any(name.lower().endswith(('.jpg','.jpeg','.png','.webp','.gif','.avif')) for name,_ in records):
        raise ValueError('No comic images found; original retained.')
    required=sum(size for _,size in records)*2+64*1024*1024
    if shutil.disk_usage(source.parent).free<required:raise ValueError('Insufficient temporary disk space; original retained.')
    stage=source.parent/('.comic-metadata-convert-'+uuid.uuid4().hex)
    temporary=stage/'converted.cbz'
    retained=source.parent/(source.name+'.'+uuid.uuid4().hex+'.conversion-original')
    stage.mkdir()
    with app.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS conversion_staging(path TEXT PRIMARY KEY,source TEXT,signature TEXT,created REAL)')
        con.execute('INSERT INTO conversion_staging VALUES(?,?,?,?)',(str(stage),str(source),json.dumps(original_signature),time.time()))
    try:
        run(['t','-sccUTF-8','-p',str(source)])
        run(['x','-y','-spd','-p','-sccUTF-8','-o'+str(stage),str(source)])
        manifest={}
        from PIL import Image
        with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
            for name,size in records:
                extracted=stage/Path(name)
                if not extracted.resolve().is_relative_to(stage.resolve()) or extracted.is_symlink() or getattr(extracted.stat(),'st_file_attributes',0)&0x400:
                    raise ValueError('Extracted path escaped staging; original retained.')
                if extracted.stat().st_size!=size:raise ValueError('Extracted file size differs; original retained.')
                if name.lower().endswith(('.jpg','.jpeg','.png','.webp','.gif')):
                    with Image.open(extracted) as image:image.load()
                with extracted.open('rb') as handle:manifest[name]=(size,checksum(handle))
                archive.write(extracted,name)
        verify(temporary,manifest)
        if signature(source)!=original_signature:raise ValueError('Original changed during conversion; original retained.')
        if same:os.replace(source,retained)
        elif final.exists():raise ValueError('CBZ appeared during conversion; original retained.')
        try:
            os.replace(temporary,final)
            verify(final,manifest)
            if not same and signature(source)!=original_signature:
                raise ValueError('Original changed before removal; both archives retained.')
        except Exception:
            if same and retained.exists():os.replace(retained,source)
            raise
        (retained if same else source).unlink()
        return {'original':str(path),'cbz':str(Path(path).with_suffix('.cbz')),'files_verified':len(manifest),'bytes_verified':sum(v[0] for v in manifest.values()),'original_removed':True}
    finally:
        temporary.unlink(missing_ok=True)
        if stage.resolve().parent!=source.parent.resolve() or not stage.name.startswith('.comic-metadata-convert-'):
            raise ValueError('Unsafe staging cleanup path.')
        shutil.rmtree(stage)
        with app.db() as con:con.execute('DELETE FROM conversion_staging WHERE path=?',(str(stage),))


def one(folder):
    """Convert at most one eligible archive per serial worker pass."""
    with app.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS conversions(path TEXT PRIMARY KEY,signature TEXT,result TEXT,retry_at REAL)')
        rows=[dict(row) for row in con.execute("SELECT * FROM comics WHERE status='unsupported'") if Path(row['path']).parent==Path(folder)]
    for row in rows:
        if Path(row['path']).suffix.lower() not in ('.cbz','.cbr','.cb7'):continue
        with app.db() as con:previous=con.execute('SELECT * FROM conversions WHERE path=?',(row['path'],)).fetchone()
        sig=json.dumps([row['size'],row['mtime']])
        if previous and previous['signature']==sig and previous['retry_at']>time.time():continue
        import batch
        batch.progress(phase='Converting and verifying archive',current_folder=str(folder),detail='Converting '+Path(row['path']).name+'; original retained until verification succeeds.')
        try:
            result=convert(row['path'])
            if result is None:continue
            retry=0
        except pause_control.PauseRequested:raise
        except Exception as exc:
            result={'error':str(exc),'original_removed':False};retry=time.time()+86400
        with app.db() as con:
            con.execute('INSERT OR REPLACE INTO conversions VALUES(?,?,?,?)',(row['path'],sig,json.dumps(result),retry))
            if retry:
                status='corrupted' if result['error']=='Original archive integrity check failed; needs reacquiring.' else 'unsupported'
                con.execute('UPDATE comics SET status=?,error=? WHERE id=?',(status,result['error'],row['id']))
            elif result['cbz']!=row['path']:con.execute('DELETE FROM comics WHERE id=?',(row['id'],))
        app.scan([str(folder)],recursive=False)
        return not retry
    return False
