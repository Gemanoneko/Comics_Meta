"""Cover comparison for Metron's identity check (Enrichment D, Sergei 2026-10-26).

automatic.covers_agree (unchanged) is tried first. When it says no, two failures the audit found are retried:

- Framing. A scan or digital file and Metron's image often differ by bleed, borders or a trim. Both images are
  centre-cropped to the narrower shape, then compared at 32 x 48 grey: correlation above 0.85 and edge correlation
  above 0.60, or a mean colour difference under 12 at 96 x 144 (today's thresholds are 0.94 and 0.80).
- Wraparounds. A landscape first image holding back and front covers (c2c scans) has the front cover on its right;
  that part, cut to Metron's shape, is compared the same way. Today's shape check (0.08) rejected every one.

metron.verified_cover also tries the comic's second and third images, as scanners often put a credits page first.
Measured on the live catalog (Brief, Decision Log "Enrichment matching rules"): no hard negative passed (the same
series' other issues and same-named other runs), with every true pair today's rule passes still passing.
Pure Pillow: the app's runtime has no numpy."""
import io
from math import sqrt

ASPECT_LIMIT = .08
CORRELATION = .85
EDGE_CORRELATION = .60
MEAN_DIFFERENCE = 12


def _detailed(grey):
    middle = sorted(grey)[len(grey) // 2]
    return sum(abs(v - middle) > 32 for v in grey) >= .05 * len(grey)


def _correlation(x, y):
    mx = sum(x) / len(x); my = sum(y) / len(y)
    vx = sum((v - mx) ** 2 for v in x); vy = sum((v - my) ** 2 for v in y)
    if min(vx, vy) / len(x) < 25:
        return 0.0
    return sum((u - mx) * (v - my) for u, v in zip(x, y)) / sqrt(vx * vy)


def _edges(values):
    return [values[i + 1] - values[i] for i in range(len(values) - 1) if i % 32 != 31]


def _centre(image, aspect):
    width, height = image.size
    if width / height > aspect:
        new = max(1, round(height * aspect)); left = (width - new) // 2
        return image.crop((left, 0, left + new, height))
    new = max(1, round(width / aspect)); top = (height - new) // 2
    return image.crop((0, top, width, top + new))


def _right(image, aspect):
    width, height = image.size
    new = max(1, round(height * aspect))
    return image.crop((width - new, 0, width, height)) if new < width else image


def _aligned(a, b):
    from PIL import ImageChops, ImageOps, ImageStat
    aspect = min(a.width / a.height, b.width / b.height)
    a, b = _centre(a, aspect), _centre(b, aspect)
    grey_a = list(a.convert('L').resize((32, 48)).tobytes())
    grey_b = list(b.convert('L').resize((32, 48)).tobytes())
    if not _detailed(grey_a) or not _detailed(grey_b):
        return False  # Near-blank covers agree with anything.
    colour_a = ImageOps.autocontrast(a.convert('RGB').resize((96, 144)))
    colour_b = ImageOps.autocontrast(b.convert('RGB').resize((96, 144)))
    if sum(ImageStat.Stat(ImageChops.difference(colour_a, colour_b)).mean) / 3 < MEAN_DIFFERENCE:
        return True
    return (_correlation(grey_a, grey_b) > CORRELATION
            and _correlation(_edges(grey_a), _edges(grey_b)) > EDGE_CORRELATION)


def compare(local, remote):
    """Which comparison finds the archive image (bytes) and Metron's image (bytes) the same cover, or None:
    'today' (automatic.covers_agree), 'aligned' (framing aligned) or 'wraparound' (a wraparound's front part).
    The name is kept with each write's evidence (v0.5.0 review F4)."""
    import automatic
    if automatic.covers_agree(local, remote):
        return 'today'
    from PIL import Image
    with Image.open(io.BytesIO(local), formats=('JPEG', 'PNG', 'WEBP')) as a, \
            Image.open(io.BytesIO(remote), formats=('JPEG', 'PNG', 'WEBP')) as b:  # Never EPS/Ghostscript (review F1).
        a, b = a.convert('RGB'), b.convert('RGB')
        target = b.width / b.height
        if a.width / a.height > 1.0 and target < 1.0:
            return 'wraparound' if _aligned(_right(a, target), b) else None  # Back cover left, front cover right.
        if abs(a.width / a.height - target) > ASPECT_LIMIT:
            return None
        return 'aligned' if _aligned(a, b) else None


def agree(local, remote):
    """The archive image (bytes) shows the same cover as Metron's image (bytes)."""
    return compare(local, remote) is not None
