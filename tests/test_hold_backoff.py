"""F18 (Senua, v0.1.2 review round 5): a comic held for its ComicVine identity check
backs off instead of being re-run every folder pass for as long as a fault lasts.

- The n-th held pass in a row waits 5, 10, 20 and 40 minutes, then hourly, and
  never before the comic's own ComicVine wait ends; a missing key keeps the daily retry.
- After the first held pass, a held pass only asks ComicVine again: no source
  searches, approved-list cover hash, local-model cover read or lead downloads.
- ComicVine answering any request wakes held comics whose own wait has ended.

The REAL app.api (cache, cooldown, 20-second pacing, hourly budget), discover,
ordering, due logic and source scheduling run on a virtual clock in an isolated
catalog; only urlopen, the source bodies and the local model are replaced.
"""
import io
import json
import os
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import app
import automatic
import coverage_priority
import cover_tasks
import research
import research_runtime
from test_worker import scratch_directory

HOUR = 3600


class HoldRetryScheduleTests(unittest.TestCase):
    def test_intervals_grow_to_hourly_and_respect_the_comicvine_wait(self):
        now, daily = 1000.0, 1000.0 + 86400
        waits = [automatic.hold_retry(daily, now + 300, count, now) - now for count in range(1, 8)]
        self.assertEqual(waits, [300, 600, 1200, 2400, 3600, 3600, 3600])  # Before: 300 every time.
        self.assertEqual(automatic.hold_retry(daily, now + 3600, 1, now) - now, 3600)  # Not before ComicVine's own wait ends.
        self.assertEqual(automatic.hold_retry(now + 900, now + 300, 6, now) - now, 900)  # Never later than the ordinary retry.
        self.assertEqual(automatic.hold_retry(daily, 0, 3, now), daily)  # Missing key: no known end, daily retry kept.

    def test_comicvine_answering_wakes_only_comics_whose_own_wait_ended(self):
        now = 10000.0
        answered = {'comicvine': {'status': 'available', 'checked_at': now - 10}}
        turned_away = {'hold': {'count': 3, 'at': now - 100, 'wait_end': now - 50}}
        failed_itself = {'hold': {'count': 1, 'at': now - 100, 'wait_end': now + 3000}}
        self.assertTrue(coverage_priority.comicvine_answered_since_hold(turned_away, answered, now))
        self.assertFalse(coverage_priority.comicvine_answered_since_hold(failed_itself, answered, now))  # No pause re-trigger.
        self.assertFalse(coverage_priority.comicvine_answered_since_hold(turned_away, {'comicvine': dict(answered['comicvine'], checked_at=now - 200)}, now))
        self.assertFalse(coverage_priority.comicvine_answered_since_hold(turned_away, {'comicvine': {'status': 'connection_error', 'checked_at': now}}, now))
        self.assertFalse(coverage_priority.comicvine_answered_since_hold({}, answered, now))  # Not held.
        no_end = {'hold': {'count': 1, 'at': now - 100, 'wait_end': 0}}  # Empty (cached) answer or missing key.
        self.assertFalse(coverage_priority.comicvine_answered_since_hold(no_end, answered, now))  # Daily retry, no re-run per answer.


class Clock:
    def __init__(self):
        self.real = time.time
        self.offset = 0.0
        self.start = self.real()

    def time(self):
        return self.real() + self.offset

    def sleep(self, seconds):
        self.offset += max(0, seconds)

    def hours(self):
        return (self.time() - self.start) / HOUR


class ManyHeldComicsTests(unittest.TestCase):
    """Eight comics whose Web names a ComicVine issue; ComicVine is unreachable for six hours."""

    COMICS = 8
    OUTAGE_HOURS = 6

    def setUp(self):
        self.clock = Clock()
        root = Path(self.enterContext(scratch_directory()))
        for target, name, value in ((app, 'DATA', root / 'data'), (app, 'BASE', root), (research, 'CACHE', root / 'evidence')):
            self.enterContext(patch.object(target, name, value))
        self.enterContext(patch.object(app, 'live_root', return_value=str(root)))
        self.enterContext(patch.dict(os.environ, {'COMICVINE_API_KEY': 'test-key'}))
        self.folder = root / 'Lib'
        self.folder.mkdir()
        import discovery_state
        with app.db() as con:
            discovery_state.initialize(con)
            cover_tasks.table(con)
        self.answers = {}
        for i in range(self.COMICS):
            path = self.folder / ('C%02d Good %03d (2020).cbz' % (i, i + 1))
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('001.png', path.name.encode() + b' one')
                archive.writestr('002.png', path.name.encode() + b' two')
            stat = path.stat()
            old = {'Series': 'Good', 'Number': str(i + 1), 'Year': '2020', 'Summary': 's', 'Publisher': 'Example Press',
                   'Web': 'https://comicvine.gamespot.com/good/4000-%d/' % (100 + i)}
            with app.db() as con:
                con.execute('INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,seen) VALUES(?,?,?,?,?,?,?,?,?,?)',
                            (str(path), str(self.folder), stat.st_size, stat.st_mtime_ns, 'Good', str(i + 1), '2020', json.dumps(old), 'embedded', 1))
            self.answers['issue/4000-%d' % (100 + i)] = {'status_code': 1, 'results': {
                'id': 100 + i, 'name': 'T%d' % i, 'volume': {'name': 'Good', 'id': 5}, 'issue_number': str(i + 1)}}
        self.count = Counter()
        self.plans = []

    def urlopen(self, request, timeout=None):
        resource = urllib.parse.urlparse(request.full_url).path.removeprefix('/api/').strip('/')
        self.count['comicvine requests'] += 1
        if self.clock.hours() < self.OUTAGE_HOURS:
            raise urllib.error.URLError('test: ComicVine unreachable')
        return io.BytesIO(json.dumps(self.answers[resource]).encode())

    def counted(self, name, value=None):
        def call(*args, **kwargs):
            self.count[name] += 1
            if self.clock.hours() < self.OUTAGE_HOURS and name != 'source searches':
                self.count[name + ' during the outage'] += 1
            return value
        return call

    def entries(self):
        return [e for plan in self.plans for e in json.loads(plan.read_text(encoding='utf-8'))['entries']]

    def run_passes(self, hours):
        """The folder scheduler, emulated: 5 s after a pass that queued work, otherwise 600 s."""
        import archive_conversion, getcomics, local_model, worker
        queued_at = {}
        patches = [patch.object(time, 'time', self.clock.time), patch.object(time, 'sleep', self.clock.sleep),
                   patch.object(app, 'scan'), patch.object(archive_conversion, 'one', return_value=False),
                   patch.object(worker, 'enqueue', side_effect=lambda target: self.plans.append(Path(target))),
                   patch.object(coverage_priority, 'pending_paths',
                                side_effect=lambda: {coverage_priority.path_key(e['path']) for e in self.entries()}),
                   patch.object(worker.pause_control, 'requested', return_value=False),
                   patch.object(urllib.request, 'urlopen', side_effect=self.urlopen),
                   patch.object(research_runtime, 'first_verified',
                                side_effect=lambda ready, row, old, completed, **kw: [completed(n, None, None) for n, _ in ready] and None),
                   patch.object(research_runtime, 'record_check', side_effect=self.counted('comic passes')),
                   patch.object(research, 'publisher_lookup', side_effect=self.counted('approved-list cover hashes')),
                   patch.object(research, 'resolve_leads', side_effect=self.counted('lead re-checks')),
                   patch.object(research, 'general_lookup', return_value=None), patch.object(research, 'wiki_candidates', return_value=[]),
                   patch.object(getcomics, 'lookup', return_value=None),
                   patch.object(local_model, 'available', return_value=True),
                   patch.object(local_model, 'identify_cover', side_effect=self.counted('local-model cover reads'))]
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            end = self.clock.hours() + hours
            while self.clock.hours() < end:
                more = automatic.discover(self.folder)
                for entry in self.entries():
                    queued_at.setdefault(Path(entry['path']).name, self.clock.hours())
                self.clock.offset += 5 if more else 600
        return queued_at

    def records(self):
        with app.db() as con:
            return [json.loads(r[0]) for r in con.execute('SELECT value FROM discovery_records')]

    def test_held_comics_back_off_skip_local_work_and_recover_after_the_fault(self):
        queued_at = self.run_passes(self.OUTAGE_HOURS + 1.5)
        n = self.COMICS
        # Expensive local work: once per comic, on its first held pass (before: on every pass, about 32 per comic).
        for work in ('local-model cover reads', 'lead re-checks', 'approved-list cover hashes'):
            self.assertEqual(self.count[work + ' during the outage'], n, work)
        # Passes: 5, 10, 20 and 40 minutes, then hourly (before: every 10-minute folder pass, about 33 per comic).
        passes_during = self.count['comic passes'] - n  # Each comic's recovery pass came after the outage.
        self.assertLessEqual(passes_during, n * 11)
        self.assertGreaterEqual(passes_during, n * 5)  # Still retried: holds keep their place.
        self.assertFalse([t for t in queued_at.values() if t < self.OUTAGE_HOURS])  # Nothing written during the outage.
        # Recovery: every comic is queued within about an hour of ComicVine answering again.
        self.assertEqual(len(queued_at), n)
        self.assertLessEqual(max(queued_at.values()), self.OUTAGE_HOURS + 1.25)
        self.assertLessEqual(self.count['comicvine requests'], n + 6 * 8)  # About 8 an hour during the fault, then one each.

    def test_a_held_record_counts_its_holds_and_says_only_comicvine_is_asked(self):
        self.run_passes(2)
        records = self.records()
        self.assertTrue(all(r['outcome'] == 'needs_identity_lookup' for r in records))
        # The comic whose own request failed waits an hour each time; the others back off from 5 minutes.
        self.assertTrue(all(r['hold']['count'] >= 2 for r in records), [r['hold']['count'] for r in records])
        self.assertGreaterEqual(max(r['hold']['count'] for r in records), 5)
        self.assertTrue(all('only ComicVine is asked again' in r['detail'] for r in records))
        self.assertTrue(all(r['retry_at'] >= r['hold']['wait_end'] for r in records))


if __name__ == '__main__':
    unittest.main()
