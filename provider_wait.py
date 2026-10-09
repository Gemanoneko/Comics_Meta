"""Provider-wide outages are not failures of an individual comic."""


class ProviderDeferred(ValueError):
    def __init__(self, message, provider='web', retry_at=0):
        super().__init__(message)
        self.provider = provider
        self.retry_at = retry_at


def record_failure(errors, waits, provider, exception):
    if isinstance(exception, ProviderDeferred):
        waits[exception.provider] = {'reason': str(exception), 'retry_at': exception.retry_at}
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
