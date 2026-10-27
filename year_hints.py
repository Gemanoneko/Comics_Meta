"""Years a filename or its folder states outside app.parse_name's plain "(YYYY)" (Enrichment B, Sergei 2026-10-26).

Pure text rules, no I/O. app.parse_name keeps reading only "(YYYY)"; these hints are used by Metron's lookup
(metron.identity_year) so the catalog and the other sources are unchanged.

- filename_year: "(2007-02)" and "(2007-02-15)" cover dates, a bracket that opens with a year and goes on with
  words ("(1993-Dark Horse)", "(2022, 2nd edition)"), and "[2004]". A year range ("(1993-1995)") is a run, not
  a cover year, and is not read. A bare year outside brackets is never read: app.parse_name already takes a
  trailing one as the issue number, and titles hold years ("Spider-Man 2099", "2000 AD").
- folder_year: the start year a folder names in brackets, "Catwoman (2002)" or "Lady Death (1994-1996)". It is
  the series' start year, not the issue's cover year.
"""
import re
from pathlib import PureWindowsPath

YEAR = r'(?:19|20)\d{2}'
COVER_DATE = re.compile(r'\((' + YEAR + r')-(?:0[1-9]|1[0-2])(?:-(?:0[1-9]|[12]\d|3[01]))?\)')
YEAR_WITH_WORDS = re.compile(r'\((' + YEAR + r')\s*[-,]\s*(?!' + YEAR + r'\b)[^)]*[A-Za-z][^)]*\)')
SQUARE = re.compile(r'\[(' + YEAR + r')\]')
FOLDER = re.compile(r'\((' + YEAR + r')(?:\s*[-–]\s*(?:' + YEAR + r')?\s*)?\)')


def filename_year(name):
    """The cover year a filename states in a form app.parse_name does not read, or ''."""
    stem = PureWindowsPath(str(name)).stem
    found = []
    for pattern in (COVER_DATE, YEAR_WITH_WORDS, SQUARE):
        found += pattern.findall(stem)
    years = sorted(set(found))
    return years[0] if len(years) == 1 else ''  # Two different years: no hint.


def folder_year(path):
    """The series start year the comic's folder names in brackets, or ''."""
    folder = PureWindowsPath(str(path)).parent.name
    years = sorted(set(FOLDER.findall(folder)))
    return years[0] if len(years) == 1 else ''
