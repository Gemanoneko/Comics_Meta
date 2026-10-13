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


def parent_of(value):
    """The parent publisher when `value` is a known imprint, else ''."""
    return _KEYS.get(research.normalize(value or ''), '')


def split(fields):
    """Source fields with an imprint named as Publisher moved to Imprint, under its parent.

    An Imprint the source already gave is kept. Unknown names, and fields without a
    Publisher, come back unchanged."""
    publisher = str(fields.get('Publisher') or '').strip()
    parent = parent_of(publisher)
    if not parent:
        return fields
    result = dict(fields, Publisher=parent)
    if not str(fields.get('Imprint') or '').strip():
        result['Imprint'] = publisher
    return result


def publisher_key(value):
    """Compare publishers as the same house: "Skybound" and "Image Comics", "Image" and "Image Comics"."""
    value = parent_of(value) or value
    return research.normalize(research.canonical_publisher(value) or value)
