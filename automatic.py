"""Persistent discovery of delta files and verified-ID enrichment."""
import json
import re
import time
from pathlib import Path
import app
import batch
import worker
import io
import urllib.request
import urllib.parse
import reverse_image
import research

MATCHER_VERSION = 8

def normalized(value):
    return re.sub(r'[^a-z0-9]', '', str(value).lower())

def unique_volume(candidates, series, publisher):
    matches = [v for v in candidates if normalized(v.get('name')) == normalized(series)
               and publisher and normalized((v.get('publisher') or {}).get('name')) == normalized(publisher)]
    return matches[0] if len(matches) == 1 else None

def covers_agree(local, remote):
    from PIL import Image, ImageChops, ImageStat, ImageOps
    with Image.open(io.BytesIO(local)) as a, Image.open(io.BytesIO(remote)) as b:
        if abs(a.width / a.height - b.width / b.height) > .08:
            return False
        a = ImageOps.autocontrast(a.convert('RGB').resize((96, 144)))
        b = ImageOps.autocontrast(b.convert('RGB').resize((96, 144)))
        return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3 < 12

def lookup_unidentified(row, old):
    series = old.get('Series') or row['series']
    number = old.get('Number') or row['number']
    publisher = old.get('Publisher')
    year = old.get('Year') or row['year']
    if not series or not number or not publisher or not year:
        return None
    candidates = app.api('search', query=series, resources='volume', limit=20,
                         field_list='id,name,start_year,publisher,image,count_of_issues')
    volume = unique_volume(candidates, series, publisher)
    if not volume:
        return None
    issues = app.api('issues', filter=f"volume:{volume['id']},issue_number:{number}", limit=100,
                     field_list='id,name,issue_number,cover_date,image,site_detail_url')
    issues = [i for i in issues if (i.get('cover_date') or '').startswith(str(year) + '-')]
    if len(issues) != 1:
        return None
    candidate = issues[0]
    url = (candidate.get('image') or {}).get('original_url') or ''
    host = urllib.parse.urlparse(url).hostname or ''
    if not (host == 'comicvine.gamespot.com' or host.endswith('.comicvine.com') or host == 'comicvine.com' or host.endswith('.giantbomb.com')):
        return None
    with urllib.request.urlopen(url, timeout=30) as response:
        remote = response.read(20 * 1024 * 1024 + 1)
    if len(remote) > 20 * 1024 * 1024:
        return None
    local, _, _ = reverse_image.cover(row['path'], 0)
    if not covers_agree(local, remote):
        return None
    return app.api('issue/4000-' + str(candidate['id']))

STATE = app.DATA / 'automatic.json'

def identity_matches(old, issue):
    def normalized(value):
        return re.sub(r'[^a-z0-9]', '', str(value).lower())
    return (normalized(old.get('Series')) == normalized((issue.get('volume') or {}).get('name'))
            and research.issue_number(old.get('Number')) == research.issue_number(issue.get('issue_number'))
            and bool(old.get('Series')) and bool(old.get('Number')))

def load_state():
    if STATE.exists() and STATE.stat().st_size>10*1024*1024:
        raise ValueError('Research cache exceeds its size limit; repair required.')
    return json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'checked': {}}

def discover(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError('Automatic root is unavailable.')
    app.scan([str(root)],recursive=False)
    state = load_state()
    with app.db() as con:
        rows = [dict(r) for r in con.execute("SELECT * FROM comics WHERE status NOT IN ('absent','error','unsupported') ORDER BY path")]
    checked = 0
    for row in rows:
        path = Path(row['path']).resolve()
        if path.parent != root or path.suffix.lower() != '.cbz':
            continue
        signature = [row['size'], row['mtime']]
        previous = state['checked'].get(str(path), {})
        if previous.get('version') == MATCHER_VERSION and previous.get('signature') == signature and previous.get('retry_at', 0) > time.time():
            continue
        checked += 1
        if checked > 20:
            return True  # Continue this folder in the next bounded pass.
        batch.progress(phase='Automatic metadata lookup', current_folder=path.parent.name,
                       checked=checked, total=0, updated=0, review=0,
                       detail='Checking ' + path.name)
        old = json.loads(row['metadata'])
        match = re.search(r'https?://(?:www\.)?comicvine\.gamespot\.com/[^\s]*4000-(\d+)', old.get('Web', ''))
        outcome = 'needs_identity_lookup'
        retry = time.time() + 86400
        lookup_error = None
        try:
            issue = app.api('issue/4000-' + match.group(1)) if match else lookup_unidentified(row, old)
        except Exception as exc:
            lookup_error = str(exc)
            issue = None
            batch.progress(phase='Automatic metadata lookup', detail='ComicVine lookup failed; trying publisher catalog for '+path.name)
        external = None
        if not issue or not old.get('Summary'):
            try:
                import metron
                if metron.token():
                    batch.progress(phase='Automatic metadata lookup', detail='Checking Metron for '+path.name)
                    external = metron.lookup(row, old)
                    if external:
                        research.save_evidence(path, external)
                        outcome = 'web_issue_found'
            except Exception as exc:
                lookup_error = (lookup_error or '') + '; Metron: ' + str(exc)
        if (not issue or not old.get('Summary')) and not external:
            import providers, open_library
            attempts=[]
            for name,lookup in [('GCD',providers.gcd_lookup),('Google Books',providers.google_lookup),('Open Library local index',open_library.lookup)]:
                try:
                    batch.progress(phase='Automatic metadata lookup',detail='Checking '+name+' for '+path.name)
                    external=lookup(row,old)
                    attempts.append({'provider':name,'result':'verified' if external else 'no_verified_match'})
                    if external:
                        research.save_evidence(path,external)
                        outcome='web_issue_found'
                        break
                except Exception as exc:
                    attempts.append({'provider':name,'result':'unavailable','error':str(exc)})
                    lookup_error=(lookup_error or '')+'; '+str(exc)
            research.save_evidence(path,{'provider_attempts':attempts})
        if not issue:
            try:
                publisher = research.publisher_lookup(row, old) if not external else None
                if publisher:
                    external = publisher
                    research.save_evidence(path,external)
                    outcome = 'publisher_issue_found'
                    fields = {k:v for k,v in external['fields'].items() if not old.get(k)}
                    if fields:
                        changes = {k:{'before':'','after':v} for k,v in fields.items()}
                        fields['Notes'] = 'Automatic publisher catalog lookup: '+external['sources'][0]['url']+'. Exact issue title; issue-wide missing fields only. Cover edition not verified; variant-specific facts excluded.'
                        target = app.BASE/'batches'/str(time.time_ns())/'plan.json'
                        target.parent.mkdir(parents=True)
                        target.write_text(json.dumps({'folder':str(path.parent),'method':'Publisher exact title; issue-wide fields only.','entries':[{'path':str(path),'action':'write','sha256':batch.digest(path),'changes':changes,'fields':fields}]}),encoding='utf-8')
                        worker.enqueue(target)
                        outcome = 'queued'
            except Exception as exc:
                lookup_error = (lookup_error or '') + '; publisher: ' + str(exc)
            if not external:
                try:
                    import local_model
                    hint=None
                    if local_model.available():
                        try:hint=local_model.identify_cover(path)
                        except Exception:pass  # A cover-reading failure must not block filename search.
                    if hint:research.save_evidence(path,{'cover_identification':hint,'status':'search_hint_only'})
                    batch.progress(phase='Automatic metadata lookup',detail='Searching the web for '+path.name)
                    external=research.general_lookup(row,old,hint)
                    if external:
                        research.save_evidence(path,external)
                        outcome='web_issue_found'
                except Exception as exc:
                    lookup_error=(lookup_error or '')+'; web: '+str(exc)
            if not external:
                try:
                    candidates = research.wiki_candidates(row,old)
                    research.save_evidence(path,{'wiki_candidates':candidates,'status':'needs_issue_verification'})
                    if candidates:
                        outcome = 'wiki_candidates_found'
                except Exception as exc:
                    lookup_error = (lookup_error or '') + '; wiki: ' + str(exc)
        if issue:
            identity = old if match else dict(Series=old.get('Series') or row['series'], Number=old.get('Number') or row['number'])
            if identity_matches(identity, issue):
                if not external and issue.get('description'):
                    from html import unescape
                    external={'provider':'ComicVine','fields':{},'sources':[{'url':issue.get('site_detail_url') or old.get('Web',''),'title':issue.get('name') or identity['Series'],'text':unescape(re.sub('<[^>]+>',' ',issue['description'])),'scope':'Verified issue identity'}]}
                fields = app.metadata_from_issue(issue)
                # Descriptions may contain plot outcomes. Synopsis review remains separate.
                fields.pop('Summary', None)
                try:
                    volume = app.api('volume/4050-' + str(issue['volume']['id']))
                except Exception as exc:
                    lookup_error = (lookup_error or '') + '; ComicVine publisher: ' + str(exc)
                    volume = {}  # Keep verified issue fields and synopsis evidence usable.
                if (volume.get('publisher') or {}).get('name'):
                    fields['Publisher'] = volume['publisher']['name']
                fields = {k: v for k, v in fields.items() if not old.get(k)}
                if fields:
                    changes = {k: {'before': '', 'after': v} for k, v in fields.items()}
                    fields['Notes'] = ('Automatic enrichment: existing ComicVine issue ID verified against embedded series and issue number.' if match else 'Automatic match: unique exact series and publisher, issue number, publication year and cover similarity agree.') + ' Existing populated values and synopsis retained.'
                    target = app.BASE / 'batches' / str(time.time_ns()) / 'plan.json'
                    target.parent.mkdir(parents=True)
                    target.write_text(json.dumps({'folder':str(path.parent),'method':'Verified existing issue ID; fill missing fields only.', 'entries':[{'path':str(path),'action':'write','sha256':batch.digest(path),'changes':changes,'fields':fields}]}),encoding='utf-8')
                    worker.enqueue(target)
                    outcome = 'queued'
                else:
                    outcome = 'current'
                retry = time.time() + 30 * 86400
            else:
                outcome = 'identity_conflict'
        if external and outcome == 'web_issue_found':
            fields={k:v for k,v in external['fields'].items() if not old.get(k)}
            if fields:
                changes={k:{'before':'','after':v} for k,v in fields.items()}
                fields['Notes']='Automatic verified lookup: '+external.get('provider','web research')+'. Issue or edition identity checked against the source. Sources: '+', '.join(s['url'] for s in external['sources'])
                target=app.BASE/'batches'/str(time.time_ns())/'plan.json';target.parent.mkdir(parents=True)
                target.write_text(json.dumps({'folder':str(path.parent),'method':'Verified issue-wide web fields.','entries':[{'path':str(path),'action':'write','sha256':batch.digest(path),'changes':changes,'fields':fields}]}),encoding='utf-8')
                worker.enqueue(target);outcome='queued'
        if not old.get('Summary') and outcome != 'queued':
            import local_model
            if local_model.available():
                batch.progress(phase='Automatic metadata lookup', detail='Reviewing internet-sourced synopsis: '+path.name)
                try:
                    sources = (external or {}).get('sources',[])
                    proposal = local_model.sourced_synopsis(sources) if sources else None
                    if proposal:
                        research.save_evidence(path,dict(external or {}, synopsis=proposal))
                        fields = {'Summary':proposal['summary'],'Notes':'Synopsis composed from verified internet source text; generated by '+proposal['model']+'. Supporting quotations and claim/spoiler review stored in research evidence. Sources: '+', '.join(proposal['sources'])}
                        target = app.BASE/'batches'/str(time.time_ns())/'plan.json'
                        target.parent.mkdir(parents=True)
                        target.write_text(json.dumps({'folder':str(path.parent),'method':'Exact publisher issue identity; internet-only synopsis with quote and spoiler checks.','entries':[{'path':str(path),'action':'write','sha256':batch.digest(path),'changes':{'Summary':{'before':'','after':proposal['summary']}},'fields':fields}]}),encoding='utf-8')
                        worker.enqueue(target)
                        outcome = 'queued'
                except Exception as exc:
                    lookup_error = (lookup_error or '') + '; local model: ' + str(exc)
            else:
                # Notice installation promptly instead of caching the unavailable model for a day.
                retry = min(retry,time.time()+600)
        if lookup_error:
            retry = min(retry,time.time()+3600)
        state['checked'][str(path)] = {'version':MATCHER_VERSION,'signature':signature,'outcome':outcome,'retry_at':retry,'error':lookup_error[:2000] if lookup_error else None}
        worker.save(STATE, state)
        if outcome == 'queued':
            return True
    batch.progress(phase='Automatic discovery complete', detail='Discovery checked this root. Unidentified comics remain pending further identity lookup; next delta scan in 10 minutes.')
    return False
