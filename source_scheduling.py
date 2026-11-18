"""Scheduling only: source results still pass their ordinary identity verifiers."""
import random
import time
import research
import providers
from provider_wait import ProviderDeferred

KEYS={'Metron':'metron','GCD':'gcd','Google Books':'google_books','Open Library local index':'open_library',
      'GCD offline':'gcd_offline',
      'Dark Horse':'darkhorse_catalog','Image Comics':'image_catalog','PREVIEWSworld':'previews_catalog','GetComics':'getcomics',
      'General free web':'free_web','Wikipedia/wiki':'wikipedia',
      'ComicVine search':'comicvine_search'}
FREE_SOURCES={'General free web','Wikipedia/wiki'}
# ComicVine name search (2026-11-18): every miss waits scheduling.long_miss_days from the first one. Its ComicVine
# answers are cached 30 days (app.api's cache), so a sooner re-ask gives the same answer, and short re-asks of about
# 11,800 comics would hold its hourly allowance for good (pilot 2026-11-17, recommendation 4).
LONG_MISS_SOURCES={'ComicVine search'}


def useful(result,old,replaceable=None):
    """The result adds something: an empty field, a synopsis source, or (Sergei 2026-10-13) a
    verified value that disagrees with one the in-book tiers wrote (provenance.in_book_values)."""
    if not result:return False
    import imprints
    fields=imprints.split(result.get('fields',{}))  # As it would be written: an imprint in Imprint.
    if any(value and not old.get(key) for key,value in fields.items()):return True
    if replaceable:
        import provenance
        if any(key in replaceable and provenance.disagrees(key,replaceable[key],value) for key,value in fields.items()):return True
    return not old.get('Summary') and any(len(s.get('text','').split())>=20 for s in result.get('sources',[]))


def blocked(status,now):
    return status.get('status')=='human_verification' or status.get('retry_at',0)>now


def attempt_status(name,attempt,statuses):
    state=statuses.get(KEYS.get(name,''),{})
    engine=attempt.get('engine')
    if name=='General free web' and engine in ('ddg','bing','yandex'):
        return state.get('engines',{}).get(engine,state)
    return state


def available_free_alternative(name,attempt,statuses,now):
    # A pending Yandex challenge must not indefinitely pin DDG/Bing. Retain
    # the recorded comic deadline before reconsidering those ordinary engines.
    state=statuses.get('free_web',{})
    return (name=='General free web' and attempt.get('engine')=='yandex' and attempt.get('next_at',0)<=now
            and state.get('engines',{}).get('yandex',{}).get('status')=='human_verification'
            and any(state.get('engines',{}).get(engine,{}).get('status')=='available'
                    and not blocked(state['engines'][engine],now) for engine in ('ddg','bing')))


FINAL_RESULTS=('no_verified_match','verified_no_new_data')


def gcd_offline_settled(attempt):
    """Option 5 (Sergei 2026-11-17): GCD offline already answered this comic under the active index and matching
    rules, and found nothing to write. The index is a fixed local file, so asking again gives the same answer
    until a new dump or new rules change gcd_offline.rules_stamp()."""
    import gcd_offline,pipeline_config
    return (pipeline_config.scheduling('gcd_offline_miss_final') and (attempt or {}).get('result') in FINAL_RESULTS
            and gcd_offline.current() is not None and attempt.get('rules')==gcd_offline.rules_stamp())


def can_search(name,row,old,schedule=None):
    """Whether a source's lookup could ask anything for this comic: its own early gate, credentials aside.
    schedule (the comic's source_schedule) lets a settled GCD offline miss count as nothing left to ask."""
    import re
    series,number=research.query_identity(row,old)
    query=old.get('Title') or series
    hint=research.normalize(str(old.get('Publisher') or '')+' '+str(row.get('path','')))
    if name=='Metron':
        import metron
        return metron.identity(row,old) is not None
    if name=='ComicVine search':
        import comicvine_search
        return comicvine_search.can_search(row,old)
    if name=='GCD offline':
        import gcd_offline
        if gcd_offline_settled((schedule or {}).get('GCD offline')):return False
        return bool(series and not gcd_offline.legends_path(row.get('path','')) and gcd_offline.current())
    if name=='GCD':return bool(series and number and (old.get('Year') or row.get('year')))
    if name=='Google Books':return providers.is_book(row,old) and bool(old.get('Title') or old.get('Series') or row.get('series') or old.get('ISBN'))
    if name=='Open Library local index':return bool(re.sub('[^0-9X]','',str(old.get('ISBN') or '').upper())) and providers.is_book(row,old)
    if name=='Dark Horse':return 'darkhorse' in hint and bool(query)
    if name=='Image Comics':return 'image' in hint and bool(query)
    return True  # Title searches (PREVIEWSworld, GetComics, free web, wiki) can always ask.


def nothing_can_search(row,old,schedule=None):
    """Enrichment A: no switched-on source can ask anything for this comic, nor can the Coffin Comics shop route
    (research.publisher_lookup). Its research cannot change until its file, the sources or the matching rules do.
    Since 0.6.0 GCD offline can take any comic with a series, so the marker reached almost no comic (2026-11-17:
    1,348 markers, 9,721 unresolved comics Metron cannot search); option 5 counts a settled GCD offline miss
    (gcd_offline_settled, from schedule) as nothing left to ask."""
    import pipeline_config
    if any(can_search(name,row,old,schedule) for name in KEYS if pipeline_config.source_enabled(name)):return False
    series,number=research.query_identity(row,old)
    return not (research.normalize(old.get('Publisher'))=='coffincomics' and series and number)


_fingerprint=(None,None)


def search_fingerprint():
    """What decided that nothing could search a comic: the matching rules, the switched-on sources and whether
    Google Lens cover search is on (v0.5.0 review F2: switching Lens back on must reach these comics, the ones a
    cover search is for). Kept until config.json changes: the catalog probe asks for it per waiting comic."""
    global _fingerprint
    import pipeline_config,metron,browser_search
    import gcd_offline
    key=(pipeline_config.config_key(),gcd_offline.rules_stamp())
    if _fingerprint[0]==key:return dict(_fingerprint[1])
    sources=sorted(name for name in KEYS if pipeline_config.source_enabled(name))
    if 'Metron' in sources and 'ComicVine search' in sources:
        # The ComicVine name search can ask only comics Metron's own rules can (comicvine_search.can_search), so
        # with Metron on, switching it either way leaves every marker true and must not wake the marked comics.
        sources.remove('ComicVine search')
    value={'rules':metron.rules_stamp(),'gcd_rules':gcd_offline.rules_stamp(),'sources':sources,
           'lens':bool(browser_search.settings().get('enabled'))}
    if not pipeline_config.scheduling('gcd_offline_miss_final'):
        # Option 5 switched off: markers set while it was on (a settled GCD miss counted as nothing left to ask)
        # no longer match, so those comics are asked again. Markers from before option 5 keep their fingerprint.
        value['gcd_offline_miss_final']=False
    _fingerprint=(key,value)
    return dict(value)


def due(previous,signature,version,statuses,new_leads=False,now=None):
    now=time.time() if now is None else now
    if new_leads or previous.get('signature')!=signature or previous.get('version')!=version:return True
    import gcd_offline, pipeline_config
    gcd_attempt=previous.get('source_schedule',{}).get('GCD offline',{})
    if (previous.get('outcome')=='needs_identity_lookup' and not previous.get('hold')
            and pipeline_config.source_enabled('GCD offline') and gcd_offline.current()
            and gcd_attempt.get('rules')!=gcd_offline.rules_stamp()):return True
    if (previous.get('unsearchable') and previous.get('outcome')=='needs_identity_lookup' and not previous.get('hold')
            and previous['unsearchable']==search_fingerprint()):
        return False  # Enrichment A: nothing can search it until its file, the sources or the rules change.
    import pipeline_config
    # A source switched off in config.json never makes a comic due again.
    attempts={name:a for name,a in previous.get('source_schedule',{}).items() if pipeline_config.source_enabled(name)}
    if previous.get('retry_at',0)<=now:
        # An unchanged, unresolved comic cannot gain a match by repeating a pass
        # whose recorded sources are all still waiting. Keep legacy/no-schedule,
        # successful, conflicting and held records on their existing retry path.
        # New evidence, matcher changes and changed archives returned above.
        if (previous.get('outcome')=='needs_identity_lookup' and not previous.get('hold')
                and attempts and all(name in attempts for name in KEYS if pipeline_config.source_enabled(name))
                and all(not ready(name,a,statuses,now) for name,a in attempts.items())):
            return False
        return True
    if any(available_free_alternative(name,attempt,statuses,now) for name,attempt in attempts.items()):return True
    if any(a.get('result')=='error' and a.get('next_at',0)<=now and
           (name not in FREE_SOURCES or not blocked(attempt_status(name,a,statuses),now))
           for name,a in attempts.items()):return True
    # Only recorded free attempts gain independent eligibility; legacy records
    # keep their existing comic retry, rather than a deployment-wide retry wave.
    if any(name in FREE_SOURCES and a.get('next_at',0)<=now and
           not blocked(attempt_status(name,a,statuses),now) for name,a in attempts.items()):return True
    return any(attempt.get('result')=='unavailable' and attempt_status(name,attempt,statuses).get('status') in ('available','offline_index_ready')
               and not blocked(attempt_status(name,attempt,statuses),now)
               for name,attempt in attempts.items())


def ready(name,attempt,statuses,now):
    if not attempt:return True  # Allow ordinary caches on a source's first attempt.
    if name=='GCD offline':
        import gcd_offline
        if gcd_offline.current() and attempt.get('rules')!=gcd_offline.rules_stamp():return True
    if name=='Metron' and attempt.get('result')=='no_verified_match':
        import metron
        if attempt.get('rules')!=metron.rules_stamp():return True  # Enrichment B/C/D: new rules ask once more.
    if name=='ComicVine search' and attempt.get('result')=='no_verified_match':
        import comicvine_search
        if attempt.get('rules')!=comicvine_search.rules_stamp():return True  # Its identity or cover rules changed.
    if available_free_alternative(name,attempt,statuses,now):return True
    if attempt.get('result')=='unavailable' and blocked(attempt_status(name,attempt,statuses),now):return False
    if attempt.get('result')=='unavailable' and attempt_status(name,attempt,statuses).get('status') in ('available','offline_index_ready'):return True
    return attempt.get('next_at',0)<=now


SPREAD=random.random  # Option 5's random stretch; tests replace it.


def miss_delay(failures,long=False):
    """Seconds until a comic whose source answered nothing new is asked again (option 5, Sergei 2026-11-17).

    1, 2, 4, then 7 days as before; after scheduling.long_miss_after misses in a row, scheduling.long_miss_days.
    long (LONG_MISS_SOURCES): scheduling.long_miss_days from the first miss.
    Each wait is stretched by a random 0 to scheduling.retry_spread of itself: after the 0.6.1 re-ask, about 33,000
    comics all came due within three days, a week later and every week after (diagnosis 2026-11-17 §2.5)."""
    import pipeline_config
    delay=min(86400*2**min(failures-1,3),7*86400)
    after=pipeline_config.scheduling('long_miss_after')
    if long or (after and failures>=after):delay=max(delay,pipeline_config.scheduling('long_miss_days')*86400)
    return delay*(1+pipeline_config.scheduling('retry_spread')*SPREAD())


def record(previous,result,error,old,now,replaceable=None,rules=None,long_miss=False):
    """rules: the source's matching-rules stamp (Metron, GCD offline, ComicVine search). Misses are counted under the
    rules in force: a miss under other rules starts the count again, so new rules get the short waits first.
    long_miss: a miss waits scheduling.long_miss_days from the first one (LONG_MISS_SOURCES)."""
    if isinstance(error,ProviderDeferred):
        value={'result':'unavailable','failures':0,'next_at':error.retry_at if error.retry_at>now else now+3600}
        if getattr(error,'engine',None) in ('ddg','bing','yandex'):value['engine']=error.engine
        return value
    failures=previous.get('failures',0)+1
    if error:return {'result':'error','failures':failures,'next_at':now+min(3600*2**min(failures-1,3),6*3600)}
    if useful(result,old,replaceable):return {'result':'verified','failures':0,'next_at':now+86400}
    if rules is not None and previous.get('rules') not in (None,rules):failures=1
    return {'result':'verified_no_new_data' if result else 'no_verified_match','failures':failures,
            'next_at':now+miss_delay(failures,long_miss)}


def order(sources,row,old):
    preferred=[]
    if old.get('ISBN'):preferred+=['Open Library local index','Google Books']
    elif providers.is_book(row,old):preferred+=['Google Books']
    hint=research.normalize(old.get('Publisher','')+' '+row.get('path',''))
    if 'darkhorse' in hint:preferred.append('Dark Horse')
    if 'image' in hint:preferred.append('Image Comics')
    rank={name:i for i,name in enumerate(preferred)}
    return sorted(sources,key=lambda entry:rank.get(entry[0],len(preferred)))
