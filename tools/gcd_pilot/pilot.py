"""GCD pilot: read-only "would write" list for every unmatched live comic, under Sergei's 2026-10-27 rulings
and the trial's guard rules. Read-only on the catalog snapshot and the GCD index; writes only to <out dir>.
Usage: pilot.py <catalog snapshot> <gcd index> <out dir>"""
import collections, csv, json, random, re, sqlite3, sys, time
from decimal import Decimal
from pathlib import Path

cat_path, idx_path, out_dir = sys.argv[1], sys.argv[2], Path(sys.argv[3])
out_dir.mkdir(exist_ok=True)
LIB = 'y:\\comix\\'

# ---- copies of app helpers (research.py, coverage_priority.py, metron.py, imprints.py @ 7bcd05c) ----
def normalize(v): return re.sub(r'[^a-z0-9]', '', str(v).lower())
def series_key(v): return normalize(re.sub(r"^Brian Pulido['\u2019]s\s+", '', str(v), flags=re.I))
def issue_number(value):
    value = str(value).strip().lower()
    m = re.fullmatch(r'(\d+(?:\.\d+)?)([a-z]?)', value)
    if m: return format(Decimal(m[1]).normalize(), 'f') + m[2]
    return normalize(value)
def query_identity(row, old):
    series = old.get('Series') or row.get('series') or ''
    number = old.get('Number') or row.get('number') or ''
    chapter = re.search(r'\(Chapter\s+\d+\)\s*-\s*(.*?)\s+\d+\s*\(\d{4}\)', Path(row['path']).stem, re.I)
    if chapter and normalize(chapter.group(1)) not in normalize(series):
        subtitle = chapter.group(1)
        if normalize(subtitle).startswith(normalize(series)):
            title = old.get('Title', '')
            series = title if normalize(title).startswith(normalize(series)) and not re.search(r'\bchapter\b', title, re.I) else subtitle
        else: series += ': ' + subtitle
    return series, str(number)
def path_key(path):
    text = str(path)
    if text.startswith('\\\\?\\UNC\\'): text = '\\\\' + text[8:]
    elif text.startswith('\\\\?\\'): text = text[4:]
    return text.casefold()
def language_eligible(row, old):
    language = str(old.get('LanguageISO') or '').strip().lower().replace('_', '-').split('-')[0]
    if language and language not in ('en', 'eng', 'english'): return False
    return not re.search(r'\((?:fr|french|de|german|es|spanish|it|italian|ru|russian|jp|japanese)\)', Path(row['path']).name, re.I)
VOLUME_TAIL = re.compile(r'[\s,(-]+(?:vol(?:ume)?\.?\s*|v)(\d+)\)?\s*$', re.I)
IMPRINT_PARENTS = {
    'Skybound': 'Image Comics', 'Skybound Entertainment': 'Image Comics', 'Top Cow': 'Image Comics',
    'Top Cow Productions': 'Image Comics', 'Shadowline': 'Image Comics', 'Ghost Machine': 'Image Comics',
    'Vertigo': 'DC Comics', 'Vertigo Comics': 'DC Comics', 'Black Label': 'DC Comics', 'DC Black Label': 'DC Comics',
    'WildStorm': 'DC Comics', 'WildStorm Productions': 'DC Comics', 'Young Animal': 'DC Comics', 'DC Young Animal': 'DC Comics',
    'Icon': 'Marvel', 'Icon Comics': 'Marvel', 'Epic': 'Marvel', 'Epic Comics': 'Marvel', 'MAX': 'Marvel', 'Marvel MAX': 'Marvel',
    'Marvel Knights': 'Marvel', 'Archaia': 'BOOM! Studios', 'BOOM! Box': 'BOOM! Studios', 'KaBOOM!': 'BOOM! Studios',
    'Berger Books': 'Dark Horse Comics'}
IMPRINT_KEYS = {normalize(k): (k, v) for k, v in IMPRINT_PARENTS.items()}
# GCD publisher names -> the app's canonical names (imprints.py in-book canonical names); others kept as GCD prints them.
GCD_CANON = {'dc': 'DC Comics', 'image': 'Image Comics', 'darkhorse': 'Dark Horse Comics', 'idw': 'IDW Publishing',
             'boomstudios': 'BOOM! Studios', 'marvel': 'Marvel', 'archie': 'Archie Comics', 'onipress': 'Oni Press'}

# ---- pilot-only exclusions ----
LANG_WORDS = ('rus|ru|russian|ukr|ua|ukrainian|fr|fre|fra|french|de|ger|deu|german|es|esp|spa|spanish|it|ita|italian|'
              'pt|por|portuguese|br|pl|pol|polish|nl|dut|dutch|cz|cze|czech|hu|hun|hungarian|tr|tur|turkish|gr|gre|greek|'
              'se|swe|swedish|dk|dan|danish|no|nor|norwegian|fi|fin|finnish|jp|jap|jpn|japanese|cn|chi|chinese|kr|kor|korean|'
              'ar|ara|arabic|he|heb|hebrew|ro|rom|romanian|bg|bul|bulgarian|sr|srb|serbian|hr|cro|croatian')
SQUARE_LANG = re.compile(r'\[\s*(?:' + LANG_WORDS + r')\s*\]', re.I)
ROUND_LANG_MISSED = re.compile(r'\(\s*(?:' + LANG_WORDS + r')\s*\)', re.I)   # round-bracket codes the app rule does not list

BOOK_MARK = re.compile(r'\b(TPB|HC|GN|OGN|omnibus|graphic novel|hardcover|trade paperback|collection|collected|compendium|deluxe edition|library edition|absolute edition)\b', re.I)
VOL_IN_NAME = re.compile(r'(?:^|[\s_-])(?:v|vol\.?\s*|volume\s+|book\s+)(\d{1,3})\b', re.I)
YEAR = re.compile(r'(?<!\d)(19[3-9]\d|20[0-2]\d)(?!\d)')

# ---- catalog ----
cat = sqlite3.connect(f"file:{cat_path}?mode=ro", uri=True)
cat.row_factory = sqlite3.Row
hist = collections.defaultdict(set)
for p, s in cat.execute('SELECT path, source FROM history'):
    hist[path_key(p)].add(s or '')
inbook_fields = collections.defaultdict(set)
for p, f in cat.execute("SELECT path, fields FROM write_ledger WHERE source LIKE 'in-book:%'"):
    try: inbook_fields[path_key(p)].update(json.loads(f or '{}').keys())
    except ValueError: pass
records = {path_key(p): json.loads(v) for p, v in cat.execute('SELECT path, value FROM discovery_records')}

groups = collections.Counter(); pool = []
for r in cat.execute("SELECT * FROM comics WHERE status <> 'absent'"):
    row = dict(r); old = json.loads(row['metadata'] or '{}'); pk = path_key(row['path']); src = hist.get(pk, set())
    if not language_eligible(row, old): g = 'X'
    elif src and any(not s.startswith('in-book:') for s in src): g = 'A'
    elif src: g = 'B'
    elif row['status'] == 'embedded' and (records.get(pk) or {}).get('outcome') == 'current': g = 'C'
    elif row['status'] in ('embedded', 'tagged'): g = 'D'
    else: g = 'E'
    groups[g] += 1
    row['group'] = g; row['old'] = old; row['pk'] = pk
    if g in ('B', 'D', 'E'): pool.append(row)

def folder_year(path):
    m = YEAR.search(Path(path).parent.name)
    return m[1] if m else ''
def extended_year(path, series):
    for m in YEAR.finditer(Path(path).stem):
        if m[1] in series: continue
        return m[1]
    return ''

# ---- GCD index ----
idx = sqlite3.connect(f"file:{idx_path}?mode=ro", uri=True)
idx.row_factory = sqlite3.Row
DUMP = idx.execute("SELECT value FROM meta WHERE key='dump'").fetchone()[0].replace('.db', '')
def gcd_series(series, strip_volume=True):
    keys = {series_key(series)}
    tail = VOLUME_TAIL.search(series)
    base = series[:tail.start()].strip(' -:,') if tail else ''
    if base and strip_volume: keys.add(series_key(base))
    keys.discard('')
    out = {}
    for k in keys:
        for s in idx.execute("SELECT * FROM series WHERE (key=? OR sort_key=?) AND lang='en'", (k, k)):
            out[s['id']] = dict(s)
    return out
def issues_of(ss, num=None):
    if not ss: return []
    q = ','.join('?' * len(ss))
    if num is None: return [dict(i) for i in idx.execute(f'SELECT * FROM issue WHERE series_id IN ({q})', list(ss))]
    return [dict(i) for i in idx.execute(f'SELECT * FROM issue WHERE series_id IN ({q}) AND (num_key=? OR alt_key=?)', list(ss) + [num, num])]
def iyear(i): return i['year'] or i['sale_year']
def is_book_series(s): return (s['pub_type'] == 'book') or bool(re.search(r'collect|trade|tpb|hardcover|graphic novel', s['fmt'] or '', re.I))
def ycheck(i, s, year): return str(iyear(i) or '') == year or (iyear(i) is None and str(s['year_began']) == year)

def match_guarded(path, series, number, year, year_src, fyear=''):
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
    ss = gcd_series(series, strip_volume=bool(year or fyear))
    ss_book = {k: v for k, v in ss.items() if is_book_series(v)}
    ss_issue = {k: v for k, v in ss.items() if not is_book_series(v)}
    if book:
        target = vol or (issue_number(number) if number else None)
        c = issues_of(ss_book)
        if target: c = [i for i in c if target in (i['num_key'], i['alt_key'])]
        else: c = [i for i in c if i['num_key'] in ('', '1') or (ss_book[i['series_id']]['issue_count'] or 0) <= 1]
        if year: c = [i for i in c if ycheck(i, ss_book[i['series_id']], year)]; ys = year_src
        elif fyear: c = [i for i in c if str(ss_book[i['series_id']]['year_began']) == fyear]; ys = 'folder (series start)'
        else: ys = 'none'
        return 'collection', c, year or fyear, ys, ss, target
    if number:
        c = issues_of(ss_issue, issue_number(number))
        if year: return ('file-name year' if year_src == 'file name (G4)' else 'exact'), [i for i in c if str(iyear(i) or '') == year], year, year_src, ss, issue_number(number)
        if fyear:
            near = sorted({ss_issue[i['series_id']]['year_began'] for i in c if abs((ss_issue[i['series_id']]['year_began'] or 0) - int(fyear)) == 1})
            NEAR[path] = near
            return 'folder year', [i for i in c if str(ss_issue[i['series_id']]['year_began']) == fyear], fyear, 'folder (series start)', ss, issue_number(number)
        return 'no year', c, '', 'none', ss, issue_number(number)
    c = issues_of(ss)
    whole = [i for i in c if i['num_key'] == '' or ss[i['series_id']]['singleton'] or (ss[i['series_id']]['issue_count'] or 0) <= 1]
    if year: return 'unnumbered', [i for i in whole if ycheck(i, ss[i['series_id']], year)], year, year_src, ss, None
    if fyear: return 'unnumbered', [i for i in whole if str(ss[i['series_id']]['year_began']) == fyear], fyear, 'folder (series start)', ss, None
    return 'unnumbered', whole, '', 'none', ss, None

NEAR = {}
GCD_CANON.update({'titan': 'Titan Comics', 'vault': 'Vault Comics', 'aftershock': 'AfterShock Comics', 'first': 'First Comics'})
def canon_publisher(name):
    name = re.sub(r'\s*\[[^\]]*\]', '', name or '').strip()   # GCD disambiguation notes, e.g. 'Ace Magazines [1940s-1950s]'
    return GCD_CANON.get(normalize(name), name)
def gcd_fields(i, s, target):
    """ComicInfo fields GCD supplies for one issue (pilot field set)."""
    f = {'Series': s['name']}
    if target and i['alt_key'] == target and i['num_key'] != target: f['Number'] = i['alt_txt']
    elif i['num_txt']: f['Number'] = i['num_txt']
    y = iyear(i)
    if y: f['Year'] = str(y)
    if i['key_date'] and len(i['key_date']) >= 7 and i['key_date'][5:7] not in ('00', ''): f['Month'] = str(int(i['key_date'][5:7]))
    pub = canon_publisher(s['publisher'])
    imp = IMPRINT_KEYS.get(normalize(pub))
    if imp: f['Publisher'], f['Imprint'] = imp[1], imp[0]
    else:
        f['Publisher'] = pub
        b = IMPRINT_KEYS.get(normalize(i['brand'] or ''))
        if b and normalize(b[1]) == normalize(pub): f['Imprint'] = b[0]
    row = idx.execute('SELECT value FROM fields WHERE issue_id=?', (i['id'],)).fetchone()
    fv = json.loads(row[0]) if row else {}
    for k in ('Writer', 'Penciller', 'Inker', 'Colorist', 'Letterer', 'CoverArtist', 'Editor'):
        if fv.get(k): f[k] = ', '.join(fv[k])
    if (i['title'] or '').strip(): f['Title'] = i['title'].strip()
    digits = re.sub(r'\D', '', i['barcode'] or '')
    if not i['variants'] and digits:
        gt = digits[:12] if len(digits) == 17 else digits[:13] if len(digits) == 18 else digits if len(digits) in (12, 13, 14) else ''
        if gt: f['GTIN'] = gt
    if re.fullmatch(r'\d{9}[\dX]|\d{13}', i['isbn'] or ''): f['ISBN'] = i['isbn']
    if s['year_ended'] and s['issue_count']: f['Count'] = str(s['issue_count'])
    f['LanguageISO'] = 'en'
    f['Web'] = f"https://www.comics.org/issue/{i['id']}/"
    return f, bool(fv.get('Summary'))

def differs(field, cur, new, s=None):
    # An article or the "Brian Pulido's" prefix is not a different series: the match itself was made on that key.
    if field == 'Series': return series_key(cur) not in (series_key(new), s['sort_key'] if s else None)
    if field == 'Number': return issue_number(cur) != issue_number(new)
    if field == 'Publisher': return normalize(canon_publisher(cur)) != normalize(new)
    return str(cur).strip() != str(new).strip()

# ---- run ----
cnt = collections.Counter(); rows_out = []; t0 = time.time()
for row in pool:
    path = row['path']; old = row['old']
    rel = path[4:] if path.startswith('\\\\?\\') else path
    rel = rel[len(LIB):] if rel.lower().startswith(LIB) else rel
    if SQUARE_LANG.search(Path(path).name): cnt['excluded: language tag in [ ]'] += 1; continue
    if ROUND_LANG_MISSED.search(Path(path).name): cnt['excluded: language tag in ( ) the app rule misses'] += 1; continue
    series, number = query_identity(row, old)
    # G5 (pilot): a file named only by a number ("10.cbz", "#2 - #2 (of 4).cbz" in a series folder) has no series in
    # its name. A number title the folder repeats ("300 (1999).cbz" in "(1998)  300") is kept.
    g5 = re.fullmatch(r'[#\W_]*(\d{1,4})[\W_]*', series)
    if g5 and not old.get('Series') and not re.search(r'(?<!\d)' + g5[1] + r'(?!\d)', Path(path).parent.name):
        cnt['excluded: file name is only a number (G5)'] += 1; continue
    if old.get('Year'): year, ysrc = str(old['Year']), 'ComicInfo'
    elif row.get('year'): year, ysrc = str(row['year']), 'file name (YYYY)'
    else: year, ysrc = '', 'none'
    rule, c, yused, ysrc, ss, target = match_guarded(path, series, number, year, ysrc, folder_year(path))
    if len(c) != 1:
        cnt[f'not matched ({rule}): ' + ('no candidate' if not c else 'several candidates')] += 1; continue
    i = c[0]; s = ss[i['series_id']]
    f, syn = gcd_fields(i, s, target)
    write, replaced = {}, []
    for k, v in f.items():
        cur = old.get(k)
        if not cur: write[k] = v
        elif k in inbook_fields.get(row['pk'], set()) and row['group'] == 'B' and differs(k, cur, v, s):
            write[k] = v; replaced.append(f'{k} ({cur} -> {v})')
    substantive = [k for k in write if k not in ('Web', 'LanguageISO')]
    synopsis = syn and not old.get('Summary')
    if not substantive and not synopsis:
        cnt[f'matched, nothing new ({rule})'] += 1; continue
    write['Notes'] = f'+ "Metadata from the Grand Comics Database (www.comics.org), CC BY-SA 4.0, data dump {DUMP}: {f["Web"]}"'
    cnt[f'would write: {rule}'] += 1
    rows_out.append({'path': rel, 'group': row['group'], 'rule': rule, 'year_source': ysrc,
                     'identity_used': f'{series} | {number or "-"} | {yused or "-"}',
                     'gcd_issue_id': i['id'], 'gcd_link': f['Web'],
                     'gcd_match': f"{s['name']} ({s['year_began']}, {s['publisher']}{', collected edition' if is_book_series(s) else ''}) #{i['number']} {i['key_date'] or 'no date'}",
                     'fields_written': ' | '.join(f'{k}={v}' for k, v in write.items()),
                     'replaced_in_book': '; '.join(replaced), 'synopsis_to_review': 'yes' if synopsis else '',
                     'comicvine_link': 'yes' if 'comicvine' in str(old.get('Web') or '') else '',
                     'check_note': ('another same-name series starts ' + ', '.join(map(str, NEAR[path])) + ' (folder year off by one?)') if NEAR.get(path) and rule == 'folder year' else ''})
elapsed = time.time() - t0

cols = list(rows_out[0].keys())
with open(out_dir / 'GCDPilot_WouldWrite_2026-10-27.csv', 'w', newline='', encoding='utf-8-sig') as fh:
    w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows_out)

# ---- stratified sample, weighted toward the riskier rules ----
QUOTA = {'exact': 25, 'file-name year': 25, 'folder year': 30, 'no year': 45, 'unnumbered': 40, 'collection': 35}
random.seed(20261027)
by_rule = collections.defaultdict(list)
for r in rows_out: by_rule[r['rule']].append(r)
sample = []
for rule in QUOTA:
    pick = random.sample(by_rule[rule], min(QUOTA[rule], len(by_rule[rule])))
    sample += sorted(pick, key=lambda r: r['path'].lower())

per_group = collections.Counter((r['rule'], r['group']) for r in rows_out)
stats = {'groups': dict(groups), 'pool': len(pool), 'counts': dict(cnt), 'would_write': len(rows_out), 'per_rule_group': {f'{a}|{b}': n for (a, b), n in per_group.items()},
         'replaced_in_book': sum(1 for r in rows_out if r['replaced_in_book']), 'replaced_fields': dict(collections.Counter(x.strip() for r in rows_out for x in r['replaced_in_book'].split(';') if x.strip())),
         'check_note': sum(1 for r in rows_out if r['check_note']),
         'synopsis_to_review': sum(1 for r in rows_out if r['synopsis_to_review']), 'comicvine_link': sum(1 for r in rows_out if r['comicvine_link']),
         'field_counts': dict(collections.Counter(p.split('=', 1)[0] for r in rows_out for p in r['fields_written'].split(' | '))),
         'sample_n': len(sample), 'seconds': round(elapsed, 1), 'dump': DUMP}
(out_dir / 'stats.json').write_text(json.dumps(stats, indent=1, ensure_ascii=False), encoding='utf-8')
(out_dir / 'sample.json').write_text(json.dumps(sample, indent=1, ensure_ascii=False), encoding='utf-8')
print(json.dumps(stats, indent=1, ensure_ascii=False))
