import hashlib
import inspect
import io
import os
import struct
import tracemalloc
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
import app
import reverse_image
from test_worker import scratch_directory

NO_COVER='No cover could be read from this file.'


class CoverTests(unittest.TestCase):
    def test_cover_preview_selects_only_requested_image(self):
        with scratch_directory() as root:
            comic=Path(root)/'Comic.cbz'
            with zipfile.ZipFile(comic,'w') as archive:
                archive.writestr('01.jpg',b'cover');archive.writestr('02.png',b'second image')
            self.assertEqual(reverse_image.cover(comic),(b'cover','image/jpeg','.jpg'))
            self.assertEqual(reverse_image.cover(comic,1),(b'second image','image/png','.png'))
            with self.assertRaises(ValueError):reverse_image.cover(comic,2)


def picture(size=(300,450),color=(200,30,30),kind='JPEG',mode='RGB',**options):
    out=io.BytesIO()
    Image.new(mode,size,color).save(out,kind,**options)
    return out.getvalue()


def fingerprint(path):
    info=os.stat(path)
    return hashlib.sha256(Path(path).read_bytes()).hexdigest(),info.st_size,info.st_mtime_ns


class FileCoverPreviewTests(unittest.TestCase):
    """Cover in this file (UXSpec FileCover 2026-10-16): read-only, bounded, by comic id."""
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))

    def comic(self,name,members):
        path=self.root/name
        with zipfile.ZipFile(path,'w') as archive:
            for member,data in members:
                archive.writestr(member,data)
        return path

    def decoded(self,data):
        with Image.open(io.BytesIO(data)) as image:
            return image.format,image.size,image.convert('RGB').getpixel((image.width//2,image.height//2))

    def test_first_image_by_name_as_bounded_jpeg_and_archive_untouched(self):
        path=self.comic('Comic.cbz',[('02.jpg',picture(color=(0,0,255))),('01.png',picture((1200,1800),(255,0,0),'PNG')),
                                     ('ComicInfo.xml',b'<ComicInfo/>')])
        before,listing=fingerprint(path),sorted(os.listdir(self.root))
        kind,size,pixel=self.decoded(reverse_image.preview(path))
        self.assertEqual((fingerprint(path),sorted(os.listdir(self.root))),(before,listing))  # Bytes, size, mtime, no new files.
        self.assertEqual((kind,size),('JPEG',(480,720)))
        self.assertTrue(pixel[0]>200 and pixel[2]<60,pixel)  # 01.png, the image cover(path, 0) gives the rest of the app.
        self.assertEqual(reverse_image.cover(path)[2],'.png')
        small=self.comic('Small.cbz',[('01.jpg',picture())])
        self.assertEqual(self.decoded(reverse_image.preview(small))[1],(300,450))  # Never enlarged.

    def test_orientation_transparency_and_formats(self):
        exif=Image.Exif();exif[0x0112]=6  # Rotate 90 degrees when shown.
        turned=self.comic('Turned.cbz',[('01.jpg',picture((450,300),exif=exif.tobytes()))])
        self.assertEqual(self.decoded(reverse_image.preview(turned))[1],(300,450))
        clear=self.comic('Clear.cbz',[('01.png',picture((300,450),(255,0,0,0),'PNG','RGBA'))])
        self.assertTrue(all(abs(a-b)<8 for a,b in zip(self.decoded(reverse_image.preview(clear))[2],reverse_image.PREVIEW_BACKGROUND)))
        webp=self.comic('Web.cbz',[('01.webp',picture(kind='WEBP'))])
        self.assertEqual(self.decoded(reverse_image.preview(webp))[0],'JPEG')

    def test_every_unreadable_file_has_one_answer(self):
        (self.root/'Corrupt.cbz').write_bytes(b'PK\x03\x04'+b'\x00'*200)
        (self.root/'Rar.cbz').write_bytes(b'Rar!\x1a\x07\x01\x00'+b'\x00'*200)
        (self.root/'Rar.cbr').write_bytes(b'Rar!\x1a\x07\x00'+b'\x00'*200)
        (self.root/'Seven.cb7').write_bytes(b'7z\xbc\xaf\x27\x1c'+b'\x00'*200)
        unsupported=io.BytesIO();Image.new('RGB',(30,45)).save(unsupported,'TIFF')
        cases={'no images':self.comic('Empty.cbz',[('ComicInfo.xml',b'<ComicInfo/>')]),
               'corrupt ZIP':self.root/'Corrupt.cbz','RAR named .cbz':self.root/'Rar.cbz','.cbr':self.root/'Rar.cbr',
               '.cb7':self.root/'Seven.cb7','not an image':self.comic('Text.cbz',[('01.jpg',b'not a picture')]),
               'other format under an image name':self.comic('Tiff.cbz',[('01.jpg',unsupported.getvalue())]),
               'truncated image':self.comic('Cut.cbz',[('01.jpg',picture()[:300])]),
               'missing file':self.root/'Gone.cbz'}
        for label,path in cases.items():
            with self.subTest(label):
                before=fingerprint(path) if path.exists() else None
                with self.assertRaises(reverse_image.NoPreview) as caught:
                    reverse_image.preview(path)
                self.assertEqual(str(caught.exception),NO_COVER)
                if before:
                    self.assertEqual(fingerprint(path),before)

    def test_byte_and_pixel_limits(self):
        path=self.comic('Limits.cbz',[('01.jpg',picture((100,150)))])
        with patch.object(reverse_image,'COVER_BYTES',100),self.assertRaises(reverse_image.NoPreview):
            reverse_image.preview(path)
        with patch.object(reverse_image,'PREVIEW_PIXELS',100*150-1),self.assertRaises(reverse_image.NoPreview):
            reverse_image.preview(path)
        with patch.object(reverse_image,'PREVIEW_PIXELS',100*150):
            self.assertEqual(self.decoded(reverse_image.preview(path))[1],(100,150))
        huge=self.comic('Huge.cbz',[('01.png',picture((8000,8000),1,'PNG','1'))])  # 64 MP: refused from its header.
        with patch('PIL.ImageFile.ImageFile.load',side_effect=AssertionError('decoded')) as load:
            with self.assertRaises(reverse_image.NoPreview):
                reverse_image.preview(huge)
            load.assert_not_called()
        with patch('PIL.ImageFile.ImageFile.load',side_effect=AssertionError('decoded')) as load:  # Positive control.
            with self.assertRaises(reverse_image.NoPreview):
                reverse_image.preview(path)
            load.assert_called()

    def test_no_read_while_a_metadata_write_is_under_way(self):
        path=self.comic('Busy.cbz',[('01.jpg',picture())])
        temporary=Path(str(path)+'.metadata-tmp')
        temporary.write_bytes(b'')
        with patch.object(reverse_image,'open_shared') as opened,self.assertRaises(reverse_image.NoPreview):
            reverse_image.preview(path)
        opened.assert_not_called()
        temporary.unlink()
        real=reverse_image.open_shared
        def write_starts(target):
            handle=real(target)
            temporary.write_bytes(b'')
            return handle
        with patch.object(reverse_image,'open_shared',side_effect=write_starts),\
             patch.object(reverse_image,'thumbnail') as decode,self.assertRaises(reverse_image.NoPreview):
            reverse_image.preview(path)
        decode.assert_not_called()
        # The temporary is the one the metadata write creates before rewriting and removes after os.replace.
        self.assertIn("path.with_name(path.name + '.metadata-tmp')",inspect.getsource(app._write_metadata_guarded))

    @unittest.skipUnless(os.name=='nt','Windows sharing rules')
    def test_handle_allows_rename_and_delete_and_closes_before_decoding(self):
        path=self.comic('Shared.cbz',[('01.jpg',picture())])
        moved=self.root/'Moved.cbz'
        with open(path,'rb'),self.assertRaises(PermissionError):  # Positive control: a plain handle blocks it.
            os.replace(path,moved)
        with reverse_image.open_shared(app.filesystem_path(path)) as handle:
            handle.read(2)
            os.replace(path,moved)
            os.replace(moved,path)
        real=reverse_image.thumbnail
        def decode(data):
            # A write's os.replace onto the archive succeeds here: nothing holds the archive.
            os.replace(self.comic('Swap.cbz',[('01.jpg',picture(color=(0,255,0)))]),path)
            return real(data)
        with patch.object(reverse_image,'thumbnail',side_effect=decode):
            self.assertEqual(self.decoded(reverse_image.preview(path))[0],'JPEG')
        self.assertFalse(moved.exists())

    def test_endpoint_takes_a_comic_id_and_same_origin_only(self):
        path=self.comic('Endpoint.cbz',[('01.jpg',picture())])
        empty=self.comic('Blank.cbz',[('ComicInfo.xml',b'<ComicInfo/>')])
        def get(url,target=path,**headers):
            item=object.__new__(app.Handler)
            item.server=SimpleNamespace(server_port=8765)
            item.path=url
            item.headers={'Host':'127.0.0.1:8765',**headers}
            replies=[]
            item.respond=lambda payload,status=200,mime='application/json':replies.append((status,mime,payload))
            with patch.object(app,'comic',return_value={'id':7,'path':str(target)}) as lookup:
                item.do_GET()
            return replies[-1],lookup
        for site in ('same-origin',None):
            (status,mime,body),lookup=get('/api/cover?id=7',**({'Sec-Fetch-Site':site} if site else {}))
            self.assertEqual((status,mime,self.decoded(body)[0]),(200,'image/jpeg','JPEG'))
            lookup.assert_called_once_with(7)
        for url,headers in (('/api/cover?id=7',{'Sec-Fetch-Site':'cross-site'}),('/api/cover?id=7',{'Sec-Fetch-Site':'same-site'})):
            (status,_,_),lookup=get(url,**headers)
            self.assertEqual(status,403)
            lookup.assert_not_called()
        for url in ('/api/cover?id=7&path=C:/x.cbz','/api/cover?id=7&id=8','/api/cover?path=C:/x.cbz','/api/cover?id=x'):
            (status,_,_),lookup=get(url)
            self.assertEqual(status,400,url)
            lookup.assert_not_called()
        # A malformed id or index is a clean 400, never Python's int() text (Futaba 0.2.3 m6).
        for url,message in (('/api/cover?id=abc','Choose a comic.'),('/api/cover?id=abc&index=0','Choose a comic.'),('/api/cover?id=-1','Choose a comic.'),
                            ('/api/cover?id=7&index=x','Choose a suitable image among the first five archive images.')):
            (status,_,body),lookup=get(url)
            self.assertEqual((status,body),(400,{'error':message}),url)
            lookup.assert_not_called()
        (status,_,body),_=get('/api/cover?id=7',empty)
        self.assertEqual((status,body),(400,{'error':NO_COVER}))
        (status,mime,body),_=get('/api/cover?id=7&index=0')  # The Archive image picker is unchanged.
        self.assertEqual((status,mime,body),(200,'image/jpeg',picture()))


def lying(path,data,method,declared):
    """An archive whose one image really holds `data` while both headers declare `declared` bytes."""
    with zipfile.ZipFile(path,'w',compression=method) as archive:
        archive.writestr('01.jpg',data)
    raw=bytearray(path.read_bytes())
    struct.pack_into('<I',raw,raw.index(b'PK\x03\x04')+22,declared)
    struct.pack_into('<I',raw,raw.rindex(b'PK\x01\x02')+24,declared)
    path.write_bytes(bytes(raw))


def peak(action):
    """Peak traced memory while running action, and what it raised."""
    tracemalloc.start()
    try:
        try:
            action()
        except Exception as exc:
            return tracemalloc.get_traced_memory()[1],exc
        return tracemalloc.get_traced_memory()[1],None
    finally:
        tracemalloc.stop()


class BoundedImageReadTests(unittest.TestCase):
    """Senua v0.2.3 P1: cover() and preview() are bounded by the bytes actually decompressed."""
    REAL=16*1024*1024
    LIMIT=1024*1024

    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))

    def test_an_entry_larger_than_it_declares_is_capped_for_deflate_bzip2_and_lzma(self):
        data=bytes(self.REAL)
        for method in (zipfile.ZIP_DEFLATED,zipfile.ZIP_BZIP2,zipfile.ZIP_LZMA):
            with self.subTest(method=method):
                path=self.root/('Lying-'+str(method)+'.cbz')
                lying(path,data,method,1000)
                with zipfile.ZipFile(path) as archive:
                    info=reverse_image.images(archive)[0]
                    self.assertEqual((info.file_size,info.compress_type),(1000,method))  # The fixture does lie.
                    # Positive control: archive.read() decompresses the real size before any check.
                    used,_=peak(lambda:archive.read(info))
                    self.assertGreater(used,self.REAL)
                with patch.object(reverse_image,'COVER_BYTES',self.LIMIT):
                    used,raised=peak(lambda:reverse_image.cover(path))
                    self.assertIsNotNone(raised)
                    self.assertLess(used,4*self.LIMIT)
                    with patch.object(reverse_image,'thumbnail') as decode:
                        used,raised=peak(lambda:reverse_image.preview(path))
                    self.assertIsInstance(raised,reverse_image.NoPreview)
                    self.assertLess(used,4*self.LIMIT)
                    decode.assert_not_called()

    def test_honest_stored_and_deflated_covers_still_read_and_others_are_refused(self):
        for method in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):
            path=self.root/('Honest-'+str(method)+'.cbz')
            with zipfile.ZipFile(path,'w',compression=method) as archive:
                archive.writestr('01.jpg',picture())
            self.assertEqual(reverse_image.cover(path)[0],picture())
            self.assertEqual(Image.open(io.BytesIO(reverse_image.preview(path))).format,'JPEG')
        for method in (zipfile.ZIP_BZIP2,zipfile.ZIP_LZMA):  # The file would choose the decoder's memory.
            path=self.root/('Other-'+str(method)+'.cbz')
            with zipfile.ZipFile(path,'w',compression=method) as archive:
                archive.writestr('01.jpg',picture())
            with self.assertRaises(ValueError):
                reverse_image.cover(path)
            with self.assertRaises(reverse_image.NoPreview):
                reverse_image.preview(path)

    def test_the_running_total_is_enforced_even_if_the_member_overruns(self):
        class Overrun:
            def open(self,info):
                return io.BytesIO(b'x'*(reverse_image.COVER_BYTES+1))
        info=zipfile.ZipInfo('01.jpg')
        info.file_size=info.compress_size=1
        with self.assertRaises(ValueError):
            reverse_image.read_image(Overrun(),info)
        info2=zipfile.ZipInfo('01.jpg')
        info2.file_size=info2.compress_size=1
        class Exact:
            def open(self,info):
                return io.BytesIO(b'x'*reverse_image.COVER_BYTES)
        self.assertEqual(len(reverse_image.read_image(Exact(),info2)),reverse_image.COVER_BYTES)  # Control: at the limit it reads.


if __name__=='__main__':
    unittest.main()
