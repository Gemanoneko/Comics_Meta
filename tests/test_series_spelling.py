"""Sergei 2026-10-13: the in-book Series keeps the FILENAME text, with obvious spelling and
formatting slips fixed. "Don_t Look Back" becomes "Don't Look Back".

Deterministic, no guessing: an underscore inside a word standing for an apostrophe becomes
one, other underscores become spaces, repeated spaces collapse, stray separators and dots at
the ends go. Accents come from the cover only when the cover title is the same text once
accents are ignored. The wording is never shortened to the cover title.
"""
import json
import unittest
from unittest.mock import patch
import in_book
import pipeline_config


def judge(name, title, issue=None, old=None):
    """issue=None: the cover shows the filename's own number (the cover-confirmed rule)."""
    row = {'path': 'Library/Series/' + name, 'size': 10, 'mtime': 1, 'metadata': json.dumps(old or {})}
    hint = {'title': title, 'issue': (in_book.filename_identity(row['path']) or ('', ''))[1] if issue is None else issue}
    return in_book.identify(row, old or {}, {'cover_identification': hint, 'cover_signature': [10, 1]})


class SeriesSpellingTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(pipeline_config, 'in_book_cover', return_value=True))

    def series(self, name, title, issue=None):
        book = judge(name, title, issue)
        self.assertIsNotNone(book, name)
        return book['fields']['Series'], book['evidence']['fields']['Series']

    def test_dont_look_back(self):
        # Sergei's example. Before (1c34df2): Series "Don_t Look Back".
        value, evidence = self.series("Don_t Look Back 001 (2020).cbz", "DON'T LOOK BACK")
        self.assertEqual(value, "Don't Look Back")
        self.assertEqual(evidence['normalised'], {'filename_text': 'Don_t Look Back', 'changes': ['underscore for an apostrophe']})
        for name, expected in (("Won_t Back Down 002.cbz", "Won't Back Down"), ("X_s Mark the Spot 003.cbz", "X's Mark the Spot"),
                               ("Superman_s Pal Jimmy Olsen 004.cbz", "Superman's Pal Jimmy Olsen"), ("THEY_LL COME 005.cbz", "THEY'LL COME")):
            self.assertEqual(self.series(name, expected.upper())[0], expected, name)

    def test_multiple_underscores(self):
        value, evidence = self.series('Batman_Superman__World_s_Finest 001 (2022).cbz', "WORLD'S FINEST")
        self.assertEqual(value, "Batman Superman World's Finest")  # The filename's wording, not the cover's shorter title.
        self.assertEqual(evidence['normalised']['changes'], ['underscore for an apostrophe', 'underscores as spaces', 'repeated spaces'])
        self.assertEqual(self.series('Spider_Man_2099 001.cbz', 'SPIDER-MAN 2099')[0], 'Spider Man 2099')
        self.assertEqual(self.series('Ghost_Rider 001.cbz', 'GHOST RIDER')[0], 'Ghost Rider')  # "_R" is no contraction.

    def test_accents_restored_from_an_exact_cover_title(self):
        value, evidence = self.series('Asterix 001.cbz', 'ASTÉRIX')
        self.assertEqual(value, 'Astérix')
        self.assertEqual(evidence['normalised']['changes'], ['accents from the cover'])
        self.assertEqual(self.series('Pokemon Adventures 001.cbz', 'Pokémon Adventures')[0], 'Pokémon Adventures')
        self.assertEqual(self.series('La Esquina de Eric 002.cbz', 'LA ESQUINA DE ÉRIC #2')[0], 'La Esquina de Éric')

    def test_accent_mismatch_is_left_as_is(self):
        # The cover is shorter, longer or punctuated differently: not the same text, nothing borrowed.
        for name, title, expected in (('Asterix and the Goths 001.cbz', 'ASTÉRIX', 'Asterix and the Goths'),
                                      ('Asterix 001.cbz', 'ASTÉRIX!', 'Asterix'),
                                      ('Pokemon Adventures 001.cbz', 'Pokémon', 'Pokemon Adventures'),
                                      ('Asterix 001.cbz', 'ASTERIX', 'Asterix')):
            value, evidence = self.series(name, title)
            self.assertEqual(value, expected, name)
            self.assertNotIn('normalised', evidence, name)

    def test_bracketed_title_words_from_the_filename_are_kept(self):
        # Live snapshot: "Midlife (or How to Hero at Fifty) 001"; the cover reads "MIDLIFE". Before: Series "Midlife".
        value, evidence = self.series('Midlife (or How to Hero at Fifty) 001 (2023) (Digital) (Zone-Empire).cbz', 'MIDLIFE')
        self.assertEqual(value, 'Midlife (or How to Hero at Fifty)')
        self.assertEqual(evidence['normalised'], {'filename_text': 'Midlife', 'changes': ['bracketed title words kept']})
        book = judge('Midlife (or How to Hero at Fifty) (2023) (Digital).cbz', 'MIDLIFE', issue='')  # A whole book.
        self.assertEqual(book['fields']['Series'], 'Midlife (or How to Hero at Fifty)')
        # Years, release and scan tags, publishers and numbering are not title words.
        for name, title, expected in (('Batman (2016) 005 (Digital).cbz', 'BATMAN', 'Batman'),
                                      ('Hellboy (Dark Horse Comics) 001.cbz', 'HELLBOY', 'Hellboy'),
                                      ('Spawn 001 (1992) (Digital) (Zone-Empire).cbz', 'SPAWN', 'Spawn'),
                                      ('Judge Dredd - The Complete Case Files 003 (Maximum Colour Edition).cbz', 'JUDGE DREDD',
                                       'Judge Dredd - The Complete Case Files'),
                                      ('Foo Bar (Son of Ultron-Empire) (2019).cbz', 'FOO BAR', 'Foo Bar')):
            book = judge(name, title, '' if 'Foo' in name else None)
            self.assertEqual(book['fields']['Series'], expected, name)
            self.assertNotIn('normalised', book['evidence']['fields']['Series'], name)

    def test_ends_trimmed_but_initialisms_kept(self):
        self.assertEqual(self.series('Batman. 001.cbz', 'BATMAN')[0], 'Batman')
        self.assertEqual(self.series('Agents of S.H.I.E.L.D. 001.cbz', 'AGENTS OF S.H.I.E.L.D.')[0], 'Agents of S.H.I.E.L.D.')
        self.assertEqual(self.series('Spider-Man Jr. 001.cbz', 'SPIDER-MAN JR.')[0], 'Spider-Man Jr.')

    def test_control_nothing_to_change(self):
        for name, title, expected in (('Spawn 001 (1992).cbz', 'SPAWN', 'Spawn'),
                                      ("Don't Look Back 001.cbz", "DON'T LOOK BACK", "Don't Look Back"),
                                      ('Uncanny X-Men 141 (1981).cbz', 'X-MEN', 'Uncanny X-Men'),
                                      ('Batman - The Long Halloween (1998).cbz', 'Batman: The Long Halloween', 'Batman - The Long Halloween')):
            book = judge(name, title)
            self.assertEqual(book['fields']['Series'], expected, name)
            self.assertNotIn('normalised', book['evidence']['fields']['Series'], name)
            self.assertNotIn('spelling tidied', in_book.notes(book), name)

    def test_provenance_in_notes_and_evidence(self):
        book = judge("Don_t Look Back 001 (2020).cbz", "DON'T LOOK BACK")
        self.assertEqual(book['evidence']['filename']['series'], 'Don_t Look Back')  # The raw filename text is kept.
        self.assertIn("filename's text with its spelling tidied (underscore for an apostrophe)", in_book.notes(book))
        entry = in_book.entry('Library/Series/Don_t Look Back 001 (2020).cbz', book, 'digest')
        self.assertEqual(entry['changes']['Series'], {'before': '', 'after': "Don't Look Back"})

    def test_credits_tier_uses_the_same_spelling(self):
        reading = {'indicia': "DON'T LOOK BACK #1, May 2020. Published by Image Comics.", 'credits': ''}
        row = {'path': 'Library/Don_t Look Back 001 (2020).cbz', 'size': 1, 'mtime': 1}
        book = in_book.judge_credits(row, {}, reading, [1, 1], creators=False)
        self.assertEqual(book['fields']['Series'], "Don't Look Back")
        self.assertIn('spelling tidied', in_book.notes(book))
        # Embedded Series written the old way still agrees, so nothing conflicts.
        self.assertEqual(in_book.judge_credits(row, {'Series': 'Don_t Look Back'}, reading, [1, 1], creators=False)['fields'],
                         {'Number': '1'})


if __name__ == '__main__':
    unittest.main()
