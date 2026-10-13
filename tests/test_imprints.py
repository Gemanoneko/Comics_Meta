"""Sergei 2026-10-13: the brand line goes in Imprint, the main publisher in Publisher.

A small explicit table maps known imprints to parents; unknown names are left alone. An outside
source that names an imprint as the publisher (Metron: "Skybound") is split, so it agrees with an
in-book "Image Comics" instead of replacing it (Kroma 001 in the pilot). Empty fields only.
"""
import io
import json
import unittest
from unittest.mock import patch
import app
import imprints
import research
from test_failure_filters import handler
from test_in_book_replacement import METRON, ReplacementHarness


class SplitTests(unittest.TestCase):
    def test_known_imprints_split_unknown_names_stay(self):
        self.assertEqual(imprints.split({'Publisher': 'Skybound', 'Year': '2022'}),
                         {'Publisher': 'Image Comics', 'Imprint': 'Skybound', 'Year': '2022'})
        for imprint, parent in (('Vertigo', 'DC Comics'), ('DC Black Label', 'DC Comics'), ('WildStorm', 'DC Comics'),
                                ('Icon', 'Marvel'), ('Epic Comics', 'Marvel'), ('MAX', 'Marvel'), ('Top Cow', 'Image Comics'),
                                ('Archaia', 'BOOM! Studios')):
            self.assertEqual(imprints.split({'Publisher': imprint},year='2022'), {'Publisher': parent, 'Imprint': imprint}, imprint)
        for publisher in ('Image Comics', 'DC Comics', 'Mad Cave Studios', 'Vault Comics', 'Vertigo Press Ltd', ''):
            self.assertEqual(imprints.split({'Publisher': publisher}), {'Publisher': publisher}, publisher)
        self.assertEqual(imprints.split({'Series': 'Spawn'}), {'Series': 'Spawn'})
        # The source's own Imprint is kept: Metron already sends DC Comics + DC Black Label.
        self.assertEqual(imprints.split({'Publisher': 'DC Comics', 'Imprint': 'DC Black Label'}), {'Publisher': 'DC Comics', 'Imprint': 'DC Black Label'})
        self.assertEqual(imprints.split({'Publisher': 'Vertigo', 'Imprint': 'Vertigo Crime'})['Imprint'], 'Vertigo Crime')

    def test_same_house(self):
        self.assertEqual(imprints.publisher_key('Skybound'), imprints.publisher_key('Image Comics'))
        self.assertEqual(imprints.publisher_key('Image'), imprints.publisher_key('Image Comics'))
        self.assertNotEqual(imprints.publisher_key('Vertigo'), imprints.publisher_key('Image Comics'))


class KromaTests(ReplacementHarness):
    """Pilot 2026-10-13: both readings print Image Comics; Metron says Skybound."""

    def written_in_book_with_publisher(self):
        self.save()
        row = self.row()
        research.save_evidence(self.path, {'cover_identification': {'title': 'AMAZING SPIDER-MAN', 'issue': '1', 'publisher': 'Image Comics'},
                                           'cover_signature': [row['size'], row['mtime']],
                                           'credits_reading': {'indicia': 'AMAZING SPIDER-MAN #1. Published by Image Comics, Inc.', 'credits': ''},
                                           'credits_signature': [row['size'], row['mtime']]})
        entries = self.run_pass()
        self.assertEqual(entries[0]['fields']['Publisher'], 'Image Comics')  # The printed name (publisher agreement, on).

    def test_no_flip_flop_and_the_imprint_is_filled(self):
        self.written_in_book_with_publisher()
        self.metron.return_value = dict(METRON, fields={'Series': 'Amazing Spider-Man', 'Number': '1', 'Year': '2022', 'Publisher': 'Skybound'})
        entries = self.run_pass()
        # Before the split: a replacement of "Image Comics" with "Skybound" (item 3).
        self.assertNotIn('Publisher', entries[0]['changes'])
        self.assertEqual(entries[0]['changes']['Imprint'], {'before': '', 'after': 'Skybound'})
        self.assertNotIn('replaced', entries[0])
        metadata = self.metadata()
        self.assertEqual((metadata['Publisher'], metadata['Imprint']), ('Image Comics', 'Skybound'))
        # Later passes: another source says "Image", Metron again says "Skybound": nothing moves.
        for fields in ({'Publisher': 'Image', 'Year': '2022'}, {'Publisher': 'Skybound', 'Year': '2022'}):
            self.metron.return_value = dict(METRON, fields=dict(fields, Series='Amazing Spider-Man', Number='1'))
            calls = self.metron.call_count
            self.later_pass()
            self.assertGreater(self.metron.call_count, calls)  # The pass really asked Metron.
            metadata = self.metadata()
            self.assertEqual((metadata['Publisher'], metadata['Imprint']), ('Image Comics', 'Skybound'), fields)
        self.assertNotIn('replaced-in-book:Metron', self.history())

    def test_a_different_house_is_still_replaced(self):
        # Positive control: the split does not hide a real disagreement.
        self.written_in_book_with_publisher()
        self.metron.return_value = dict(METRON, fields={'Series': 'Amazing Spider-Man', 'Number': '1', 'Publisher': 'Vertigo'})
        entries = self.run_pass()
        self.assertEqual(entries[0]['changes']['Publisher'], {'before': 'Image Comics', 'after': 'DC Comics'})
        self.assertEqual(entries[0]['changes']['Imprint'], {'before': '', 'after': 'Vertigo'})

    def test_values_already_there_are_kept(self):
        self.save('<ComicInfo><Series>Amazing Spider-Man</Series><Number>1</Number><Publisher>Skybound</Publisher><Imprint>Skybound Entertainment</Imprint></ComicInfo>')
        self.metron.return_value = dict(METRON, fields={'Series': 'Amazing Spider-Man', 'Number': '1', 'Year': '2022', 'Publisher': 'Skybound'})
        entries = self.run_pass()
        self.assertEqual(set(entries[0]['changes']), {'Year'})  # Another program's Publisher and Imprint stay.
        self.assertEqual(self.metadata()['Publisher'], 'Skybound')

    def later_pass(self):
        with app.db() as con:
            con.execute("UPDATE discovery_records SET value=json_set(value,'$.retry_at',0,'$.source_schedule',json('{}'))")
        self.run_pass()


class DashboardApplyTests(ReplacementHarness):
    """The manual ComicVine apply writes, and its preview shows, the same split."""

    def comicvine(self, resource, **params):
        if resource == 'issue/4000-1':
            return {'id': 1, 'name': 'Sleep of the Just', 'issue_number': '1', 'volume': {'id': 5, 'name': 'The Sandman'},
                    'cover_date': '1989-01-01', 'site_detail_url': 'https://comicvine.gamespot.com/sandman-1/4000-1/'}
        if resource == 'volume/4050-5':
            return {'publisher': {'name': 'Vertigo'}}
        raise AssertionError(resource)

    def test_preview_and_apply(self):
        self.save()
        self.api.side_effect = self.comicvine
        import pause_control
        with patch.object(pause_control, 'requested', return_value=False):
            status, preview = handler('/api/preview', {'issue': 1})
            self.assertEqual((status, preview['Publisher'], preview['Imprint']), (200, 'DC Comics', 'Vertigo'))
            status, reply = handler('/api/apply', {'comic': self.row()['id'], 'issue': 1})
        self.assertEqual(status, 200, reply)
        metadata = self.metadata()
        self.assertEqual((metadata['Publisher'], metadata['Imprint']), ('DC Comics', 'Vertigo'))

    def test_manual_preview_and_apply_keep_human_house_without_wrong_imprint(self):
        self.save('<ComicInfo><Series>Amazing Spider-Man</Series><Number>1</Number><Publisher>Dark Horse Comics</Publisher></ComicInfo>')
        def api(resource,**params):
            return {'publisher':{'name':'Skybound'}} if resource.startswith('volume/') else {'id':1,'issue_number':'1','volume':{'id':5,'name':'Amazing Spider-Man'}}
        self.api.side_effect=api
        import pause_control
        with patch.object(pause_control,'requested',return_value=False):
            status,preview=handler('/api/preview',{'comic':self.row()['id'],'issue':1})
            self.assertEqual(status,200)
            self.assertNotIn('Publisher',preview);self.assertNotIn('Imprint',preview)
            status,reply=handler('/api/apply',{'comic':self.row()['id'],'issue':1})
        self.assertEqual(status,200,reply)
        self.assertEqual(self.metadata()['Publisher'],'Dark Horse Comics')
        self.assertFalse(self.metadata().get('Imprint'))

    def test_manual_preview_and_apply_use_retained_human_year(self):
        self.save('<ComicInfo><Series>Amazing Spider-Man</Series><Number>1</Number><Publisher>Image Comics</Publisher><Year>1998</Year></ComicInfo>')
        def api(resource,**params):
            return {'publisher':{'name':'WildStorm'}} if resource.startswith('volume/') else {'id':1,'issue_number':'1','cover_date':'2020-01-01','volume':{'id':5,'name':'Amazing Spider-Man'}}
        self.api.side_effect=api
        import pause_control
        with patch.object(pause_control,'requested',return_value=False):
            status,preview=handler('/api/preview',{'comic':self.row()['id'],'issue':1})
            self.assertEqual((status,preview['Imprint']),(200,'WildStorm'))
            self.assertNotIn('Publisher',preview);self.assertNotIn('Year',preview)
            status,reply=handler('/api/apply',{'comic':self.row()['id'],'issue':1})
        self.assertEqual(status,200,reply)
        self.assertEqual((self.metadata()['Publisher'],self.metadata()['Year'],self.metadata()['Imprint']),('Image Comics','1998','WildStorm'))


if __name__ == '__main__':
    unittest.main()
