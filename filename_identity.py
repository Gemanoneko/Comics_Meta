"""Conservative filename syntax; edition volumes are not ordinary issue numbers."""
import re
from pathlib import Path


SCANNER_SUFFIX = re.compile(r'(?<=[)\]])\s+KFRONE\s+HAMPTA\s*$', re.I)
EDITION = re.compile(
    r'^(?P<series>.+?)\s+(?P<label>v|vol\.?\s*|volume\s+|book\s+)'
    r'(?P<number>\d{1,3})(?:\s*[-:]\s*(?P<subtitle>.+))?$', re.I)


def _parse(title):
    years = re.findall(r'\((19\d{2}|20\d{2})\)', title)
    clean = re.sub(r'\([^)]*\)|\[[^]]*\]', ' ', title)
    match = re.search(r'(?:\s|#)(\d+(?:\.\d+)?[A-Za-z]?)\s*$', clean)
    number = (match.group(1).lstrip('0') or '0') if match else ''
    if number.startswith('.'):
        number = '0' + number
    series = clean[:match.start()] if match else clean
    return re.sub(r'\s+', ' ', series).strip(' -_'), number, years[0] if years else ''


def legacy_parse(path):
    return _parse(Path(path).stem)


def parse_name(path):
    title = SCANNER_SUFFIX.sub('', Path(path).stem)
    clean = re.sub(r'\([^)]*\)|\[[^]]*\]', ' ', title).rstrip(' _')
    # A bare title such as District_9 is ambiguous. Only the demonstrated
    # zero-padded scan syntax gains a number; internal underscores stay intact.
    match = re.search(r'_(0\d+(?:\.\d+)?[A-Za-z]?)$', clean)
    if match:
        series = clean[:match.start()].strip(' -_')
        if series:
            number = match[1].lstrip('0') or '0'
            if number.startswith('.'):
                number = '0' + number
            return series, number, _parse(title)[2]
    return _parse(title)


def query_parts(row):
    """Refresh an unchanged legacy catalog parse without modifying the catalog.

    A deliberate catalog override is retained. Embedded ComicInfo values are
    applied by the caller and always take precedence.
    """
    saved = tuple(str(row.get(k) or '') for k in ('series', 'number', 'year'))
    if row.get('path') and saved == legacy_parse(row['path']):
        return parse_name(row['path'])
    return saved


def collection(path):
    """Explicit single Vol/Book label, optionally followed by its subtitle."""
    title = SCANNER_SUFFIX.sub('', Path(path).stem)
    clean = re.sub(r'\([^)]*\)|\[[^]]*\]', ' ', title)
    clean = re.sub(r'\s+', ' ', clean).strip()
    if re.search(r'fan[ -]?made|complete\s+vol|\b(?:part|chapter|tome)\b', title, re.I):
        return None
    match = EDITION.fullmatch(clean)
    if not match or int(match['number']) < 1:
        return None
    # Nested labels denote different numbering systems; do not choose one.
    if re.search(r'\b(?:v\d|vol\.?\s*\d|volume\s+\d|book\s+\d)', match['series'] + ' ' + (match['subtitle'] or ''), re.I):
        return None
    return match['series'].strip(' -:,'), str(int(match['number'])), (match['subtitle'] or '').strip()
