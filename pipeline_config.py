"""Reversible pipeline switches from config.json. Switching something off keeps its code."""
import math
import app

# Sources with no verified write in the 2026-10-12 throughput review. They are off
# unless config.json names its own list; {"sources": {"disabled": []}} turns all on.
# 'Saved lead re-checks' covers re-fetching a saved lead already rejected for this
# archive and identity; new leads are always checked.
DEFAULT_DISABLED_SOURCES = ('General free web', 'Wikipedia/wiki', 'Saved lead re-checks', 'GetComics', 'PREVIEWSworld')
# Enrichment E (Sergei 2026-10-26): no written comic cites these sources since history began (2026-10-02), while
# GCD and Dark Horse used their daily budgets every day. They are off even when config.json names its own
# "disabled" list (one written before this change would otherwise keep them on); "sources": {"enabled": [...]}
# turns one back on. Their code is kept.
RETIRED_SOURCES = ('GCD', 'Dark Horse', 'Google Books', 'Open Library local index')
# New sources that start switched off (Sergei 2026-11-17: a new source goes on after its results are checked). Like
# the retired ones they stay off whatever "disabled" lists; "sources": {"enabled": [...]} switches one on.
# 'ComicVine search': comicvine_search.py, the name search after Metron and GCD offline find nothing.
# 'VerseDB': versedb.py, after those and the ComicVine name search find nothing.
OPT_IN_SOURCES = ('ComicVine search', 'VerseDB')


def load():
    return app.load_config()


def section(name):
    value = load().get(name, {})
    return value if isinstance(value, dict) else {}


def disabled_sources():
    sources = section('sources')
    value = sources.get('disabled')
    disabled = set(DEFAULT_DISABLED_SOURCES) if not isinstance(value, list) else {str(item) for item in value}
    enabled = sources.get('enabled')
    enabled = {str(item) for item in enabled} if isinstance(enabled, list) else set()
    return (disabled | set(RETIRED_SOURCES) | set(OPT_IN_SOURCES)) - enabled


# Enrichment B, C and D (Sergei 2026-10-26). Looser Metron matching rules. Each default follows the precision
# measured against comics that already carry verified tags (Brief, Decision Log "Enrichment matching rules"): a rule
# is on only where it measured at least as precise as the rule before it. "matching": {"<name>": true|false} in
# config.json overrides one.
MATCHING_DEFAULTS = {
    'filename_year_formats': True,   # B: "(2007-02)", "(1993-Dark Horse)", "[2004]" read as the cover year.
    'folder_year': True,             # B: a folder's "(2002)" read as the series start year when the file names no year.
    'yearless': False,               # B: no year at all; measured too loose (several volumes share a name and number).
    'unnumbered_as_one': True,       # C: a book with no number and no volume or part marker is issue 1.
    'cover_rule_v2': True,           # D: the revised cover comparison.
    # Sergei 2026-11-17 (Docs/ComicsMetaOrganizer_EnrichmentDiagnosis_2026-11-17.md options 2 and 3). Off until a
    # read-only "would write" listing (tools/metron_would_write.py) has been sampled. A switch that is off leaves
    # metron.rules_stamp unchanged, so shipping them wakes nothing.
    'metron_spellings': False,       # Option 2: a leading "The", "&"/"and" and a trailing "(YYYY)" in the Series.
    'collection_label': False,       # Option 3: "Vol N"/"vNN"/"Book N" plus a year is issue N of a collection series.
}


def matching(name):
    value = section('matching').get(name)
    return value if isinstance(value, bool) else MATCHING_DEFAULTS[name]


# Option 5 (Sergei 2026-11-17, Docs/ComicsMetaOrganizer_EnrichmentDiagnosis_2026-11-17.md §2.5): research re-asks.
# "scheduling": {"<name>": value} in config.json overrides one; 0 or false switches a part off.
SCHEDULING_DEFAULTS = {
    'retry_spread': 0.5,            # A miss's wait is stretched by a random 0-50%, so comics asked together drift apart.
    'long_miss_after': 6,           # After this many misses in a row under the same rules (0: never)...
    'long_miss_days': 30,           # ...the next ask waits this many days instead of at most 7.
    'gcd_offline_miss_final': True, # A GCD offline miss under the same index and rules is final (Enrichment A works again).
}


def scheduling(name):
    """One option 5 setting; a missing or wrongly typed value falls back to its default."""
    default = SCHEDULING_DEFAULTS[name]
    value = section('scheduling').get(name)
    if isinstance(default, bool):
        return value if isinstance(value, bool) else default
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        return default
    return value


def config_key():
    """Changes whenever config.json does (or a switch function is replaced): a key for values derived from it."""
    path = app.STATE_ROOT / 'config.json'
    try:
        stat = path.stat()
        found = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        found = None
    return (str(path), found, id(matching), id(disabled_sources), id(source_enabled), id(lens_enabled), id(scheduling))


def lens_enabled():
    """Google Lens cover search (Enrichment E, Sergei 2026-10-26: off). No lead it saved since 2026-10-03, while it
    kept asking Sergei to solve Google's checks. On only with "browser_search": {"lens": true}; the older
    "enabled" key alone no longer switches it on."""
    return section('browser_search').get('lens') is True


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


def in_book_publisher_agreement():
    """The in-book tiers write Publisher only when the cover reading and the credits/indicia
    reading of the same pages both name the same publisher (Sergei 2026-10-13). On unless set
    false: Sergei switched it on after Futaba's pilot (2026-10-13: when both readings agreed,
    Metron agreed 164 of 165 times; the one miss was the imprint Skybound for Image Comics).

    It reads the credits/indicia pages with the local model (about 2.7 s per comic, once) for
    comics whose cover names a publisher, even when "credits_pages" is off. The v0.1.3
    "publisher" key (a publisher from one reading) is retired: on its own it writes nothing
    (v0.1.3 review F21: one reading disagreed with known publishers about 4-5% of the time)."""
    return section('in_book').get('publisher_agreement', True) is not False


def in_book_credits_year():
    """With the credits tier on, also write Year and Month from a cover date printed after the
    issue number (off unless set true). The pilot (2026-10-13) found 23.5% of those years right
    on 2024-2026 books; Sergei: keep it off."""
    return section('in_book').get('credits_year', False) is True


def in_book_filename_number():
    """A numbered file whose cover number could not be read gets Series and Number from the
    filename, when the cover title agrees with the filename series (Sergei 2026-10-13).
    On unless set false."""
    return section('in_book').get('filename_number', True) is not False
