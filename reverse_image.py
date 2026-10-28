"""Local cover extraction shared by identification and browser search."""
import io
import os
import threading
import zipfile
from pathlib import Path
import app

IMAGE_EXTENSIONS=('.jpg','.jpeg','.png','.webp','.gif','.bmp')
COVER_BYTES=20_000_000
READ_CHUNK=1<<20  # Each read decompresses at most this much (deflate's max_length).
READABLE=(zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED)  # What real comics use.


def images(archive):
    """Archive images in name order. The first is the comic's cover everywhere in the app."""
    return sorted((i for i in archive.infolist() if i.filename.lower().endswith(IMAGE_EXTENSIONS)),key=lambda i:i.filename)


def read_image(archive, info):
    """One image's bytes, bounded by the bytes actually decompressed (Senua v0.2.3 P1).

    ZipInfo sizes come from the file and can lie. archive.read() decompresses a whole member
    before any size is enforced: up to 2 GiB per call for deflate, and for bzip2 or LZMA the
    file also chooses the decoder's memory. So only stored and deflated members are read;
    reading through open() in READ_CHUNK pieces bounds every decompression call, and the
    running total is refused as soon as it passes COVER_BYTES. ZipExtFile also stops at the
    declared size, then fails its CRC check. Shared by cover() and preview()."""
    if info.compress_type not in READABLE or info.file_size>COVER_BYTES or info.compress_size>2*COVER_BYTES:
        raise ValueError('Choose a suitable image among the first five archive images.')
    data=bytearray()
    with archive.open(info) as member:
        while chunk:=member.read(READ_CHUNK):
            data+=chunk
            if len(data)>COVER_BYTES:
                raise ValueError('Choose a suitable image among the first five archive images.')
    return bytes(data)


def cover(path, index=0):
    with zipfile.ZipFile(app.filesystem_path(path)) as archive:
        found=images(archive)
        if not 0 <= index < min(5,len(found)):
            raise ValueError('Choose a suitable image among the first five archive images.')
        data=read_image(archive,found[index])
        extension=Path(found[index].filename).suffix.lower()
        mime={'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp','.gif':'image/gif','.bmp':'image/bmp'}[extension]
        return data,mime,extension


# "Cover in this file" on the recovery screens (UXSpec FileCover 2026-10-16).
PREVIEW_PIXELS=40_000_000  # Larger first images are not previewed: bounds decode time and memory.
PREVIEW_BOX=(480,720)      # 3x the 160 x 240 slot, so it stays sharp at 200% zoom on a 1.5x screen.
PREVIEW_WAIT=10            # Seconds a request waits for one of the decode slots.
PREVIEW_BACKGROUND=(18,21,28)  # The slot's #12151c, under transparent pixels.
_decoders=threading.BoundedSemaphore(2)
_kernel=None


class NoPreview(ValueError):
    """One answer for every cause; the dashboard does not diagnose (spec section 4)."""
    def __init__(self):
        super().__init__('No cover could be read from this file.')


def open_shared(path):
    """Open read-only, letting other programs rename or delete the file meanwhile.

    Python's open() omits FILE_SHARE_DELETE on Windows, so a reader would make a
    conversion's rename or removal of the original fail. Replacing the file
    (os.replace onto it) still fails while any handle is open: see writing()."""
    if os.name!='nt':
        return open(path,'rb')
    global _kernel
    import ctypes, msvcrt
    from ctypes import wintypes
    if _kernel is None:
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateFileW.restype=wintypes.HANDLE
        kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        _kernel=kernel
    # GENERIC_READ; share read, write and delete; OPEN_EXISTING; not inheritable.
    handle=_kernel.CreateFileW(str(path),0x80000000,0x7,None,3,0x80,None)
    if handle is None or handle==wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY)
    except BaseException:
        _kernel.CloseHandle(handle)
        raise
    return os.fdopen(descriptor,'rb')


def writing(path):
    """True while app.write_metadata is rewriting this archive. Its temporary exists from
    before the rewrite until after os.replace swaps it in, and Windows refuses that replace
    while any other handle on the archive is open; before the temporary exists the writer
    only reads. Its write guard is not probed: a writer that finds it held gives up."""
    return path.with_name(path.name+'.metadata-tmp').exists()


def preview(path):
    """The comic's cover (the first image, as cover(path, 0)) as a small JPEG.

    Read-only: opened for reading only, so nothing is written and the archive's
    modification time is unchanged. Nothing is opened while a metadata write is under
    way, and the handle is closed before decoding, so it is held only while the image
    bytes are read. Only real ZIP archives are read; RAR and 7-Zip files (.cbr, .cb7, or
    renamed .cbz) raise NoPreview like every other failure."""
    try:
        source=app.filesystem_path(path)
        if writing(source) or not _decoders.acquire(timeout=PREVIEW_WAIT):
            raise NoPreview()
        try:
            with open_shared(source) as handle:
                if writing(source):  # A write that started while this was opening.
                    raise NoPreview()
                with zipfile.ZipFile(handle) as archive:
                    found=images(archive)
                    if not found:
                        raise NoPreview()
                    data=read_image(archive,found[0])
            return thumbnail(data)
        finally:
            _decoders.release()
    except NoPreview:
        raise
    except Exception as exc:
        raise NoPreview() from exc


def thumbnail(data):
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(data),formats=('JPEG','PNG','WEBP','GIF','BMP')) as image:
        width,height=image.size
        if width<1 or height<1 or width*height>PREVIEW_PIXELS:
            raise NoPreview()
        image.getexif()  # Read the orientation before resizing replaces the pixels.
        picture=image  # thumbnail() decodes a JPEG at a reduced scale (draft) before resizing.
        if picture.mode=='P':
            picture=picture.convert('RGBA' if 'transparency' in picture.info else 'RGB')
        picture.thumbnail(PREVIEW_BOX)
        picture=ImageOps.exif_transpose(picture)
        if picture.mode in ('RGBA','LA','PA'):
            flat=Image.new('RGB',picture.size,PREVIEW_BACKGROUND)
            flat.paste(picture,mask=picture.getchannel('A'))
            picture=flat
        elif picture.mode!='RGB':
            picture=picture.convert('RGB')
        out=io.BytesIO()
        picture.save(out,'JPEG',quality=85)
        return out.getvalue()
