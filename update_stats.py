"""Update statistics (UXSpec UpdateStats 2026-10-26; Backlog § Update statistics graph).

How many distinct live-library comics the app updated in a period, in total and per
bar, read from the write history. `history` gets one row per verified write and is
never pruned, so "All time" starts at the earliest row.

* A comic is its path as coverage_priority.path_key reads it: the extended prefix
  stripped and the case folded, so `\\\\?\\D:\\A.cbz` and `d:\\a.cbz` count once.
* Live library only: rows outside the configured library folder are left out.
* Periods: last hour, today, this week, this month, this year, all time, custom.
* Day, week (from Monday), month and year boundaries are local time and are built
  here, so the page never works out daylight saving. "Last hour" is the 60 minutes
  ending at `now`, in 12 equal bars. All time and Custom use the finest unit that
  fits in 60 bars (spec Addendum A1).
* The total is a distinct count over the whole period, never a sum of the bars.

Read-only, apart from one additive index, history(timestamp), created once per
catalog like comics_path_nocase. Results are cached by the newest history id.
"""
import bisect
import datetime
import os
import re
import threading
import time
from collections import OrderedDict
from pathlib import Path
import app

PERIODS = ('hour', 'today', 'week', 'month', 'year', 'all', 'custom')
HOUR = 3600
ONE_DAY = datetime.timedelta(days=1)
# Spec Addendum A1: nothing was updated before the app existed, and with this floor
# yearly bars stay at 60 or fewer through 2059.
EARLIEST = datetime.date(2000, 1, 1)
MAX_BARS = 60
FIT_UNITS = ('day', 'week', 'month', 'year')
ISO_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
CACHE_SIZE = 32

_lock = threading.Lock()
_cache = OrderedDict()
_indexed = set()


class StatsError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class LocalWall:
    """The OS local zone, daylight saving included (C library mktime and localtime)."""

    def midnight(self, day):
        return time.mktime((day.year, day.month, day.day, 0, 0, 0, 0, 0, -1))

    def date(self, epoch):
        moment = time.localtime(epoch)
        return datetime.date(moment.tm_year, moment.tm_mon, moment.tm_mday)


LOCAL = LocalWall()


def _next_month(day):
    return datetime.date(day.year + day.month // 12, day.month % 12 + 1, 1)


def hourly(day, wall=LOCAL):
    """One slot per clock hour of a local day: 24, or 23/25 on a daylight-saving date."""
    start, end = wall.midnight(day), wall.midnight(day + ONE_DAY)
    edges = [start]
    while edges[-1] + HOUR < end:
        edges.append(edges[-1] + HOUR)
    edges.append(end)
    return edges


def _next_cut(unit, day):
    """The next slot start after `day`: the next day, Monday, 1st of a month, or 1 January."""
    if unit == 'day':
        return day + ONE_DAY
    if unit == 'week':
        return day + datetime.timedelta(days=7 - day.weekday())
    if unit == 'month':
        return _next_month(day)
    return datetime.date(day.year + 1, 1, 1)


def bar_count(unit, first, last):
    """Slots of this unit that the local days first..last touch, both partial ends included."""
    if unit == 'day':
        return (last - first).days + 1
    if unit == 'week':
        return (last - (first - datetime.timedelta(days=first.weekday()))).days // 7 + 1
    if unit == 'month':
        return (last.year - first.year) * 12 + last.month - first.month + 1
    return last.year - first.year + 1


def span_frame(first, last, wall=LOCAL):
    """Bars for a run of local days, both included (spec Addendum A1, the 60-bar rule).

    One day is hourly. A longer run uses the finest of day, week (from Monday), month
    and year whose bar count for these exact dates is 60 or fewer; a week, month or year
    cut by the first or last day is clipped to it."""
    if last <= first:
        return 'hour', hourly(first, wall)
    unit = next((u for u in FIT_UNITS if bar_count(u, first, last) <= MAX_BARS), FIT_UNITS[-1])
    cuts = [first]
    day = _next_cut(unit, first)
    while day <= last:
        cuts.append(day)
        day = _next_cut(unit, day)
    cuts.append(last + ONE_DAY)
    return unit, [wall.midnight(day) for day in cuts]


def _day(text):
    if not isinstance(text, str) or not ISO_DATE.fullmatch(text):
        raise StatsError('invalid_range', 'Pick both dates.')
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        raise StatsError('invalid_range', 'Pick both dates.') from None


def resolve(period, now, first_at=None, first_text=None, last_text=None, wall=LOCAL):
    """The period's unit and bar edges (epoch seconds), from one `now`."""
    today = wall.date(now)
    if period == 'hour':
        return 'five_minutes', [now - HOUR + 300 * index for index in range(12)] + [now]
    if period == 'today':
        return 'hour', hourly(today, wall)
    if period == 'week':
        monday = today - datetime.timedelta(days=today.weekday())
        return 'day', [wall.midnight(monday + datetime.timedelta(days=i)) for i in range(8)]
    if period == 'month':
        # Spec Addendum 2 (This month): one bar per calendar day of the current month, 28 to 31.
        first = today.replace(day=1)
        days = (_next_month(first) - first).days
        return 'day', [wall.midnight(first + datetime.timedelta(days=i)) for i in range(days + 1)]
    if period == 'year':
        cuts = [datetime.date(today.year, month, 1) for month in range(1, 13)] + [datetime.date(today.year + 1, 1, 1)]
        return 'month', [wall.midnight(day) for day in cuts]
    if period == 'all':
        first = today if first_at is None else min(wall.date(first_at), today)
        return span_frame(first, today, wall)
    if period == 'custom':
        # One message, in the page's order (spec Addendum A1).
        first, last = _day(first_text), _day(last_text)
        if first > today or last > today:
            raise StatsError('invalid_range', 'Dates after today are not available.')
        if first < EARLIEST or last < EARLIEST:
            raise StatsError('invalid_range', 'Dates before 2000 are not available.')
        if last < first:
            raise StatsError('invalid_range', 'End date is before the start date.')
        return span_frame(first, last, wall)
    raise StatsError('invalid_period', 'Choose a period.')


def current_slot(edges, now):
    """Index of the bar that holds `now` (the last bar when the period ends now), or None."""
    index = bisect.bisect_right(edges, now) - 1
    if 0 <= index < len(edges) - 1:
        return index
    return len(edges) - 2 if edges[-1] == now else None


def _scope(root):
    import coverage_priority
    return coverage_priority.path_key(Path(root)).rstrip('\\/') + os.sep if root else ''


def _member(path, prefix, memo):
    """The comic's key when the path is in the live library, else ''. Memoized per raw path."""
    key = memo.get(path)
    if key is None:
        import coverage_priority
        key = coverage_priority.path_key(path) if path else ''
        if prefix and not key.startswith(prefix):
            key = ''
        memo[path] = key
    return key


def _bounds(con, prefix):
    """Earliest and latest live-library history timestamps (indexed scans, first match wins)."""
    def edge(order):
        memo = {}
        for path, stamp in con.execute('SELECT path,timestamp FROM history WHERE timestamp IS NOT NULL ORDER BY timestamp ' + order):
            if _member(path, prefix, memo):
                return stamp
        return None
    return edge('ASC'), edge('DESC')


def _count(con, prefix, edges, now):
    """Distinct comics per bar and over the whole period; nothing after `now` counts."""
    slots = [set() for _ in range(len(edges) - 1)]
    upper = min(edges[-1], now)
    if upper > edges[0]:
        memo = {}
        for path, stamp in con.execute('SELECT path,timestamp FROM history WHERE timestamp>=? AND timestamp<?', (edges[0], upper)):
            key = _member(path, prefix, memo)
            if key:
                slots[bisect.bisect_right(edges, stamp) - 1].add(key)
    return [len(slot) for slot in slots], len(set().union(*slots))


def _cached(key, compute):
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    value = compute()
    with _lock:
        _cache[key] = value
        _cache.move_to_end(key)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return value


def _index(con):
    """Additive, created once per catalog (the comics_path_nocase pattern)."""
    if str(app.DATA) not in _indexed:
        con.execute('CREATE INDEX IF NOT EXISTS history_timestamp ON history(timestamp)')
        _indexed.add(str(app.DATA))


def _arguments(query):
    def one(name):
        values = query.get(name, [])
        if len(values) != 1:
            raise StatsError('invalid_period' if name == 'period' else 'invalid_range', 'Choose a period.')
        return values[0]
    period = one('period')
    if period not in PERIODS:
        raise StatsError('invalid_period', 'Choose a period.')
    allowed = {'period', 'from', 'to'} if period == 'custom' else {'period'}
    if set(query) - allowed:
        raise StatsError('invalid_period', 'Choose a period.')
    if period == 'custom':
        return period, one('from'), one('to')
    return period, None, None


def report(query, now=None, wall=LOCAL):
    """GET /api/update-stats?period=hour|today|week|month|year|all, or period=custom&from=YYYY-MM-DD&to=YYYY-MM-DD.

    slots: [start, end, count] in epoch seconds, count None for a bar that starts after now.
    current: the bar holding now, or None. first_at/last_at: earliest and latest live-library
    update (None when there is none)."""
    period, first_text, last_text = _arguments(query)
    now = time.time() if now is None else float(now)
    prefix = _scope(app.live_root())
    with app.db() as con:
        _index(con)
        revision = con.execute('SELECT MAX(id) FROM history').fetchone()[0]
        catalog = (str(app.DATA), prefix, revision)
        first_at, last_at = _cached(catalog + ('bounds',), lambda: _bounds(con, prefix))
        unit, edges = resolve(period, now, first_at, first_text, last_text, wall)
        current = current_slot(edges, now)
        counts, total = _cached(catalog + (tuple(edges), current), lambda: _count(con, prefix, edges, now))
    slots = [[edges[i], edges[i + 1], None if edges[i] > now else counts[i]] for i in range(len(counts))]
    result = {'period': period, 'now': now, 'start': edges[0], 'end': edges[-1], 'unit': unit, 'slots': slots,
              'current': current, 'total': total, 'first_at': first_at, 'last_at': last_at, 'revision': revision}
    if period == 'custom':
        result.update({'from': first_text, 'to': last_text})
    return result
