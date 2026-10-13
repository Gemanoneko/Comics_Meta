"""Reversible pipeline switches from config.json. Switching something off keeps its code."""
import json
import app

# Sources with no verified write in the 2026-10-12 throughput review. They are off
# unless config.json names its own list; {"sources": {"disabled": []}} turns all on.
# 'Saved lead re-checks' covers re-fetching a saved lead already rejected for this
# archive and identity; new leads are always checked.
DEFAULT_DISABLED_SOURCES = ('General free web', 'Wikipedia/wiki', 'Saved lead re-checks', 'GetComics', 'PREVIEWSworld')
_cache = {}


def load():
    loader = getattr(app, 'load_config', None)  # Present once config moves to the state root.
    if loader:
        return loader()
    path = app.BASE / 'config.json'
    try:
        stat = path.stat()
    except FileNotFoundError:
        return {}
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if _cache.get('key') != key:
        _cache.update(key=key, value=json.loads(path.read_text(encoding='utf-8')))
    return _cache['value']


def section(name):
    value = load().get(name, {})
    return value if isinstance(value, dict) else {}


def disabled_sources():
    value = section('sources').get('disabled')
    if not isinstance(value, list):
        return set(DEFAULT_DISABLED_SOURCES)
    return {str(item) for item in value}


def source_enabled(name):
    return name not in disabled_sources()


def inventory_interval():
    """Seconds between whole-library folder walks (default 6 hours, at least 10 minutes)."""
    try:
        value = float(section('automatic').get('inventory_interval_seconds', 6 * 3600))
    except (TypeError, ValueError):
        value = 6 * 3600.0
    return max(600.0, value)


def in_book_cover():
    """Tier 1: saved cover readings that agree with the filename (on unless set false)."""
    return section('in_book').get('cover', True) is not False


def in_book_credits_pages():
    """Stretch tier: indicia and credits pages read by the local model (off unless set true)."""
    return section('in_book').get('credits_pages', False) is True


def in_book_credits_creators():
    """With the credits tier on, also write creators from labelled credits lines (off unless set true)."""
    return section('in_book').get('credits_creators', False) is True


def in_book_publisher():
    """The in-book tiers also write a canonical publisher named in full in the reading (off unless set true).

    Off by default since 2026-10-13, pending Sergei's decision (v0.1.3 review F21): the
    local model's publisher reading disagreed with embedded or same-folder publishers
    about 4-5% of the time, and a wrong value sticks because later sources fill only
    empty fields. Series and Number are unaffected."""
    return section('in_book').get('publisher', False) is True
