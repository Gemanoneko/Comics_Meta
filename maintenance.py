"""Bounded cleanup of regenerable project data; never delete recovery evidence."""
import json
import re
import shutil
import time
from pathlib import Path
import app
import library_lock
import storage

def remove_tree(path,root):
    path=Path(path);root=Path(root)
    if path.is_symlink() or getattr(path.stat(),'st_file_attributes',0)&0x400 or not path.resolve().is_relative_to(root.resolve()) or path.resolve()==root.resolve():
        raise ValueError('Cleanup target is outside its owned directory.')
    for item in path.rglob('*'):
        if item.is_symlink() or getattr(item.stat(),'st_file_attributes',0)&0x400:
            raise ValueError('Cleanup target contains a filesystem link.')
    size=sum(item.stat().st_size for item in path.rglob('*') if item.is_file())
    shutil.rmtree(path)
    return size

def browser_cache(profile):
    """Only call while this worker's browser context is closed."""
    root=Path(profile);freed=0
    for relative in ('Default/Cache','Default/Code Cache','Default/GPUCache','Default/DawnGraphiteCache','Default/DawnWebGPUCache','ShaderCache','GrShaderCache','GPUPersistentCache','BrowserMetrics'):
        target=root/relative
        if target.is_dir():
            try:freed+=remove_tree(target,root)
            except (OSError,ValueError):pass
    return freed

def run(force=False):
    report_path=app.DATA/'maintenance.json'
    old=json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
    now=time.time()
    if not force and now-old.get('timestamp',0)<3600:return old
    freed=0;expired=0
    with app.db() as con:
        expired=con.execute('DELETE FROM cache WHERE fetched<?',(now-30*86400,)).rowcount
        # Cap response payloads, without removing catalog or evidence tables.
        total=con.execute('SELECT COALESCE(SUM(length(value)),0) FROM cache').fetchone()[0]
        for row in con.execute('SELECT key,length(value) AS size FROM cache ORDER BY fetched').fetchall():
            if total<=64*1024*1024:break
            con.execute('DELETE FROM cache WHERE key=?',(row['key'],));total-=row['size'];expired+=1
    research=app.DATA/'research'
    candidates=sorted((p for p in research.glob('*.json') if re.fullmatch(r'[0-9a-f]{64}',p.stem)),key=lambda p:p.stat().st_mtime)
    total=sum(p.stat().st_size for p in candidates)
    for path in candidates:
        if now-path.stat().st_mtime>30*86400 or total>64*1024*1024:
            size=path.stat().st_size;path.unlink();total-=size;freed+=size
    for path in app.DATA.rglob('*.tmp'):
        if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(app.DATA.resolve()) and now-path.stat().st_mtime>86400:
            size=path.stat().st_size;path.unlink();freed+=size
    test_runs=app.STATE_ROOT/'work'/'test-runs'
    for path in test_runs.glob('*'):
        if path.is_dir() and re.fullmatch(r'[0-9a-f-]{36}',path.name) and now-path.stat().st_mtime>86400:
            freed+=remove_tree(path,test_runs)
    with app.db() as con:
        if con.execute("SELECT 1 FROM sqlite_master WHERE name='conversion_staging'").fetchone():
            for row in con.execute('SELECT * FROM conversion_staging WHERE created<?',(now-86400,)).fetchall():
                stage=Path(row['path']);source=Path(row['source'])
                if not stage.exists():
                    con.execute('DELETE FROM conversion_staging WHERE path=?',(row['path'],));continue
                if stage.resolve().parent!=source.resolve().parent or not stage.name.startswith('.comic-metadata-convert-'):continue
                unchanged=False
                if source.is_file():
                    stat=source.stat()
                    unchanged=[stat.st_size,stat.st_mtime_ns]==json.loads(row['signature'])
                if not unchanged:
                    # Only future conversions with an explicit verified final-byte proof qualify.
                    if 'verified_target' not in row.keys() or not row['verified_target'] or not row['verified_sha256']:continue
                    final=Path(row['verified_target'])
                    if final!=source.with_suffix('.cbz') or not final.is_file() or final.is_symlink():continue
                    import archive_conversion
                    with final.open('rb') as handle:
                        if archive_conversion.checksum(handle)!=row['verified_sha256']:continue
                try:library_lock.require(source)
                except library_lock.LibraryBusy:continue  # Another copy owns this library.
                import archive_conversion
                size=sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())
                archive_conversion.cleanup_stage(stage,source)
                freed+=size
                con.execute('DELETE FROM conversion_staging WHERE path=?',(row['path'],))
    if expired:
        try:
            with app.db() as con:
                con.execute('PRAGMA wal_checkpoint(TRUNCATE)');con.execute('VACUUM')
        except Exception:pass  # Active readers can defer compaction safely.
    report={'timestamp':now,'bytes_removed':freed,'expired_cache_entries':expired,'detail':'Catalog, evidence, active queues, browser cookies and recovery backups retained.'}
    storage.save(report_path,report)
    return report
