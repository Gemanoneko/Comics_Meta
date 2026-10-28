"""0.6.0 regressions; fixture archives and mocked providers only."""
import io
import json
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import app
import automatic
from test_worker import scratch_directory


class ManualPickTests(unittest.TestCase):
    def test_critter_manual_issue_pick_survives_the_next_identity_check(self):
        root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'DATA', root / 'data'))
        comic = root / 'Critter 008 (2025).cbz'
        wrong = 'https://comicvine.gamespot.com/critter-7/4000-1117156/'
        right = 'https://comicvine.gamespot.com/critter-8/4000-1119999/'
        with zipfile.ZipFile(comic, 'w') as archive:
            archive.writestr('001.jpg', b'unchanged page')
            archive.writestr('ComicInfo.xml', '<ComicInfo><Series>Critter</Series><Number>8</Number><Year>2025</Year><Title>Personal title</Title><Web>' + wrong + '</Web></ComicInfo>')
        app.scan([str(root)], recursive=False)
        with app.db() as con:
            row = dict(con.execute('SELECT * FROM comics WHERE path=?', (str(comic),)).fetchone())
        issue = {'id':1119999, 'issue_number':'8', 'volume':{'name':'Critter'}, 'site_detail_url':right}
        handler = object.__new__(app.Handler)
        handler.path = '/api/apply'
        handler.server = SimpleNamespace(server_port=8765)
        body = json.dumps({'comic':row['id'], 'issue':1119999}).encode()
        handler.headers = {'Host':'127.0.0.1:8765','Origin':'http://127.0.0.1:8765','Content-Length':str(len(body))}
        handler.rfile = io.BytesIO(body)
        app.JOB['running'] = False
        with patch('pause_control.requested', return_value=False), patch.object(app, 'api', return_value=issue), patch.object(handler, 'respond') as response:
            handler.do_POST()
        self.assertTrue(response.call_args.args[0].get('verified'), response.call_args)
        saved = app.read_metadata(comic)[0]
        self.assertEqual(saved['Web'], right)
        self.assertEqual(saved['Title'], 'Personal title')
        self.assertTrue(automatic.identity_matches(saved, issue))


class LanguageTests(unittest.TestCase):
    def test_bracketed_codes_and_names_across_languages(self):
        for language in ('rus','ukr','fra','deu','spa','ita','por','pol','nld','ces','hun','tur','ell','swe','dan','nor','fin','jpn','zho','kor','ara','heb','ron','bul','srp','hrv','hin','tha','vie','ind','fas','cat'):
            for opening, closing in (('[',']'),('(',')')):
                with self.subTest(language=language, bracket=opening):
                    self.assertFalse(automatic.language_eligible({'path':'Comic '+opening+language+closing+'.cbz'},{}))
        for name in ('Comic [eng].cbz','Comic (en).cbz','Comic [scan].cbz','Comic.cbz'):
            self.assertTrue(automatic.language_eligible({'path':name},{}))


class RasterTests(unittest.TestCase):
    def test_gif_and_bmp_cover_preview_and_comparison(self):
        from PIL import Image
        import reverse_image
        from test_cover_match import art
        root=Path(self.enterContext(scratch_directory()))
        for format in ('GIF','BMP'):
            data=io.BytesIO();art(7).save(data,format=format)
            path=root/('Comic.'+format+'.cbz')
            with zipfile.ZipFile(path,'w') as archive:archive.writestr('001.'+format.lower(),data.getvalue())
            with self.subTest(format=format):
                self.assertEqual(reverse_image.cover(path)[0],data.getvalue())
                self.assertTrue(automatic.covers_agree(data.getvalue(),data.getvalue()))
                self.assertTrue(reverse_image.preview(path).startswith(b'\xff\xd8'))

    def test_engine_startup_disables_eps_even_without_a_callsite_allowlist(self):
        from PIL import Image
        from test_review_050_fixes import EPS, no_ghostscript
        with no_ghostscript(self), self.assertRaises(OSError):
            Image.open(io.BytesIO(EPS)).load()


class ConversionCleanupTests(unittest.TestCase):
    def test_readonly_extracted_page_is_removed_after_verified_conversion(self):
        import archive_conversion
        import stat
        root=Path(self.enterContext(scratch_directory()))
        stage=root/('.comic-metadata-convert-'+'a'*32)
        stage.mkdir();page=stage/'001.jpg';page.write_bytes(b'page');page.chmod(stat.S_IREAD)
        self.addCleanup(lambda: page.chmod(stat.S_IWRITE) if page.exists() else None)
        archive_conversion.cleanup_stage(stage,root/'Comic.cbr')
        self.assertFalse(stage.exists())
