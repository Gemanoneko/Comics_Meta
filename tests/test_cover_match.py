"""Enrichment D (Sergei 2026-10-26): the revised Metron cover comparison. Synthetic covers only; no network."""
import io
import random
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw
import app
import automatic
import cover_match
import metron
import pipeline_config
from test_worker import scratch_directory


def art(seed, size=(400, 615), band=None):
    """A detailed synthetic cover; band paints the same logo strip across the top (shared trade dress)."""
    rnd = random.Random(seed)
    image = Image.new('RGB', size, tuple(rnd.randrange(256) for _ in range(3)))
    draw = ImageDraw.Draw(image)
    for _ in range(60):
        x, y = rnd.randrange(size[0]), rnd.randrange(size[1])
        w, h = rnd.randrange(20, 160), rnd.randrange(20, 160)
        shape = draw.ellipse if rnd.random() < .5 else draw.rectangle
        shape((x, y, x + w, y + h), fill=tuple(rnd.randrange(256) for _ in range(3)))
    if band is not None:
        logo = art(band, (size[0], size[1] // 5))
        image.paste(logo, (0, 0))
    return image


def jpeg(image):
    out = io.BytesIO()
    image.save(out, 'JPEG', quality=92)
    return out.getvalue()


def bleed(image, fraction):
    """The same cover with extra bleed on the left and right, as a scan often has."""
    extra = round(image.width * fraction)
    canvas = Image.new('RGB', (image.width + 2 * extra, image.height), (250, 250, 245))
    canvas.paste(image, (extra, 0))
    return canvas


class ComparisonTests(unittest.TestCase):
    def test_extra_bleed_passes_after_alignment(self):
        cover = art(1)
        local, remote = jpeg(bleed(cover, .03)), jpeg(cover)
        self.assertFalse(automatic.covers_agree(local, remote))  # Today's rule rejects the framing difference.
        self.assertTrue(cover_match.agree(local, remote))

    def test_a_wraparound_matches_its_front_cover(self):
        front, back = art(2), art(3)
        wrap = Image.new('RGB', (front.width * 2, front.height))
        wrap.paste(back, (0, 0))
        wrap.paste(front, (front.width, 0))
        self.assertFalse(automatic.covers_agree(jpeg(wrap), jpeg(front)))  # Before: rejected on shape.
        self.assertTrue(cover_match.agree(jpeg(wrap), jpeg(front)))
        self.assertFalse(cover_match.agree(jpeg(wrap), jpeg(art(4))))  # Another front cover is still rejected.

    def test_another_issue_behind_the_same_logo_band_is_rejected(self):
        one, other = art(10, band=99), art(11, band=99)
        self.assertFalse(cover_match.agree(jpeg(one), jpeg(other)))
        self.assertFalse(cover_match.agree(jpeg(bleed(one, .03)), jpeg(other)))

    def test_todays_passes_still_pass(self):
        cover = art(5)
        self.assertTrue(automatic.covers_agree(jpeg(cover), jpeg(cover)))
        self.assertTrue(cover_match.agree(jpeg(cover), jpeg(cover)))


class VerifiedCoverTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))

    def comic(self, pages):
        path = self.root / 'Example 001 (2024).cbz'
        with zipfile.ZipFile(path, 'w') as archive:
            for index, page in enumerate(pages):
                archive.writestr('%03d.jpg' % index, jpeg(page))
        return path

    def verified(self, path, remote):
        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *exc): return False
        class Opener:
            def open(self, url, timeout=None): return Response(remote)
        with patch.object(metron.urllib.request, 'build_opener', return_value=Opener()):
            return metron.verified_cover(str(path), 'https://static.metron.cloud/media/issue/x.jpg')

    def test_a_credits_page_before_the_cover(self):
        cover = art(20)
        credits = Image.new('RGB', cover.size, (255, 255, 255))
        ImageDraw.Draw(credits).text((40, 300), 'Scanned by somebody', fill=(0, 0, 0))
        path = self.comic([credits, cover, art(21)])
        self.assertTrue(self.verified(path, jpeg(cover)))  # Before: only the credits page was compared.
        with patch.object(pipeline_config, 'matching', side_effect=lambda name: name != 'cover_rule_v2' and pipeline_config.MATCHING_DEFAULTS[name]):
            self.assertFalse(self.verified(path, jpeg(cover)))  # Switched off: today's comparison, first image only.
        self.assertFalse(self.verified(self.comic([credits, art(22), art(23)]), jpeg(cover)))  # Not in the first three.


if __name__ == '__main__':
    unittest.main()
