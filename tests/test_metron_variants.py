"""#5 Metron name variants and #6 variant covers. Mocked Metron responses and cover checks only."""
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import metron
from test_worker import scratch_directory


def issue(id, name, number, date, volume=None, image=None):
    series = {'name': name}
    if volume is not None:
        series['volume'] = volume
    return {'id': id, 'series': series, 'number': number, 'cover_date': date,
            'image': image or 'https://static.metron.cloud/%d.jpg' % id}


class FakeMetron:
    def __init__(self, lists, details):
        self.lists, self.details, self.searched = lists, details, []

    def __call__(self, endpoint, **params):
        if 'series_name' in params:
            self.searched.append(params['series_name'])
            results = self.lists.get(params['series_name'], [])
            return {'count': len(results), 'next': None, 'results': results}
        return self.details[int(endpoint.split('/')[1])]


class NameVariantTests(unittest.TestCase):
    def setUp(self):
        # Stage timing writes the catalog; keep it out of the checkout's data/.
        self.enterContext(patch.object(app, 'DATA', Path(self.enterContext(scratch_directory())) / 'data'))

    def lookup(self, fake, series, number, year, covers=lambda path, url: True):
        row = {'path': 'x.cbz', 'series': series, 'number': number, 'year': year}
        with patch.object(metron, 'token', return_value='synthetic'), patch.object(metron, 'request', side_effect=fake), \
                patch.object(metron, 'verified_cover', side_effect=covers):
            return metron.lookup(row, {})

    def test_dash_and_colon_spellings_are_both_searched(self):
        found = issue(7, 'Batman: Year One', '1', '1987-02-01')
        fake = FakeMetron({'Batman: Year One': [found]}, {7: dict(found, desc='Bruce returns to Gotham.')})
        result = self.lookup(fake, 'Batman - Year One', '1', '1987')
        self.assertEqual(result['fields']['Series'], 'Batman: Year One')  # Before: no match under " - ".
        self.assertEqual(fake.searched, ['Batman - Year One', 'Batman: Year One'])
        self.assertEqual([n for n, _, _ in metron.name_variants('Batman: Year One')], ['Batman: Year One', 'Batman - Year One'])

    def test_trailing_volume_is_searched_without_it_and_must_match_the_volume(self):
        right = issue(36, 'Amazing Spider-Man', '36', '2002-01-01', volume=2)
        wrong = issue(99, 'Amazing Spider-Man', '36', '2002-01-01', volume=5)
        fake = FakeMetron({'Amazing Spider-Man': [right, wrong]}, {36: right})
        self.assertEqual(self.lookup(fake, 'Amazing Spider-Man v2', '36', '2002')['fields']['Web'], 'https://metron.cloud/issue/36/')
        self.assertEqual(fake.searched, ['Amazing Spider-Man v2', 'Amazing Spider-Man'])
        for name in ('Amazing Spider-Man Vol. 2', 'Amazing Spider-Man Volume 2', 'Amazing Spider-Man (Vol 2)'):
            self.assertEqual(metron.name_variants(name)[-1][1:], ('amazingspiderman', 2), name)
        # A candidate from another volume never matches.
        fake = FakeMetron({'Amazing Spider-Man': [wrong]}, {99: wrong})
        self.assertIsNone(self.lookup(fake, 'Amazing Spider-Man v2', '36', '2002'))

    def test_a_name_that_exists_is_not_searched_again(self):
        other = issue(1, 'Batman - Year One', '2', '1987-03-01')
        fake = FakeMetron({'Batman - Year One': [other]}, {})
        self.assertIsNone(self.lookup(fake, 'Batman - Year One', '1', '1987'))
        self.assertEqual(fake.searched, ['Batman - Year One'])


class VariantCoverTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(app, 'DATA', Path(self.enterContext(scratch_directory())) / 'data'))
        self.candidate = issue(42, 'Example', '1', '2024-01-01', image='https://static.metron.cloud/primary.jpg')
        self.detail = dict(self.candidate, upc='761941341828', desc='A teaser.',
                           variants=[{'name': 'Cover B', 'image': 'https://static.metron.cloud/b.jpg'},
                                     {'name': 'Cover C', 'image': 'https://static.metron.cloud/c.jpg'}])

    def lookup(self, agreeing):
        checked = []
        def covers(path, url):
            checked.append(url.rsplit('/', 1)[1])
            return url.rsplit('/', 1)[1] in agreeing
        fake = FakeMetron({'Example': [self.candidate]}, {42: self.detail})
        row = {'path': 'x.cbz', 'series': 'Example', 'number': '1', 'year': '2024'}
        with patch.object(metron, 'token', return_value='synthetic'), patch.object(metron, 'request', side_effect=fake), \
                patch.object(metron, 'verified_cover', side_effect=covers):
            return metron.lookup(row, {}), checked

    def test_variant_cover_match_is_accepted_without_the_primary_barcode(self):
        result, checked = self.lookup({'c.jpg'})
        self.assertIsNotNone(result)  # Before: rejected after the primary cover differed.
        self.assertEqual(checked, ['primary.jpg', 'b.jpg', 'c.jpg'])
        self.assertNotIn('GTIN', result['fields'])
        self.assertIn('variant cover (Cover C)', result['sources'][0]['scope'])

    def test_no_agreeing_cover_is_still_rejected(self):
        result, checked = self.lookup(set())
        self.assertIsNone(result)
        self.assertEqual(checked, ['primary.jpg', 'b.jpg', 'c.jpg'])

    def test_primary_match_keeps_its_barcode_and_checks_no_variants(self):
        result, checked = self.lookup({'primary.jpg'})
        self.assertEqual(result['fields']['GTIN'], '761941341828')
        self.assertEqual(checked, ['primary.jpg'])


if __name__ == '__main__':
    unittest.main()
