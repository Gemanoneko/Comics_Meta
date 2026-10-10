"""Scheduling only: source results still pass their ordinary identity verifiers."""
import time
import research
import providers
from provider_wait import ProviderDeferred

KEYS={'Metron':'metron','GCD':'gcd','Google Books':'google_books','Open Library local index':'open_library',
      'Dark Horse':'darkhorse_catalog','Image Comics':'image_catalog','PREVIEWSworld':'previews_catalog','GetComics':'getcomics'}


def useful(result,old):
    if not result:return False
    if any(value and not old.get(key) for key,value in result.get('fields',{}).items()):return True
    return not old.get('Summary') and any(len(s.get('text','').split())>=20 for s in result.get('sources',[]))


def blocked(status,now):
    return status.get('status')=='human_verification' or status.get('retry_at',0)>now


def due(previous,signature,version,statuses,new_leads=False,now=None):
    now=time.time() if now is None else now
    if new_leads or previous.get('signature')!=signature or previous.get('version')!=version:return True
    if previous.get('retry_at',0)<=now:return True
    if any(a.get('result')=='error' and a.get('next_at',0)<=now for a in previous.get('source_schedule',{}).values()):return True
    return any(attempt.get('result')=='unavailable' and statuses.get(KEYS.get(name,''),{}).get('status') in ('available','offline_index_ready')
               and not blocked(statuses.get(KEYS.get(name,''),{}),now)
               for name,attempt in previous.get('source_schedule',{}).items())


def ready(name,attempt,statuses,now):
    if not attempt:return True  # Allow ordinary caches on a source's first attempt.
    if attempt.get('result')=='unavailable' and blocked(statuses.get(KEYS.get(name,''),{}),now):return False
    if attempt.get('result')=='unavailable' and statuses.get(KEYS.get(name,''),{}).get('status') in ('available','offline_index_ready'):return True
    return attempt.get('next_at',0)<=now


def record(previous,result,error,old,now):
    if isinstance(error,ProviderDeferred):
        return {'result':'unavailable','failures':0,'next_at':error.retry_at if error.retry_at>now else now+3600}
    failures=previous.get('failures',0)+1
    if error:return {'result':'error','failures':failures,'next_at':now+min(3600*2**min(failures-1,3),6*3600)}
    if useful(result,old):return {'result':'verified','failures':0,'next_at':now+86400}
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
