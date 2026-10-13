"""Imprints as their own field (Sergei 2026-10-13).

The main publisher goes in Publisher (Image Comics, DC Comics), the brand line in Imprint
(Skybound, Vertigo, Black Label). ComicInfo has had <Imprint> since schema 2.0; YACReader
9.13 and later read it and show it in a comic's Properties (Authors tab).

A small, explicit table maps known imprints to their parent publisher. A name not in it is
left exactly as it came. When an outside source names an imprint as the publisher (Metron
lists Skybound as a publisher), it is split before anything is written or compared, so it
agrees with an in-book "Image Comics" instead of replacing it (Kroma 001, pilot 2026-10-13).
"""
import research

# Imprint (as sources print it) -> parent publisher, under the in-book canonical names.
IMPRINT_PARENTS = {
    'Skybound': 'Image Comics', 'Skybound Entertainment': 'Image Comics', 'Top Cow': 'Image Comics',
    'Top Cow Productions': 'Image Comics', 'Shadowline': 'Image Comics', 'Ghost Machine': 'Image Comics',
    'Vertigo': 'DC Comics', 'Vertigo Comics': 'DC Comics', 'Black Label': 'DC Comics', 'DC Black Label': 'DC Comics',
    'WildStorm': 'DC Comics', 'WildStorm Productions': 'DC Comics', 'Young Animal': 'DC Comics', 'DC Young Animal': 'DC Comics',
    'Icon': 'Marvel', 'Icon Comics': 'Marvel', 'Epic': 'Marvel', 'Epic Comics': 'Marvel', 'MAX': 'Marvel', 'Marvel MAX': 'Marvel',
    'Marvel Knights': 'Marvel',
    'Archaia': 'BOOM! Studios', 'BOOM! Box': 'BOOM! Studios', 'KaBOOM!': 'BOOM! Studios',
    'Berger Books': 'Dark Horse Comics',
}
_KEYS = {research.normalize(name): parent for name, parent in IMPRINT_PARENTS.items()}
PUBLISHER_ALIASES = {
    'Image Comics': ('Image Comics, Inc.',),
    'Marvel': ('Marvel Comics Group', 'Marvel Entertainment'),
    'DC Comics': ('DC Comics Inc.', 'DC Entertainment'),
    'Dark Horse Comics': ('Dark Horse Comics, Inc.',),
    'IDW Publishing': ('IDW Publishing, LLC',),
    'Oni Press': ('Oni Press, Inc.',),
    'Archie Comics': ('Archie Comic Publications',),
}
_PUBLISHER_KEYS = {research.normalize(alias): name for name, aliases in PUBLISHER_ALIASES.items() for alias in aliases}


DATE_AWARE = {research.normalize(name) for name in ('WildStorm','WildStorm Productions','Archaia')}


def publication_year(value):
    text=str(value or '').strip()
    return int(text) if len(text)==4 and text.isdigit() and 1900<=int(text)<=2100 else None


def parent_of(value, year=None):
    """The parent publisher when `value` is a known imprint, else ''."""
    key=research.normalize(value or '')
    if key in DATE_AWARE:
        year=publication_year(year)
        if year is None:return ''
        if key==research.normalize('Archaia'):
            return 'BOOM! Studios' if year>=2013 else ''  # Independent before acquisition.
        return 'Image Comics' if year<1999 else 'DC Comics'
    return _KEYS.get(key, '')


def split(fields, year=None):
    """Source fields with an imprint named as Publisher moved to Imprint, under its parent.

    An Imprint the source already gave is kept. Unknown names, and fields without a
    Publisher, come back unchanged."""
    publisher = str(fields.get('Publisher') or '').strip()
    year=fields.get('Year') if year is None else year
    if research.normalize(publisher) in DATE_AWARE and publication_year(year) is None:
        return {k:v for k,v in fields.items() if k not in ('Publisher','Imprint')}
    parent = parent_of(publisher,year)
    if not parent:
        return fields
    result = dict(fields, Publisher=parent)
    if not str(fields.get('Imprint') or '').strip():
        result['Imprint'] = publisher
    return result


def publisher_key(value, year=None):
    """Compare publishers as the same house: "Skybound" and "Image Comics", "Image" and "Image Comics"."""
    value = parent_of(value,year) or value
    value = _PUBLISHER_KEYS.get(research.normalize(value), value)
    return research.normalize(research.canonical_publisher(value) or value)
