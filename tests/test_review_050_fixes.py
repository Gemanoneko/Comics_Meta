"""v0.5.0 review fixes (Senua 2026-10-27): F1 no page reaches Ghostscript, F2 Lens in the unsearchable fingerprint,
F3 an unreadable page 2 or 3 is no match, F4 the accepting cover check is recorded. Synthetic files only; Pillow's
Ghostscript call and subprocess.Popen are replaced, so nothing is launched even on the old code."""
import io
import json
import re
import struct
import unittest
import zipfile
import zlib
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import app
import automatic
import cover_match
import metron
from test_cover_match import art, jpeg
from test_worker import scratch_directory

CODE = Path(__file__).resolve().parents[1]
# PostScript a page can hold under a .jpg name. Its bounding box has a cover's shape, so today's shape check passes
# and decoding (Ghostscript) is reached: the case review F1 probed.
EPS = b'%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 400 615\nnewpath 0 0 moveto 400 615 lineto stroke\nshowpage\n%%EOF\n'


def huge_png():
    """A PNG whose header claims 20,000 x 20,000 pixels: Pillow refuses it at open as a decompression bomb."""
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 20000, 20000, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\0' * 64)) + chunk(b'IEND', b''))


@contextmanager
def no_ghostscript(test):
    with patch('PIL.EpsImagePlugin.Ghostscript', side_effect=OSError('Ghostscript blocked by the test')) as ghostscript, \
            patch('subprocess.Popen', side_effect=OSError('subprocess blocked by the test')) as popen:
        yield
    test.assertEqual((ghostscript.call_count, popen.call_count), (0, 0), 'a page reached Ghostscript or started a process')


class Archive(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.enterContext(patch.object(app, 'STATE_ROOT', self.root))

    def comic(self, pages, name='Example 001 (2024).cbz', corrupt=None):
        path = self.root / name
        with zipfile.ZipFile(path, 'w') as archive:
            for index, page in enumerate(pages):
                archive.writestr('%03d.jpg' % index, page if isinstance(page, bytes) else jpeg(page))
        if corrupt is not None:  # Flip one byte inside a stored member, so reading it fails its CRC check.
            raw = bytearray(path.read_bytes())
            start = raw.find(pages[corrupt] if isinstance(pages[corrupt], bytes) else jpeg(pages[corrupt]))
            raw[start + 200] ^= 0xFF
            path.write_bytes(bytes(raw))
        return path

    def download(self, covers):
        """metron's opener answers each Metron image URL with the given bytes."""
        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *exc): return False
        class Opener:
            def open(self, url, timeout=None): return Response(covers[url])
        return patch.object(metron.urllib.request, 'build_opener', return_value=Opener())

    def verified(self, path, remote):
        with self.download({'https://static.metron.cloud/x.jpg': remote}):
            return metron.verified_cover(str(path), 'https://static.metron.cloud/x.jpg')


class GhostscriptTests(Archive):
    """F1: a page holding PostScript fails closed and never starts Ghostscript."""
    def test_postscript_as_page_one_fails_closed(self):
        path = self.comic([EPS, art(1)])
        with no_ghostscript(self):
            with self.assertRaises(OSError):  # As any unreadable first image: the lookup fails, nothing is written.
                self.verified(path, jpeg(art(1)))

    def test_postscript_as_page_two_is_no_match(self):
        path = self.comic([art(1), EPS, art(2)])
        with no_ghostscript(self):
            self.assertIs(self.verified(path, jpeg(art(3))), False)  # Before: Ghostscript ran, then the lookup raised.

    def test_every_decoding_site_refuses_postscript(self):
        import browser_search, local_model, reverse_image
        cover = jpeg(art(4))
        calls = [lambda: automatic.covers_agree(EPS, cover), lambda: automatic.covers_agree(cover, EPS),
                 lambda: cover_match.compare(EPS, cover)]
        pages = self.comic([EPS, EPS, EPS, EPS], name='Pages 001 (2024).cbz')
        calls += [lambda: local_model.opening_images(pages), lambda: local_model.credits_pages(pages)]
        with patch.object(reverse_image, 'cover', return_value=(EPS, 'image/jpeg', '.jpg')):
            calls += [lambda: local_model.identify_cover(pages, ask=lambda *a: {}), lambda: browser_search.cover_bytes(pages)]
            for call in calls:
                with no_ghostscript(self), self.assertRaises(OSError):
                    call()

    def test_every_pillow_open_names_its_formats(self):
        """Every Image.open in the app passes formats=: a new one without it fails here (review F1)."""
        missing = []
        for source in sorted(CODE.glob('*.py')):
            for number, line in enumerate(source.read_text(encoding='utf-8').splitlines(), 1):
                if re.search(r'\bImage\.open\(', line) and line.count('Image.open(') != line.count('formats='):
                    missing.append('%s:%d' % (source.name, number))
        self.assertEqual(missing, [])
        self.assertIn("formats=('JPEG','PNG','WEBP','GIF')", (CODE / 'archive_conversion.py').read_text(encoding='utf-8'))


class LensFingerprintTests(Archive):
    """F2: switching Lens on or off makes comics marked unsearchable due again."""
    def config(self, lens):
        (self.root / 'config.json').write_text(json.dumps({'browser_search': {'enabled': True, 'lens': lens}}), encoding='utf-8')

    def due(self, mark):
        import source_scheduling
        previous = {'version': automatic.MATCHER_VERSION, 'signature': [10, 1], 'retry_at': 0, 'outcome': 'needs_identity_lookup',
                    'unsearchable': mark}
        return source_scheduling.due(previous, [10, 1], automatic.MATCHER_VERSION, {}, now=1000)

    def test_lens_switched_on_wakes_comics_marked_while_it_was_off(self):
        import source_scheduling
        self.config(False)
        mark = source_scheduling.search_fingerprint()
        self.assertFalse(self.due(mark))
        self.config(True)
        self.assertTrue(self.due(mark))  # Before: the same fingerprint, so never due again.

    def test_lens_switched_off_wakes_comics_marked_while_it_was_on(self):
        import source_scheduling
        self.config(True)
        mark = source_scheduling.search_fingerprint()
        self.assertFalse(self.due(mark))
        self.config(False)
        self.assertTrue(self.due(mark))


class UnreadablePageTests(Archive):
    """F3: a page 2 or 3 that will not read or decode is no match for that page; the lookup goes on."""
    def test_each_kind_of_bad_later_page_is_no_match(self):
        truncated = jpeg(art(5))[:1500]
        for name, pages, corrupt in (('truncated', [art(1), truncated, art(2)], None),
                                     ('not an image', [art(1), b'this is not an image at all', art(2)], None),
                                     ('bad CRC', [art(1), art(6), art(2)], 1),
                                     ('too large', [art(1), huge_png(), art(2)], None)):
            path = self.comic(pages, name=name + ' 001 (2024).cbz', corrupt=corrupt)
            self.assertIs(self.verified(path, jpeg(art(3))), False, name)  # Before: raised, filed as an error.

    def test_variant_covers_are_still_tried(self):
        variant = art(7)
        path = self.comic([variant, jpeg(art(5))[:1500], art(8)])  # Page 1 is the variant; page 2 is truncated.
        primary_url, variant_url = 'https://static.metron.cloud/p.jpg', 'https://static.metron.cloud/v.jpg'
        listing = {'id': 9, 'series': {'name': 'Example', 'year_began': 2024}, 'number': '1', 'cover_date': '2024-01-01', 'image': primary_url}
        detail = dict(listing, variants=[{'name': 'Cover B', 'image': variant_url}], desc='')
        def request(endpoint, **params):
            return {'count': 1, 'next': None, 'results': [listing]} if endpoint == 'issue/' else detail
        row = {'path': str(path), 'series': 'Example', 'number': '1', 'year': '2024'}
        with patch.object(metron, 'token', return_value='synthetic'), patch.object(metron, 'request', side_effect=request), \
                self.download({primary_url: jpeg(art(9)), variant_url: jpeg(variant)}):
            result = metron.lookup(row, {})
        self.assertEqual(result['cover_match'], {'comparison': 'today', 'page': 1, 'image': 'variant: Cover B'})  # Before: raised.


class CoverRecordTests(Archive):
    """F4: which check accepted the cover, and on which page, is kept with the write."""
    def test_verified_cover_names_the_check_and_page(self):
        cover = art(10)
        self.assertEqual(self.verified(self.comic([cover]), jpeg(cover)), {'comparison': 'today', 'page': 1})
        credits = Image.new('RGB', cover.size, (255, 255, 255))
        self.assertEqual(self.verified(self.comic([credits, cover], name='Second 001 (2024).cbz'), jpeg(cover)),
                         {'comparison': 'today', 'page': 2})
        wrap = Image.new('RGB', (cover.width * 2, cover.height))
        wrap.paste(art(11), (0, 0)); wrap.paste(cover, (cover.width, 0))
        self.assertEqual(self.verified(self.comic([wrap], name='Wrap 001 (2024).cbz'), jpeg(cover)),
                         {'comparison': 'wraparound', 'page': 1})
        import pipeline_config  # Switched off: today's comparison on page 1, still recorded.
        with patch.object(pipeline_config, 'matching', side_effect=lambda name: name != 'cover_rule_v2' and pipeline_config.MATCHING_DEFAULTS[name]):
            self.assertEqual(self.verified(self.comic([cover], name='Off 001 (2024).cbz'), jpeg(cover)), {'comparison': 'today', 'page': 1})

    def test_the_pass_plan_entry_carries_the_cover_record(self):
        import archive_conversion, cover_tasks, local_model, research, research_runtime, worker
        from contextlib import ExitStack
        self.enterContext(patch.object(research, 'CACHE', self.root / 'evidence'))  # Read back after the pass, below.
        folder = self.root / 'Example'
        folder.mkdir()
        path = folder / 'Example 001 (2024).cbz'
        path.write_bytes(b'isolated fixture')
        stat = path.stat()
        with app.db() as con:
            con.execute('INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,seen) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (str(path), str(folder), stat.st_size, stat.st_mtime_ns, 'Example', '1', '2024', '{}', 'missing', 1))
        found = {'provider': 'Metron', 'metadata_version': 2, 'match_rule': 'year', 'cover_match': {'comparison': 'aligned', 'page': 2, 'image': 'primary'},
                 'fields': {'Writer': 'Verified writer'}, 'sources': [{'url': 'https://metron.cloud/issue/9/', 'text': ''}], 'status': 'issue_verified'}
        patches = [patch.object(app, 'scan'), patch.object(archive_conversion, 'one', return_value=False),
                   patch.object(worker.pause_control, 'requested', return_value=False), patch.object(automatic.batch, 'progress'),
                   patch.object(research_runtime, 'reuse', return_value=None), patch.object(metron, 'token', return_value='synthetic'),
                   patch.object(metron, 'lookup', return_value=found), patch.object(local_model, 'available', return_value=False),
                   patch.object(worker, 'QUEUE', self.root / 'queue'),
                   patch.object(cover_tasks, 'identified'), patch.object(app, 'api', side_effect=AssertionError('no ComicVine call'))]
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            enqueue = stack.enter_context(patch.object(worker, 'enqueue'))
            automatic.discover(folder)
        plan = json.loads(Path(enqueue.call_args.args[0]).read_text(encoding='utf-8'))
        entry = plan['entries'][0]
        self.assertEqual((entry['match_rule'], entry['cover_match']), ('year', found['cover_match']))  # Before: no cover record.
        self.assertEqual(research.read_evidence(path.resolve())['cover_match'], found['cover_match'])  # And in the evidence.


if __name__ == '__main__':
    unittest.main()
