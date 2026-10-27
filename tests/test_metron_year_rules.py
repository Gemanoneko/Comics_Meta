"""Enrichment B and C (Sergei 2026-10-26): Metron matching for comics with no printed year and for unnumbered books.

Mocked Metron answers and cover checks only; nothing leaves the machine."""
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import metron
import pipeline_config
import year_hints
from test_worker import scratch_directory


def issue(id, name, number, date, began=None, volume=None, kind=None, image=None):
    series = {'name': name, 'year_began': began if began is not None else int(date[:4])}
    if volume is not None:
        series['volume'] = volume
    if kind:
        series['series_type'] = {'name': kind}
    return {'id': id, 'series': series, 'number': number, 'cover_date': date,
            'image': image or 'https://static.metron.cloud/%d.jpg' % id}


class FakeMetron:
    """Answers issue searches by name, number and cover year as Metron's filters do."""
    def __init__(self, issues):
        self.issues, self.asked = {i['id']: i for i in issues}, []

    def __call__(self, endpoint, **params):
        if endpoint == 'issue/':
            self.asked.append(dict(params))
            found = [i for i in self.issues.values() if params['series_name'].lower() in i['series']['name'].lower()
                     and ('number' not in params or i['number'] == params['number'])
                     and ('cover_year' not in params or i['cover_date'].startswith(str(params['cover_year'])))]
            return {'count': len(found), 'next': None, 'results': found}
        return dict(self.issues[int(endpoint.split('/')[1])], desc='')


class YearHintTests(unittest.TestCase):
    def test_filename_years_parse_name_does_not_read(self):
        self.assertEqual(year_hints.filename_year('Catwoman 062 (2007-02) (DeadmanWade-DCP).cbz'), '2007')
        self.assertEqual(year_hints.filename_year('Catwoman 062 (2007-02-14).cbz'), '2007')
        self.assertEqual(year_hints.filename_year('Accident Man #001 (of 3) (1993-Dark Horse).cbz'), '1993')
        self.assertEqual(year_hints.filename_year('Shinjuku (2022, 2nd edition) (Digital-Empire).cbz'), '2022')
        self.assertEqual(year_hints.filename_year("By Bizarre Hands #03 [2004]  (Resin--DCP).cbz"), '2004')
        for name in ('Lady Death (1994-1996) 01.cbz', 'Lady Death - Swimsuit Special 2005.cbz', 'Spider-Man 2099 001.cbz',
                     'Example 001 (2007).cbz', 'Example (2007-02) (2008-03).cbz'):
            self.assertEqual(year_hints.filename_year(name), '', name)  # A run, a bare year, the plain form, or two years.

    def test_folder_start_year(self):
        self.assertEqual(year_hints.folder_year(r'Y:\Comix\Catwoman (2002)\Catwoman 003.cbz'), '2002')
        self.assertEqual(year_hints.folder_year(r'Y:\Comix\Lady Death (1994-1996)\Lady Death 01.cbz'), '1994')
        self.assertEqual(year_hints.folder_year(r'Y:\Comix\Lady Death (1994 - )\Lady Death 01.cbz'), '1994')
        self.assertEqual(year_hints.folder_year(r'Y:\Comix\2000 AD\2000 AD 0001.cbz'), '')  # Not in brackets.
        self.assertEqual(year_hints.folder_year(r'Y:\Comix\X (1990) (2005)\X 01.cbz'), '')  # Two years: no hint.


def only_off(switch):
    """The shipped matching defaults with one rule switched off."""
    return lambda name: False if name == switch else pipeline_config.MATCHING_DEFAULTS[name]


class MetronLookup(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(app, 'DATA', Path(self.enterContext(scratch_directory())) / 'data'))

    def lookup(self, fake, path, covers=lambda path, url: True, row_year=''):
        row = {'path': path, 'series': app.parse_name(path)[0], 'number': app.parse_name(path)[1], 'year': row_year or app.parse_name(path)[2]}
        with patch.object(metron, 'token', return_value='synthetic'), patch.object(metron, 'request', side_effect=fake), \
                patch.object(metron, 'verified_cover', side_effect=covers):
            return metron.lookup(row, {})


class MetronRuleTests(MetronLookup):
    def test_cover_date_in_the_filename_is_the_cover_year(self):
        fake = FakeMetron([issue(62, 'Catwoman', '62', '2007-02-01', began=2002), issue(162, 'Catwoman', '62', '2016-11-01', began=2011)])
        result = self.lookup(fake, r'Y:\Comix\Catwoman\Catwoman 062 (2007-02) (DeadmanWade-DCP).cbz')
        self.assertEqual(result['fields']['Web'], 'https://metron.cloud/issue/62/')  # Before: None, no year.
        self.assertEqual((result['match_rule'], fake.asked[0].get('cover_year')), ('filename_year', '2007'))

    def test_folder_year_is_the_series_start_year(self):
        old_run = issue(3, 'Catwoman', '3', '1994-01-01', began=1993, volume=2)
        new_run = issue(203, 'Catwoman', '3', '2002-03-01', began=2002, volume=3)
        fake = FakeMetron([old_run, new_run])
        result = self.lookup(fake, r'Y:\Comix\Catwoman (2002)\Catwoman V1 003 (DeadmanWade-DCP) (digital).cbz')
        self.assertIsNone(result)  # "V1" is a volume tail: Metron's volume must then be 1, which neither run states as 2002.
        result = self.lookup(fake, r'Y:\Comix\Catwoman (2002)\Catwoman 003.cbz')
        self.assertEqual(result['fields']['Web'], 'https://metron.cloud/issue/203/')  # Before: None, no year.
        self.assertEqual(result['match_rule'], 'folder_year')
        self.assertNotIn('cover_year', fake.asked[-1])  # Searched over every year, then narrowed by the start year.
        self.assertIsNone(self.lookup(FakeMetron([old_run]), r'Y:\Comix\Catwoman (2002)\Catwoman 003.cbz'))  # Only another run.

    def test_no_year_anywhere_is_not_searched_while_yearless_is_off(self):
        fake = FakeMetron([issue(5, 'Dragonseed', '1', '2003-01-01')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Dragonseed\Dragonseed 001.cbz'))
        self.assertEqual(fake.asked, [])
        with patch.object(pipeline_config, 'matching', side_effect=lambda name: True):
            self.assertEqual(self.lookup(fake, r'Y:\Comix\Dragonseed\Dragonseed 001.cbz')['match_rule'], 'yearless')

    def test_looser_rules_still_need_a_unique_match_and_an_agreeing_cover(self):
        two = FakeMetron([issue(203, 'Catwoman', '3', '2002-03-01', began=2002), issue(303, 'Catwoman', '3', '2002-09-01', began=2002, volume=4)])
        self.assertIsNone(self.lookup(two, r'Y:\Comix\Catwoman (2002)\Catwoman 003.cbz'))  # Two runs began in 2002.
        one = FakeMetron([issue(203, 'Catwoman', '3', '2002-03-01', began=2002)])
        self.assertIsNone(self.lookup(one, r'Y:\Comix\Catwoman (2002)\Catwoman 003.cbz', covers=lambda path, url: False))

    def test_switches_turn_each_rule_off(self):
        fake = FakeMetron([issue(62, 'Catwoman', '62', '2007-02-01')])
        with patch.object(pipeline_config, 'matching', side_effect=only_off('filename_year_formats')):
            self.assertIsNone(self.lookup(fake, r'Y:\Comix\Catwoman\Catwoman 062 (2007-02).cbz'))
        fake = FakeMetron([issue(203, 'Catwoman', '3', '2002-03-01', began=2002)])
        with patch.object(pipeline_config, 'matching', side_effect=only_off('folder_year')):
            self.assertIsNone(self.lookup(fake, r'Y:\Comix\Catwoman (2002)\Catwoman 003.cbz'))
        fake = FakeMetron([issue(11, 'Dimwood', '1', '2025-05-01', kind='Graphic Novel')])
        with patch.object(pipeline_config, 'matching', side_effect=only_off('unnumbered_as_one')):
            self.assertIsNone(self.lookup(fake, r'Y:\Comix\Oni\Dimwood (2025).cbz'))


class UnnumberedBookTests(MetronLookup):
    def test_an_unnumbered_graphic_novel_is_issue_one(self):
        fake = FakeMetron([issue(11, 'Dimwood', '1', '2025-05-01', kind='Graphic Novel'), issue(12, 'Dimwood', '2', '2025-09-01', kind='Graphic Novel')])
        result = self.lookup(fake, r'Y:\Comix\Oni\Dimwood (2025) (digital) (Son of Ultron-Empire).cbz')
        self.assertEqual((result['fields']['Number'], result['match_rule']), ('1', 'unnumbered'))  # Before: None.
        self.assertEqual(fake.asked[0]['cover_year'], '2025')

    def test_issue_one_of_an_ordinary_series_is_not_taken(self):
        for kind in ('Single Issue', 'Limited Series', None):
            fake = FakeMetron([issue(11, 'Dimwood', '1', '2025-05-01', kind=kind)])
            self.assertIsNone(self.lookup(fake, r'Y:\Comix\Oni\Dimwood (2025).cbz'), kind)

    def test_names_with_any_number_volume_or_part_are_not_unnumbered(self):
        fake = FakeMetron([issue(11, 'The Chronicles of Conan', '1', '2003-05-01', kind='Trade Paperback')])
        for name in ('The Chronicles of Conan v02 Rogues in the House TPB (2003).cbz', 'Druuna 02 Druuna (of 9) (1993).cbz',
                     'Vampirella_V3_002_(of_6)_(2016).cbz', 'Hellina Vol 2 - Scythe (2017).cbz', 'Saga Book Two (2003).cbz',
                     'Red Zone (of 4) (2023).cbz', 'Dimwood.cbz'):
            self.assertIsNone(self.lookup(fake, 'Y:\\Comix\\X\\' + name), name)
        self.assertEqual(fake.asked, [])  # None of them was searched.


if __name__ == '__main__':
    unittest.main()
