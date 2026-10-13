"""In-book identification: what the comic itself says (Sergei, 2026-10-12).

"If the comic itself carries the information, that is enough." Tier 1 uses only
cover transcriptions the local model has already saved (no new GPU or network
work) and needs the cover to agree with the filename:

- A numbered file gets Series and Number when the cover title and the cover
  number both agree with the filename. An unread or different cover number
  writes nothing; those files are left for a later decision.
- A file without a number is a whole book: Series when the cover title agrees
  exactly. No Number is taken from its cover.
- Publisher only under the canonical full-name rule: a known publisher whose
  distinctive full name is on the cover, never a one-word or partial reading.
- Creators are never taken from covers. Year comes only from an explicit cover
  date, never a copyright year; cover readings carry no date, so none is written.

Only empty fields are filled, and an embedded Series or Number must already
agree. Until this agreement check passes, a cover reading is search evidence only.

The v0.1.2 identity rules come first (identity_blocked): a comic whose Web names
a ComicVine issue, or whose record holds an identity conflict, is never written
by this tier.
"""
import json
import re
import time
from pathlib import Path
import app
import pipeline_config
import research

SOURCE = 'in-book:cover'
METHOD = 'In-book identification: cover text agrees with the filename; empty fields only.'
# A last filename word that makes the trailing number a volume, book or part, not an issue.
VOLUME_WORDS = {'vol', 'volume', 'v', 'book', 'bk', 'tome', 'part', 'pt', 'chapter', 'ch', 'tpb', 'tp', 'hc', 'sc',
                'gn', 'ogn', 'omnibus', 'collection', 'season', 'arc', 'phase', 'year'}
# Words that only label the issue number ("Batman No. 5").
LABEL_WORDS = {'no', 'nr', 'issue', 'number', 'num'}
# A cover "title" made only of these says nothing about which series this is.
GENERIC_WORDS = {'comics', 'comic', 'presents', 'special', 'annual', 'edition', 'issue', 'volume', 'vol', 'collection',
                 'graphic', 'novel', 'preview', 'previews', 'catalog', 'magazine', 'free', 'variant', 'cover'}
PUBLISHER_KEYS = {alias for aliases, _ in research.PUBLISHERS.values() for alias in aliases}
# Publisher aliases that are also ordinary words; they do not make a reading ambiguous.
AMBIGUOUS_ALIASES = {'image', 'first'}
# A translation tagged in the filename; its cover still shows the original publisher.
LANGUAGE_TAG = re.compile(r'[\[(](?:rus?|russian|fre?|fra|french|de|ger|deu|german|esp?|spa|spanish|ita|italian|jpn?|japanese|'
                          r'pt|por|portuguese|br|pol?|polish|nl|dut|dutch|cze?|czech|hun|tr|tur|turkish|chi|chn|chinese|kor|korean)[\])]', re.I)
PAREN_NUMBER = re.compile(r'\((\d{1,4}(?:\.\d+)?)\)')
COVER_NUMBER = re.compile(r'(?:#|no\.?|nr\.?|number|issue|iss\.?)?\s*#?\s*(\d+(?:\.\d+)?[a-z]?)(?:\s*(?:of|/)\s*\d+)?', re.I)
TITLE_NUMBER = re.compile(r'\s*#\s*(\d+(?:\.\d+)?[a-z]?)\s*$', re.I)
# The embedded ComicVine issue link automatic.discover checks identity against.
COMICVINE_ISSUE = re.compile(r'https?://(?:www\.)?comicvine\.gamespot\.com/[^\s]*4000-(\d+)')


def identity_blocked(old, previous=None):
    """True when the v0.1.2 identity rules forbid an in-book write.

    - Web names a ComicVine issue. ComicVine is that comic's identity check: until
      it answers and agrees, a conflict may stand (a hold), may already stand, or
      the id is dead and every write must be verified strictly. A cover reading is
      not a strict verification, so the tier never writes such a comic.
    - The comic's record holds an identity conflict (outcome or saved conflict
      issue): a conflict blocks every field write.
    """
    if COMICVINE_ISSUE.search(str((old or {}).get('Web') or '')):
        return True
    previous = previous or {}
    return previous.get('outcome') == 'identity_conflict' or bool(previous.get('conflict_issue'))


def tokens(value):
    """Letters and digits of a title, accents folded; a leading "The" is optional."""
    text = re.sub(r"^\s*Brian Pulido['’]s\s+", '', str(value or ''), flags=re.I)
    words = re.findall(r'[^\W_]+', research.fold(text).lower())
    return words[1:] if words[:1] == ['the'] else words


def filename_identity(path):
    """(series, number) from the filename, or None when its number is a volume, book or part."""
    series, number, _ = app.parse_name(path)
    if not number:
        # "Conan the Barbarian (180)": a bare number in parentheses is the issue, not a whole book.
        found = [n for n in PAREN_NUMBER.findall(Path(path).stem) if not re.fullmatch(r'(?:19|20)\d{2}', n)]
        if len(found) > 1:
            return None
        if found:
            number = found[0].lstrip('0') or '0'
    words = series.split()
    while words and re.sub(r'[^a-z]', '', words[-1].lower()) in LABEL_WORDS:
        words.pop()
    series = ' '.join(words).strip(' -_#:,')
    if not number:
        series = research.BOOK_FORMAT.sub('', series).strip(' -_:,')  # "Watchmen TPB" is the book "Watchmen".
    last = tokens(series)[-1:]
    if not last or last[0] in VOLUME_WORDS or re.fullmatch(r'(?:v|vol)\d+', last[0]):
        return None
    return series, number


def cover_number(hint):
    """The issue number printed on the cover, or None when it is missing or not one plain number."""
    raw = hint.get('issue')
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        raw = str(raw)
    if isinstance(raw, str) and raw.strip():
        match = COVER_NUMBER.fullmatch(raw.strip())
        return research.issue_number(match[1]) if match else None
    title = hint.get('title')
    match = TITLE_NUMBER.search(title) if isinstance(title, str) else None
    return research.issue_number(match[1]) if match else None


def title_agreement(file_words, cover_words, numbered):
    """'exact', 'cover_title_within_filename' (numbered files only) or '' for no agreement.

    A cover title longer than the filename's series ("Batman Damned" for a file named
    "Batman 1") never agrees: the filename may be missing words."""
    if not file_words or not cover_words:
        return ''
    if cover_words == file_words:
        return 'exact'
    if not numbered or len(cover_words) >= len(file_words) or len(''.join(cover_words)) < 4:
        return ''
    if set(cover_words) <= GENERIC_WORDS or ''.join(cover_words) in PUBLISHER_KEYS:
        return ''
    size = len(cover_words)
    for i in range(len(file_words) - size + 1):
        if file_words[i:i + size] != cover_words:
            continue
        # A number in the filename's series that the cover does not show is a
        # reading-order prefix or chapter naming ("003 Strange Academy - Blood
        # Hunt", "Vampirella Monthly 14 - World's End 2"), not this series' title.
        if any(word.isdigit() for word in file_words[:i] + file_words[i + size:]):
            return ''
        return 'cover_title_within_filename'
    return ''


def cover_publisher(value):
    """(canonical publisher, matched phrase) when exactly one known publisher is named in full."""
    if not isinstance(value, str) or not value.strip():
        return '', ''
    found = [(name, phrase) for name, (_, phrases) in research.PUBLISHERS.items()
             for phrase in phrases if research.named(research.words(phrase), value)]
    if len({name for name, _ in found}) != 1:
        return '', ''
    # A reading that also names another publisher ("DC DARK HORSE COMICS") is ambiguous.
    words = set(research.words(value))
    others = {alias for name, (aliases, _) in research.PUBLISHERS.items() if name != found[0][0]
              for alias in aliases} - AMBIGUOUS_ALIASES
    return found[0] if not words & others else ('', '')


def empty(old, key):
    return not str(old.get(key) or '').strip()


def judge(row, old, hint, signature):
    if LANGUAGE_TAG.search(Path(row['path']).name):
        return None
    parsed = filename_identity(row['path'])
    if not parsed:
        return None
    series, number = parsed
    title = hint.get('title') if isinstance(hint.get('title'), str) else ''
    agreement = title_agreement(tokens(series), tokens(TITLE_NUMBER.sub('', title)), bool(number))
    if not agreement:
        return None
    if number and cover_number(hint) != research.issue_number(number):
        return None  # Unread or different cover number: left for a later decision.
    if not empty(old, 'Series') and research.book_key(old['Series']) != research.book_key(series):
        return None
    if not empty(old, 'Number') and (not number or research.issue_number(old['Number']) != research.issue_number(number)):
        return None
    fields, evidence = {}, {}
    if empty(old, 'Series'):
        fields['Series'] = series
        evidence['Series'] = {'value': series, 'from': 'filename', 'cover_title': title, 'agreement': agreement}
    if number and empty(old, 'Number'):
        fields['Number'] = research.issue_number(number)
        evidence['Number'] = {'value': fields['Number'], 'from': 'filename', 'cover_number': hint.get('issue') or title}
    publisher, phrase = cover_publisher(hint.get('publisher')) if pipeline_config.in_book_publisher() else ('', '')
    if publisher and empty(old, 'Publisher'):
        fields['Publisher'] = publisher
        evidence['Publisher'] = {'value': publisher, 'from': 'cover', 'cover_publisher': hint.get('publisher'),
                                 'rule': 'canonical publisher named in full: ' + phrase}
    if not fields:
        return None
    import local_model
    return {'fields': fields, 'evidence': {
        'tier': 'cover', 'source': SOURCE, 'model': local_model.MODEL, 'cover_signature': list(signature),
        'filename': {'series': series, 'number': number},
        'rule': 'numbered: cover title and number agree with the filename' if number else 'unnumbered whole book: cover title agrees exactly',
        'not_taken_from_cover': ['creators', 'year'], 'fields': evidence, 'decided_at': time.time()}}


def identify(row, old, saved, signature=None, previous=None):
    """Fields the comic's own saved readings support, with per-field evidence, or None.

    The cover tier comes first; the credits/indicia tier is used only when it is
    switched on in config.json and a reading exists for this exact archive.
    `previous` is the comic's discovery record; see identity_blocked."""
    if identity_blocked(old, previous):
        return None
    signature = [row['size'], row['mtime']] if signature is None else list(signature)
    hint = saved.get('cover_identification')
    if saved.get('cover_signature') == signature and isinstance(hint, dict) and pipeline_config.in_book_cover():
        book = judge(row, old, hint, signature)
        if book:
            return book
    reading = saved.get('credits_reading')
    if saved.get('credits_signature') == signature and isinstance(reading, dict) and pipeline_config.in_book_credits_pages():
        return judge_credits(row, old, reading, signature)
    return None


def ready(row, saved, previous=None):
    """A saved reading would write now; makes the comic due before its usual retry.

    A comic the identity rules block is never made due here, so a held or
    conflicting comic keeps its own retry instead of being re-passed."""
    if not saved.get('cover_identification') and not saved.get('credits_reading'):
        return False
    try:
        old = json.loads(row.get('metadata') or '{}')
    except ValueError:
        return False
    return identify(row, old if isinstance(old, dict) else {}, saved, previous=previous) is not None


# --- Stretch tier: indicia and credits pages (off unless "in_book": {"credits_pages": true}) ---

CREDITS_SOURCE = 'in-book:credits'
CREDITS_METHOD = 'In-book identification: indicia text agrees with the filename; empty fields only.'
MONTHS = {name: number for number, names in enumerate((
    ('january', 'jan'), ('february', 'feb'), ('march', 'mar'), ('april', 'apr'), ('may',), ('june', 'jun'), ('july', 'jul'),
    ('august', 'aug'), ('september', 'sep', 'sept'), ('october', 'oct'), ('november', 'nov'), ('december', 'dec')), 1) for name in names}
# "SPAWN #1, May 1992." / "BATMAN No. 50, September 2018." The title stops at punctuation.
INDICIA_ISSUE = re.compile(r'(?P<title>[^\n#,;:.]{2,80}?)\s*,?\s*(?:#|No\.?\s|Number\s|Issue\s)\s*#?\s*(?P<number>\d+(?:\.\d+)?[A-Za-z]?)\b(?P<rest>[^\n]{0,80})', re.I)
# An explicit cover date printed right after the issue number; a copyright year never matches.
COVER_DATE = re.compile(r'^\s*[,.]?\s*(?:\(\s*)?(?P<month>[A-Za-z]{3,9})\.?,?\s+(?P<year>(?:19|20)\d{2})\b')
ROLE_LABELS = (
    ('Writer', ('written by', 'story by', 'script by', 'words by', 'writer', 'script', 'story', 'words', 'plot')),
    ('Penciller', ('pencils by', 'art by', 'illustrated by', 'drawn by', 'artist', 'art', 'pencils', 'penciller', 'penciler', 'illustrator')),
    ('Inker', ('inked by', 'inks by', 'inks', 'inker')),
    ('Colorist', ('colored by', 'coloured by', 'colors by', 'colours by', 'colors', 'colours', 'colorist', 'colourist')),
    ('Letterer', ('lettered by', 'letters by', 'letters', 'letterer', 'lettering')),
    # Labels that end a name list but are never written: covers are variant-specific, editors line-wide.
    (None, ('variant cover', 'cover art', 'covers', 'cover', 'editor in chief', 'assistant editor', 'associate editor', 'edited by',
            'editor', 'editors', 'design', 'designer', 'production', 'publisher', 'president', 'logo', 'special thanks', 'created by')),
)
LABEL_FIELD = {label: field for field, labels in ROLE_LABELS for label in labels}
ROLE_LABEL = re.compile(r'(?<![A-Za-z])(' + '|'.join(re.escape(label) for label in sorted(LABEL_FIELD, key=len, reverse=True)) + r')(?![A-Za-z])', re.I)


def credit_fields(text, series):
    """Creators from labelled credits lines ("Story & Art: Todd McFarlane"); person-like names only."""
    title_words = set(research.words(series))
    publisher_words = set(research.words(' '.join(research.PUBLISHERS)))
    found = {}
    for line in re.split(r'[\n;|•]+', str(text or '')):
        labels = list(ROLE_LABEL.finditer(line))
        i = 0
        while i < len(labels):
            group = [labels[i]]
            while i + 1 < len(labels) and re.fullmatch(r'\s*(?:&|and|/|,)\s*', line[labels[i].end():labels[i + 1].start()], re.I):
                i += 1
                group.append(labels[i])
            end = labels[i + 1].start() if i + 1 < len(labels) else len(line)
            chunk = re.sub(r'^\s*(?:by\b)?\s*[:\-–—]?\s*', '', line[labels[i].end():end], flags=re.I)
            names = [n.strip(' .,:') for n in re.split(r'\s*(?:,|&|/|\band\b)\s*', chunk) if n.strip(' .,:')]
            names = [n for n in names if research.person(n, research.name_words(n), title_words, publisher_words)]
            for label in group:
                field = LABEL_FIELD[label.group(1).lower()]
                if field:
                    for name in names:
                        if name not in found.setdefault(field, []):
                            found[field].append(name)
            i += 1
    return {field: ', '.join(names) for field, names in found.items() if names}


def judge_credits(row, old, reading, signature, creators=None):
    """Fields an indicia line that names this series and issue supports, with per-field evidence.

    creators=None follows config.json; the pilot harness passes True to measure them."""
    if LANGUAGE_TAG.search(Path(row['path']).name):
        return None
    parsed = filename_identity(row['path'])
    if not parsed or not parsed[1]:
        return None  # Numbered issues only: an unnumbered book's indicia carry no issue to agree on.
    series, number = parsed
    indicia = str(reading.get('indicia') or '')
    match = None
    for candidate in INDICIA_ISSUE.finditer(indicia):
        if (title_agreement(tokens(series), tokens(candidate['title']), True)
                and research.issue_number(candidate['number']) == research.issue_number(number)):
            match = candidate
            break
    if not match:
        return None
    if not empty(old, 'Series') and research.book_key(old['Series']) != research.book_key(series):
        return None
    if not empty(old, 'Number') and research.issue_number(old['Number']) != research.issue_number(number):
        return None
    fields, evidence = {}, {}
    line = match.group(0).strip()
    if empty(old, 'Series'):
        fields['Series'] = series
        evidence['Series'] = {'value': series, 'from': 'filename', 'indicia': line}
    if empty(old, 'Number'):
        fields['Number'] = research.issue_number(number)
        evidence['Number'] = {'value': fields['Number'], 'from': 'filename', 'indicia': line}
    date = COVER_DATE.match(match['rest'])
    month = MONTHS.get(date['month'].lower()) if date else None
    if month and empty(old, 'Year') and empty(old, 'Month'):
        fields['Year'], fields['Month'] = date['year'], '%02d' % month
        evidence['Year'] = evidence['Month'] = {'from': 'indicia cover date', 'indicia': line}
    publisher, phrase = cover_publisher(indicia) if pipeline_config.in_book_publisher() else ('', '')
    if publisher and empty(old, 'Publisher'):
        fields['Publisher'] = publisher
        evidence['Publisher'] = {'value': publisher, 'from': 'indicia', 'rule': 'canonical publisher named in full: ' + phrase}
    if pipeline_config.in_book_credits_creators() if creators is None else creators:
        for field, names in credit_fields(reading.get('credits'), series).items():
            if empty(old, field):
                fields[field] = names
                evidence[field] = {'value': names, 'from': 'credits page'}
    if not fields:
        return None
    return {'fields': fields, 'evidence': {
        'tier': 'credits', 'source': CREDITS_SOURCE, 'model': reading.get('model', ''), 'credits_signature': list(signature),
        'filename': {'series': series, 'number': number}, 'pages': reading.get('pages', []),
        'rule': 'indicia names the filename series and issue number; year only from a printed cover date',
        'fields': evidence, 'decided_at': time.time()}}


def notes(book):
    if book['evidence'].get('tier') == 'credits':
        return ('In-book identification: the indicia text, read by the local model, names the series and issue number '
                'in the filename. No external source; a year comes only from a printed cover date.')
    numbered = bool(book['evidence']['filename']['number'])
    return ('In-book identification: the cover text, read by the local model, agrees with the filename on '
            + ('the series title and issue number' if numbered else 'the title of this whole book')
            + '. No external source; creators and year are not taken from the cover.')


def entry(path, book, digest):
    fields = dict(book['fields'])
    changes = {key: {'before': '', 'after': value} for key, value in fields.items()}
    fields['Notes'] = notes(book)
    credits = book['evidence'].get('tier') == 'credits'
    return {'path': str(path), 'action': 'write', 'sha256': digest, 'changes': changes, 'fields': fields,
            'method': CREDITS_METHOD if credits else METHOD, 'source': CREDITS_SOURCE if credits else SOURCE,
            'evidence': book['evidence']}
