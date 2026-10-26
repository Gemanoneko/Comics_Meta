"""Update statistics endpoint and bar edges (UXSpec UpdateStats 2026-10-26, Backlog rulings).

Distinct comics per bar and per period, from write history; live library only; Monday weeks;
local-time boundaries (a fixed Central European wall clock pins the daylight-saving dates);
a rolling last hour. The catalog is a throwaway fixture; nothing outside it is read."""
import datetime
import json
import time
import unittest
from datetime import date, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import app
import update_stats as stats
from test_worker import scratch_directory

ROOT = 'D:\\Comics'


class CentralEurope:
    """CET/CEST by the EU rule: summer time from 01:00 UTC on the last Sunday of March
    to 01:00 UTC on the last Sunday of October. In 2026: 29 March and 25 October."""

    @staticmethod
    def _change(year, month):
        last = date(year, month, 31)
        sunday = last - datetime.timedelta(days=(last.weekday() + 1) % 7)
        return datetime.datetime(year, month, sunday.day, 1, tzinfo=timezone.utc).timestamp()

    def offset(self, epoch):
        year = datetime.datetime.fromtimestamp(epoch, timezone.utc).year
        return 7200 if self._change(year, 3) <= epoch < self._change(year, 10) else 3600

    def local(self, y, mo, d, h=0, mi=0, fold=0):
        """Epoch of a wall-clock time; fold=1 picks the second of a repeated hour."""
        naive = datetime.datetime(y, mo, d, h, mi, tzinfo=timezone.utc).timestamp()
        found = [naive - off for off in (7200, 3600) if self.offset(naive - off) == off]
        return found[min(fold, len(found) - 1)]

    def midnight(self, day):
        return self.local(day.year, day.month, day.day)

    def date(self, epoch):
        return datetime.datetime.fromtimestamp(epoch + self.offset(epoch), timezone.utc).date()

    def wall(self, epoch):
        return datetime.datetime.fromtimestamp(epoch + self.offset(epoch), timezone.utc).replace(tzinfo=None)


WALL = CentralEurope()
NOW = WALL.local(2026, 10, 28, 12, 30)  # Wednesday 28 October 2026, 12:30 CET.


def query(period, first=None, last=None):
    value = {'period': [period]}
    if first is not None:
        value['from'] = [first]
    if last is not None:
        value['to'] = [last]
    return value


class BarEdgeTests(unittest.TestCase):
    """The bar-edge maths alone: no catalog."""

    def walls(self, edges):
        return [WALL.wall(edge) for edge in edges]

    def test_today_is_one_bar_per_clock_hour(self):
        unit, edges = stats.resolve('today', NOW, wall=WALL)
        self.assertEqual(unit, 'hour')
        self.assertEqual(len(edges) - 1, 24)
        self.assertEqual(edges[0], WALL.local(2026, 10, 28))
        self.assertEqual(edges[-1], WALL.local(2026, 10, 29))
        self.assertEqual([w.hour for w in self.walls(edges[:-1])], list(range(24)))

    def test_daylight_saving_days_have_23_and_25_hourly_bars(self):
        unit, edges = stats.resolve('today', WALL.local(2026, 10, 25, 12), wall=WALL)
        self.assertEqual(len(edges) - 1, 25)
        self.assertEqual([w.hour for w in self.walls(edges[:-1])], [0, 1, 2, 2, *range(3, 24)])
        self.assertEqual(edges[-1] - edges[0], 25 * 3600)
        unit, edges = stats.resolve('today', WALL.local(2026, 3, 29, 20), wall=WALL)
        self.assertEqual(len(edges) - 1, 23)
        self.assertEqual([w.hour for w in self.walls(edges[:-1])], [0, 1, *range(3, 24)])
        self.assertEqual(edges[-1] - edges[0], 23 * 3600)

    def test_local_zone_hourly_bars_cover_each_day_exactly(self):
        """The OS zone this machine runs in: every 2026 day is contiguous 1-hour bars from midnight to midnight."""
        day = date(2026, 1, 1)
        while day.year == 2026:
            edges = stats.hourly(day)
            self.assertEqual(edges[0], time.mktime((day.year, day.month, day.day, 0, 0, 0, 0, 0, -1)))
            self.assertEqual(stats.LOCAL.date(edges[0]), day)
            self.assertEqual(stats.LOCAL.date(edges[-1]), day + datetime.timedelta(days=1))
            self.assertIn(len(edges) - 1, (23, 24, 25))
            self.assertTrue(all(0 < b - a <= 3600 for a, b in zip(edges, edges[1:])))
            day += datetime.timedelta(days=1)

    def test_week_starts_monday_whatever_today_is(self):
        for day, monday in ((28, 26), (26, 26), (25, 19), (1, 26)):
            month = 11 if day == 1 else 10
            unit, edges = stats.resolve('week', WALL.local(2026, month, day, 9), wall=WALL)
            self.assertEqual(unit, 'day')
            self.assertEqual(len(edges) - 1, 7)
            self.assertEqual(edges[0], WALL.local(2026, 10, monday))
            self.assertEqual([WALL.date(e).weekday() for e in edges[:-1]], list(range(7)))

    def test_week_across_fall_back_keeps_a_25_hour_sunday(self):
        unit, edges = stats.resolve('week', WALL.local(2026, 10, 25, 9), wall=WALL)
        self.assertEqual(edges[-1] - edges[-2], 25 * 3600)
        self.assertEqual(edges[-1], WALL.local(2026, 10, 26))

    def test_month_is_one_bar_per_calendar_day(self):
        """Addendum 2 (This month): the 1st 00:00 to the 1st of the next month, local; 28 to 31 daily bars."""
        for now, days in ((WALL.local(2026, 2, 14, 9), 28), (WALL.local(2028, 2, 29, 23, 59), 29),
                          (WALL.local(2026, 4, 1, 0, 5), 30), (NOW, 31), (WALL.local(2026, 12, 31, 23), 31)):
            unit, edges = stats.resolve('month', now, wall=WALL)
            first = WALL.date(now).replace(day=1)
            self.assertEqual((unit, len(edges) - 1), ('day', days), first)
            self.assertEqual([WALL.date(e) for e in edges], [first + datetime.timedelta(days=i) for i in range(days + 1)])
            self.assertEqual([WALL.wall(e).hour for e in edges], [0] * (days + 1))

    def test_month_across_clock_changes(self):
        unit, edges = stats.resolve('month', NOW, wall=WALL)  # October 2026: Sunday 25 has 25 hours.
        lengths = [b - a for a, b in zip(edges, edges[1:])]
        self.assertEqual(lengths[24], 25 * 3600)
        self.assertEqual(lengths.count(86400), 30)
        unit, edges = stats.resolve('month', WALL.local(2026, 3, 30, 12), wall=WALL)  # March 2026: Sunday 29 has 23 hours.
        self.assertEqual(edges[29] - edges[28], 23 * 3600)

    def test_year_is_twelve_calendar_months(self):
        unit, edges = stats.resolve('year', NOW, wall=WALL)
        self.assertEqual(unit, 'month')
        self.assertEqual([WALL.date(e) for e in edges], [date(2026, m, 1) for m in range(1, 13)] + [date(2027, 1, 1)])

    def test_last_hour_is_twelve_five_minute_bars_ending_now(self):
        unit, edges = stats.resolve('hour', NOW, wall=WALL)
        self.assertEqual(unit, 'five_minutes')
        self.assertEqual(len(edges) - 1, 12)
        self.assertEqual((edges[0], edges[-1]), (NOW - 3600, NOW))
        self.assertTrue(all(b - a == 300 for a, b in zip(edges, edges[1:])))
        self.assertEqual(stats.current_slot(edges, NOW), 11)

    def frame(self, first, last):
        unit, edges = stats.span_frame(first, last, WALL)
        self.assertEqual(edges[0], WALL.midnight(first))
        self.assertEqual(edges[-1], WALL.midnight(last + datetime.timedelta(days=1)))
        return unit, edges, [WALL.date(e) for e in edges[1:-1]]

    def test_sixty_bar_rule_acceptance_ranges(self):
        """Spec Addendum A1 and A5 item 3: the finest of day, week, month, year that fits in 60 bars."""
        last = date(2026, 10, 28)
        for span, unit, bars in ((1, 'hour', 24), (2, 'day', 2), (60, 'day', 60), (61, 'week', None), (421, 'month', 14)):
            found, edges, _ = self.frame(last - datetime.timedelta(days=span - 1), last)
            self.assertEqual(found, unit, span)
            if bars:
                self.assertEqual(len(edges) - 1, bars, span)
        cases = [(date(2026, 1, 4), date(2027, 2, 21), 414, 'week', 60),   # Sunday start, 60 weeks.
                 (date(2026, 1, 4), date(2027, 2, 27), 420, 'month', 14),  # Sunday start touches 61 weeks.
                 (date(2026, 1, 5), date(2027, 2, 28), 420, 'week', 60),   # Monday start, 60 weeks.
                 (date(2021, 1, 1), date(2025, 12, 31), None, 'month', 60),
                 (date(2021, 1, 1), date(2026, 1, 1), None, 'year', 6)]
        for first, last, days, unit, bars in cases:
            if days:
                self.assertEqual((last - first).days + 1, days)
            found, edges, cuts = self.frame(first, last)
            self.assertEqual((found, len(edges) - 1), (unit, bars), (first, last))
            if unit == 'week':
                self.assertTrue(all(cut.weekday() == 0 for cut in cuts))
                # A Sunday start's first slot is one day (its clipped week); a Monday start's is a full week.
                self.assertEqual(edges[1] - edges[0], (7 - first.weekday()) * 86400, first)
            if unit == 'month':
                self.assertTrue(all(cut.day == 1 for cut in cuts))
        unit, edges, cuts = self.frame(date(2021, 1, 1), date(2026, 1, 1))
        self.assertEqual(cuts, [date(y, 1, 1) for y in range(2022, 2027)])
        self.assertEqual(edges[-1] - edges[-2], 86400)  # The last year holds one day.

    def test_no_range_from_2000_draws_more_than_60_bars(self):
        """Every start day from 2000-01-01 to today, ending today and at the unit borders; and the 2059 limit."""
        today = date.today()
        spans = (2, 60, 61, 414, 415, 420, 421, 1827)
        flat = SimpleNamespace(midnight=lambda d: d.toordinal() * 86400.0)  # Bar structure does not depend on the zone.
        day = stats.EARLIEST
        while day <= today:
            for last in [today] + [day + datetime.timedelta(days=s - 1) for s in spans if day + datetime.timedelta(days=s - 1) <= today]:
                unit, edges = stats.span_frame(day, last, flat)
                self.assertLessEqual(len(edges) - 1, 60, (day, last, unit))
                if unit != 'hour':
                    self.assertEqual(len(edges) - 1, stats.bar_count(unit, day, last), (day, last, unit))
            day += datetime.timedelta(days=1)
        self.assertEqual(stats.bar_count('year', stats.EARLIEST, date(2059, 12, 31)), 60)

    def test_year_bars_cut_at_1_january(self):
        unit, edges, cuts = self.frame(date(2020, 1, 12), date(2026, 10, 28))
        self.assertEqual((unit, len(edges) - 1), ('year', 7))
        self.assertEqual(cuts, [date(y, 1, 1) for y in range(2021, 2027)])

    def test_all_time_follows_the_first_update(self):
        unit, edges = stats.resolve('all', NOW, WALL.local(2026, 10, 2, 15), wall=WALL)
        self.assertEqual((unit, len(edges) - 1), ('day', 27))
        self.assertEqual(edges[0], WALL.local(2026, 10, 2))
        self.assertEqual(stats.resolve('all', NOW, None, wall=WALL), stats.resolve('today', NOW, wall=WALL))
        self.assertEqual(stats.resolve('all', NOW, WALL.local(2026, 10, 28, 1), wall=WALL)[0], 'hour')

    def test_custom_ranges_are_checked(self):
        # One message, in the page's order: both dates, after today, before 2000, end before start.
        bad = [('2026-10-20', '2026-10-19', 'End date is before the start date.'),
               ('2026-10-20', '2026-10-29', 'Dates after today are not available.'),
               ('2026-13-01', '2026-10-20', 'Pick both dates.'), ('', '2026-10-20', 'Pick both dates.'),
               ('20261020', '2026-10-21', 'Pick both dates.'), ('1999-12-31', '2026-10-20', 'Dates before 2000 are not available.'),
               ('1999-12-31', '2026-10-29', 'Dates after today are not available.'),
               ('2026-10-29', '2026-10-20', 'Dates after today are not available.'),
               ('2000-01-02', '1999-12-30', 'Dates before 2000 are not available.')]
        for first, last, message in bad:
            with self.assertRaises(stats.StatsError) as caught:
                stats.resolve('custom', NOW, None, first, last, wall=WALL)
            self.assertEqual((caught.exception.code, str(caught.exception)), ('invalid_range', message), (first, last))
        unit, edges = stats.resolve('custom', NOW, None, '2000-01-01', '2026-10-28', wall=WALL)  # The floor itself is allowed.
        self.assertEqual((unit, len(edges) - 1), ('year', 27))

    def test_current_slot(self):
        edges = [0, 10, 20, 30]
        self.assertEqual([stats.current_slot(edges, n) for n in (0, 9, 10, 29, 30, 31)], [0, 0, 1, 2, 2, None])


class UpdateStatsTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(scratch_directory())
        self.enterContext(patch.object(app, 'DATA', Path(directory) / 'catalog'))
        self.root = ROOT
        self.enterContext(patch.object(app, 'live_root', side_effect=lambda: self.root))
        stats._cache.clear()
        with app.db():
            pass

    def write(self, path, stamp):
        with app.db() as con:
            con.execute('INSERT INTO history(path,backup,source,timestamp) VALUES(?,?,?,?)', (path, '', 'fixture', stamp))

    def get(self, period, first=None, last=None, now=NOW):
        return stats.report(query(period, first, last), now=now, wall=WALL)

    def counts(self, result):
        return [slot[2] for slot in result['slots']]

    def test_a_comic_counts_once_per_bar_and_once_per_period(self):
        a, b = ROOT + '\\Batman\\Batman 001.cbz', ROOT + '\\Spawn\\Spawn 112.cbz'
        for h, mi, path in ((9, 5, a), (9, 40, a), (11, 10, a), (9, 20, b)):
            self.write(path, WALL.local(2026, 10, 28, h, mi))
        result = self.get('today')
        counts = self.counts(result)
        self.assertEqual((counts[9], counts[10], counts[11]), (2, 0, 1))
        self.assertEqual(result['total'], 2)
        self.assertGreater(sum(c for c in counts if c), result['total'])
        self.assertEqual(result['current'], 12)
        self.assertEqual(counts[13:], [None] * 11)  # Hours after now draw nothing.
        self.assertEqual(counts[:9], [0] * 9)

    def test_extended_and_plain_paths_are_the_same_comic(self):
        self.write('\\\\?\\D:\\Comics\\Batman\\Batman 001.cbz', WALL.local(2026, 10, 28, 10))
        self.write('d:\\comics\\batman\\BATMAN 001.CBZ', WALL.local(2026, 10, 28, 10, 30))
        self.write('\\\\?\\D:\\Comics\\Batman\\Batman 001.cbz', WALL.local(2026, 10, 28, 11))
        result = self.get('today')
        self.assertEqual((self.counts(result)[10], self.counts(result)[11], result['total']), (1, 1, 1))

    def test_unc_library_paths(self):
        self.root = '\\\\nas\\share\\Comics'
        self.write('\\\\?\\UNC\\nas\\share\\Comics\\X 001.cbz', WALL.local(2026, 10, 28, 8))
        self.write('\\\\NAS\\Share\\Comics\\x 001.cbz', WALL.local(2026, 10, 28, 9))
        self.write('\\\\nas\\other\\Comics\\Y 001.cbz', WALL.local(2026, 10, 28, 9))
        self.assertEqual(self.get('today')['total'], 1)

    def test_only_the_live_library_counts(self):
        self.write('E:\\Elsewhere\\Early.cbz', WALL.local(2026, 10, 1, 8))
        self.write('\\\\?\\D:\\Comics\\Inside 001.cbz', WALL.local(2026, 10, 2, 15))
        self.write('D:\\ComicsOld\\Sibling 001.cbz', WALL.local(2026, 10, 28, 9))  # Same prefix, other folder.
        self.write('\\\\?\\D:\\Comics\\Sub\\Inside 002.cbz', WALL.local(2026, 10, 27, 9))
        self.write('E:\\Elsewhere\\Late.cbz', WALL.local(2026, 10, 28, 11))
        result = self.get('all')
        self.assertEqual(result['total'], 2)
        self.assertEqual((result['first_at'], result['last_at']), (WALL.local(2026, 10, 2, 15), WALL.local(2026, 10, 27, 9)))
        self.assertEqual((result['unit'], len(result['slots']), result['start']), ('day', 27, WALL.local(2026, 10, 2)))
        self.assertEqual(self.get('today')['total'], 0)
        self.root = ''  # No library configured: every row counts, as the /api/state counters do.
        stats._cache.clear()
        self.assertEqual(self.get('all')['total'], 5)

    def test_daylight_saving_hours_are_separate_bars(self):
        now = WALL.local(2026, 10, 25, 12)
        self.write(ROOT + '\\A.cbz', WALL.local(2026, 10, 25, 2, 30, fold=0))  # 02:30 summer time.
        self.write(ROOT + '\\B.cbz', WALL.local(2026, 10, 25, 2, 30, fold=1))  # 02:30 winter time, an hour later.
        self.write(ROOT + '\\A.cbz', WALL.local(2026, 10, 25, 3, 15))
        result = self.get('today', now=now)
        self.assertEqual(len(result['slots']), 25)
        self.assertEqual(self.counts(result)[1:5], [0, 1, 1, 1])
        self.assertEqual(result['total'], 2)

    def test_week_counts_from_monday(self):
        self.write(ROOT + '\\Sunday.cbz', WALL.local(2026, 10, 25, 23, 30))
        self.write(ROOT + '\\Monday.cbz', WALL.local(2026, 10, 26, 0, 10))
        self.write(ROOT + '\\Wednesday.cbz', WALL.local(2026, 10, 28, 12, 0))
        result = self.get('week')
        self.assertEqual(result['start'], WALL.local(2026, 10, 26))
        self.assertEqual(self.counts(result), [1, 0, 1, None, None, None, None])
        self.assertEqual((result['total'], result['current']), (2, 2))

    def test_empty_period_still_reports_the_last_update(self):
        self.write(ROOT + '\\Old.cbz', WALL.local(2026, 10, 25, 22, 14))
        result = self.get('today')
        self.assertEqual(result['total'], 0)
        self.assertEqual(self.counts(result)[:13], [0] * 13)
        self.assertEqual(result['last_at'], WALL.local(2026, 10, 25, 22, 14))
        empty = self.get('custom', '2026-09-01', '2026-09-30')
        self.assertEqual((empty['total'], empty['current'], set(self.counts(empty))), (0, None, {0}))
        self.assertEqual((empty['from'], empty['to']), ('2026-09-01', '2026-09-30'))

    def test_no_history_at_all(self):
        result = self.get('all')
        self.assertEqual((result['unit'], len(result['slots']), result['total']), ('hour', 24, 0))
        self.assertEqual((result['first_at'], result['last_at'], result['revision']), (None, None, None))

    def test_last_hour_rolls_with_now(self):
        self.write(ROOT + '\\Before.cbz', NOW - 3660)
        self.write(ROOT + '\\Early.cbz', NOW - 3590)
        self.write(ROOT + '\\Recent.cbz', NOW - 120)
        self.write(ROOT + '\\Later.cbz', NOW + 60)  # A clock set back: after now never counts.
        result = self.get('hour')
        self.assertEqual(self.counts(result), [1] + [0] * 10 + [1])
        self.assertEqual((result['total'], result['current'], result['end']), (2, 11, NOW))

    def test_rows_after_now_never_count(self):
        """A clock set back can leave history rows dated later today; bars and total stop at now."""
        self.write(ROOT + '\\Now.cbz', WALL.local(2026, 10, 28, 12, 10))
        self.write(ROOT + '\\Future.cbz', WALL.local(2026, 10, 28, 15, 0))
        result = self.get('today')
        self.assertEqual((result['total'], self.counts(result)[12], self.counts(result)[15]), (1, 1, None))
        self.assertEqual(self.get('week')['total'], 1)

    def test_this_month_counts_days_and_stops_at_today(self):
        a, b = ROOT + '\\A.cbz', ROOT + '\\B.cbz'
        self.write(a, WALL.local(2026, 9, 30, 23, 59))  # Last month.
        self.write(a, WALL.local(2026, 10, 1, 0, 0))
        self.write(a, WALL.local(2026, 10, 26, 10))
        self.write(b, WALL.local(2026, 10, 28, 12, 10))
        result = self.get('month')
        counts = self.counts(result)
        self.assertEqual((result['unit'], len(counts)), ('day', 31))
        self.assertEqual((result['start'], result['end']), (WALL.local(2026, 10, 1), WALL.local(2026, 11, 1)))
        self.assertEqual((counts[0], counts[25], counts[27]), (1, 1, 1))
        self.assertEqual(counts[28:], [None] * 3)  # Days after today draw nothing.
        self.assertEqual((result['total'], result['current']), (2, 27))
        # The 1st, just after midnight: a new month with nothing yet; the last update is still reported.
        first = self.get('month', now=WALL.local(2026, 11, 1, 0, 30))
        self.assertEqual((first['total'], first['current'], len(first['slots'])), (0, 0, 30))
        self.assertEqual(self.counts(first), [0] + [None] * 29)
        self.assertEqual(first['last_at'], WALL.local(2026, 10, 28, 12, 10))

    def test_year_bars_and_future_months(self):
        self.write(ROOT + '\\Jan.cbz', WALL.local(2026, 1, 1, 0, 0))
        self.write(ROOT + '\\Dec.cbz', WALL.local(2025, 12, 31, 23, 59))
        result = self.get('year')
        self.assertEqual(self.counts(result), [1] + [0] * 9 + [None, None])
        self.assertEqual(result['current'], 9)

    def test_cache_follows_the_newest_history_id(self):
        self.write(ROOT + '\\A.cbz', WALL.local(2026, 10, 28, 9))
        real = stats._count
        with patch.object(stats, '_count', side_effect=real) as counted:
            self.assertEqual(self.get('today')['total'], 1)
            self.assertEqual(self.get('today')['total'], 1)
            self.assertEqual(counted.call_count, 1)
            self.write(ROOT + '\\B.cbz', WALL.local(2026, 10, 28, 10))
            result = self.get('today')
            self.assertEqual(counted.call_count, 2)
        self.assertEqual((result['total'], result['revision']), (2, 2))

    def test_timestamp_index_is_added_and_used(self):
        self.get('today')
        with app.db() as con:
            self.assertTrue(con.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name='history_timestamp'").fetchone())
            plan = ' '.join(r[3] for r in con.execute('EXPLAIN QUERY PLAN SELECT path,timestamp FROM history WHERE timestamp>=? AND timestamp<?', (0, 1)))
        self.assertIn('history_timestamp', plan)

    def test_route_answers_and_refuses(self):
        self.write(ROOT + '\\A.cbz', time.time() - 5)
        status, payload = self.handler('/api/update-stats?period=hour')
        self.assertEqual(status, 200)
        self.assertEqual(payload['total'], 1)
        status, payload = self.handler('/api/update-stats?period=month')
        self.assertEqual((status, payload['period'], payload['unit']), (200, 'month', 'day'))
        json.dumps(payload)
        for path, code in (('/api/update-stats?period=decade', 'invalid_period'), ('/api/update-stats', 'invalid_period'),
                           ('/api/update-stats?period=today&from=2026-01-01', 'invalid_period'),
                           ('/api/update-stats?period=custom&from=2026-01-02&to=2026-01-01', 'invalid_range'),
                           ('/api/update-stats?period=custom&from=2026-01-01', 'invalid_range')):
            status, payload = self.handler(path)
            self.assertEqual((status, payload.get('code')), (400, code), path)

    def handler(self, path):
        item = object.__new__(app.Handler)
        item.server = SimpleNamespace(server_port=8765)
        item.path = path
        item.headers = {'Host': '127.0.0.1:8765'}
        replies = []
        item.respond = lambda payload, status=200, mime='application/json': replies.append((status, payload))
        item.do_GET()
        return replies[-1]


if __name__ == '__main__':
    unittest.main()
