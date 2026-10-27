"""Build the trimmed English GCD match index + enrichment fields from the SQLite dump (same as the 2026-10-26 trial).
Read-only on the dump. Usage: build_index.py <dump.db> <out.sqlite>"""
import json, re, sqlite3, sys, time
from decimal import Decimal
from pathlib import Path

dump, out = sys.argv[1], Path(sys.argv[2])
assert not out.exists()


def normalize(v):
    return re.sub(r'[^a-z0-9]', '', str(v).lower())


def series_key(v):
    return normalize(re.sub(r"^Brian Pulido['’]s\s+", '', str(v), flags=re.I))


def issue_number(value):  # copy of research.issue_number
    value = str(value).strip().lower()
    m = re.fullmatch(r'(\d+(?:\.\d+)?)([a-z]?)', value)
    if m:
        return format(Decimal(m[1]).normalize(), 'f') + m[2]
    return normalize(value)


def gcd_parts(raw):
    """GCD number -> (primary text, alternate text). '[nn]' -> ''. '[3]' -> '3'. '6 (18)' -> '6','18'."""
    s = (raw or '').strip()
    m = re.fullmatch(r'\[(.*)\]', s)
    if m:
        s = m[1].strip()
    if s.lower() in ('nn', '') or s.lower().startswith('nn-'):
        return '', ''
    m = re.fullmatch(r'(\S+)\s*\(([^)]+)\)', s)
    if m:
        return m[1], m[2]
    return s, ''


def year_of(d):
    m = re.match(r'(\d{4})', d or '')
    y = int(m[1]) if m else None
    return y if y and y > 1000 else None


t0 = time.time()
con = sqlite3.connect('file:' + out.as_posix(), uri=True)
con.execute('PRAGMA journal_mode=OFF')
con.execute('PRAGMA synchronous=OFF')
con.execute("ATTACH ? AS g", ('file:' + Path(dump).as_posix() + '?mode=ro&immutable=1',))
con.create_function('skey', 1, series_key, deterministic=True)
con.create_function('yr', 1, year_of, deterministic=True)
con.create_function('num1', 1, lambda r: issue_number(gcd_parts(r)[0]) if gcd_parts(r)[0] else '', deterministic=True)
con.create_function('num2', 1, lambda r: issue_number(gcd_parts(r)[1]) if gcd_parts(r)[1] else '', deterministic=True)
con.create_function('txt1', 1, lambda r: gcd_parts(r)[0], deterministic=True)
con.create_function('txt2', 1, lambda r: gcd_parts(r)[1], deterministic=True)
con.executescript('''
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE series(id INTEGER PRIMARY KEY, name TEXT, key TEXT, sort_key TEXT, year_began INT, year_ended INT,
  publisher TEXT, lang TEXT, country TEXT, issue_count INT, pub_type TEXT, fmt TEXT, singleton INT);
CREATE TABLE issue(id INTEGER PRIMARY KEY, series_id INT, number TEXT, num_key TEXT, alt_key TEXT, num_txt TEXT, alt_txt TEXT,
  key_date TEXT, year INT, on_sale TEXT, sale_year INT, title TEXT, barcode TEXT, isbn TEXT, page_count REAL, rating TEXT,
  indicia TEXT, brand TEXT, variants INT);
''')
con.execute('''INSERT INTO series SELECT s.id, s.name, skey(s.name), skey(s.sort_name), s.year_began, s.year_ended, p.name, l.code, c.code,
  s.issue_count, pt.name, s.publishing_format, s.is_singleton
  FROM g.gcd_series s JOIN g.gcd_publisher p ON p.id=s.publisher_id JOIN g.stddata_language l ON l.id=s.language_id
  JOIN g.stddata_country c ON c.id=s.country_id LEFT JOIN g.gcd_series_publication_type pt ON pt.id=s.publication_type_id
  WHERE s.deleted=0 AND l.code='en' ''')
con.execute('''CREATE TEMP TABLE vc AS SELECT variant_of_id id, count(*) n FROM g.gcd_issue WHERE deleted=0 AND variant_of_id IS NOT NULL GROUP BY variant_of_id''')
con.execute('CREATE INDEX temp.vc_id ON vc(id)')
con.execute('''INSERT INTO issue SELECT i.id, i.series_id, i.number, num1(i.number), num2(i.number), txt1(i.number), txt2(i.number),
  i.key_date, yr(i.key_date), i.on_sale_date, yr(i.on_sale_date),
  i.title, i.barcode, i.valid_isbn, i.page_count, i.rating, ip.name, NULL, COALESCE(vc.n,0)
  FROM g.gcd_issue i JOIN series s ON s.id=i.series_id LEFT JOIN g.gcd_indicia_publisher ip ON ip.id=i.indicia_publisher_id
  LEFT JOIN vc ON vc.id=i.id
  WHERE i.deleted=0 AND i.variant_of_id IS NULL''')
con.execute('''CREATE TEMP TABLE ib AS SELECT ibe.issue_id id, min(b.name) name FROM g.gcd_issue_brand_emblem ibe
  JOIN g.gcd_brand b ON b.id=ibe.brand_id GROUP BY ibe.issue_id''')
con.execute('CREATE INDEX temp.ib_id ON ib(id)')
con.execute('UPDATE issue SET brand=(SELECT name FROM ib WHERE ib.id=issue.id)')
con.executescript('''CREATE INDEX series_key ON series(key); CREATE INDEX series_sort_key ON series(sort_key);
CREATE INDEX issue_series_num ON issue(series_id, num_key); CREATE INDEX issue_series_alt ON issue(series_id, alt_key);''')
con.commit()
t2 = time.time()
print(f'stage1: series {con.execute("select count(*) from series").fetchone()[0]}, issues {con.execute("select count(*) from issue").fetchone()[0]}, seconds {t2-t0:.1f}', flush=True)

con.execute('''CREATE TEMP TABLE st AS SELECT st.id, st.issue_id, st.type_id, st.title, st.script, st.pencils, st.inks, st.colors, st.letters, st.editing,
  st.characters, st.synopsis, st.genre, st.sequence_number FROM g.gcd_story st JOIN issue e ON e.id=st.issue_id
  WHERE st.deleted=0 AND st.type_id IN (19,6)''')
con.execute('CREATE INDEX temp.st_id ON st(id)')
roles = {1: ['Writer'], 2: ['Penciller'], 3: ['Inker'], 4: ['Colorist'], 5: ['Letterer'], 6: ['Editor'], 7: ['Penciller', 'Inker'],
         8: ['Penciller', 'Inker', 'Colorist'], 9: ['Penciller'], 10: ['Writer', 'Penciller', 'Inker'],
         11: ['Writer', 'Penciller', 'Inker', 'Colorist'], 12: ['Writer', 'Penciller', 'Inker', 'Letterer'],
         13: ['Writer', 'Penciller', 'Inker', 'Colorist', 'Letterer'], 14: ['Penciller', 'Inker', 'Letterer']}
fields = {}


def add(iid, field, name):
    name = (name or '').strip()
    if not name or name in ('?', 'None'):
        return
    lst = fields.setdefault(iid, {}).setdefault(field, [])
    if name not in lst:
        lst.append(name)


for sid, iid, tid, ctid, name in con.execute('''SELECT st.id, st.issue_id, st.type_id, sc.credit_type_id, cnd.name FROM g.gcd_story_credit sc
   JOIN st ON st.id=sc.story_id JOIN g.gcd_creator_name_detail cnd ON cnd.id=sc.creator_id WHERE sc.deleted=0
   ORDER BY st.issue_id, st.sequence_number'''):
    if tid == 6:
        if ctid in (2, 7, 8, 9, 10, 11, 12, 13, 14):
            add(iid, 'CoverArtist', name)
    else:
        for f in roles.get(ctid, []):
            add(iid, f, name)


def split_text(t):
    t = re.sub(r'\[[^]]*\]|\([^)]*\)', '', t or '')
    return [p.strip() for p in t.split(';') if p.strip() and p.strip() != '?']


for iid, tid, title, script, pencils, inks, colors, letters, editing, chars, syn, genre in con.execute(
        'SELECT issue_id, type_id, title, script, pencils, inks, colors, letters, editing, characters, synopsis, genre FROM st ORDER BY issue_id, sequence_number'):
    if tid == 6:
        if 'CoverArtist' not in fields.get(iid, {}):
            for n in split_text(pencils):
                add(iid, 'CoverArtist', n)
        continue
    for txt, f in ((script, 'Writer'), (pencils, 'Penciller'), (inks, 'Inker'), (colors, 'Colorist'), (letters, 'Letterer'), (editing, 'Editor')):
        if f not in fields.get(iid, {}):
            for n in split_text(txt):
                add(iid, f, n)
    if title:
        add(iid, 'StoryTitles', title)
    if syn and syn.strip():
        add(iid, 'Summary', syn.strip())
for iid, name in con.execute('''SELECT ic.issue_id, cnd.name FROM g.gcd_issue_credit ic JOIN issue e ON e.id=ic.issue_id
     JOIN g.gcd_creator_name_detail cnd ON cnd.id=ic.creator_id WHERE ic.deleted=0 AND ic.credit_type_id=6'''):
    add(iid, 'Editor', name)
con.execute('CREATE TABLE fields(issue_id INTEGER PRIMARY KEY, value TEXT)')
con.executemany('INSERT INTO fields VALUES (?,?)', ((k, json.dumps(v, ensure_ascii=False)) for k, v in fields.items()))
con.execute("INSERT INTO meta VALUES ('dump', ?), ('built', ?)", (Path(dump).name, time.strftime('%Y-%m-%d %H:%M:%S')))
con.commit()
t3 = time.time()
print(f'stage2: issues with fields {len(fields)}, seconds {t3-t2:.1f}', flush=True)
con.execute('DETACH g')
con.execute('VACUUM')
con.close()
print(f'total seconds {time.time()-t0:.1f}; bytes {out.stat().st_size}')
