"""Judy's failure-filter spec (2026-10-13, decisions by Sergei the same day): the record side.

R1 a dead-link marker; R2 a held comic's structured next try and cause; R3 a conflict detail
sentence; R4 Try again (one attempt, the failure count kept); R5 the missing-key line needs no
restart. Plus the counts and filters the dashboard reads: one reason per comic, only while the
record still applies, live root only.

The REAL app.api and discovery run (ComicVineWorld); only urllib.request.urlopen, the other
sources and the local model are replaced. A virtual clock passes the waits.
"""
import io
import json
import os
import time
import unittest
import urllib.error
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import app
import coverage_priority
import discovery_state
import problems
import progress_snapshot
from provider_wait import ProviderDeferred, record_failure
from test_comicvine_dead_id import CONFLICTING, GOOD_WEB, MATCHING, NOT_FOUND, VOLUME, ComicVineWorld, http_error, ok
from test_worker import scratch_directory

GOOD = 'B Good 001 (2020).cbz'


def handler(path, body=None):
    """The dashboard's request handler with its reply captured, as test_app does."""
    item = object.__new__(app.Handler)
    item.server = SimpleNamespace(server_port=8765)
    item.path = path
    if body is None:
        item.headers = {'Host': '127.0.0.1:8765'}
    else:
        raw = json.dumps(body).encode()
        item.headers = {'Host': '127.0.0.1:8765', 'Origin': 'http://127.0.0.1:8765', 'Content-Length': str(len(raw))}
        item.rfile = io.BytesIO(raw)
    replies = []
    item.respond = lambda payload, status=200, mime='application/json': replies.append((status, payload))
    (item.do_GET if body is None else item.do_POST)()
    return replies[-1]


class World(ComicVineWorld):
    def good(self, old=None):
        return self.add(GOOD, dict({'Series': 'Good', 'Number': '1', 'Year': '2020', 'Summary': 'Existing synopsis.', 'Web': GOOD_WEB}, **(old or {})))

    def row(self, name=GOOD):
        with app.db() as con:
            return dict(con.execute('SELECT * FROM comics WHERE path=?', (str(self.folder / name),)).fetchone())

    def problem(self, name=GOOD):
        row = self.row(name)
        return problems.classify(self.record(name), [row['size'], row['mtime']])

    def later(self, seconds):
        self.clock.offset += seconds


class CauseCodeTests(World):
    """R2: every way the REAL app.api cannot answer carries its cause code."""

    def cause(self, answer=None, setup=None):
        self.answers['issue/4000-123'] = answer
        if setup:
            setup()
        with patch('urllib.request.urlopen', side_effect=self.urlopen), self.assertRaises(ProviderDeferred) as caught:
            app.api('issue/4000-123')
        waits = {}
        record_failure(None, waits, 'ComicVine', caught.exception)
        self.assertEqual(waits['comicvine']['cause'], caught.exception.cause)
        return caught.exception.cause

    def test_each_cause(self):
        def cooling():
            with app.db() as con:
                con.execute('UPDATE api_state SET blocked_until=? WHERE id=1', (time.time() + 300,))
        self.assertEqual(self.cause(ok(MATCHING), cooling), 'cooldown')
        with app.db() as con:
            con.execute('UPDATE api_state SET blocked_until=0 WHERE id=1')
            con.executemany('INSERT INTO api_requests VALUES(?)', [(time.time() - 10,)] * 180)
        self.assertEqual(self.cause(ok(MATCHING)), 'limit')  # Hourly budget.
        with app.db() as con:
            con.execute('DELETE FROM api_requests')
        self.later(3600)
        self.assertEqual(self.cause(http_error(429, b'')), 'limit')  # Rate limit.
        self.later(7200)
        self.assertEqual(self.cause(http_error(500, b'oops')), 'unreachable')
        self.later(7200)
        self.assertEqual(self.cause(lambda url: urllib.error.URLError('offline')), 'unreachable')
        self.later(7200)
        self.assertEqual(self.cause({'status_code': 100, 'error': 'Invalid API Key', 'results': []}), 'rejected')
        with patch.dict(os.environ, {'COMICVINE_API_KEY': ''}):
            self.assertEqual(self.cause(ok(MATCHING)), 'no_key')


class HoldRecordTests(World):
    """R2 in the saved record: hold.next_try_at equals retry_at; hold.cause names the cause."""

    def held(self, answer, setup=None):
        path = self.good()
        self.answers['issue/4000-123'] = answer
        if setup:
            setup()
        self.passes()
        record = self.record(GOOD)
        self.assertEqual(record['outcome'], 'needs_identity_lookup')
        self.assertEqual(record['hold']['next_try_at'], record['retry_at'])
        self.assertGreater(record['hold']['next_try_at'], 0)
        return record, path

    def test_outage_cause_and_time(self):
        record, _ = self.held(http_error(500, b'oops'))
        self.assertEqual(record['hold']['cause'], 'unreachable')
        self.assertEqual(self.problem(), {'code': 'held', 'retry_at': record['retry_at'], 'cause': 'unreachable'})

    def test_rejected_and_rate_limit(self):
        record, _ = self.held({'status_code': 100, 'error': 'Invalid API Key', 'results': []})
        self.assertEqual(record['hold']['cause'], 'rejected')

    def test_rate_limit(self):
        record, _ = self.held(http_error(429, b''))
        self.assertEqual(record['hold']['cause'], 'limit')

    def test_empty_answer_waits_a_day(self):
        record, _ = self.held(ok([]))
        self.assertEqual(record['hold']['cause'], 'empty')
        self.assertAlmostEqual(record['hold']['next_try_at'] - time.time(), 86400, delta=60)

    def test_missing_key_waits_a_day_with_its_own_cause(self):
        with patch.dict(os.environ, {'COMICVINE_API_KEY': ''}):
            record, _ = self.held(ok(MATCHING))
        self.assertEqual(record['hold']['cause'], 'no_key')
        self.assertAlmostEqual(record['hold']['next_try_at'] - time.time(), 86400, delta=60)

    def test_repeated_holds_follow_hold_retry(self):
        # A short shared cooldown each pass, so the comic's own growing interval decides.
        # (An HTTP error gives the comic an hour's wait of its own: 60 minutes from the start.)
        self.good()
        self.answers['issue/4000-123'] = ok(MATCHING)
        steps = []
        for _ in range(6):
            with app.db() as con:
                con.execute('UPDATE api_state SET blocked_until=? WHERE id=1', (time.time() + 1,))
            self.passes()
            record = self.record(GOOD)
            hold = record['hold']
            steps.append(round((hold['next_try_at'] - hold['at']) / 60))
            self.assertEqual(hold['next_try_at'], record['retry_at'])
            self.assertEqual(hold['cause'], 'cooldown')
            self.clock.offset += hold['next_try_at'] - time.time() + 1
        self.assertEqual(steps, [5, 10, 20, 40, 60, 60])

    def test_a_held_comic_whose_file_changes_is_no_longer_counted(self):
        _, path = self.held(http_error(500, b'oops'))
        self.assertEqual(problems.counts(str(self.root))['held'], 1)
        with app.db() as con:
            con.execute('UPDATE comics SET mtime=mtime+1 WHERE path=?', (str(path),))
        self.assertIsNone(self.problem())
        self.assertEqual(problems.counts(str(self.root))['held'], 0)


class DeadLinkMarkerTests(World):
    """R1."""

    def test_dead_number_is_marked_and_counted_once(self):
        self.good()
        self.answers['issue/4000-123'] = NOT_FOUND
        self.passes()
        record = self.record(GOOD)
        self.assertEqual(record['dead_link'], '123')
        self.assertEqual(self.problem(), {'code': 'dead_link', 'issue_id': '123'})
        self.assertEqual(problems.counts(str(self.root)), dict(dict.fromkeys(problems.CODES, 0), dead_link=1, limit=5))

    def test_no_marker_for_a_live_number_a_hold_or_a_conflict(self):
        with app.db() as con:
            con.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)', ('volume/4050-5?format=json', json.dumps(VOLUME), time.time()))
        for answer in (ok(MATCHING), http_error(500, b'oops'), ok(dict(CONFLICTING, id=123))):
            with app.db() as con:
                con.execute('DELETE FROM discovery_records')
                con.execute("DELETE FROM cache WHERE key LIKE 'issue/%'")
                con.execute('UPDATE api_state SET blocked_until=0 WHERE id=1')
            self.answers['issue/4000-123'] = answer
            if not (self.folder / GOOD).exists():
                self.good()
            self.passes()
            self.assertNotIn('dead_link', self.record(GOOD), answer if isinstance(answer, dict) else 'outage')
            self.later(7200)

    def test_a_stopped_write_on_a_dead_link_shows_only_the_write(self):
        self.good()
        self.answers['issue/4000-123'] = NOT_FOUND
        self.passes()
        for _ in range(5):
            discovery_state.write_not_done(self.folder / GOOD, 'write_failed', 'Access is denied.')
        self.assertEqual(self.problem()['code'], 'write_stopped')
        self.assertEqual(problems.counts(str(self.root))['dead_link'], 0)


class ConflictDetailTests(World):
    """R3: the record's detail is the row's first sentence, word for word."""

    def conflict(self, issue=None):
        self.good()
        self.answers['issue/4000-123'] = ok(issue or dict(CONFLICTING, id=123))
        self.passes()
        return self.record(GOOD)

    def test_fresh_conflict(self):
        record = self.conflict()
        self.assertEqual(record['outcome'], 'identity_conflict')
        self.assertEqual(record['detail'], 'ComicVine issue 123 is Another Series #7; the file says Good #1.')
        self.assertEqual(self.problem(), {'code': 'conflict', 'issue_id': '123', 'cv_series': 'Another Series', 'cv_number': '7',
                                          'file_series': 'Good', 'file_number': '1'})

    def test_conflict_kept_through_an_outage(self):
        self.conflict()
        with app.db() as con:
            con.execute("DELETE FROM cache WHERE key LIKE 'issue/%'")
        self.answers['issue/4000-123'] = http_error(500, b'oops')
        self.later(3 * 86400)
        self.passes()
        record = self.record(GOOD)
        self.assertEqual(record['outcome'], 'identity_conflict')
        self.assertNotIn('hold', record)
        self.assertEqual(record['detail'], 'ComicVine issue 123 is Another Series #7; the file says Good #1.')

    def test_conflict_with_a_dead_link_keeps_the_conflict_sentence(self):
        self.conflict()
        with app.db() as con:
            con.execute("DELETE FROM cache WHERE key LIKE 'issue/%'")
        self.answers['issue/4000-123'] = NOT_FOUND
        self.later(3 * 86400)
        self.passes()
        record = self.record(GOOD)
        self.assertEqual(record['dead_link'], '123')
        self.assertEqual(record['detail'], 'ComicVine issue 123 is Another Series #7; the file says Good #1.')
        self.assertEqual(self.problem()['code'], 'conflict')

    def test_comicvine_values_missing(self):
        record = self.conflict({'id': 123, 'volume': {'id': 6}, 'issue_number': '', 'description': ''})
        self.assertEqual(record['detail'], "ComicVine's series or issue number for this link differs from the file's.")
        self.assertEqual(problems.conflict_sentence(record), record['detail'])


class TryAgainTests(World):
    """R4: one attempt; the failure count is kept."""

    def stopped(self, failures=5):
        path = self.good({'Web': ''})
        row = self.row()
        discovery_state.save_one(path, {'version': 9, 'signature': [row['size'], row['mtime']], 'outcome': 'queued', 'retry_at': 0})
        for _ in range(failures):
            discovery_state.write_not_done(path, 'write_failed', 'The process cannot access the file because it is being used by another process.')
        return path, row

    def test_clears_the_stop_keeps_the_count_and_makes_the_comic_due(self):
        path, row = self.stopped()
        record = self.record(GOOD)
        self.assertTrue(coverage_priority.write_retry_waiting(record, [row['size'], row['mtime']], time.time()))
        changed, problem = problems.try_again(row['id'])
        self.assertTrue(changed)
        record = self.record(GOOD)
        self.assertEqual((record['write_failures']['count'], record['write_failures']['stopped']), (5, False))
        self.assertAlmostEqual(record['retry_at'], time.time(), delta=5)
        self.assertEqual(problem['code'], 'write_failed')
        self.assertFalse(coverage_priority.write_retry_waiting(record, [row['size'], row['mtime']], time.time()))  # Due again.
        discovery_state.write_not_done(path, 'write_failed', 'Access is denied.')  # The one attempt fails.
        record = self.record(GOOD)
        self.assertEqual((record['write_failures']['count'], record['write_failures']['stopped']), (6, True))
        self.assertIn('stopped after 6 failed attempts', record['detail'])

    def test_does_nothing_for_a_stale_or_unstopped_record(self):
        path, row = self.stopped(failures=2)
        self.assertEqual(problems.try_again(row['id'])[0], False)  # Not stopped.
        for _ in range(3):
            discovery_state.write_not_done(path, 'write_failed', 'Access is denied.')
        with app.db() as con:
            con.execute('UPDATE comics SET mtime=mtime+1 WHERE id=?', (row['id'],))  # The file changed.
        before = self.record(GOOD)
        self.assertEqual(problems.try_again(row['id']), (False, None))
        self.assertEqual(self.record(GOOD), before)

    def test_the_route_works_while_paused_and_other_manual_work_does_not(self):
        _, row = self.stopped()
        import pause_control
        with patch.object(pause_control, 'requested', return_value=True):
            status, reply = handler('/api/try-again', {'comic': row['id']})
            self.assertEqual((status, reply['changed'], reply['problem']['code']), (200, True, 'write_failed'))
            status, reply = handler('/api/scan', {'roots': [str(self.folder)]})  # Positive control: still refused.
            self.assertEqual((status, reply['error']), (400, 'Processing is paused. Resume before starting manual work.'))


class DashboardReadTests(World):
    """/api/progress counts and /api/comics filters: one reason per comic, live and current only."""

    def setUp(self):
        super().setUp()
        self.names = {}
        for code, name in (('write_stopped', 'C Stopped 001.cbz'), ('write_failed', 'D Failed 001.cbz'),
                           ('conflict', 'E Conflict 001.cbz'), ('dead_link', 'F Dead 001.cbz'), ('held', 'G Held 001.cbz'),
                           ('both', 'H Both 001.cbz'), ('stale', 'I Stale 001.cbz'), ('absent', 'J Absent 001.cbz'), ('fine', 'K Fine 001.cbz')):
            path = self.add(name, {'Series': name[2:-8], 'Number': '1'})
            self.names[code] = name
            row = self.row(name)
            signature = [row['size'], row['mtime']]
            record = {'version': 9, 'signature': signature, 'outcome': 'queued', 'retry_at': time.time() + 86400}
            if code in ('write_stopped', 'both', 'stale', 'absent'):
                record['outcome'] = 'write_failed'
                record['write_failures'] = {'signature': signature, 'count': 5, 'stopped': True}
                record['write_error'] = 'Access is denied.'
            elif code == 'write_failed':
                record.update(outcome='write_failed', write_failures={'signature': signature, 'count': 2, 'stopped': False}, write_error='Bad CRC.')
            elif code == 'conflict':
                record.update(outcome='identity_conflict', conflict_issue={'id': '7', 'volume': {'name': 'X'}, 'issue_number': '2'},
                              conflict_file={'series': 'Conflict', 'number': '1'})
            elif code == 'dead_link':
                record['dead_link'] = '999'
            elif code == 'held':
                record.update(outcome='needs_identity_lookup', hold={'count': 1, 'at': time.time(), 'wait_end': 0, 'next_try_at': time.time() + 300, 'cause': 'limit'})
            if code == 'both':
                record['dead_link'] = '888'
            discovery_state.save_one(path, record)
        with app.db() as con:
            con.execute('UPDATE comics SET mtime=mtime+1 WHERE path=?', (str(self.folder / self.names['stale']),))
            con.execute("UPDATE comics SET status='absent' WHERE path=?", (str(self.folder / self.names['absent']),))

    def test_counts_one_reason_per_current_live_comic(self):
        counts = problems.counts(str(self.root))
        self.assertEqual(counts, {'write_stopped': 2, 'dead_link': 1, 'conflict': 1, 'write_failed': 1, 'held': 1, 'limit': 5})
        with progress_snapshot.Files() as files:
            snapshot = progress_snapshot.collect(files)
        self.assertEqual(snapshot['problems'], counts)

    def test_each_filter_lists_its_comics_with_their_problem(self):
        totals = {}
        for code in problems.CODES:
            status, reply = handler('/api/comics?status=' + code)
            self.assertEqual(status, 200)
            totals[code] = reply['total']
            self.assertTrue(all(r['problem']['code'] == code for r in reply['rows']), code)
        self.assertEqual(totals, {k: v for k, v in problems.counts(str(self.root)).items() if k != 'limit'})
        _, both = handler('/api/comics?status=write_stopped&q=Both')
        self.assertEqual([Path(r['path']).name for r in both['rows']], [self.names['both']])
        self.assertEqual(handler('/api/comics?status=dead_link&q=Both')[1]['total'], 0)  # Counted once, as stopped.
        self.assertEqual(problems.counts(str(self.root))['write_stopped'], 2)  # The search box never changes the counts.

    def test_every_row_carries_its_problem_whatever_the_filter(self):
        _, reply = handler('/api/comics')
        found = {Path(r['path']).name: r.get('problem', {}).get('code') for r in reply['rows']}
        self.assertEqual(found[self.names['held']], 'held')
        self.assertEqual(found[self.names['write_failed']], 'write_failed')
        self.assertIsNone(found[self.names['stale']])
        self.assertIsNone(found[self.names['fine']])
        failed = next(r for r in reply['rows'] if Path(r['path']).name == self.names['write_failed'])['problem']
        self.assertEqual(failed, {'code': 'write_failed', 'count': 2, 'limit': 5, 'retry_at': failed['retry_at'], 'last_error': 'Bad CRC.'})


class MissingKeyTests(unittest.TestCase):
    """R5: adding the key to .env takes effect without a restart; line C reads not_configured."""

    def test_api_key_and_status_follow_the_env_file(self):
        import providers
        with scratch_directory() as directory, patch.object(app, 'STATE_ROOT', Path(directory) / 'app'), \
                patch.object(app, 'DATA', Path(directory) / 'app' / 'data'), patch.dict(os.environ, {'COMICVINE_API_KEY': ''}):
            (Path(directory) / 'app').mkdir()
            self.assertEqual(app.api_key(), '')
            self.assertEqual(providers.comicvine_status()['status'], 'not_configured')
            (Path(directory) / 'app' / '.env').write_text('COMICVINE_API_KEY=abc123\n', encoding='utf-8')
            self.assertEqual(app.api_key(), 'abc123')  # Same process: no restart.
            self.assertNotEqual(providers.comicvine_status()['status'], 'not_configured')


if __name__ == '__main__':
    unittest.main()
