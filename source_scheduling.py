"""Scheduling only: source results still pass their ordinary identity verifiers."""
import time
import research
import providers
from provider_wait import ProviderDeferred

KEYS={'Metron':'metron','GCD':'gcd','Google Books':'google_books','Open Library local index':'open_library',
      'Dark Horse':'darkhorse_catalog','Image Comics':'image_catalog','PREVIEWSworld':'previews_catalog','GetComics':'getcomics',
      'General free web':'free_web','Wikipedia/wiki':'wikipedia'}
FREE_SOURCES={'General free web','Wikipedia/wiki'}


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


def due(previous,signature,version,statuses,new_leads=False,now=None):
    now=time.time() if now is None else now
    if new_leads or previous.get('signature')!=signature or previous.get('version')!=version:return True
    if previous.get('retry_at',0)<=now:return True
    import pipeline_config
    # A source switched off in config.json never makes a comic due again.
    attempts={name:a for name,a in previous.get('source_schedule',{}).items() if pipeline_config.source_enabled(name)}
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
    if available_free_alternative(name,attempt,statuses,now):return True
    if attempt.get('result')=='unavailable' and blocked(attempt_status(name,attempt,statuses),now):return False
    if attempt.get('result')=='unavailable' and attempt_status(name,attempt,statuses).get('status') in ('available','offline_index_ready'):return True
    return attempt.get('next_at',0)<=now


def record(previous,result,error,old,now,replaceable=None):
    if isinstance(error,ProviderDeferred):
        value={'result':'unavailable','failures':0,'next_at':error.retry_at if error.retry_at>now else now+3600}
        if getattr(error,'engine',None) in ('ddg','bing','yandex'):value['engine']=error.engine
        return value
    failures=previous.get('failures',0)+1
    if error:return {'result':'error','failures':failures,'next_at':now+min(3600*2**min(failures-1,3),6*3600)}
    if useful(result,old,replaceable):return {'result':'verified','failures':0,'next_at':now+86400}
    return {'result':'verified_no_new_data' if result else 'no_verified_match','failures':failures,
            'next_at':now+min(86400*2**min(failures-1,3),7*86400)}


def order(sources,row,old):
    preferred=[]
    if old.get('ISBN'):preferred+=['Open Library local index','Google Books']
    elif providers.is_book(row,old):preferred+=['Google Books']
    hint=research.normalize(old.get('Publisher','')+' '+row.get('path',''))
    if 'darkhorse' in hint:preferred.append('Dark Horse')
    if 'image' in hint:preferred.append('Image Comics')
    rank={name:i for i,name in enumerate(preferred)}
    return sorted(sources,key=lambda entry:rank.get(entry[0],len(preferred)))
