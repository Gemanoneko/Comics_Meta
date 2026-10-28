"""Approved GCD pilot matching rules, including the post-sample reversals."""
import json
import re
from pathlib import Path
from gcd_index import normalize, series_key, issue_number
import imprints

VOLUME_TAIL = re.compile(r'[\s,(-]+(?:vol(?:ume)?\.?\s*|v)(\d+)\)?\s*$', re.I)
IMPRINT_KEYS = {normalize(k): k for k in imprints.IMPRINT_PARENTS}
# GCD publisher names -> the app's canonical names (imprints.py in-book canonical names); others kept as GCD prints them.
GCD_CANON = {'dc': 'DC Comics', 'image': 'Image Comics', 'darkhorse': 'Dark Horse Comics', 'idw': 'IDW Publishing',
             'boomstudios': 'BOOM! Studios', 'marvel': 'Marvel', 'archie': 'Archie Comics', 'onipress': 'Oni Press'}

BOOK_MARK = re.compile(r'\b(TPB|HC|GN|OGN|omnibus|graphic novel|hardcover|trade paperback|collection|collected|compendium|deluxe edition|library edition|absolute edition)\b', re.I)
VOL_IN_NAME = re.compile(r'(?:^|[\s_-])(?:v|vol\.?\s*|volume\s+|book\s+)(\d{1,3})\b', re.I)
YEAR = re.compile(r'(?<!\d)(19[3-9]\d|20[0-2]\d)(?!\d)')

def folder_year(path):
    match = YEAR.search(Path(path).parent.name)
    return match[1] if match else ''

def extended_year(path, series):
    return next((m[1] for m in YEAR.finditer(Path(path).stem) if m[1] not in series), '')


GCD_CANON.update({'titan': 'Titan Comics', 'vault': 'Vault Comics', 'aftershock': 'AfterShock Comics', 'first': 'First Comics'})
def canon_publisher(name):
    name = re.sub(r'\s*\[[^\]]*\]', '', name or '').strip()   # GCD disambiguation notes, e.g. 'Ace Magazines [1940s-1950s]'
    return GCD_CANON.get(normalize(name), name)

class Matcher:
    def __init__(self, index):
        self.index = index

    def gcd_series(self, series, strip_volume=True):
        keys = {series_key(series)}
        tail = VOLUME_TAIL.search(series)
        base = series[:tail.start()].strip(' -:,') if tail else ''
        if base and strip_volume: keys.add(series_key(base))
        keys.discard('')
        out = {}
        for k in keys:
            for s in self.index.execute("SELECT * FROM series WHERE (key=? OR sort_key=?) AND lang='en'", (k, k)):
                out[s['id']] = dict(s)
        return out
    def issues_of(self, ss, num=None):
        if not ss: return []
        q = ','.join('?' * len(ss))
        if num is None: return [dict(i) for i in self.index.execute(f'SELECT * FROM issue WHERE series_id IN ({q})', list(ss))]
        return [dict(i) for i in self.index.execute(f'SELECT * FROM issue WHERE series_id IN ({q}) AND (num_key=? OR alt_key=?)', list(ss) + [num, num])]
    def iyear(self, i): return i['year'] or i['sale_year']
    def is_book_series(self, s): return (s['pub_type'] == 'book') or bool(re.search(r'collect|trade|tpb|hardcover|graphic novel', s['fmt'] or '', re.I))
    def ycheck(self, i, s, year): return str(self.iyear(i) or '') == year or (self.iyear(i) is None and str(s['year_began']) == year)

    def match_guarded(self, path, series, number, year, year_src, fyear=''):
        """Trial guards G1-G4 (Docs/ComicsMetaOrganizer_GCDTrial_2026-10-26.md §2). Returns (rule, candidates, year used, year source, series map)."""
        name = Path(path).name
        vol = None
        if not number:
            m = VOL_IN_NAME.search(Path(path).stem)
            if m: vol = issue_number(m[1])
        elif VOLUME_TAIL.search(series) is None:
            m = re.search(r'\bv(\d{1,3})\b', Path(path).stem, re.I)
            if m and issue_number(m[1]) == issue_number(number) and not re.search(r'\bv\d+\s+\d+', Path(path).stem, re.I):
                vol = issue_number(number)
        book = bool(BOOK_MARK.search(name)) or vol is not None
        if not year and number:
            ey = extended_year(path, series)
            if ey: year, year_src = ey, 'file name (G4)'
        ss = self.gcd_series(series, strip_volume=bool(year or fyear))
        ss_book = {k: v for k, v in ss.items() if self.is_book_series(v)}
        ss_issue = {k: v for k, v in ss.items() if not self.is_book_series(v)}
        if book:
            target = vol or (issue_number(number) if number else None)
            c = self.issues_of(ss_book)
            if target: c = [i for i in c if target in (i['num_key'], i['alt_key'])]
            else: c = [i for i in c if i['num_key'] in ('', '1') or (ss_book[i['series_id']]['issue_count'] or 0) <= 1]
            if year: c = [i for i in c if self.ycheck(i, ss_book[i['series_id']], year)]; ys = year_src
            elif fyear: c = [i for i in c if str(ss_book[i['series_id']]['year_began']) == fyear]; ys = 'folder (series start)'
            else: ys = 'none'
            return 'collection', c, year or fyear, ys, ss, target
        if number:
            c = self.issues_of(ss_issue, issue_number(number))
            if year: return ('file-name year' if year_src == 'file name (G4)' else 'exact'), [i for i in c if str(self.iyear(i) or '') == year], year, year_src, ss, issue_number(number)
            if fyear:
                return 'folder year', [i for i in c if str(ss_issue[i['series_id']]['year_began']) == fyear], fyear, 'folder (series start)', ss, issue_number(number)
            return 'no year', c, '', 'none', ss, issue_number(number)
        c = self.issues_of(ss)
        whole = [i for i in c if i['num_key'] == '' or ss[i['series_id']]['singleton'] or (ss[i['series_id']]['issue_count'] or 0) <= 1]
        if year: return 'unnumbered', [i for i in whole if self.ycheck(i, ss[i['series_id']], year)], year, year_src, ss, None
        if fyear: return 'unnumbered', [i for i in whole if str(ss[i['series_id']]['year_began']) == fyear], fyear, 'folder (series start)', ss, None
        return 'unnumbered', whole, '', 'none', ss, None

    def gcd_fields(self, i, s, target):
        """ComicInfo fields GCD supplies for one issue (pilot field set)."""
        f = {'Series': s['name']}
        if target and i['alt_key'] == target and i['num_key'] != target: f['Number'] = i['alt_txt']
        elif i['num_txt']: f['Number'] = i['num_txt']
        y = self.iyear(i)
        if y: f['Year'] = str(y)
        if i['key_date'] and len(i['key_date']) >= 7 and i['key_date'][5:7] not in ('00', ''): f['Month'] = str(int(i['key_date'][5:7]))
        pub = canon_publisher(s['publisher'])
        f.update(imprints.split({'Publisher': IMPRINT_KEYS.get(normalize(pub), pub)}, year=y))
        brand = IMPRINT_KEYS.get(normalize(i['brand'] or ''))
        if brand and imprints.parent_of(brand, y) == f.get('Publisher'):
            f.setdefault('Imprint', brand)
        row = self.index.execute('SELECT value FROM fields WHERE issue_id=?', (i['id'],)).fetchone()
        fv = json.loads(row[0]) if row else {}
        for k in ('Writer', 'Penciller', 'Inker', 'Colorist', 'Letterer', 'CoverArtist', 'Editor'):
            if fv.get(k): f[k] = ', '.join(fv[k])
        if (i['title'] or '').strip(): f['Title'] = i['title'].strip()
        digits = re.sub(r'\D', '', i['barcode'] or '')
        if not i['variants'] and digits:
            gt = digits[:12] if len(digits) == 17 else digits[:13] if len(digits) == 18 else digits if len(digits) in (12, 13, 14) else ''
            if gt and self.index.execute('SELECT COALESCE((SELECT uses FROM gtin_counts WHERE value=?),0)', (gt,)).fetchone()[0] == 1: f['GTIN'] = gt
        if re.fullmatch(r'\d{9}[\dX]|\d{13}', i['isbn'] or ''): f['ISBN'] = i['isbn']
        if s['year_ended'] and s['issue_count']: f['Count'] = str(s['issue_count'])
        f['LanguageISO'] = 'en'
        f['Web'] = f"https://www.comics.org/issue/{i['id']}/"
        return f, bool(fv.get('Summary'))

