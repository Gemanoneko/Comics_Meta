"""Assemble only authenticated ZIP/wheel inputs; never run package installers."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / 'build'
INPUT = BUILD / 'downloads'
STAGE = BUILD / 'staged'
LOCK = json.loads((ROOT / 'scripts/packaging/runtime-lock.json').read_text('utf-8'))


def plain(path):
    """No junction/symlink ancestor may redirect packaging writes."""
    for part in (path, *path.parents):
        try:
            attributes = part.lstat().st_file_attributes
        except FileNotFoundError:
            continue
        if attributes & 0x400:
            raise RuntimeError(f'Reparse path refused: {part}')
    return path


def authenticated(item):
    path = plain(INPUT / item['filename'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
        raise RuntimeError(f'Input checksum mismatch: {path.name}')
    return path


def unzip(archive, target, wheel=False):
    seen = set()
    total = 0
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            name = entry.filename
            parts = PurePosixPath(name).parts
            if not parts or '\\' in name or ':' in name or name.startswith('/') or '..' in parts:
                raise RuntimeError(f'Unsafe ZIP member: {name}')
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise RuntimeError(f'ZIP symlink refused: {name}')
            if wheel and parts[0].endswith('.data'):
                if len(parts) < 3 or parts[1] not in ('purelib', 'platlib'):
                    raise RuntimeError(f'Unsupported wheel relocation: {name}')
                parts = parts[2:]
            key = '/'.join(parts).casefold()
            if key in seen:
                raise RuntimeError(f'Duplicate ZIP member: {name}')
            seen.add(key)
            destination = plain(target.joinpath(*parts))
            if entry.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            total += entry.file_size
            if total > 600_000_000:
                raise RuntimeError('Archive expansion limit exceeded')
            if destination.exists():
                raise RuntimeError(f'Overlapping vendored file: {name}')
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.open(entry) as stream, destination.open('xb') as output:
                shutil.copyfileobj(stream, output)


def main():
    if sys.platform != 'win32' or sys.version_info[:3] != (3, 14, 8):
        raise RuntimeError('Assembly requires audited CPython 3.14.8 on Windows')
    plain(STAGE)
    try:
        STAGE.lstat()
    except FileNotFoundError:
        pass
    else:
        raise RuntimeError('Staged output already exists; preserve or remove reviewed disposable output first')
    # Authenticate all inputs before creating the staged output.
    archives = [authenticated(LOCK['python']), *(authenticated(w) for w in LOCK['wheels'])]
    STAGE.mkdir(parents=True, exist_ok=False)
    python = STAGE / 'runtime/python'
    python.mkdir(parents=True)
    unzip(archives[0], python)
    packages = python / 'Lib/site-packages'
    packages.mkdir(parents=True)
    for wheel in archives[1:]:
        unzip(wheel, packages, wheel=True)
    (python / 'python314._pth').write_text('python314.zip\n.\nLib/site-packages\n../../engine\n', encoding='utf-8')
    engine = STAGE / 'engine'
    engine.mkdir()
    for source in sorted(ROOT.glob('*.py')):
        plain(source)
        shutil.copy2(source, engine / source.name)
    for name in ('VERSION', 'requirements.txt'):
        shutil.copy2(plain(ROOT / name), engine / name)
    # Static tree only: refuse every reparse point before copying.
    static = plain(ROOT / 'static')
    for source in static.rglob('*'):
        plain(source)
    shutil.copytree(static, engine / 'static')
    licenses = STAGE / 'licenses'
    licenses.mkdir()
    shutil.copy2(python / 'LICENSE.txt', licenses / 'Python-LICENSE.txt')
    shutil.copy2(ROOT / 'scripts/packaging/runtime-lock.json', licenses / 'runtime-lock.json')
    (licenses / 'THIRD-PARTY.txt').write_text(
        'CPython: PSF license; Python-LICENSE.txt. Vendored wheel licenses are retained in runtime/python/Lib/site-packages.\n'
        '7-Zip: LGPL/BSD/unRAR restriction; runtime/7zip/License.txt. Unmodified upstream source: https://github.com/ip7z/7zip/tree/26.04\n'
        'Runtime provenance and exact input SHA-256: runtime-lock.json.\n', encoding='utf-8')


def guard_output(mode):
    if sys.platform != 'win32':
        raise RuntimeError('Output guard requires Windows native file attributes')
    if mode == '--guard-prepare':
        for target in (BUILD, INPUT):
            plain(target)
            target.mkdir(parents=True, exist_ok=True)
            plain(target)
        for entry in INPUT.rglob('*'):
            plain(entry)
    elif mode == '--guard-extract':
        target = plain(BUILD / 'sevenzip-extracted')
        # lstat sees dangling junctions/symlinks; exclusive mkdir never treats
        # any existing entry as safe empty output.
        target.mkdir(exist_ok=False)
        plain(target)
        plain(STAGE / 'runtime/7zip')
    elif mode == '--guard-build':
        for target in (ROOT / 'dist', BUILD / 'cache/electron', BUILD / 'cache/electron-builder'):
            plain(target)
            target.mkdir(parents=True, exist_ok=True)
            plain(target)
            for entry in target.rglob('*'):
                plain(entry)
        plain(STAGE)
        for entry in STAGE.rglob('*'):
            plain(entry)
    else:
        raise RuntimeError('Unsupported fixed output guard mode')


if __name__ == '__main__':
    raise RuntimeError('Legacy runtime assembly retired; use separately reviewed pinned Job graph and complete held runtime manifest')
