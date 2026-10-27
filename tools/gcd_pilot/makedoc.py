"""Write the Futaba sample doc from the pilot outputs. Usage: makedoc.py <out dir> <csv full path for the doc text> <doc path>"""
import collections, csv, json, sys
from pathlib import Path
out, csv_text, doc = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
st = json.loads((out / 'stats.json').read_text(encoding='utf-8'))
sample = json.loads((out / 'sample.json').read_text(encoding='utf-8'))
rows = list(csv.DictReader(open(out / 'GCDPilot_WouldWrite_2026-10-27.csv', encoding='utf-8-sig')))
RULES = ['exact', 'file-name year', 'folder year', 'no year', 'unnumbered', 'collection']
DESC = {'exact': 'series + number + year (year from ComicInfo or "(YYYY)" in the name)',
        'file-name year': 'series + number + a year written another way in the file name, e.g. "(2007-02)", "(1993-Dark Horse)"',
        'folder year': 'series + number, no issue year; the folder year must equal the GCD series start year',
        'no year': 'series + number, no year anywhere; the only English GCD issue with that series and number',
        'unnumbered': 'no number; a one-shot, a one-issue series or an "[nn]" issue (with the year when known)',
        'collection': 'named as a collection (TPB, Omnibus, Collection, v01, Vol 3...); only GCD collected-edition series, volume N as the number'}
c = st['counts']
def g(rule, grp): return st['per_rule_group'].get(f'{rule}|{grp}', 0)
def esc(t): return str(t).replace('|', '\\|')
def short(r):
    f = dict(p.split('=', 1) for p in r['fields_written'].split(' | ') if '=' in p)
    keep = []
    for k in f:
        if k in ('Notes', 'LanguageISO', 'Web'): continue
        if k in ('Series', 'Number', 'Year', 'Publisher', 'Imprint'): keep.append(f'{k} {f[k]}')
        else: keep.append(k)
    s = ', '.join(keep)
    if r['replaced_in_book']: s += '; **replaces** ' + r['replaced_in_book']
    if r['synopsis_to_review']: s += '; synopsis to review'
    return esc(s)
L = []
L += ['# Comics Meta Organizer — GCD pilot sample for Futaba (2026-10-27)', '',
      'Ender, read-only pilot under Sergei\'s 2026-10-27 rulings (Backlog, "GCD data dump as an offline source") and the trial\'s guard rules '
      '(`Docs/ComicsMetaOrganizer_GCDTrial_2026-10-26.md` §2). Nothing was written to any comic or to the catalog.', '',
      f'- **Data:** GCD dump {st["dump"]} (`current.zip`), English series only; one read-only catalog snapshot taken 2026-10-27 07:54.',
      f'- **Comics considered:** every unmatched live comic: groups B + D + E of the diagnosis, {st["pool"]:,} comics.',
      f'- **Full list ({st["would_write"]:,} rows):** `{csv_text}`',
      '- **Fields in the pilot set** (only empty fields are filled):',
      '  - identity and date: Series, Number, Year, Month;',
      '  - publishing: Publisher (GCD names mapped to the app\'s, e.g. "DC" -> "DC Comics"), Imprint (known imprints only);',
      '  - credits: Writer, Penciller, Inker, Colorist, Letterer, CoverArtist, Editor;',
      '  - other: Title (issue title only), GTIN (only when GCD lists no variant covers), ISBN, Count (finished series only), LanguageISO, Web;',
      '  - Notes: a GCD attribution line.',
      '  - A GCD synopsis is not written. It goes to the existing synopsis review.',
      '- **Replacing in-book values:** an in-book Series or Publisher (group B) is replaced only when GCD names a different one.',
      '  - Case, punctuation, a leading "The" and the "Brian Pulido\'s" prefix do not count as different.',
      '  - This reading of the write ledger is approximate: it does not re-check the archive signature chain.',
      '- **Excluded until the language-tag bug is fixed:** any file with a language tag the app rule misses, in square or round brackets.',
      '- **New guard G5, added in this pilot:** a file named only by a number (`10.cbz`, `#2 - #2 (of 4).cbz` inside a series folder) is skipped.',
      '  - Without it, such files matched GCD series literally called "3", "5", "10", "12" or "2".',
      '  - A number title that the folder repeats (`300 (1999).cbz` in `(1998)  300`) is kept.', '',
      '## How to check a row', '',
      '1. Find the comic under `Y:\\Comix\\` (path in the table). Open it in YACReader to view only; do not save or edit it.',
      '2. Open the GCD link. Compare the cover, the title, the issue number or volume number, and the cover date or year with the comic.',
      '3. Write a verdict in the last column:',
      '   - **R:** right issue or edition. A variant cover of the right issue counts as R.',
      '   - **W:** a wrong issue, volume, edition (single issue vs collection, US vs UK) or language.',
      '   - **?:** cannot tell.',
      '4. For a W, add a few words on what it should be.',
      '5. If time allows, glance at Year and Writer against the comic\'s credits page.', '',
      '## Counts for the whole list', '',
      '| Rule | What it means | Would write | B (in-book) | D (other tool) | E (bare) | Not matched: none / several |',
      '|---|---|---:|---:|---:|---:|---:|']
tot = [0, 0, 0, 0, 0, 0]
for rule in RULES:
    ww = c.get(f'would write: {rule}', 0); none = c.get(f'not matched ({rule}): no candidate', 0); sev = c.get(f'not matched ({rule}): several candidates', 0)
    vals = [ww, g(rule, 'B'), g(rule, 'D'), g(rule, 'E'), none, sev]
    tot = [a + b for a, b in zip(tot, vals)]
    L.append(f'| {rule} | {DESC[rule]} | {ww:,} | {vals[1]:,} | {vals[2]:,} | {vals[3]:,} | {none:,} / {sev:,} |')
L.append(f'| **Total** | | **{tot[0]:,}** | {tot[1]:,} | {tot[2]:,} | {tot[3]:,} | {tot[4]:,} / {tot[5]:,} |')
nothing = sum(v for k, v in c.items() if k.startswith('matched, nothing new'))
L += ['', 'Also:',
      f'- **Matched, but nothing new to write:** {nothing}.',
      f'- **Excluded for a language tag:** {c.get("excluded: language tag in [ ]", 0)} in `[ ]` (almost all `[rus]`), plus {c.get("excluded: language tag in ( ) the app rule misses", 0)} in `( )` with a code the app rule does not list (e.g. `(rus)`).',
      f'- **Excluded as number-only file names (G5):** {c.get("excluded: file name is only a number (G5)", 0)}.',
      f'- **Synopsis queued for review:** {st["synopsis_to_review"]:,} rows.',
      f'- **Rows whose comic carries a ComicVine link:** {st["comicvine_link"]}. In the app these would wait for the ComicVine identity check.',
      f'- **Rows that replace an in-book value:** {st["replaced_in_book"]}, all Publisher.', '',
      'How often the full list fills each field:', '',
      '| Field | Rows |', '|---|---:|']
for k, v in sorted(st['field_counts'].items(), key=lambda kv: -kv[1]):
    L.append(f'| {k} | {v:,} |')
# targeted rows: one per flagged folder
seen = set(); targ = []
ODD = ('Best of the Best 003 (2025))', '(Complete Vol)')   # parsing oddities Ender spotted while preparing the list
for r in rows:
    if any(o in r['path'] for o in ODD) and r['check_note'] == '':
        r['check_note'] = 'Ender: the file name looks like a single issue or a complete collection, not this GCD record'
    if not (r['check_note'] or r['replaced_in_book']): continue
    folder = r['path'].rsplit('\\', 1)[0]
    if folder in seen: continue
    seen.add(folder); targ.append(r)
nflag = sum(1 for r in rows if (r['check_note'] or r['replaced_in_book']))
L += ['', '## Targeted checks (not random)', '',
      f'{nflag} rows share a risk Ender spotted. Below is one row per folder. If a row is W, every row of that folder in the CSV is suspect (filter the CSV on the folder).', '',
      '- **"another same-name series starts …":** the folder-year rule found the series that starts in the folder\'s year, but GCD also has a same-name series one year off. Check it is the right one.',
      '  - Most suspect: `Savage Sword of Conan [1975]` (17 rows). It matched the **Marvel UK weekly** (1975), while the US magazine started in 1974.',
      '- **"replaces Publisher":** an in-book Publisher that GCD names differently.',
      '- **"Ender: …":** a file name the parser read oddly. For example, `003 (2025))` with a doubled bracket lost its issue number, so the file was treated as unnumbered and matched a collection.', '',
      '| # | Comic | Rule | GCD match | Would write | Note | Verdict |', '|---:|---|---|---|---|---|---|']
for n, r in enumerate(targ, 1):
    L.append(f'| T{n} | `{esc(r["path"])}` | {r["rule"]} | [{esc(r["gcd_match"])}]({r["gcd_link"]}) | {short(r)} | {esc(r["check_note"])} | |')
L += ['', f'## Random sample ({len(sample)} rows)', '',
      'Stratified by rule and weighted toward the riskier rules. Seed 20261027; rows are sorted by path within each rule.', '',
      '| Rule | Rows in list | Sampled |', '|---|---:|---:|']
per = collections.Counter(r['rule'] for r in sample)
for rule in RULES:
    L.append(f'| {rule} | {c.get(f"would write: {rule}", 0):,} | {per[rule]} |')
n = 0
for rule in RULES:
    L += ['', f'### {rule}', '', f'{DESC[rule]}.', '', '| # | Comic | Year from | GCD match | Would write | Verdict |', '|---:|---|---|---|---|---|']
    for r in [x for x in sample if x['rule'] == rule]:
        n += 1
        L.append(f'| {n} | `{esc(r["path"])}` | {esc(r["year_source"])} | [{esc(r["gcd_match"])}]({r["gcd_link"]}) | {short(r)} | |')
L += ['', '## Tally (Futaba)', '', '| Rule | Checked | R | W | ? |', '|---|---:|---:|---:|---:|']
for rule in RULES:
    L.append(f'| {rule} | | | | |')
L.append('| Targeted | | | | |')
doc.write_text('\n'.join(L) + '\n', encoding='utf-8')
print('wrote', doc, len(L), 'lines; targeted', len(targ), 'sample', len(sample))
