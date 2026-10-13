"""Sergei 2026-10-13, item 3: outside sources may REPLACE in-book values when they disagree.

- Only fields whose value the in-book tiers wrote, untouched since (provenance.py).
- Only from a verified external source; recorded in history and in Notes.
- Never values Sergei or other programs wrote: a manual write, another program saving
  the archive, or a value that changed all leave the field alone.
- An identity conflict or a ComicVine hold still blocks every field write.
- F22: an edit made between the folder scan and the write is never overwritten.

provenance is imported inside tests so that, on 1c34df2, the pipeline tests fail on their
assertions rather than on the import. Isolated catalog, queue and archives; sources mocked.
"""
import io
import json
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import app
import automatic
import batch
import cover_tasks
import providers
import research
import worker
from provider_wait import ProviderDeferred
from test_worker import scratch_directory

NAME = 'Amazing Spider-Man 001 (1963).cbz'
WEB = 'https://comicvine.gamespot.com/amazing-spider-man-1/4000-123/'
METRON = {'provider': 'Metron', 'metadata_version': 2, 'status': 'issue_verified',
          'fields': {'Series': 'The Amazing Spider-Man', 'Number': '001', 'Year': '1963', 'Publisher': 'Marvel'},
          'sources': [{'url': 'https://metron.cloud/issue/1/', 'title': 'The Amazing Spider-Man #1', 'text': ''}]}


class ReplacementHarness(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        for target, name, value in ((app, 'DATA', self.root / 'data'), (app, 'BASE', self.root),
                                    (research, 'CACHE', self.root / 'research'), (worker, 'QUEUE', self.root / 'queue')):
            self.enterContext(patch.object(target, name, value))
        (self.root / 'data').mkdir()
        (self.root / 'data' / 'progress.json').write_text('{"completed": []}', encoding='utf-8')
        import archive_conversion, getcomics, local_model, metron, open_library, publisher_catalogs, research_runtime
        for target, name, value in ((worker.pause_control, 'requested', False), (batch.pause_control, 'requested', False),
                                    (providers, 'statuses', {}), (archive_conversion, 'one', False),
                                    (local_model, 'available', False), (research_runtime, 'reuse', None),
                                    (metron, 'token', 'token'), (providers, 'gcd_lookup', None), (providers, 'google_lookup', None),
                                    (open_library, 'lookup', None), (publisher_catalogs, 'lookup', None), (getcomics, 'lookup', None),
                                    (research, 'publisher_lookup', None), (research, 'resolve_leads', None),
                                    (research, 'general_lookup', None), (research, 'wiki_candidates', [])):
            self.enterContext(patch.object(target, name, return_value=value))
        self.metron = self.enterContext(patch.object(metron, 'lookup', return_value=None))
        self.enterContext(patch.object(batch, 'progress'))
        self.enterContext(patch.object(cover_tasks, 'enqueue'))
        self.enterContext(patch.object(cover_tasks, 'identified'))
        self.api = self.enterContext(patch.object(app, 'api', side_effect=AssertionError('no ComicVine call without a Web id')))
        self.folder = self.root / 'Spider-Man'
        self.folder.mkdir()
        self.path = self.folder / NAME

    def save(self, comicinfo=None):
        """Write the archive as another program would: new bytes and a new modification time."""
        from PIL import Image
        cover = io.BytesIO()
        Image.new('RGB', (60, 90), 'blue').save(cover, format='JPEG')
        before = self.path.stat().st_mtime_ns if self.path.exists() else None
        while True:
            with zipfile.ZipFile(self.path, 'w') as archive:
                archive.writestr('001.jpg', cover.getvalue())
                archive.writestr('002.jpg', b'page' * 100)
                if comicinfo:
                    archive.writestr('ComicInfo.xml', comicinfo)
            if self.path.stat().st_mtime_ns != before:
                break
            time.sleep(0.01)
        app.scan([str(self.folder)], recursive=False)

    def row(self):
        with app.db() as con:
            return dict(con.execute('SELECT * FROM comics WHERE path=?', (str(self.path),)).fetchone())

    def metadata(self):
        return app.read_metadata(self.path)[0]

    def written_in_book(self):
        """v0.1.3's tier writes Series and Number from an agreeing cover reading."""
        self.save()
        row = self.row()
        research.save_evidence(self.path, {'cover_identification': {'title': 'AMAZING SPIDER-MAN', 'issue': '1'},
                                           'cover_signature': [row['size'], row['mtime']]})
        entries = self.run_pass()
        self.assertEqual(entries[0]['source'], 'in-book:cover')
        self.assertEqual((self.metadata()['Series'], self.metadata()['Number']), ('Amazing Spider-Man', '1'))

    def plan(self):
        automatic.discover(self.folder)
        entries, self.plans = [], []
        for _, item in worker.tickets():
            if item['state'] == 'pending':
                self.plans.append(Path(item['plan']))
                entries += json.loads(self.plans[-1].read_text(encoding='utf-8'))['entries']
        return entries

    def run_pass(self):
        entries = self.plan()
        worker.run_one()
        return entries

    def history(self):
        with app.db() as con:
            return [r[0] for r in con.execute('SELECT source FROM history ORDER BY id')]


class ReplacementTests(ReplacementHarness):
    def test_a_verified_source_replaces_the_in_book_value_it_disagrees_with(self):
        self.written_in_book()
        self.metron.return_value = METRON
        entries = self.run_pass()
        entry = entries[0]
        # Before (1c34df2): only Year and Publisher; the in-book Series stayed.
        self.assertEqual(entry['changes']['Series'], {'before': 'Amazing Spider-Man', 'after': 'The Amazing Spider-Man'})
        self.assertNotIn('Number', entry['changes'])  # "001" and "1" are the same number: nothing to replace.
        self.assertEqual(entry['changes']['Year'], {'before': '', 'after': '1963'})
        self.assertEqual(entry['source'], 'replaced-in-book:Metron')
        self.assertEqual(entry['replaced'], {'Series': {'in_book': 'Amazing Spider-Man', 'external': 'The Amazing Spider-Man'}})
        metadata = self.metadata()
        self.assertEqual((metadata['Series'], metadata['Number'], metadata['Year']), ('The Amazing Spider-Man', '1', '1963'))
        self.assertIn('Replaced in-book values with Metron, a verified external source: Series "Amazing Spider-Man" with "The Amazing Spider-Man".',
                      metadata['Notes'])
        self.assertIn('In-book identification', metadata['Notes'])  # Earlier provenance kept.
        self.assertEqual(self.history(), ['in-book:cover', 'replaced-in-book:Metron'])
        import provenance
        self.assertEqual(provenance.in_book_values(self.row(), metadata), {'Number': '1'})  # Series is Metron's now.

    def test_the_write_ledger_records_each_write(self):
        self.written_in_book()
        import provenance
        links = provenance.chain(self.row())
        self.assertEqual(len(links), 1)
        self.assertEqual((links[0]['source'], links[0]['writer']), ('in-book:cover', 'automatic'))
        self.assertEqual(json.loads(links[0]['fields']), {'Series': 'Amazing Spider-Man', 'Number': '1'})
        self.assertEqual([links[0]['output_size'], links[0]['output_mtime']], [self.row()['size'], self.row()['mtime']])
        self.assertEqual(provenance.in_book_values(self.row(), self.metadata()), {'Series': 'Amazing Spider-Man', 'Number': '1'})

    def test_values_sergei_changed_are_never_replaced(self):
        self.written_in_book()
        self.save('<ComicInfo><Series>Amazing Spider-Man (Sergei)</Series><Number>1</Number></ComicInfo>')
        self.metron.return_value = METRON
        entries = self.run_pass()
        self.assertTrue(entries)  # Positive control: Metron still fills the empty fields.
        self.assertNotIn('Series', entries[0]['changes'])
        self.assertEqual(self.metadata()['Series'], 'Amazing Spider-Man (Sergei)')

    def test_nothing_older_is_replaced_once_another_program_saved_the_comic(self):
        # Same Series and Number, re-saved by a tagger that added a Title: the values may be Sergei's now.
        self.written_in_book()
        self.save('<ComicInfo><Series>Amazing Spider-Man</Series><Number>1</Number><Title>Sergei title</Title></ComicInfo>')
        import provenance
        self.assertEqual(provenance.in_book_values(self.row(), self.metadata()), {})
        self.metron.return_value = METRON
        entries = self.run_pass()
        self.assertNotIn('Series', entries[0]['changes'])
        self.assertEqual(self.metadata()['Series'], 'Amazing Spider-Man')

    def test_a_manual_write_makes_every_value_in_place_sergeis(self):
        self.written_in_book()
        app.write_metadata(self.row(), {'Title': 'Picked by Sergei'}, remove_verified_backups=True)  # The dashboard's writer.
        self.metron.return_value = METRON
        entries = self.run_pass()
        self.assertNotIn('Series', entries[0]['changes'])
        self.assertEqual(self.metadata()['Series'], 'Amazing Spider-Man')

    def test_values_other_tools_wrote_are_never_replaced(self):
        self.save('<ComicInfo><Series>Amazing Spider-Man</Series><Number>1</Number></ComicInfo>')  # Tagged elsewhere.
        self.metron.return_value = METRON
        entries = self.run_pass()
        self.assertEqual(set(entries[0]['changes']), {'Year', 'Publisher'})
        self.assertNotIn('source', entries[0])

    def test_a_later_automatic_write_keeps_the_in_book_provenance(self):
        self.written_in_book()
        app.write_metadata(self.row(), {'Year': '1963'}, writer='automatic', remove_verified_backups=True)
        import provenance
        self.assertEqual(provenance.in_book_values(self.row(), self.metadata()), {'Series': 'Amazing Spider-Man', 'Number': '1'})


class ConflictAndHoldTests(ReplacementHarness):
    """The v0.1.2 identity rules: a conflict or a hold blocks field writes, replacements included."""

    def with_comicvine_web(self):
        self.written_in_book()
        # An automatic write by the app adds a ComicVine link; the in-book values keep their provenance.
        app.write_metadata(self.row(), {'Web': WEB}, writer='automatic', remove_verified_backups=True)
        self.metron.return_value = METRON

    def answer(self, value):
        def api(resource, **params):
            if isinstance(value, Exception):
                raise value
            return value
        self.api.side_effect = api

    def test_positive_control_comicvine_agrees_and_the_value_is_replaced(self):
        self.with_comicvine_web()
        self.answer({'id': 123, 'name': 'Spidey', 'volume': {'name': 'Amazing Spider-man', 'id': 5}, 'issue_number': '1'})
        entries = self.plan()
        self.assertEqual(entries[0]['changes']['Series']['before'], 'Amazing Spider-Man')

    def test_a_conflict_blocks_the_replacement(self):
        self.with_comicvine_web()
        self.answer({'id': 123, 'name': 'Other', 'volume': {'name': 'Batman', 'id': 9}, 'issue_number': '7'})
        self.assertEqual(self.plan(), [])
        with app.db() as con:
            record = json.loads(con.execute('SELECT value FROM discovery_records WHERE path=?', (str(self.path),)).fetchone()[0])
        self.assertEqual(record['outcome'], 'identity_conflict')
        self.assertEqual(self.metadata()['Series'], 'Amazing Spider-Man')

    def test_a_hold_blocks_the_replacement(self):
        self.with_comicvine_web()
        self.answer(ProviderDeferred('ComicVine is cooling down.', 'comicvine', time.time() + 300))
        self.assertEqual(self.plan(), [])
        self.assertEqual(self.metadata()['Series'], 'Amazing Spider-Man')


class MidPassEditTests(ReplacementHarness):
    """F22 for replacements: the planned "before" is the in-book value."""

    def test_an_edit_between_scan_and_write_is_kept(self):
        self.written_in_book()
        self.metron.return_value = METRON
        entries = self.plan()
        self.assertEqual(entries[0]['changes']['Series']['before'], 'Amazing Spider-Man')
        self.save('<ComicInfo><Series>Spider-Man (Sergei)</Series><Number>1</Number></ComicInfo>')  # During the pass.
        worker.run_one()
        self.assertEqual(self.metadata()['Series'], 'Spider-Man (Sergei)')
        plan = self.plans[0]
        self.assertEqual([Path(s['path']).name for s in json.loads((plan.parent / 'skipped.json').read_text(encoding='utf-8'))], [NAME])
        self.assertEqual(self.history(), ['in-book:cover'])

    def test_the_comicinfo_guard_compares_against_the_in_book_value(self):
        # No scan signature and a digest of the edited archive: only the ComicInfo guard can tell.
        self.written_in_book()
        stale = self.metadata()
        self.save('<ComicInfo><Series>Spider-Man (Sergei)</Series><Number>1</Number></ComicInfo>')
        fields, changes, replaced = automatic.external_plan(stale, METRON['fields'], {'Series': stale['Series']}, True)
        target = self.root / 'batches' / str(time.time_ns()) / 'plan.json'
        target.parent.mkdir(parents=True)
        entry = {'path': str(self.path), 'action': 'write', 'sha256': batch.digest(self.path), 'method': 'test',
                 'changes': changes, 'fields': fields}
        target.write_text(json.dumps({'folder': str(self.folder), 'method': 'test', 'entries': [entry]}), encoding='utf-8')
        batch.apply(target, remove_verified_backups=True)
        self.assertEqual(self.metadata()['Series'], 'Spider-Man (Sergei)')
        skipped = json.loads((target.parent / 'skipped.json').read_text(encoding='utf-8'))
        self.assertIn('ComicInfo changed since planning', skipped[0]['reason'])
        self.assertIn('Series', skipped[0]['reason'])


class ProvenanceUnitTests(ReplacementHarness):
    def test_disagreement_is_about_meaning_not_spelling(self):
        import provenance
        self.assertTrue(provenance.disagrees('Series', 'Amazing Spider-Man', 'The Amazing Spider-Man'))
        self.assertFalse(provenance.disagrees('Series', 'Spawn', ' Spawn '))
        self.assertFalse(provenance.disagrees('Number', '1', '001'))
        self.assertTrue(provenance.disagrees('Number', '1', '2'))
        self.assertFalse(provenance.disagrees('Publisher', 'Image Comics', 'Image'))
        self.assertTrue(provenance.disagrees('Publisher', 'DC Comics', 'Marvel'))
        self.assertFalse(provenance.disagrees('Publisher', 'DC Comics', 'Vertigo'))  # An imprint of the same house (imprints.py).
        self.assertFalse(provenance.disagrees('Publisher', 'Image Comics', 'Skybound'))
        self.assertFalse(provenance.disagrees('Month', '05', '5'))
        self.assertFalse(provenance.disagrees('Writer', 'Todd McFarlane', 'Todd  McFarlane'))
        self.assertFalse(provenance.disagrees('Series', 'Spawn', ''))  # An empty source value never replaces.

    def test_backfill_records_v013_batch_writes(self):
        self.written_in_book()
        import provenance
        with app.db() as con:
            con.execute('DELETE FROM write_ledger')  # As v0.1.3 left it: history and batch folders, no ledger.
        self.assertEqual(provenance.in_book_values(self.row(), self.metadata()), {})  # Unknown write: nothing replaceable.
        counts = provenance.backfill()
        self.assertEqual(counts['recorded'], 1)
        self.assertEqual(provenance.in_book_values(self.row(), self.metadata()), {'Series': 'Amazing Spider-Man', 'Number': '1'})
        self.assertEqual(provenance.backfill()['recorded'], 0)  # Idempotent.
        with app.db() as con:
            self.assertEqual(json.loads(con.execute("SELECT value FROM ledger_meta WHERE key='write_ledger_backfill_v1'").fetchone()[0])['recorded'], 0)

    def test_discovery_runs_the_backfill_once(self):
        self.written_in_book()
        import provenance
        with app.db() as con:
            con.execute('DELETE FROM write_ledger')  # A v0.1.3 catalog: no ledger rows, no backfill marker.
            con.execute('DELETE FROM ledger_meta')
        provenance._backfilled.clear()
        self.metron.return_value = METRON
        entries = self.plan()
        self.assertEqual(entries[0]['changes']['Series']['before'], 'Amazing Spider-Man')

    def test_a_reference_batch_counts_as_manual(self):
        self.save()
        target = self.root / 'batches' / str(time.time_ns()) / 'plan.json'
        target.parent.mkdir(parents=True)
        entry = {'path': str(self.path), 'action': 'write', 'sha256': batch.digest(self.path), 'source': 'in-book:cover',
                 'changes': {'Series': {'before': '', 'after': 'Amazing Spider-Man'}}, 'fields': {'Series': 'Amazing Spider-Man'}}
        target.write_text(json.dumps({'folder': str(self.folder), 'reference': 'x.cbz', 'entries': [entry]}), encoding='utf-8')
        batch.apply(target, remove_verified_backups=True)
        import provenance
        self.assertEqual(provenance.chain(self.row())[0]['writer'], 'manual')
        self.assertEqual(provenance.in_book_values(self.row(), self.metadata()), {})


if __name__ == '__main__':
    unittest.main()
