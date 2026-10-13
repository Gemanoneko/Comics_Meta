"""Provider-wide outages are not failures of an individual comic."""


# Why a provider cannot answer, as a code the dashboard can name (failure-filter spec R2):
# cooling down, a request limit, unreachable or an HTTP error, a refused request, no key.
CAUSES = ('cooldown', 'limit', 'unreachable', 'rejected', 'no_key')


class ProviderDeferred(ValueError):
    def __init__(self, message, provider='web', retry_at=0, cause=None):
        super().__init__(message)
        self.provider = provider
        self.retry_at = retry_at
        self.cause = cause if cause in CAUSES else None


def record_failure(errors, waits, provider, exception):
    if isinstance(exception, ProviderDeferred):
        waits[exception.provider] = {'reason': str(exception), 'retry_at': exception.retry_at}
        if exception.cause:
            waits[exception.provider]['cause'] = exception.cause
        return errors
    return (errors + '; ' if errors else '') + provider + ': ' + str(exception)


def retry_time(normal_retry, errors, now):
    return min(normal_retry, now + 3600) if errors else normal_retry


def repair_old_getcomics_error(record):
    message = 'GetComics needs human verification or rejected access; automatic requests stopped.'
    error = record.get('error') or ''
    if message not in error:return False
    remaining = error.replace(message, '').strip('; ')
    record['error'] = remaining or None
    record.setdefault('provider_waits', {})['getcomics'] = {'reason': message, 'retry_at': 0}
    if not remaining and record.get('retry_at'):
        normal_delay = 30*86400 if record.get('outcome')=='current' else 86400
        record['retry_at'] += normal_delay - 3600
    return True
