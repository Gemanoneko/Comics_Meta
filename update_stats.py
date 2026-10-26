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

Writes no rows. Its one schema write is an additive covering index,
history(timestamp, path), created once per catalog like comics_path_nocase. Opening
the catalog through app.db() runs its schema script, which takes the write lock for a
moment, so a request can wait behind a writer's transaction (30 s busy timeout).

Consistency (Senua M1, Futaba QA-3): each request reads the newest history id first,
then takes `now`; every query stops at that id and nothing dated at or after `now`
counts, the first and last update included. Speed (Futaba QA-2): history is
append-only, so a period's per-bar comic sets are kept and only rows added since are
read on the next request; the cold read is an index-only scan. When history holds a
row dated at or after `now` (a clock set back) nothing is kept for that request.
"""
import bisect
import datetime
import os
import re
import sys
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
AGGREGATES = 8  # Kept per-bar sets: the presets plus a couple of custom ranges.
INDEX = 'history_timestamp_path'

_lock = threading.Lock()
_cache = OrderedDict()  # First and last update, per catalog, library and newest id.
_aggregates = OrderedDict()  # (catalog, library, bar edges) -> _Aggregate
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
    """The comic's key when the path is in the live library, else ''. Memoized per raw path.

    Interned, so the kept bar sets of every period share one string per comic instead of a copy each."""
    key = memo.get(path)
    if key is None:
        import coverage_priority
        key = sys.intern(coverage_priority.path_key(path)) if path else ''
        if prefix and not key.startswith(prefix):
            key = ''
        memo[path] = key
    return key


def _rows(con, sql, args):
    """Plain tuples: these loops can read every history row, and sqlite3.Row costs more per row."""
    cursor = con.cursor()
    cursor.row_factory = None
    return cursor.execute(sql, args)


def _bounds(con, prefix, now, revision):
    """Earliest and latest live-library update dated before `now`, rows up to `revision` (first match wins)."""
    def edge(order):
        memo = {}
        for path, stamp in _rows(con, 'SELECT path,timestamp FROM history INDEXED BY ' + INDEX +
                                 ' WHERE timestamp<? AND id<=? ORDER BY timestamp ' + order, (now, revision)):
            if _member(path, prefix, memo):
                return stamp
        return None
    return edge('ASC'), edge('DESC')


PERIOD_ROWS = 'SELECT path,timestamp FROM history INDEXED BY ' + INDEX + ' WHERE timestamp>=? AND timestamp<? AND id<=?'
# NOT INDEXED keeps the planner on the id range (the rows added since), never a timestamp index scan.
NEW_ROWS = 'SELECT path,timestamp FROM history NOT INDEXED WHERE id>? AND id<=? AND timestamp>=? AND timestamp<?'


def _tally(rows, prefix, edges):
    """The live-library comics in each bar, for these rows."""
    slots = [set() for _ in range(len(edges) - 1)]
    memo = {}
    for path, stamp in rows:
        key = _member(path, prefix, memo)
        if key:
            slots[bisect.bisect_right(edges, stamp) - 1].add(key)
    return slots


class _Aggregate:
    """Bar counts for one set of bar edges, from history rows up to `revision`.

    A row is stamped when it is written, so rows added later land in the newest bar that has
    rows, or a later one. Only that bar's comics and the period's are kept (not every bar's).
    A row that lands in an earlier bar (a clock set back) has the period read again."""

    def __init__(self):
        self.lock = threading.Lock()
        self.revision = 0
        self.counts, self.newest, self.comics, self.total = [], None, set(), set()

    def build(self, slots, revision):
        self.counts = [len(slot) for slot in slots]
        self.newest = max((i for i, slot in enumerate(slots) if slot), default=None)
        self.comics = slots[self.newest] if self.newest is not None else set()
        self.total = set().union(*slots)
        self.revision = revision

    def extend(self, rows, prefix, edges, revision):
        """Adds the rows written since; False if one lands before the newest bar (the caller rebuilds)."""
        memo = {}
        for path, stamp in rows:
            key = _member(path, prefix, memo)
            if not key:
                continue
            index = bisect.bisect_right(edges, stamp) - 1
            if self.newest is None or index > self.newest:
                self.newest, self.comics = index, set()
            elif index < self.newest:
                return False
            self.comics.add(key)
            self.counts[index] = len(self.comics)
            self.total.add(key)
        self.revision = revision
        return True


def _count(con, prefix, edges, now, revision, keep):
    """Distinct comics per bar and over the whole period, from rows up to `revision` dated before `now`.

    keep: no row up to `revision` is dated at or after `now`, so the answer depends on the rows
    alone. The bars are then kept and the next request reads only the rows added since."""
    size = len(edges) - 1
    upper = min(edges[-1], now)
    if revision is None or upper <= edges[0]:
        return [0] * size, 0
    if not keep:
        slots = _tally(_rows(con, PERIOD_ROWS, (edges[0], upper, revision)), prefix, edges)
        return [len(slot) for slot in slots], len(set().union(*slots))
    key = (str(app.DATA), prefix, tuple(edges))
    with _lock:
        aggregate = _aggregates.get(key)
        if aggregate is None:
            aggregate = _aggregates[key] = _Aggregate()
        _aggregates.move_to_end(key)
        while len(_aggregates) > AGGREGATES:
            _aggregates.popitem(last=False)
    with aggregate.lock:
        if aggregate.revision > revision:
            # A newer request already read rows this one must not count (or history was replaced): no reuse.
            return _count(con, prefix, edges, now, revision, False)
        if aggregate.revision < revision:
            if aggregate.revision == 0 or not aggregate.extend(_rows(con, NEW_ROWS, (aggregate.revision, revision, edges[0], edges[-1])),
                                                               prefix, edges, revision):
                aggregate.build(_tally(_rows(con, PERIOD_ROWS, (edges[0], edges[-1], revision)), prefix, edges), revision)
        return list(aggregate.counts), len(aggregate.total)


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
    """Additive, created once per catalog (the comics_path_nocase pattern). Covering, so the period scans
    read only the index (QA-2: through 0.4.0's history(timestamp) index, every row cost a table lookup)."""
    if str(app.DATA) not in _indexed:
        con.execute('CREATE INDEX IF NOT EXISTS ' + INDEX + ' ON history(timestamp,path)')
        _indexed.add(str(app.DATA))


def _arguments(query):
    def one(name):
        values = query.get(name, [])
        if len(values) != 1:
            if name == 'period':
                raise StatsError('invalid_period', 'Choose a period.')
            raise StatsError('invalid_range', 'Pick both dates.')  # Senua m1: a missing date, as the page says it.
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
    prefix = _scope(app.live_root())
    with app.db() as con:
        _index(con)
        revision = con.execute('SELECT MAX(id) FROM history').fetchone()[0]
        # Senua M1: `now` is read after the newest id, so a write that lands in between is inside both bounds.
        now = time.time() if now is None else float(now)
        keep = revision is not None and con.execute('SELECT 1 FROM history INDEXED BY ' + INDEX + ' WHERE timestamp>=? AND id<=? LIMIT 1',
                                                    (now, revision)).fetchone() is None
        if revision is None:
            first_at = last_at = None
        elif keep:
            first_at, last_at = _cached((str(app.DATA), prefix, revision, 'bounds'), lambda: _bounds(con, prefix, now, revision))
        else:
            first_at, last_at = _bounds(con, prefix, now, revision)  # QA-3: a row dated after now is not the last update.
        unit, edges = resolve(period, now, first_at, first_text, last_text, wall)
        current = current_slot(edges, now)
        # The rolling last hour never repeats its edges, so keeping its bars would only push the others out.
        counts, total = _count(con, prefix, edges, now, revision, keep and period != 'hour')
    slots = [[edges[i], edges[i + 1], None if edges[i] > now else counts[i]] for i in range(len(counts))]
    result = {'period': period, 'now': now, 'start': edges[0], 'end': edges[-1], 'unit': unit, 'slots': slots,
              'current': current, 'total': total, 'first_at': first_at, 'last_at': last_at, 'revision': revision}
    if period == 'custom':
        result.update({'from': first_text, 'to': last_text})
    return result
