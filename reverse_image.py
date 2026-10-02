"""Cover-only TinEye fallback. Results are evidence, never write authorization."""
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import app


def cover(path, index=0):
    with zipfile.ZipFile(app.filesystem_path(path)) as archive:
        images=sorted((i for i in archive.infolist() if i.filename.lower().endswith(('.jpg','.jpeg','.png','.webp'))),key=lambda i:i.filename)
        if not 0 <= index < min(5,len(images)) or images[index].file_size > 20_000_000:
            raise ValueError('Choose a suitable image among the first five archive images.')
        data=archive.read(images[index])
        extension=Path(images[index].filename).suffix.lower()
        mime={'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp'}[extension]
        return data,mime,extension


def settings():
    path=app.BASE/'config.json'
    config=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    options=config.get('reverse_image',{})
    key=os.environ.get('TINEYE_API_KEY','').strip()
    paths=[app.BASE/'.env']
    if config.get('env_file'): paths.append(Path(config['env_file']))
    if not key:
        for env_path in paths:
            if not env_path.exists(): continue
            for line in env_path.read_text(encoding='utf-8-sig').splitlines():
                name,sep,value=line.partition('=')
                if sep and name.strip()=='TINEYE_API_KEY': key=value.strip().strip('\"\'')
    return options,key


def normalize(payload):
    rows=[];seen=set()
    for match in payload.get('results',{}).get('matches',[]):
        for backlink in match.get('backlinks',[]):
            url=backlink.get('backlink','')
            parsed=urllib.parse.urlparse(url)
            if parsed.scheme not in ('http','https') or not parsed.hostname or url in seen: continue
            seen.add(url)
            issue=re.search(r'/4000-(\d+)(?:/|$)',parsed.path) if parsed.hostname in ('comicvine.gamespot.com','www.comicvine.com','comicvine.com') else None
            rows.append({'url':url,'title':backlink.get('title') or parsed.hostname,
                         'score':match.get('score'),'comicvine_issue':int(issue[1]) if issue else None})
    return rows[:50]


def search(path,index=0):
    data,mime,extension=cover(path,index)
    digest=hashlib.sha256(data).hexdigest();cache_key='tineye:cover:v1:'+digest
    options,key=settings()
    with app.db() as con:
        cached=con.execute('SELECT value FROM cache WHERE key=? AND fetched>?',(cache_key,time.time()-30*86400)).fetchone()
        if cached: return dict(json.loads(cached['value']),cached=True)
    limit=int(options.get('monthly_request_limit',0))
    if not options.get('enabled') or not key or limit<=0:
        raise ValueError('Automatic image search is disabled. Configure a TinEye key and monthly request limit, or download the cover for a free browser search.')
    month=datetime.now(timezone.utc).strftime('%Y-%m')
    with app.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS reverse_requests(month TEXT, timestamp REAL, digest TEXT)')
        con.execute('BEGIN IMMEDIATE')
        used=con.execute('SELECT COUNT(*) FROM reverse_requests WHERE month=?',(month,)).fetchone()[0]
        if used>=limit: raise ValueError('Monthly reverse-image request limit reached.')
        # Failures count too; no retry loop can silently exhaust a prepaid bundle.
        con.execute('INSERT INTO reverse_requests VALUES(?,?,?)',(month,time.time(),digest))
    boundary='ComicCover'+uuid.uuid4().hex
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="image_upload"; filename="cover{extension}"\r\nContent-Type: {mime}\r\n\r\n'.encode()+data+f'\r\n--{boundary}--\r\n'.encode())
    request=urllib.request.Request('https://api.tineye.com/rest/search/?limit=20&sort=score&order=desc',data=body,headers={'X-API-Key':key,'Content-Type':'multipart/form-data; boundary='+boundary})
    try:
        with urllib.request.urlopen(request,timeout=45) as response:
            payload=json.loads(response.read(5_000_001))
    except (urllib.error.URLError,ValueError):
        raise ValueError('Image-search service could not complete the request; no automatic retry was made.') from None
    if payload.get('code')!=200: raise ValueError('Image-search service rejected the request; check account availability.')
    result={'provider':'TinEye','cover_sha256':digest,'matches':normalize(payload),'cached':False,
            'notice':'Cover matches are leads. Confirm issue, publisher, date and edition before writing.'}
    with app.db() as con:
        con.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',(cache_key,json.dumps(result),time.time()))
    return result
