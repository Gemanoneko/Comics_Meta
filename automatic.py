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
import discovery_state
from provider_wait import record_failure, retry_time
import research_runtime
import storage

MATCHER_VERSION = 9

def normalized(value):
    return re.sub(r'[^a-z0-9]', '', str(value).lower())


def verified_issue_fields(issue):
    fields=app.metadata_from_issue(issue)
    fields.pop('Summary',None)  # Separate narrative and spoiler review.
    fields.pop('CoverArtist',None)  # A primary issue ID does not identify every variant cover.
    return fields


def language_eligible(row,old):
    language=str(old.get('LanguageISO') or '').strip().lower().replace('_','-').split('-')[0]
    if language and language not in ('en','eng','english'):return False
    return not re.search(r'\((?:fr|french|de|german|es|spanish|it|italian|ru|russian|jp|japanese)\)',Path(row['path']).name,re.I)

def unique_volume(candidates, series, publisher):
    matches = [v for v in candidates if research.series_key(v.get('name')) == research.series_key(series)
               and publisher and normalized((v.get('publisher') or {}).get('name')) == normalized(publisher)]
    return matches[0] if len(matches) == 1 else None

def covers_agree(local, remote):
    from PIL import Image, ImageChops, ImageStat, ImageOps
    with Image.open(io.BytesIO(local)) as a, Image.open(io.BytesIO(remote)) as b:
        if abs(a.width / a.height - b.width / b.height) > .08:
            return False
        grey_a=list(a.convert('L').resize((32,48)).tobytes())
        grey_b=list(b.convert('L').resize((32,48)).tobytes())
        a = ImageOps.autocontrast(a.convert('RGB').resize((96, 144)))
        b = ImageOps.autocontrast(b.convert('RGB').resize((96, 144)))
        if sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3 < 12:return True
        # Scanned covers can have very different printing/brightness from catalog images.
        # Require agreement in both overall layout and fine structure; flat images fail.
        from math import sqrt
        def correlation(x,y):
            mx=sum(x)/len(x);my=sum(y)/len(y)
            vx=sum((v-mx)**2 for v in x);vy=sum((v-my)**2 for v in y)
            if min(vx,vy)/len(x)<25:return 0
            return sum((u-mx)*(v-my) for u,v in zip(x,y))/sqrt(vx*vy)
        edges=lambda values:[values[i+1]-values[i] for i in range(len(values)-1) if i%32!=31]
        return correlation(grey_a,grey_b)>.94 and correlation(edges(grey_a),edges(grey_b))>.80

def lookup_unidentified(row, old):
    series = old.get('Series') or row['series']
    number = old.get('Number') or row['number']
    publisher = research.publisher_hint(row,old)
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
    return (research.series_key(old.get('Series')) == research.series_key((issue.get('volume') or {}).get('name'))
            and research.issue_number(old.get('Number')) == research.issue_number(issue.get('issue_number'))
            and bool(old.get('Series')) and bool(old.get('Number')))

def load_state():
    if STATE.exists() and STATE.stat().st_size>10*1024*1024:
        raise ValueError('Research cache exceeds its size limit; repair required.')
    return json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'checked': {}}

@research_runtime.timed("Research pass")
def discover(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError('Automatic root is unavailable.')
    with research_runtime.stage('Folder inventory'):
        app.scan([str(root)],recursive=False)
    import archive_conversion
    if archive_conversion.one(root):return True  # Verify one conversion, then continue this folder.
    state = discovery_state.load(root)
    import providers,source_scheduling
    source_statuses=providers.statuses()
    with app.db() as con:
        scope,args=app.scope_filter(root)
        rows = [dict(r) for r in con.execute("SELECT * FROM comics WHERE status NOT IN ('absent','error','corrupted','unsupported') AND "+scope+' ORDER BY path',args)]
    rows.sort(key=lambda row: (bool(state['checked'].get(row['path'])) and state['checked'][row['path']].get('signature')==[row['size'],row['mtime']], state['checked'].get(row['path'],{}).get('outcome') not in ('web_issue_found','publisher_issue_found','current'), row['path']))
    checked = 0
    for row in rows:
        import pause_control
        if pause_control.requested():return True  # Retain a due folder; resume from persisted per-file state.
        path = Path(row['path']).resolve()
        if path.parent != root or path.suffix.lower() != '.cbz':
            continue
        signature = [row['size'], row['mtime']]
        previous = state['checked'].get(str(path), {})
        evidence_path=research.CACHE/('evidence-'+__import__('hashlib').sha256(str(path).encode()).hexdigest()+'.json')
        saved=json.loads(evidence_path.read_text(encoding='utf-8')) if evidence_path.exists() else {}
        new_cover_leads=saved.get('reverse_image_signature')==signature and previous.get('cover_leads')!=saved.get('reverse_image_matches')
        old_metron=(saved.get('verified_evidence') or {}).get('result',{})
        metron_upgrade=old_metron.get('provider')=='Metron' and old_metron.get('metadata_version',0)<2 and previous.get('metron_metadata_version',0)<2
        if not metron_upgrade and not source_scheduling.due(previous,signature,MATCHER_VERSION,source_statuses,new_cover_leads):
            continue
        checked += 1
        if checked > 20:
            return True  # Continue this folder in the next bounded pass.
        batch.progress(phase='Automatic metadata lookup', current_folder=path.parent.name,
                       checked=checked, total=0, updated=0, review=0,
                       detail='Checking ' + path.name)
        old = json.loads(row['metadata'])
        if not language_eligible(row,old):
            discovery_state.save_one(path,{'version':MATCHER_VERSION,'signature':signature,'outcome':'excluded_language','retry_at':time.time()+30*86400})
            continue
        match = re.search(r'https?://(?:www\.)?comicvine\.gamespot\.com/[^\s]*4000-(\d+)', old.get('Web', ''))
        outcome = 'needs_identity_lookup'
        target = None
        retry = time.time() + 86400
        lookup_error = None
        provider_waits = {}
        source_schedule=dict(previous.get('source_schedule',{})) if previous.get('signature')==signature and previous.get('version')==MATCHER_VERSION and not new_cover_leads else {}
        if metron_upgrade:source_schedule.pop('Metron',None)
        external=research_runtime.reuse(path,row,old,saved,MATCHER_VERSION)
        if external and external.get('provider')=='Metron' and external.get('metadata_version',0)<2:external=None
        reused_evidence=bool(external)
        issue=saved.get('verified_evidence',{}).get('issue') if external else None
        issue_reused=bool(issue)
        if external and not source_scheduling.useful(external,old):
            external=None
            reused_evidence=False  # A thin cached match must not block richer sources.
        try:
            if not external and not issue_reused:
                with research_runtime.stage('ComicVine'):
                    issue = app.api('issue/4000-' + match.group(1)) if match else lookup_unidentified(row, old)
        except Exception as exc:
            lookup_error = record_failure(lookup_error,provider_waits,'ComicVine',exc)
            issue = None
            batch.progress(phase='Automatic metadata lookup', detail='ComicVine lookup failed; trying publisher catalog for '+path.name)
        hint = None
        if external:outcome='web_issue_found'
        if (not issue or not old.get('Summary')) and not external:
            import providers, open_library, getcomics, publisher_catalogs, metron
            attempts=[]
            def completed(name,result,exc):
                nonlocal lookup_error
                source_schedule[name]=source_scheduling.record(source_schedule.get(name,{}),result,exc,old,time.time())
                attempts.append({'provider':name,'result':source_schedule[name]['result']})
                if exc:lookup_error=record_failure(lookup_error,provider_waits,name,exc)
            sources=[('Metron',lambda row,old:metron.lookup(row,old) if metron.token() else None),
                     ('GCD',providers.gcd_lookup),('Google Books',providers.google_lookup),('Open Library local index',open_library.lookup),
                     ('Dark Horse',lambda row,old:publisher_catalogs.lookup(row,old,'darkhorse_catalog')),
                     ('Image Comics',lambda row,old:publisher_catalogs.lookup(row,old,'image_catalog')),
                     ('PREVIEWSworld',lambda row,old:publisher_catalogs.lookup(row,old,'previews_catalog')),
                     ('GetComics',getcomics.lookup)]
            sources=source_scheduling.order(sources,row,old)
            ready=[]
            for name,lookup in sources:
                if source_scheduling.ready(name,source_schedule.get(name,{}),source_statuses,time.time()):ready.append((name,lookup))
                else:attempts.append({'provider':name,'result':'scheduled_wait','next_at':source_schedule[name]['next_at']})
            batch.progress(phase='Automatic metadata lookup',detail='Researching up to two sources for '+path.name)
            try:external=research_runtime.first_verified(ready,row,old,completed,accept=lambda result:source_scheduling.useful(result,old))
            except pause_control.PauseRequested:return True
            if external:
                research.save_evidence(path,external)
                outcome='web_issue_found'
            research.save_evidence(path,{'provider_attempts':attempts})
        if not issue:
            try:
                with research_runtime.stage('Publisher research'):
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
                        outcome = 'queued'
            except Exception as exc:
                lookup_error = record_failure(lookup_error,provider_waits,'Publisher',exc)
            if not external:
                try:
                    import local_model
                    hint=None
                    if saved.get('cover_signature')==signature:hint=saved.get('cover_identification')
                    if not hint and local_model.available():
                        try:hint=local_model.identify_cover(path)
                        except Exception:pass  # A cover-reading failure must not block filename search.
                    if hint:research.save_evidence(path,{'cover_identification':hint,'cover_signature':signature,'status':'search_hint_only'})
                    batch.progress(phase='Automatic metadata lookup',detail='Verifying saved web and wiki references for '+path.name)
                    with research_runtime.stage('Saved lead verification'):
                        external=research.resolve_leads(row,old,hint)
                    batch.progress(phase='Automatic metadata lookup',detail='Searching the web for '+path.name)
                    if not external:
                        with research_runtime.stage('General web research'):
                            external=research.general_lookup(row,old,hint)
                    if external:
                        research.save_evidence(path,external)
                        outcome='web_issue_found'
                except Exception as exc:
                    lookup_error=record_failure(lookup_error,provider_waits,'Web',exc)
            if not external:
                try:
                    with research_runtime.stage('Wiki research'):
                        candidates = research.wiki_candidates(row,old)
                    research.save_evidence(path,{'wiki_candidates':candidates,'status':'needs_issue_verification'})
                    if candidates:
                        with research_runtime.stage('Saved lead verification'):
                            external=research.resolve_leads(row,old,hint)
                        outcome = 'web_issue_found' if external else 'wiki_candidates_found'
                        if external:research.save_evidence(path,external)
                except Exception as exc:
                    lookup_error = record_failure(lookup_error,provider_waits,'Wiki',exc)
            if not external:
                import cover_tasks
                cover_tasks.enqueue(row)
        if external:
            import cover_tasks
            cover_tasks.identified(row)
        if issue:
            identity = old if match else dict(Series=old.get('Series') or row['series'], Number=old.get('Number') or row['number'])
            if identity_matches(identity, issue):
                import cover_tasks
                cover_tasks.identified(row)
                if not external and issue.get('description'):
                    from html import unescape
                    external={'provider':'ComicVine','fields':{},'sources':[{'url':issue.get('site_detail_url') or old.get('Web',''),'title':issue.get('name') or identity['Series'],'text':unescape(re.sub('<[^>]+>',' ',issue['description'])),'scope':'Verified issue identity'}]}
                fields = verified_issue_fields(issue)
                # Descriptions may contain plot outcomes. Synopsis review remains separate.
                fields.pop('Summary', None)
                try:
                    with research_runtime.stage('ComicVine publisher'):
                        volume = app.api('volume/4050-' + str(issue['volume']['id'])) if not old.get('Publisher') else {}
                except Exception as exc:
                    lookup_error = record_failure(lookup_error,provider_waits,'ComicVine publisher',exc)
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
                    outcome = 'queued'
                else:
                    outcome = 'current'
                retry = time.time() + 30 * 86400
            else:
                outcome = 'identity_conflict'
        if external and not reused_evidence:
            research_runtime.remember(path,row,old,external,MATCHER_VERSION,issue=issue if not issue_reused and issue and identity_matches(old if match else dict(Series=old.get('Series') or row['series'],Number=old.get('Number') or row['number']),issue) else None)
        if external and outcome == 'web_issue_found':
            fields={k:v for k,v in external['fields'].items() if not old.get(k)}
            if fields:
                changes={k:{'before':'','after':v} for k,v in fields.items()}
                fields['Notes']='Automatic verified lookup: '+external.get('provider','web research')+'. Issue or edition identity checked against the source. Sources: '+', '.join(s['url'] for s in external['sources'])
                target=app.BASE/'batches'/str(time.time_ns())/'plan.json';target.parent.mkdir(parents=True)
                target.write_text(json.dumps({'folder':str(path.parent),'method':'Verified issue-wide web fields.','entries':[{'path':str(path),'action':'write','sha256':batch.digest(path),'changes':changes,'fields':fields}]}),encoding='utf-8')
                outcome='queued'
        if not old.get('Summary'):
            import local_model
            if local_model.available():
                batch.progress(phase='Automatic metadata lookup', detail='Reviewing internet-sourced synopsis: '+path.name)
                diagnostics={}
                try:
                    sources = (external or {}).get('sources',[])
                    proposal=None
                    if sources:
                        with research_runtime.stage('Synopsis review'):
                            proposal = local_model.sourced_synopsis(sources,diagnostics)
                        research.save_evidence(path,{'synopsis_diagnostics':diagnostics})
                        if not proposal:
                            with research_runtime.stage('Synopsis rejection: '+diagnostics.get('reason','unknown')):pass
                        with research_runtime.stage('Synopsis accepted' if proposal else 'Synopsis rejected'):pass
                    if proposal:
                        research.save_evidence(path,dict(external or {}, synopsis=proposal))
                        fields = {'Summary':proposal['summary'],'Notes':'Synopsis composed from verified internet source text; generated by '+proposal['model']+'. Supporting quotations and claim/spoiler review stored in research evidence. Sources: '+', '.join(proposal['sources'])}
                        if outcome == 'queued':
                            # One digest, one archive rewrite, one verification for
                            # metadata and the separately reviewed synopsis.
                            plan=json.loads(target.read_text(encoding='utf-8'))
                            entry=plan['entries'][0]
                            entry['fields']['Summary']=proposal['summary']
                            entry['fields']['Notes']+='\n\n'+fields['Notes']
                            entry['changes']['Summary']={'before':'','after':proposal['summary']}
                            storage.save(target,plan)
                        else:
                            target = app.BASE/'batches'/str(time.time_ns())/'plan.json'
                            target.parent.mkdir(parents=True)
                            target.write_text(json.dumps({'folder':str(path.parent),'method':'Exact publisher issue identity; internet-only synopsis with quote and spoiler checks.','entries':[{'path':str(path),'action':'write','sha256':batch.digest(path),'changes':{'Summary':{'before':'','after':proposal['summary']}},'fields':fields}]}),encoding='utf-8')
                        outcome = 'queued'
                except Exception as exc:
                    if pause_control.requested():
                        if outcome == 'queued':worker.enqueue(target)
                        return True
                    research.save_evidence(path,{'synopsis_diagnostics':dict(diagnostics,status='error',error=str(exc)[:500])})
                    lookup_error = (lookup_error or '') + '; local model: ' + str(exc)
            else:
                # Notice installation promptly instead of caching the unavailable model for a day.
                retry = min(retry,time.time()+600)
        retry = retry_time(retry,lookup_error,time.time())
        state['checked'][str(path)] = {'version':MATCHER_VERSION,'metron_metadata_version':2,'signature':signature,'outcome':outcome,'retry_at':retry,'cover_leads':saved.get('reverse_image_matches'),'provider_waits':provider_waits,'source_schedule':source_schedule,'error':lookup_error[:2000] if lookup_error else None}
        discovery_state.save_one(path,state['checked'][str(path)])
        if outcome == 'queued':worker.enqueue(target)
        research_runtime.record_check(outcome)
        if outcome == 'queued':
            return True
    batch.progress(phase='Automatic discovery complete', detail='Discovery checked this root. Unidentified comics remain pending further identity lookup; next delta scan in 10 minutes.')
    return False
