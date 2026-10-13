"""In-book identification: what the comic itself says (Sergei, 2026-10-12 and 2026-10-13).

"If the comic itself carries the information, that is enough." Tier 1 uses only
cover transcriptions the local model has already saved (no new GPU or network
work) and needs the cover to agree with the filename:

- A numbered file gets Series and Number when the cover title and the cover
  number both agree with the filename. A different cover number writes nothing.
- Sergei 2026-10-13: when the cover number could not be read at all, the cover
  title agreeing with the filename series is enough, and the Number comes from the
  filename alone (source 'in-book:filename-number'). Not when the cover carries
  other numbering text ("Vol. 2", "Annual"), and not when the filename's number may
  be another numbering: a number in brackets ("(180)"), chapter, episode or part
  numbering, plus every v0.1.3 skip below.
- A file without a number is a whole book: Series when the cover title agrees
  exactly. No Number is taken from its cover.
- Publisher (Sergei 2026-10-13) only when the cover reading and the credits/indicia
  reading of the same pages both name the same publisher in full under the
  canonical rule (publisher_agreement), and only while its switch is on.
- Creators are never taken from covers. Year comes only from an explicit cover
  date, never a copyright year; cover readings carry no date, so none is written.

Only empty fields are filled, and an embedded Series or Number must already
agree. Until this agreement check passes, a cover reading is search evidence only.
A value written here may later be replaced by a verified external source that
disagrees with it (provenance.py).

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
FILENAME_NUMBER_SOURCE = 'in-book:filename-number'
FILENAME_NUMBER_METHOD = 'In-book identification: cover title agrees with the filename; number from the filename, no plain cover number; empty fields only.'
# A cover reading's issue text that says nothing: the number could not be read.
UNREAD_ISSUE = re.compile(r'(?:n/?a|none|unknown|illegible|unreadable|not (?:visible|legible|readable|shown|printed)|blank|-+|\?+|#)', re.I)
# A number in brackets ("(180)", "[12]") that is not a year: another numbering, or the only number.
BRACKET_NUMBER = re.compile(r'[(\[]\s*#?\s*(\d{1,4}(?:\.\d+)?)\s*[)\]]')
# Chapter, episode or part numbering anywhere in the filename, brackets included.
CHAPTER_MARK = re.compile(r'(?<![^\W\d_])(?:chapter|chap|ch|episode|ep|part|pt)\.?\s*#?\s*\d', re.I)
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


def filename_parts(path):
    """(series, number, number_in_brackets) from the filename, or None when its number is a volume, book or part."""
    series, number, _ = app.parse_name(path)
    if number.startswith('.'):
        number = '0' + number  # parse_name strips "0.5" to ".5", which would read as issue 5.
    bracketed = False
    if not number:
        # "Conan the Barbarian (180)": a bare number in parentheses is the issue, not a whole book.
        found = [n for n in PAREN_NUMBER.findall(Path(path).stem) if not re.fullmatch(r'(?:19|20)\d{2}', n)]
        if len(found) > 1:
            return None
        if found:
            number, bracketed = found[0].lstrip('0') or '0', True
    words = series.split()
    while words and re.sub(r'[^a-z]', '', words[-1].lower()) in LABEL_WORDS:
        words.pop()
    series = ' '.join(words).strip(' -_#:,')
    if not number:
        series = research.BOOK_FORMAT.sub('', series).strip(' -_:,')  # "Watchmen TPB" is the book "Watchmen".
    last = tokens(series)[-1:]
    if not last or last[0] in VOLUME_WORDS or re.fullmatch(r'(?:v|vol)\d+', last[0]):
        return None
    return series, number, bracketed


def filename_identity(path):
    """(series, number) from the filename, or None when its number is a volume, book or part."""
    parts = filename_parts(path)
    return parts[:2] if parts else None


def filename_number_doubt(path, series, number, bracketed):
    """Why the filename's number cannot stand alone without the cover's agreement, or ''.

    Sergei 2026-10-13 kept the v0.1.3 skips for numbers taken from the filename alone:
    a number in brackets ("(180)", whether the only number or beside another) may be a
    different numbering, and chapter, episode or part numbering is not an issue number.
    A catalog or magazine title says nothing about which issue this is, and a four-digit
    number with a leading zero is a date code ("Previews 0315" is March 2015).
    Reading-order prefixes, translations and collections are refused before this."""
    stem = Path(path).stem
    words = set(tokens(series))
    if bracketed or [n for n in BRACKET_NUMBER.findall(stem) if not re.fullmatch(r'(?:19|20)\d{2}', n)]:
        return 'number in brackets'
    if CHAPTER_MARK.search(stem):
        return 'chapter, episode or part numbering'
    if words <= GENERIC_WORDS:
        return 'catalog or magazine title'
    if words & COLLECTION_WORDS:
        return 'collection'
    if words & SCAN_TAGS:
        return 'scan tag in the name'
    if len(number.split('.')[0]) >= 4:
        return 'a year or code, not an issue number'  # 1992, 2494, 17689: from the filename alone, too often a title or code.
    # app.parse_name's terminal number, before its leading zeros are dropped.
    terminal = re.search(r'(?:\s|#)(\d+(?:\.\d+)?[A-Za-z]?)\s*$', re.sub(r'\([^)]*\)|\[[^]]*\]', ' ', stem))
    if terminal and re.fullmatch(r'0\d{3}', terminal.group(1)):
        return 'date code'
    if terminal and re.fullmatch(r'0\d+\.\d+', terminal.group(1)):
        return 'zero-padded decimal'  # "003.3": a volume and issue, or a part
    return ''


WORD_NUMBERS = {word: str(n) for n, word in enumerate(
    'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen '
    'eighteen nineteen twenty'.split())}
_WORDS = '|'.join(WORD_NUMBERS)
_MONTH = (r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?'
          r'|nov(?:ember)?|dec(?:ember)?)')
# Cover dates, years and prices carry no issue number: "JUNE 2005", "MAY '95", "$2.99".
COVER_DATE_TEXT = re.compile(r"(?<![^\W\d_])" + _MONTH + r"(?![^\W\d_])\.?,?(?:\s*\d{1,2}(?:st|nd|rd|th)?\b,?)?(?:\s*(?:'\d{2}|(?:19|20)\d{2})\b)?"
                             r"|(?<!\d)(?:19|20)\d{2}(?!\d)|'\d{2}\b", re.I)
PRICE_TEXT = re.compile(r'[$£€]\s*\d+(?:[.,]\d{2})?|\b\d+(?:[.,]\d{2})?\s*(?:¢|cents?)', re.I)
OF_TOTAL = re.compile(r'\(?\s*\b(?:of|/)\s*\d+\s*\)?', re.I)
# Another numbering printed where the issue number would be: a part, book, volume, chapter...
OTHER_NUMBERING_TEXT = re.compile(r'(?<![^\W\d_])(?:part|pt|book|bk|vol|volume|v|tome|episode|ep|chapter|chap|ch|season|arc|phase|act|year)'
                                  r'\.?\s*#?\s*(?:\d|(?:[ivxlc]+|' + _WORDS + r')(?![^\W\d_]))', re.I)
# A cover that names another kind of issue than the filename's series: "Annual", "Special".
KIND_WORDS = {'annual', 'special', 'oneshot', 'shot', 'preview', 'previews', 'giant', 'ashcan', 'sketchbook', 'king', 'treasury'}
# A number the cover marks as the issue's: "#5", "No. 5", "Nº 5", "Issue Five".
COVER_ISSUE_MARK = re.compile(r'(?:#|(?<![^\W\d_])(?:no|nr|n[º°o]|number|issue|iss)\.?)\s*#?\s*(\d+(?:\.\d+)?|' + _WORDS + r')(?![^\W_])', re.I)
# Letters of another script on the cover: the copy in hand may be a translation.
OTHER_SCRIPT = re.compile('[\u0370-\u03ff\u0400-\u052f\u0590-\u06ff\u0e00-\u0e7f\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]')
# Filename words that make the number a collection's or a scan's, never an issue's.
COLLECTION_WORDS = {'gn', 'ogn', 'tpb', 'tp', 'hc', 'sc', 'omnibus', 'collection', 'collected', 'compendium'}
SCAN_TAGS = {'c2c', 'dcp'}


def cover_issue_state(hint, number, series):
    """What the cover reading says about the issue number, compared with the filename's.

    'same': the cover shows the filename's number, plainly or in other wording ("#1 (of 4)",
    "Issue One", "Origins #08", "137: A Future Uncertain"). 'unread': no issue number at all,
    only a date, price, placeholder or subtitle. Anything else is a reason not to take the
    number from the filename: 'different'; 'other numbering' (part, book, volume, chapter...);
    'other kind' (an annual or special the filename does not name); 'other script'; 'unclear'
    (a number that is neither marked as the issue's nor the reading's first word, such as
    "UNIT 731" or "MELTDOWN 2", which may be part of a title)."""
    if cover_number(hint) is not None:
        return 'same' if cover_number(hint) == research.issue_number(number) else 'different'
    raw = hint.get('issue')
    if OTHER_SCRIPT.search(' '.join(str(hint.get(key) or '') for key in ('title', 'issue'))):
        return 'other script'
    if raw is None or (isinstance(raw, str) and (not raw.strip() or UNREAD_ISSUE.fullmatch(raw.strip()))):
        return 'unread'
    if not isinstance(raw, (str, int, float)) or isinstance(raw, bool):
        return 'unclear'
    text = str(raw)
    if OTHER_NUMBERING_TEXT.search(text):
        return 'other numbering'
    if (set(research.words(text)) | {''.join(research.words(text))}) & (KIND_WORDS - set(tokens(series))):
        return 'other kind'
    text = OF_TOTAL.sub(' ', PRICE_TEXT.sub(' ', COVER_DATE_TEXT.sub(' ', text)))
    found = {WORD_NUMBERS.get(n.lower()) or research.issue_number(n) for n in COVER_ISSUE_MARK.findall(text)}
    leading = re.match(r'\s*(\d+(?:\.\d+)?)(?![\d.])', text)
    if leading:
        found.add(research.issue_number(leading[1]))
    if text.strip().lower() in WORD_NUMBERS:
        found.add(WORD_NUMBERS[text.strip().lower()])
    if any(research.issue_number(n) not in found for n in re.findall(r'\d+(?:\.\d+)?', text)):
        return 'unclear'
    if not found:
        return 'unread'
    if len(found) > 1:
        return 'unclear'
    return 'same' if found == {research.issue_number(number)} else 'different'


def cover_number_unread(hint):
    """The cover reading carries no issue number (cover_issue_state 'unread')."""
    return cover_issue_state(hint, '', '') == 'unread' and cover_number(hint) is None


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


def credits_text(reading):
    return '\n'.join(str((reading or {}).get(key) or '') for key in ('indicia', 'credits'))


def publisher_agreement(hint, reading):
    """Publisher evidence when the cover reading and the credits/indicia reading of the same
    pages each name exactly one known publisher in full, and it is the same one (Sergei
    2026-10-13); None otherwise or while the switch is off. Either reading naming a second
    publisher, or naming none, writes nothing."""
    if not pipeline_config.in_book_publisher_agreement() or not isinstance(hint, dict) or not isinstance(reading, dict):
        return None
    cover, cover_phrase = cover_publisher(hint.get('publisher'))
    printed, printed_phrase = cover_publisher(credits_text(reading))
    if not cover or cover != printed:
        return None
    return {'value': cover, 'from': 'cover and credits/indicia pages agree', 'cover_publisher': hint.get('publisher'),
            'rule': 'the same canonical publisher named in full in both readings: ' + cover_phrase + ' / ' + printed_phrase}


# --- Series spelling (Sergei 2026-10-13): the filename's text, with obvious slips fixed ---

# An underscore standing in for an apostrophe inside a word: "Don_t", "Won_t", "X_s".
APOSTROPHE_UNDERSCORE = re.compile(r"(?<=[^\W\d_])_(?=(?:s|t|d|m|ll|re|ve)(?![^\W_]))", re.I)
# A trailing dot that belongs to the name: an initialism ("S.H.I.E.L.D.") or a short title.
KEPT_FINAL_DOT = re.compile(r'(?:(?<![^\W\d_])(?:[^\W\d_]\.){2,}|(?<![^\W\d_])(?:jr|sr|mr|mrs|ms|dr|st|vs|inc|co|ltd)\.)$', re.I)
END_SEPARATORS = ' -_.,:;~'


def restore_accents(series, cover_title):
    """The filename's words with the cover's accented letters, only when the cover title is the
    same text once accents are ignored (letter for letter, any case); otherwise unchanged."""
    cover = ' '.join(str(cover_title or '').split())
    if len(cover) != len(series) or cover == series:
        return series
    out = []
    for mine, theirs in zip(series, cover):
        plain_mine, plain_theirs = research.fold(mine), research.fold(theirs)
        if plain_mine.lower() != plain_theirs.lower() or len(plain_theirs) != 1:
            return series  # A different letter, word or punctuation mark: not the same title.
        if theirs != plain_theirs and mine == plain_mine:
            mine = theirs.upper() if mine.isupper() else theirs.lower() if mine.islower() else theirs
        out.append(mine)
    return ''.join(out)


# Words that mark a bracket group as a release, scan or format tag, never part of a title.
TAG_WORDS = {'digital', 'c2c', 'ctc', 'webrip', 'web', 'rip', 'scan', 'scans', 'scanned', 'rescan', 'hd', 'hq', 'upscaled', 'upscale',
             'cover', 'covers', 'variant', 'variants', 'dcp', 'empire', 'minutemen', 'signed', 'english', 'eng', 'retail', 'retailer',
             'incentive', 'noads', 'repack', 'ocr', 'fixed', 'colour', 'color', 'edition', 'remastered', 'hybrid', 'raw', 'translated',
             'translation', 'fan', 'pdf', 'cbr', 'cbz', 'ebook', 'magazine'} | COLLECTION_WORDS
TITLE_GROUP = re.compile(r'\(([^()\[\]]*)\)')


def title_group(text):
    """A bracket group that is an alternative title: "(or How to Hero at Fifty)", "(aka ...)".

    Narrow on purpose: on the live snapshot, other multi-word groups before the number were
    mostly author names ("Alison (Lizzy Stewart)"), formats ("(One-shot)") or notes. Never a
    year, number, numbering, release or scan tag, or publisher name."""
    words = research.words(text)
    return (len(words) >= 3 and re.match(r'\s*(?:or|aka|a\.k\.a\.)\s', text, re.I) is not None
            and not re.search(r'\d', text) and not set(words) & TAG_WORDS
            and not research.canonical_publisher(text) and not cover_publisher(text)[0]
            and not OTHER_NUMBERING_TEXT.search(text) and not re.match(r'\s*(?:of|vol|volume|chapter|part|book)\b', text, re.I))


def series_with_title_groups(path, numbered):
    """The filename's series with its bracketed title words kept, or '' when there are none.

    Sergei 2026-10-13: the Series is the filename's text; app.parse_name drops every bracket
    group, which shortened "Midlife (or How to Hero at Fifty) 001" to the cover's "Midlife".
    A group counts only before the issue number (or, for a whole book, before its year and tags)."""
    stem = Path(path).stem
    trailing = re.search(r'(?:\s*(?:\([^()]*\)|\[[^\[\]]*\]))+\s*$', stem)
    tail_start = trailing.start() if trailing else len(stem)
    kept = []
    for group in TITLE_GROUP.finditer(stem):
        if not title_group(group[1]):
            continue
        if group.start() < tail_start:
            kept.append(group)
        elif not numbered and not re.search(r'\(\s*(?:19|20)\d{2}|\[', stem[tail_start:group.start()]) and \
                all(title_group(g[1]) for g in TITLE_GROUP.finditer(stem[tail_start:group.start()])):
            kept.append(group)  # A whole book: title words before its year and tags.
    if not kept:
        return ''
    protected = stem
    for group in reversed(kept):
        protected = protected[:group.start()] + '' + group[1] + '' + protected[group.end():]
    parts = filename_parts(str(Path(path).with_name(protected + '.cbz')))
    if not parts:
        return ''
    return parts[0].replace('', '(').replace('', ')')


def normalize_series(series, cover_title='', path=None, numbered=False):
    """(series, changes): the filename's series text with obvious spelling and formatting slips
    fixed, and the list of fixes applied. Deterministic; the wording is never shortened."""
    changes = []
    full = series_with_title_groups(path, numbered) if path else ''
    if full and full != series and research.book_key(re.sub(r'\([^)]*\)', ' ', full)) == research.book_key(series):
        series, changes = full, ['bracketed title words kept']
    text = APOSTROPHE_UNDERSCORE.sub("'", series)
    if text != series:
        changes.append('underscore for an apostrophe')
    if '_' in text:
        text = text.replace('_', ' ')
        changes.append('underscores as spaces')
    collapsed = ' '.join(text.split())
    if collapsed != text.strip():
        changes.append('repeated spaces')
    text = collapsed
    trimmed = text.lstrip(END_SEPARATORS.replace('.', ''))  # A leading dot can be the name (".hack").
    trimmed = trimmed if KEPT_FINAL_DOT.search(trimmed) else trimmed.rstrip(END_SEPARATORS)
    if trimmed != text:
        changes.append('separators trimmed at the ends')
    text = trimmed
    accented = restore_accents(text, TITLE_NUMBER.sub('', cover_title or ''))
    if accented != text:
        changes.append('accents from the cover')
    if accented != series and not changes:
        changes.append('spaces trimmed')
    return accented, changes


def series_evidence(value, raw, changes, **extra):
    evidence = dict({'value': value, 'from': 'filename'}, **extra)
    if changes:
        evidence['normalised'] = {'filename_text': raw, 'changes': changes}
    return evidence


def cover_identity(row, old, hint):
    """(series, number, agreement, source) the cover reading confirms for this file, or None."""
    if LANGUAGE_TAG.search(Path(row['path']).name):
        return None
    parts = filename_parts(row['path'])
    if not parts:
        return None
    series, number, bracketed = parts
    title = hint.get('title') if isinstance(hint.get('title'), str) else ''
    agreement = title_agreement(tokens(series), tokens(TITLE_NUMBER.sub('', title)), bool(number))
    if not agreement:
        return None
    source = SOURCE
    if number and cover_number(hint) != research.issue_number(number):
        # A different cover number writes nothing. One the cover does not show as a plain
        # number (Sergei 2026-10-13) lets the filename's number stand alone, unless the cover
        # shows another number or numbering, or the filename's number may be another numbering.
        if not (cover_issue_state(hint, number, series) in ('unread', 'same') and pipeline_config.in_book_filename_number()
                and not filename_number_doubt(row['path'], series, number, bracketed)):
            return None
        source = FILENAME_NUMBER_SOURCE
    if not empty(old, 'Series') and research.book_key(old['Series']) != research.book_key(series):
        return None
    if not empty(old, 'Number') and (not number or research.issue_number(old['Number']) != research.issue_number(number)):
        return None
    return series, number, agreement, source


def judge(row, old, hint, signature, credits=None):
    """credits: the credits/indicia reading of the same pages, used only for publisher agreement."""
    found = cover_identity(row, old, hint)
    if not found:
        return None
    raw, number, agreement, source = found
    title = hint.get('title') if isinstance(hint.get('title'), str) else ''
    series, changes = normalize_series(raw, title, row['path'], bool(number))
    fields, evidence = {}, {}
    if empty(old, 'Series'):
        fields['Series'] = series
        evidence['Series'] = series_evidence(series, raw, changes, cover_title=title, agreement=agreement)
    if number and empty(old, 'Number'):
        fields['Number'] = research.issue_number(number)
        evidence['Number'] = ({'value': fields['Number'], 'from': 'filename', 'cover_number': hint.get('issue') or title}
                              if source == SOURCE else
                              {'value': fields['Number'], 'from': 'filename alone',
                               'cover_number': cover_issue_state(hint, number, raw), 'cover_issue_text': hint.get('issue')})
    publisher = publisher_agreement(hint, credits) if empty(old, 'Publisher') else None
    if publisher:
        fields['Publisher'] = publisher['value']
        evidence['Publisher'] = publisher
    if not fields:
        return None
    import local_model
    rule = ('numbered: cover title and number agree with the filename' if source == SOURCE and number else
            'numbered: cover title agrees with the filename; no plain cover number, number from the filename alone' if number else
            'unnumbered whole book: cover title agrees exactly')
    return {'fields': fields, 'evidence': {
        'tier': 'cover', 'source': source, 'model': local_model.MODEL, 'cover_signature': list(signature),
        'filename': {'series': raw, 'number': number}, 'rule': rule,
        'not_taken_from_cover': ['creators', 'year'], 'fields': evidence, 'decided_at': time.time()}}


def reading_applies(row, reading_signature, signature, old):
    """A saved reading describes this archive: taken at this signature, or, only for a missing
    Publisher while publisher agreement is on, before the app's own verified writes, which
    never change a page (provenance.pages_unchanged)."""
    if reading_signature == signature:
        return True
    if not (pipeline_config.in_book_publisher_agreement() and empty(old, 'Publisher')) or signature != [row['size'], row['mtime']]:
        return False
    import provenance
    return provenance.pages_unchanged(row, reading_signature)


def identify(row, old, saved, signature=None, previous=None):
    """Fields the comic's own saved readings support, with per-field evidence, or None.

    The cover tier comes first; the credits/indicia tier is used only when it is
    switched on in config.json and a reading exists for this exact archive.
    `previous` is the comic's discovery record; see identity_blocked."""
    if identity_blocked(old, previous):
        return None
    signature = [row['size'], row['mtime']] if signature is None else list(signature)
    hint = saved.get('cover_identification')
    hint = hint if isinstance(hint, dict) and reading_applies(row, saved.get('cover_signature'), signature, old) else None
    reading = saved.get('credits_reading')
    reading = reading if isinstance(reading, dict) and reading_applies(row, saved.get('credits_signature'), signature, old) else None
    if hint and pipeline_config.in_book_cover():
        book = judge(row, old, hint, signature, reading)
        if book:
            return book
    if reading and pipeline_config.in_book_credits_pages():
        return judge_credits(row, old, reading, signature, cover=hint if pipeline_config.in_book_cover() else None)
    return None


def needs_credits_for_publisher(row, old, saved, signature, previous=None):
    """Publisher agreement is on and only a credits/indicia reading is missing: the cover tier
    can write (or has written) this comic, its cover names a known publisher in full, and
    Publisher is empty. automatic.discover then reads the credits pages once."""
    if not pipeline_config.in_book_publisher_agreement() or not pipeline_config.in_book_cover() or not empty(old, 'Publisher'):
        return False
    if identity_blocked(old, previous):
        return False
    hint = saved.get('cover_identification')
    if not isinstance(hint, dict) or not cover_publisher(hint.get('publisher'))[0]:
        return False
    if isinstance(saved.get('credits_reading'), dict) and reading_applies(row, saved.get('credits_signature'), signature, old):
        return False
    # A failed read of these pages (unterminated JSON, an unreadable page: 8 of 403 in the pilot)
    # is no reading, never agreement, and is not repeated on every pass.
    failed = saved.get('credits_reading_error')
    if isinstance(failed, dict) and reading_applies(row, failed.get('signature'), signature, old):
        return False
    return reading_applies(row, saved.get('cover_signature'), signature, old) and cover_identity(row, old, hint) is not None


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


def judge_credits(row, old, reading, signature, creators=None, cover=None, year=None):
    """Fields an indicia line that names this series and issue supports, with per-field evidence.

    creators=None and year=None follow config.json (both off: the 2026-10-13 pilot found 42.5% of
    creators and 23.5% of recent years right); the pilot harness passes True to measure them.
    cover: the cover reading of the same pages, for publisher agreement and accents."""
    if LANGUAGE_TAG.search(Path(row['path']).name):
        return None
    parsed = filename_identity(row['path'])
    if not parsed or not parsed[1]:
        return None  # Numbered issues only: an unnumbered book's indicia carry no issue to agree on.
    raw, number = parsed
    indicia = str(reading.get('indicia') or '')
    match = None
    for candidate in INDICIA_ISSUE.finditer(indicia):
        if (title_agreement(tokens(raw), tokens(candidate['title']), True)
                and research.issue_number(candidate['number']) == research.issue_number(number)):
            match = candidate
            break
    if not match:
        return None
    if not empty(old, 'Series') and research.book_key(old['Series']) != research.book_key(raw):
        return None
    if not empty(old, 'Number') and research.issue_number(old['Number']) != research.issue_number(number):
        return None
    cover_title = (cover or {}).get('title') if isinstance((cover or {}).get('title'), str) else ''
    series, changes = normalize_series(raw, cover_title, row['path'], True)
    fields, evidence = {}, {}
    line = match.group(0).strip()
    if empty(old, 'Series'):
        fields['Series'] = series
        evidence['Series'] = series_evidence(series, raw, changes, indicia=line)
    if empty(old, 'Number'):
        fields['Number'] = research.issue_number(number)
        evidence['Number'] = {'value': fields['Number'], 'from': 'filename', 'indicia': line}
    date = COVER_DATE.match(match['rest'])
    month = MONTHS.get(date['month'].lower()) if date else None
    if month and empty(old, 'Year') and empty(old, 'Month') and (pipeline_config.in_book_credits_year() if year is None else year):
        fields['Year'], fields['Month'] = date['year'], '%02d' % month
        evidence['Year'] = evidence['Month'] = {'from': 'indicia cover date', 'indicia': line}
    publisher = publisher_agreement(cover, reading) if empty(old, 'Publisher') else None
    if publisher:
        fields['Publisher'] = publisher['value']
        evidence['Publisher'] = publisher
    if pipeline_config.in_book_credits_creators() if creators is None else creators:
        for field, names in credit_fields(reading.get('credits'), series).items():
            if empty(old, field):
                fields[field] = names
                evidence[field] = {'value': names, 'from': 'credits page'}
    if not fields:
        return None
    return {'fields': fields, 'evidence': {
        'tier': 'credits', 'source': CREDITS_SOURCE, 'model': reading.get('model', ''), 'credits_signature': list(signature),
        'filename': {'series': raw, 'number': number}, 'pages': reading.get('pages', []),
        'rule': 'indicia names the filename series and issue number; year only from a printed cover date',
        'fields': evidence, 'decided_at': time.time()}}


def notes(book):
    evidence = book['evidence']
    extra = ''
    if 'Publisher' in book['fields']:
        extra += ' The publisher is named the same way on the cover and on the credits or indicia pages.'
    if (evidence.get('fields') or {}).get('Series', {}).get('normalised'):
        extra += (" The series name is the filename's text with its spelling tidied ("
                  + ', '.join(evidence['fields']['Series']['normalised']['changes']) + ').')
    if evidence.get('tier') == 'credits':
        return ('In-book identification: the indicia text, read by the local model, names the series and issue number '
                'in the filename. No external source; a year comes only from a printed cover date.' + extra)
    if evidence.get('source') == FILENAME_NUMBER_SOURCE:
        return ('In-book identification: the cover text, read by the local model, agrees with the filename on the series '
                'title; the cover shows no plain issue number, so the number comes from the filename alone. No external '
                'source; creators and year are not taken from the cover.' + extra)
    numbered = bool(evidence['filename']['number'])
    return ('In-book identification: the cover text, read by the local model, agrees with the filename on '
            + ('the series title and issue number' if numbered else 'the title of this whole book')
            + '. No external source; creators and year are not taken from the cover.' + extra)


METHODS = {SOURCE: METHOD, FILENAME_NUMBER_SOURCE: FILENAME_NUMBER_METHOD, CREDITS_SOURCE: CREDITS_METHOD}


def entry(path, book, digest):
    fields = dict(book['fields'])
    changes = {key: {'before': '', 'after': value} for key, value in fields.items()}
    fields['Notes'] = notes(book)
    source = book['evidence'].get('source') or SOURCE
    return {'path': str(path), 'action': 'write', 'sha256': digest, 'changes': changes, 'fields': fields,
            'method': METHODS.get(source, METHOD), 'source': source, 'evidence': book['evidence']}
