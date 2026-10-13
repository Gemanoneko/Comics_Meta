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
import coverage_priority

MATCHER_VERSION = 9
HOLD_RETRY_SECONDS = 300  # First retry of a comic held for its ComicVine check; doubles per held pass in a row (F18)
HOLD_RETRY_MAX_SECONDS = 3600  # up to hourly.

def normalized(value):
    return re.sub(r'[^a-z0-9]', '', str(value).lower())


def verified_issue_fields(issue):
    fields=app.metadata_from_issue(issue)
    fields.pop('Summary',None)  # Separate narrative and spoiler review.
    fields.pop('CoverArtist',None)  # A primary issue ID does not identify every variant cover.
    return fields


def language_eligible(row,old):
    return coverage_priority.language_eligible(row,old)

def unique_volume(candidates, series, publisher):
    matches = [v for v in candidates if research.series_key(v.get('name')) == research.series_key(series)
               and publisher and normalized((v.get('publisher') or {}).get('name')) == normalized(publisher)]
    return matches[0] if len(matches) == 1 else None

def detailed(grey):
    """At least 5% of a 32x48 thumbnail differs clearly from its dominant tone.

    Near-blank covers (a flat field with a small mark) agree with any other
    near-blank cover, so they can never verify a match.
    """
    middle=sorted(grey)[len(grey)//2]
    return sum(abs(v-middle)>32 for v in grey)>=.05*len(grey)


def covers_agree(local, remote):
    from PIL import Image, ImageChops, ImageStat, ImageOps
    with Image.open(io.BytesIO(local)) as a, Image.open(io.BytesIO(remote)) as b:
        if abs(a.width / a.height - b.width / b.height) > .08:
            return False
        grey_a=list(a.convert('L').resize((32,48)).tobytes())
        grey_b=list(b.convert('L').resize((32,48)).tobytes())
        if not detailed(grey_a) or not detailed(grey_b):return False
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



def held_before(previous,signature):
    """The comic's previous pass, on this archive and matcher, was held for its ComicVine check."""
    return (isinstance(previous.get('hold'),dict) and previous.get('signature')==signature
            and previous.get('version')==MATCHER_VERSION)


def hold_retry(retry,wait_end,count,now):
    """F18: retry time after the count-th held pass in a row.

    Never before the comic's own ComicVine wait ends; otherwise 5, 10, 20 and 40
    minutes, then hourly; never later than the ordinary retry. A hold with no
    known end (missing key) keeps the ordinary daily retry. ComicVine answering
    any request wakes held comics sooner (coverage_priority.lookup_flags)."""
    if wait_end<=0:return retry
    interval=min(HOLD_RETRY_SECONDS*2**min(count-1,16),HOLD_RETRY_MAX_SECONDS)
    return min(retry,max(wait_end,now+interval))


MAX_PLAN_ENTRIES = 50


class PassPlan:
    """One reviewed plan and one queue ticket for a folder pass, holding several comics.

    The ticket is queued with the first entry. Later entries join before the
    worker can start it: discovery and writing take turns in one serial process.
    Each entry keeps its own digest, changes, fields and verification."""

    def __init__(self,folder):
        self.folder=str(folder);self.target=None;self.plan=None

    def __len__(self):
        return len(self.plan['entries']) if self.plan else 0

    def full(self):
        return len(self)>=MAX_PLAN_ENTRIES

    def add(self,path,changes,fields,method,signature=None,**extra):
        """signature: the archive's [size, mtime] at the folder scan whose metadata decided
        `changes`. batch.apply skips the comic when the archive no longer matches it (F22)."""
        if self.plan is None:
            # Plans live with the state (the state root once M1's code/state split lands).
            self.target=getattr(app,'STATE_ROOT',app.BASE)/'batches'/str(time.time_ns())/'plan.json'
            self.target.parent.mkdir(parents=True)
            self.plan={'folder':self.folder,'method':method,'entries':[]}
        entry=dict({'path':str(path),'action':'write','sha256':batch.digest(path),'changes':changes,'fields':fields,'method':method},**extra)
        if signature is not None:entry['signature']=list(signature)
        self.plan['entries'].append(entry)
        if len({e.get('method') for e in self.plan['entries']})>1:self.plan['method']='Several methods; see each entry.'
        self.save()
        if len(self.plan['entries'])==1:worker.enqueue(self.target)
        return entry

    def save(self):
        storage.save(self.target,self.plan)


def queue_in_book(plan,path,row,saved,signature,previous,book,record=True):
    """Plan the fields the comic itself supports, keep per-field evidence, end identity search."""
    import in_book,cover_tasks
    entry=in_book.entry(path,book,'')
    entry=plan.add(path,entry['changes'],entry['fields'],entry['method'],signature=signature,source=entry['source'],evidence=entry['evidence'])
    research.save_evidence(path,{'in_book':book['evidence']})
    cover_tasks.identified(row)  # The comic identified itself; a cover search is unnecessary.
    if not record:return entry  # The caller saves this comic's discovery record.
    same=previous.get('signature')==signature and previous.get('version')==MATCHER_VERSION
    record={'version':MATCHER_VERSION,'metron_metadata_version':2,'signature':signature,'outcome':'queued','tier':'in_book',
            'retry_at':time.time()+30*86400,'cover_leads':saved.get('reverse_image_matches'),'provider_waits':{},
            'source_schedule':dict(previous.get('source_schedule',{})) if same else {},'error':None}
    discovery_state.save_one(path,record)
    return entry


def credits_reading(path,saved,signature):
    """The saved indicia/credits reading for this archive, or a new one from the local model."""
    if saved.get('credits_signature')==signature and isinstance(saved.get('credits_reading'),dict):
        return saved['credits_reading']
    import local_model
    if not local_model.available():return None
    with research_runtime.stage('In-book credits reading'):
        reading=local_model.read_credits(path)
    if reading:research.save_evidence(path,{'credits_reading':reading,'credits_signature':signature})
    return reading


def external_plan(old,source_fields,replaceable,allow_replace):
    """(fields, changes, replaced) for a verified external result.

    Empty fields are filled as before. Sergei 2026-10-13: a value the in-book tiers wrote,
    untouched since (provenance.in_book_values), is replaced when the verified source
    disagrees with it, unless an identity conflict or a ComicVine hold blocks field writes.
    Its "before" is the in-book value, so batch.apply's F22 guard skips the comic if the
    value changed after the folder scan. Values Sergei or another program wrote are never
    in `replaceable`."""
    import provenance,imprints
    source_fields=imprints.split(source_fields)  # Sergei 2026-10-13: an imprint goes in Imprint, its parent in Publisher.
    fields={k:v for k,v in source_fields.items() if not old.get(k)}
    replaced={}
    if allow_replace:
        for k,v in source_fields.items():
            if k in replaceable and provenance.disagrees(k,replaceable[k],v):
                fields[k]=v
                replaced[k]={'in_book':old.get(k),'external':v}
    changes={k:{'before':old.get(k) if k in replaced else '','after':v} for k,v in fields.items()}
    return fields,changes,replaced


def replacement_record(provider,replaced):
    """(plan-entry provenance, Notes sentence) for in-book values a verified source replaces.

    The entry's source goes into the write history and ledger ('replaced-in-book:<provider>'),
    so a replaced value is never treated as in-book again."""
    if not replaced:return {},''
    import provenance
    note=('Replaced in-book values with '+provider+', a verified external source: '
          +'; '.join(k+' "'+str(v['in_book'])+'" with "'+str(v['external'])+'"' for k,v in sorted(replaced.items()))+'.')
    return {'source':(provenance.REPLACED_PREFIX+provider)[:200],'replaced':replaced},note


def read_credits_for_publisher(path,row,old,saved,signature,previous):
    """Publisher agreement (Sergei 2026-10-13, off by default): read the credits and indicia
    pages once for a comic the cover tier can write, so both readings can be compared.
    Returns the evidence to judge with. A failed reading only means no publisher this time."""
    import in_book,pause_control
    if not in_book.needs_credits_for_publisher(row,old,saved,signature,previous):return saved
    try:
        reading=credits_reading(path,saved,signature)
    except pause_control.PauseRequested:
        raise
    except Exception as exc:
        research.save_evidence(path,{'credits_reading_error':{'signature':signature,'error':type(exc).__name__,'at':time.time()}})
        return saved
    return dict(saved,credits_reading=reading,credits_signature=signature) if reading else saved


def free_fallback(row,old,hint,source_schedule,statuses,completed,strict=False,replaceable=None):
    """Independent free attempts; a wiki series hit is still only a lead."""
    import source_scheduling,pipeline_config
    wiki_found=False
    for name in ('General free web','Wikipedia/wiki'):
        if not pipeline_config.source_enabled(name):continue  # Switched off in config.json; code kept.
        if not source_scheduling.ready(name,source_schedule.get(name,{}),statuses,time.time()):continue
        try:
            if name=='General free web':
                with research_runtime.stage('General web research'):result=research.general_lookup(row,old,hint,strict=strict)
            else:
                with research_runtime.stage('Wiki research'):candidates=research.wiki_candidates(row,old)
                wiki_found=bool(candidates)
                research.save_evidence(row['path'],{'wiki_candidates':candidates,'status':'needs_issue_verification'})
                with research_runtime.stage('Saved lead verification'):
                    result=research.resolve_leads(row,old,hint,strict=strict) if candidates else None
            completed(name,result,None)
            if source_scheduling.useful(result,old,replaceable):return result,wiki_found
        except Exception as exc:
            import pause_control
            if isinstance(exc,pause_control.PauseRequested):raise
            completed(name,None,exc)
    return None,wiki_found

@research_runtime.timed("Research pass")
def discover(root,coverage_only=False):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError('Automatic root is unavailable.')
    with research_runtime.stage('Folder inventory'):
        app.scan([str(root)],recursive=False)
    import archive_conversion
    if archive_conversion.one(root):return True  # Verify one conversion, then continue this folder.
    state = discovery_state.load(root)
    import provenance
    provenance.ensure_backfilled()  # Once per catalog: v0.1.3's writes enter the write ledger.
    import providers,source_scheduling
    source_statuses=providers.statuses()
    with app.db() as con:
        scope,args=app.scope_filter(root)
        rows = [dict(r) for r in con.execute("SELECT * FROM comics WHERE status NOT IN ('absent','error','corrupted','unsupported') AND "+scope+' ORDER BY path',args)]
        written=coverage_priority.written_paths(con)
    evidence={}
    def saved_for(path):
        key=str(Path(path).resolve())
        if key not in evidence:evidence[key]=coverage_priority.saved_evidence(Path(key))
        return evidence[key]
    rows=coverage_priority.order_rows(rows,state['checked'],written,coverage_priority.pending_paths(),coverage_only,evidence=saved_for)
    checked = 0
    plan = PassPlan(root)  # Every comic queued in this pass shares one plan and one write cycle.
    import in_book
    for row in rows:
        import pause_control
        if pause_control.requested():return True  # Retain a due folder; resume from persisted per-file state.
        path = Path(row['path']).resolve()
        if path.parent != root or path.suffix.lower() != '.cbz':
            continue
        signature = [row['size'], row['mtime']]
        previous = state['checked'].get(str(path), {})
        saved=saved_for(path)
        due,new_cover_leads,metron_upgrade=coverage_priority.lookup_flags(row,previous,source_statuses,MATCHER_VERSION,saved,time.time())
        if not due:
            continue
        if plan.full():
            return True  # Write this pass's plan; the folder continues in the next pass.
        old = json.loads(row['metadata'])
        eligible=language_eligible(row,old)
        if eligible:
            try:saved=read_credits_for_publisher(path,row,old,saved,signature,previous)
            except pause_control.PauseRequested:return True
        book=in_book.identify(row,old,saved,signature,previous) if eligible else None  # None while the identity rules block it.
        if book:
            # In-book tier: the comic's own cover agrees with its filename. No external
            # source, so it does not count toward the bounded research checks below.
            batch.progress(phase='Automatic metadata lookup', current_folder=path.parent.name,
                           detail='In-book identification: '+path.name)
            queue_in_book(plan,path,row,saved,signature,previous,book)
            research_runtime.record_check('queued')
            continue
        checked += 1
        if checked > 20:
            return True  # Continue this folder in the next bounded pass.
        batch.progress(phase='Automatic metadata lookup', current_folder=path.parent.name,
                       checked=checked, total=0, updated=0, review=0,
                       detail='Checking ' + path.name)
        if not language_eligible(row,old):
            discovery_state.save_one(path,{'version':MATCHER_VERSION,'signature':signature,'outcome':'excluded_language','retry_at':time.time()+30*86400})
            continue
        import provenance
        # Sergei 2026-10-13: in-book values a verified external source may replace (provenance.py).
        replaceable=provenance.in_book_values(row,old)
        def useful(result):return source_scheduling.useful(result,old,replaceable)
        match = re.search(r'https?://(?:www\.)?comicvine\.gamespot\.com/[^\s]*4000-(\d+)', old.get('Web', ''))
        outcome = 'needs_identity_lookup'
        entry = None  # This comic's entry in the pass plan, once queued.
        retry = time.time() + 86400
        lookup_error = None
        provider_waits = {}
        source_schedule=dict(previous.get('source_schedule',{})) if previous.get('signature')==signature and previous.get('version')==MATCHER_VERSION and not new_cover_leads else {}
        if metron_upgrade:source_schedule.pop('Metron',None)
        external=research_runtime.reuse(path,row,old,saved,MATCHER_VERSION)
        if external and external.get('provider')=='Metron' and external.get('metadata_version',0)<2:external=None
        reused_evidence=bool(external)
        issue=saved.get('verified_evidence',{}).get('issue') if external else None
        if issue and match and str(issue.get('id'))!=match.group(1):issue=None  # Web now names another issue.
        issue_reused=bool(issue)
        if external and not useful(external):
            external=None
            reused_evidence=False  # A thin cached match must not block richer sources.
        attempts=[]
        def completed(name,result,exc):
            nonlocal lookup_error
            source_schedule[name]=source_scheduling.record(source_schedule.get(name,{}),result,exc,old,time.time(),replaceable)
            attempts.append({'provider':name,'result':source_schedule[name]['result']})
            if exc:lookup_error=record_failure(lookup_error,provider_waits,name,exc)
        import pipeline_config
        if not external and not issue_reused and match:
            # Metron is asked before ComicVine (20-second spacing, hourly budget).
            import metron
            if (pipeline_config.source_enabled('Metron')
                    and source_scheduling.ready('Metron',source_schedule.get('Metron',{}),source_statuses,time.time())):
                metron_first=[('Metron',lambda row,old:metron.lookup(row,old) if metron.token() else None)]
                try:external=research_runtime.first_verified(metron_first,row,old,completed,accept=useful)
                except pause_control.PauseRequested:return True
                if external:
                    research.save_evidence(path,external)
                    outcome='web_issue_found'
        dead_web = False  # ComicVine answered that the issue Web names does not exist.
        comicvine_failure = None
        try:
            # ComicVine is asked only by the comic's embedded issue ID; without one it
            # is not searched (lookup_unidentified is kept but no longer called). For
            # a comic with an ID, ComicVine is also the identity check (v0.1.2): saved
            # evidence keeps only an issue that matched, so when none was saved it is
            # asked (its API cache keeps answers 30 days) even when Metron or reused
            # evidence answered, and a conflict found on any pass blocks field writes.
            if not issue_reused and match:
                with research_runtime.stage('ComicVine'):
                    issue = app.api('issue/4000-' + match.group(1))
        except app.ComicVineNotFound:
            # F17: a definitive answer, not an outage. The comic is searched like
            # an unidentified one, with strict verification; nothing to retry soon.
            issue = None
            dead_web = True
        except Exception as exc:
            lookup_error = record_failure(lookup_error,provider_waits,'ComicVine',exc)
            comicvine_failure = str(exc)
            issue = None
            batch.progress(phase='Automatic metadata lookup', detail='ComicVine lookup failed; trying publisher catalog for '+path.name)
        if dead_web and reused_evidence:
            # Evidence saved on an earlier pass may not have been verified strictly.
            external = None
            reused_evidence = False
        hint = None
        identity = old if match else dict(Series=old.get('Series') or row['series'], Number=old.get('Number') or row['number'])
        # A ComicVine issue that disagrees with the embedded series/number is
        # not an identity: every other source is still searched, as for an
        # unidentified comic. Writes keep their own verification; the conflict
        # outcome below still blocks metadata-field plans as before.
        conflict = bool(issue) and not identity_matches(identity, issue)
        # F16: when Web names a ComicVine issue that could not be checked this
        # pass (outage, cooldown, budget, missing key, empty answer), the comic
        # is not unidentified. A conflict saved on an earlier pass still stands;
        # otherwise every field write is held until ComicVine answers.
        saved_conflict = previous.get('conflict_issue') if match and not issue else None
        if (isinstance(saved_conflict, dict) and str(saved_conflict.get('id')) == match.group(1)
                and not identity_matches(identity, saved_conflict)):
            conflict = True
        else:
            saved_conflict = None
        hold = bool(match) and not issue and not conflict and not dead_web
        # A dead Web id is no known conflict: field writes may follow, but only
        # from sources verified strictly.
        strict = conflict or hold or dead_web
        # F18: a comic already held on its previous pass searched every other source
        # strictly then and wrote nothing. While ComicVine still cannot answer, this
        # pass only asked ComicVine again: no source searches, approved-list cover
        # hash, local-model cover read, lead downloads or Lens task. New cover leads
        # still get one strict check.
        wait_only = hold and held_before(previous,signature) and not new_cover_leads
        found = None if conflict else issue
        if external:outcome='web_issue_found'
        if (not found or not old.get('Summary')) and not external and not wait_only:
            import providers, open_library, getcomics, publisher_catalogs, metron
            # While a conflict stands or is unchecked, web-verified sources need a named creator and an agreeing cover.
            sources=[('Metron',lambda row,old:metron.lookup(row,old) if metron.token() else None),
                     ('GCD',providers.gcd_lookup),('Google Books',providers.google_lookup),('Open Library local index',open_library.lookup),
                     ('Dark Horse',lambda row,old:publisher_catalogs.lookup(row,old,'darkhorse_catalog',strict=strict)),
                     ('Image Comics',lambda row,old:publisher_catalogs.lookup(row,old,'image_catalog',strict=strict)),
                     ('PREVIEWSworld',lambda row,old:publisher_catalogs.lookup(row,old,'previews_catalog',strict=strict)),
                     ('GetComics',lambda row,old:getcomics.lookup(row,old,strict=strict))]
            sources=source_scheduling.order(sources,row,old)
            ready=[]
            for name,lookup in sources:
                if not pipeline_config.source_enabled(name):
                    attempts.append({'provider':name,'result':'switched_off'})
                elif source_scheduling.ready(name,source_schedule.get(name,{}),source_statuses,time.time()):ready.append((name,lookup))
                else:attempts.append({'provider':name,'result':'scheduled_wait','next_at':source_schedule[name]['next_at']})
            batch.progress(phase='Automatic metadata lookup',detail='Researching up to two sources for '+path.name)
            try:external=research_runtime.first_verified(ready,row,old,completed,accept=useful)
            except pause_control.PauseRequested:return True
            if external:
                research.save_evidence(path,external)
                outcome='web_issue_found'
            research.save_evidence(path,{'provider_attempts':attempts})
        if not found and not wait_only:
            try:
                with research_runtime.stage('Publisher research'):
                    publisher = research.publisher_lookup(row, old, strict=strict) if not external else None
                if publisher:
                    external = publisher
                    research.save_evidence(path,external)
                    outcome = 'publisher_issue_found'
                    fields,changes,replaced = external_plan(old,external['fields'],replaceable,not (conflict or hold))
                    if fields and not (conflict or hold):  # Strict lookups return only the approved exact-cover list.
                        extra,note = replacement_record(external.get('provider') or 'Publisher catalog',replaced)
                        fields['Notes'] = 'Automatic publisher catalog lookup: '+external['sources'][0]['url']+'. Exact issue title; issue-wide missing fields only. Cover edition not verified; variant-specific facts excluded.'+(' '+note if note else '')
                        entry = plan.add(path,changes,fields,'Publisher exact title; issue-wide fields only.',signature=signature,**extra)
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
                        external=research.resolve_leads(row,old,hint,strict=strict)
                    batch.progress(phase='Automatic metadata lookup',detail='Searching the web for '+path.name)
                    if external:
                        research.save_evidence(path,external)
                        outcome='web_issue_found'
                except Exception as exc:
                    lookup_error=record_failure(lookup_error,provider_waits,'Web',exc)
                if not external:
                    external,wiki_found=free_fallback(row,old,hint,source_schedule,source_statuses,completed,strict=strict,replaceable=replaceable)
                    if wiki_found:outcome='wiki_candidates_found'
                    if external:
                        research.save_evidence(path,external)
                        outcome='web_issue_found'
            book=None
            # The identity rules come first (v0.1.2): never during a conflict, hold or dead id,
            # and never for a comic whose Web names a ComicVine issue.
            if (not external and not strict and not in_book.identity_blocked(old,previous)
                    and pipeline_config.in_book_credits_pages()):
                # Stretch tier, off by default: the indicia names this series and issue.
                try:
                    reading=credits_reading(path,saved,signature)
                    import in_book
                    cover=hint if isinstance(hint,dict) and pipeline_config.in_book_cover() else None
                    book=in_book.judge_credits(row,old,reading,signature,cover=cover) if reading else None
                except Exception as exc:
                    if isinstance(exc,pause_control.PauseRequested):raise
                    lookup_error=record_failure(lookup_error,provider_waits,'In-book credits',exc)
                if book:
                    entry=queue_in_book(plan,path,row,saved,signature,previous,book,record=False)
                    outcome='queued'
            if not external and not book:
                import cover_tasks
                cover_tasks.enqueue(row)
        from html import unescape
        issue_text=unescape(re.sub('<[^>]+>',' ',(found or {}).get('description') or ''))
        if found and not external and not old.get('Summary') and not source_scheduling.useful({'sources':[{'text':issue_text}]},old):
            # A verified API ID with no synopsis must not shadow free sources.
            external,_=free_fallback(row,old,hint,source_schedule,source_statuses,completed,replaceable=replaceable)
            if external:
                research.save_evidence(path,external)
                outcome='web_issue_found'
        if external:
            import cover_tasks
            cover_tasks.identified(row)
        if issue:
            identity = old if match else dict(Series=old.get('Series') or row['series'], Number=old.get('Number') or row['number'])
            if identity_matches(identity, issue) and external and external.get('provider')=='Metron':
                pass  # v0.1.3: Metron answered and is written below. ComicVine was asked only as the identity check: no fields, no volume request.
            elif identity_matches(identity, issue):
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
                        volume = app.api('volume/4050-' + str(issue['volume']['id'])) if not old.get('Publisher') or 'Publisher' in replaceable else {}
                except app.ComicVineNotFound:
                    volume = {}  # An answer, not a failure: the issue's own fields stay usable.
                except Exception as exc:
                    lookup_error = record_failure(lookup_error,provider_waits,'ComicVine publisher',exc)
                    volume = {}  # Keep verified issue fields and synopsis evidence usable.
                if (volume.get('publisher') or {}).get('name'):
                    fields['Publisher'] = volume['publisher']['name']
                fields, changes, replaced = external_plan(old, fields, replaceable, True)  # Identity agreed; no hold.
                if fields:
                    extra, note = replacement_record('ComicVine', replaced)
                    fields['Notes'] = ('Automatic enrichment: existing ComicVine issue ID verified against embedded series and issue number.' if match else 'Automatic match: unique exact series and publisher, issue number, publication year and cover similarity agree.') + (' Other existing populated values and synopsis retained. ' + note if note else ' Existing populated values and synopsis retained.')
                    entry = plan.add(path,changes,fields,'Verified existing issue ID; fill missing fields only.',signature=signature,**extra)
                    outcome = 'queued'
                else:
                    outcome = 'current'
                retry = time.time() + 30 * 86400
            else:
                outcome = 'identity_conflict'
        elif conflict:
            outcome = 'identity_conflict'  # Saved on an earlier pass; ComicVine cannot answer now.
        elif hold and outcome in ('web_issue_found','publisher_issue_found'):
            outcome = 'needs_identity_lookup'  # Evidence is kept; its fields wait for the ComicVine check.
        if external and not reused_evidence:
            research_runtime.remember(path,row,old,external,MATCHER_VERSION,issue=issue if not issue_reused and issue and identity_matches(old if match else dict(Series=old.get('Series') or row['series'],Number=old.get('Number') or row['number']),issue) else None)
        if external and outcome == 'web_issue_found':
            fields,changes,replaced=external_plan(old,external['fields'],replaceable,not (conflict or hold))
            if fields:
                extra,note=replacement_record(external.get('provider','web research'),replaced)
                fields['Notes']='Automatic verified lookup: '+external.get('provider','web research')+'. Issue or edition identity checked against the source. Sources: '+', '.join(s['url'] for s in external['sources'])+('\n'+note if note else '')
                entry=plan.add(path,changes,fields,'Verified issue-wide web fields.',signature=signature,**extra)
                outcome='queued'
        if not old.get('Summary') and not hold:  # A held pass writes no field, Summary included.
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
                            entry['fields']['Summary']=proposal['summary']
                            entry['fields']['Notes']+='\n\n'+fields['Notes']
                            entry['changes']['Summary']={'before':'','after':proposal['summary']}
                            plan.save()
                        else:
                            entry=plan.add(path,{'Summary':{'before':'','after':proposal['summary']}},fields,'Exact publisher issue identity; internet-only synopsis with quote and spoiler checks.',signature=signature)
                        outcome = 'queued'
                except Exception as exc:
                    if pause_control.requested():
                        return True  # A queued entry is already in the pass plan's ticket.
                    research.save_evidence(path,{'synopsis_diagnostics':dict(diagnostics,status='error',error=str(exc)[:500])})
                    lookup_error = (lookup_error or '') + '; local model: ' + str(exc)
            else:
                # Notice installation promptly instead of caching the unavailable model for a day.
                retry = min(retry,time.time()+600)
        retry = retry_time(retry,lookup_error,time.time())
        comicvine_wait = provider_waits.get('comicvine') or {}
        if hold:
            # F17: a ComicVine wait (cooldown, budget, rate limit, outage) ends at a
            # known time; ask again then, not a day later. F18: each further held
            # pass in a row doubles the wait, so a lasting fault (revoked key, a
            # machine offline for days) is not polled every folder pass. ComicVine
            # answering again wakes the comic sooner (coverage_priority.lookup_flags).
            held = previous['hold'] if held_before(previous,signature) else {}
            hold_record = {'count':held.get('count',0)+1,'since':held.get('since') or time.time(),'at':time.time(),
                           'wait_end':comicvine_wait.get('retry_at',0)}
            retry = hold_retry(retry,comicvine_wait.get('retry_at',0),hold_record['count'],time.time())
            # Failure-filter spec R2: the dashboard's "next try around" time and cause, structured.
            # next_try_at is the record's retry_at, saved with it; other code may later rewrite retry_at.
            hold_record['next_try_at'] = retry
            cause = comicvine_wait.get('cause') if comicvine_wait else (None if comicvine_failure else 'empty')
            if cause:hold_record['cause'] = cause
        # A Summary-only plan during a conflict still leaves the comic unresolved.
        state['checked'][str(path)] = {'version':MATCHER_VERSION,'metron_metadata_version':2,'signature':signature,'outcome':'identity_conflict' if conflict else outcome,'retry_at':retry,'cover_leads':saved.get('reverse_image_matches'),'provider_waits':provider_waits,'source_schedule':source_schedule,'error':lookup_error[:2000] if lookup_error else None}
        if hold:state['checked'][str(path)]['hold'] = hold_record
        if dead_web:
            state['checked'][str(path)]['dead_link'] = match.group(1)  # Failure-filter spec R1: ComicVine answered Object Not Found.
            state['checked'][str(path)]['detail'] = ('Web names ComicVine issue '+match.group(1)+', which ComicVine reports does not exist; check the Web link. '
                + ('A conflict saved on an earlier pass still blocks field writes.' if conflict else 'Other sources are searched with strict verification.'))
        elif hold:
            reason = comicvine_wait.get('reason') or comicvine_failure or 'ComicVine returned no issue.'
            state['checked'][str(path)]['detail'] = ('Field writes held: Web names ComicVine issue '+match.group(1)+', which could not be checked this pass. '
                + reason[:500] + (' Other sources were searched with strict verification on the first held pass; until ComicVine answers, only ComicVine is asked again.'
                                  if wait_only else ' Other sources are searched with strict verification.'))
        if conflict and match:
            # The conflicting issue lets later passes keep the conflict without ComicVine.
            named = issue or saved_conflict
            state['checked'][str(path)]['conflict_issue'] = {'id':match.group(1),'volume':{'name':(named.get('volume') or {}).get('name')},'issue_number':named.get('issue_number')}
            # Failure-filter spec R3: the same sentence the dashboard row opens with.
            state['checked'][str(path)]['conflict_file'] = {'series':identity.get('Series') or '','number':identity.get('Number') or ''}
            import problems
            state['checked'][str(path)]['detail'] = problems.conflict_sentence(state['checked'][str(path)])
        discovery_state.save_one(path,state['checked'][str(path)])
        research_runtime.record_check(outcome)
    if len(plan):
        return True  # Write this pass's plan; the folder is checked again once it is written.
    batch.progress(phase='Automatic discovery complete', detail='Discovery checked this root. Unidentified comics remain pending further identity lookup; next delta scan in 10 minutes.')
    return False
