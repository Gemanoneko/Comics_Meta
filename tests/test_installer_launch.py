"""Pure/mocked updater-launch regressions; no executable is ever launched."""
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'desktop' / 'installer_launch.py'
SPEC = importlib.util.spec_from_file_location('installer_launch', SOURCE)
launch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launch)


def payload(**changes):
    result = {'path': r'C:\Owned Test\payload.exe', 'size': 4,
              'sha512': base64.b64encode(hashlib.sha512(b'test').digest()).decode(), 'parent_pid': 123}
    result.update(changes)
    return result


class FakeWindows:
    def __init__(self, fail=None, early=None):
        self.events = []
        self.fail = fail
        self.early = early
        self.handles = []
        self.receipts = []

    def parent(self, pid):
        self.events.append(('parent', pid))
        if self.fail == 'parent':raise launch.LaunchError('parent','parent_unavailable')
        return 'parent'

    def alive(self, handle):
        self.events.append(('alive',handle))
        return self.fail != 'parent_exited'

    def hold(self, path, directory=False):
        self.events.append(('hold', path, directory))
        if self.fail == 'hold':raise launch.LaunchError('hold','unsafe_file_type')
        handle = ('directory' if directory else 'payload') + str(len(self.handles))
        self.handles.append(handle)
        return handle

    def verify(self, handle, size, digest, deadline=None):
        self.events.append(('verify',handle,size,digest))
        if self.fail == 'verify':raise launch.LaunchError('verify','digest_mismatch')

    def create(self, request):
        self.events.append(('create', launch.arguments(request)))
        if self.fail == 'create':raise launch.LaunchError('create','create_failed')
        return 'installer', 456

    def observe(self, handle, ms):
        self.events.append(('observe',handle,ms))
        return self.early

    def receipt(self, value):
        self.events.append(('receipt',value))
        self.receipts.append(value)
        self.assert_owned = not any(event[0] == 'close' for event in self.events)

    def wait(self, handle):
        self.events.append(('wait',handle))
        assert all(('close', h) not in self.events for h in self.handles)

    def close(self, handle):
        self.events.append(('close',handle))


class ValidationTests(unittest.TestCase):
    def test_exact_canonical_digest_and_bounded_size(self):
        request = launch.validate_request(payload())
        self.assertEqual(request['digest'],hashlib.sha512(b'test').digest())
        for size in [True,0,-1,launch.MAX_SIZE+1,'4']:
            with self.subTest(size=size),self.assertRaises(launch.LaunchError):launch.validate_request(payload(size=size))
        for digest in ['wrong',payload()['sha512']+' ',payload()['sha512'][:-2]+'AA']:
            with self.subTest(digest=digest),self.assertRaises(launch.LaunchError):launch.validate_request(payload(sha512=digest))

    def test_paths_refuse_interpretation_aliases(self):
        for path in [r'payload.exe',r'\\server\share\payload.exe',r'\\?\C:\payload.exe',
                     r'C:\folder\..\payload.exe',r'C:\folder\payload.exe:stream',r'C:\NUL.exe',
                     'C:\\folder\\payload.exe\n',r'C:\folder.\payload.exe',r'C:\folder\payload.cmd']:
            with self.subTest(path=path),self.assertRaises(launch.LaunchError):launch.validate_request(payload(path=path))

    def test_qa_directory_remains_one_last_argument(self):
        request=launch.validate_request(payload(install_dir=r'C:\Owned QA\Install'))
        self.assertEqual(launch.arguments(request),[request['path'],'--updated','/S','--force-run',r'/D=C:\Owned QA\Install'])
        for extra in [dict(unknown='ignored'),dict(parent_pid=True),dict(install_dir=r'..\bad')]:
            with self.subTest(extra=extra),self.assertRaises(launch.LaunchError):launch.validate_request(payload(**extra))

    def test_ancestors_root_first(self):
        self.assertEqual(launch.ancestors(r'C:\Owned Test\deep\payload.exe'),['C:\\',r'C:\Owned Test',r'C:\Owned Test\deep'])

    def test_bounded_line_protocol_has_sanitized_failure(self):
        for raw in [b'',b'{}',b'x'*(launch.MAX_INPUT+1)+b'\n',b'not json\n',b'{"path":"private secret"}\n']:
            receipts=[]
            result=launch.main(io.BytesIO(raw),FakeWindows(),receipts.append)
            self.assertEqual(result,1)
            self.assertEqual(len(receipts),1)
            self.assertFalse(receipts[0]['started'])
            self.assertNotIn('private',json.dumps(receipts))

    def test_second_line_and_duplicate_fields_refused(self):
        data=json.dumps(payload()).encode()+b'\n'
        duplicate=data[:-2]+b',"size":4}\n'
        for raw in [data+b'{}\n',duplicate]:
            receipts=[]
            self.assertEqual(launch.main(io.BytesIO(raw),FakeWindows(),receipts.append),1)
            self.assertFalse(receipts[0]['started'])



class NativeContractTests(unittest.TestCase):
    def test_create_follows_all_held_handles_and_hash(self):
        native=FakeWindows()
        request=launch.validate_request(payload())
        self.assertEqual(launch.run(request,native,native.receipt),0)
        names=[event[0] for event in native.events]
        self.assertLess(names.index('verify'),names.index('create'))
        self.assertLess(names.index('create'),names.index('observe'))
        self.assertLess(names.index('observe'),names.index('receipt'))
        self.assertLess(names.index('receipt'),names.index('wait'))
        self.assertLess(names.index('wait'),names.index('close'))
        held=[event for event in native.events if event[0]=='hold']
        self.assertTrue(all(event[2] for event in held[:-1]))
        self.assertFalse(held[-1][2])
        self.assertTrue(native.assert_owned)
        self.assertEqual(native.receipts,[{'started':True,'accepted':True,'phase':'started','installer_pid':456}])

    def test_invalid_missing_or_reparse_payload_never_creates_process(self):
        for phase in ['parent','hold','verify']:
            native=FakeWindows(fail=phase)
            self.assertEqual(launch.run(launch.validate_request(payload()),native,native.receipt),1)
            self.assertNotIn('create',[event[0] for event in native.events])
            self.assertEqual(len(native.receipts),1)
            self.assertFalse(native.receipts[0]['started'])
            self.assertEqual(native.receipts[0]['phase'],phase)

    def test_create_failure_never_reports_started(self):
        native=FakeWindows(fail='create')
        self.assertEqual(launch.run(launch.validate_request(payload()),native,native.receipt),1)
        self.assertEqual(native.receipts,[{'started':False,'accepted':False,'phase':'create','code':'create_failed'}])

    def test_early_nonzero_exit_is_not_success_and_keeps_handles_until_exit(self):
        native=FakeWindows(early=17)
        self.assertEqual(launch.run(launch.validate_request(payload()),native,native.receipt),1)
        self.assertEqual(native.receipts,[{'started':True,'accepted':False,'phase':'observe','code':'installer_exited_early'}])
        names=[event[0] for event in native.events]
        self.assertLess(names.index('wait'),names.index('close'))

    def test_early_zero_exit_is_not_final_install_proof(self):
        native=FakeWindows(early=0)
        self.assertEqual(launch.run(launch.validate_request(payload()),native,native.receipt),1)
        self.assertTrue(native.receipts[0]['started'])
        self.assertFalse(native.receipts[0]['accepted'])
        self.assertEqual(native.receipts[0]['code'],'installer_exited_early')

    def test_hash_setup_deadline_forbids_late_create(self):
        native=FakeWindows()
        with patch.object(launch.time,'monotonic',side_effect=[0,1,2,3,4,9]):
            self.assertEqual(launch.run(launch.validate_request(payload()),native,native.receipt),1)
        self.assertNotIn('create',[event[0] for event in native.events])
        self.assertEqual(native.receipts[0]['phase'],'deadline')
        self.assertFalse(native.receipts[0]['started'])

    def test_parent_exit_during_verification_prevents_create(self):
        native=FakeWindows(fail='parent_exited')
        self.assertEqual(launch.run(launch.validate_request(payload()),native,native.receipt),1)
        names=[event[0] for event in native.events]
        self.assertIn('verify',names)
        self.assertIn('alive',names)
        self.assertNotIn('create',names)
        self.assertFalse(native.receipts[0]['started'])
        self.assertEqual(native.receipts[0]['code'],'parent_exited_before_launch')

    def test_stdout_failure_keeps_payload_until_actual_exit(self):
        native=FakeWindows()
        calls=[]
        def broken_receipt(value):
            calls.append(value)
            raise BrokenPipeError()
        self.assertEqual(launch.run(launch.validate_request(payload()),native,broken_receipt),1)
        self.assertEqual(len(calls),1)
        self.assertTrue(calls[0]['started'])
        names=[event[0] for event in native.events]
        self.assertLess(names.index('wait'),names.index('close'))


class CapsuleContractTests(unittest.TestCase):
    def test_copied_runtime_remains_held_until_installer_exit(self):
        import os, tempfile
        with tempfile.TemporaryDirectory(dir=os.environ['COMICS_META_TEST_SCRATCH']) as folder:
            root=Path(folder)
            (root/'runtime/python').mkdir(parents=True)
            (root/'engine').mkdir()
            files={'python.exe':b'synthetic executable','python314.dll':b'synthetic dll','python314.zip':b'synthetic zip','python314._pth':b'python314.zip\n.\n../../engine\n'}
            for name,raw in files.items():(root/'runtime/python'/name).write_bytes(raw)
            helper=b'synthetic helper'
            (root/'engine/installer_launch.py').write_bytes(helper)
            manifest={'schema':1,'python':{'files':[{'path':name,'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in files.items()],'directories':[]},'helperSha256':hashlib.sha256(helper).hexdigest()}
            (root/'runtime-manifest.json').write_text(json.dumps(manifest))
            native=FakeWindows()
            request=launch.validate_request(payload(capsule_root=str(root)))
            with patch.object(launch,'__file__',str(root/'engine/installer_launch.py')),patch.object(launch.sys,'executable',str(root/'runtime/python/python.exe')):
                self.assertEqual(launch.run(request,native,native.receipt),0)
            paths=[event[1] for event in native.events if event[0]=='hold']
            self.assertIn(str(root/'runtime/python/python314.dll'),paths)
            self.assertIn(str(root/'engine/installer_launch.py'),paths)
            self.assertLess(next(i for i,e in enumerate(native.events) if e[0]=='wait'),next(i for i,e in enumerate(native.events) if e[0]=='close'))
            (root/'runtime/python/extra.py').write_text('foreign')
            native=FakeWindows()
            with patch.object(launch,'__file__',str(root/'engine/installer_launch.py')),patch.object(launch.sys,'executable',str(root/'runtime/python/python.exe')):
                self.assertEqual(launch.run(request,native,native.receipt),1)
            self.assertNotIn('create',[event[0] for event in native.events])
            self.assertFalse(native.receipts[0]['started'])
            (root/'runtime/python/extra.py').unlink()
            escaped=b'python314.zip\n.\n../../../outside\n'
            (root/'runtime/python/python314._pth').write_bytes(escaped)
            for item in manifest['python']['files']:
                if item['path']=='python314._pth':item['sha256']=hashlib.sha256(escaped).hexdigest()
            (root/'runtime-manifest.json').write_text(json.dumps(manifest))
            native=FakeWindows()
            with patch.object(launch,'__file__',str(root/'engine/installer_launch.py')),patch.object(launch.sys,'executable',str(root/'runtime/python/python.exe')):
                self.assertEqual(launch.run(request,native,native.receipt),1)
            self.assertNotIn('create',[event[0] for event in native.events])
            self.assertEqual(native.receipts[0]['code'],'capsule_module_path_escapes')


@unittest.skipUnless(os.name == 'nt', 'native Windows share modes')
class NativeShareModeTests(unittest.TestCase):
    """Real CreateFileW holds on scratch folders only; nothing is launched."""
    def sharing_violation(self, action):
        with self.assertRaises(PermissionError) as caught:action()
        self.assertEqual(caught.exception.winerror,32)

    def test_directory_hold_keeps_its_name_but_allows_child_atomic_saves(self):
        native=launch.Windows()
        with tempfile.TemporaryDirectory(dir=os.environ['COMICS_META_TEST_SCRATCH']) as folder:
            held,empty=Path(folder)/'held',Path(folder)/'empty'
            held.mkdir();empty.mkdir()
            (held/'state.json').write_text('old');(held/'state.json.tmp').write_text('new')
            (Path(folder)/'outside.txt').write_text('moved')
            handles=[native.hold(str(held),directory=True),native.hold(str(empty),directory=True)]
            try:
                os.replace(held/'state.json.tmp',held/'state.json')  # Atomic save inside a held ancestor.
                os.replace(Path(folder)/'outside.txt',held/'moved.txt')
                self.assertEqual((held/'state.json').read_text(),'new')
                self.sharing_violation(lambda:os.rename(held,Path(folder)/'renamed'))
                self.sharing_violation(lambda:os.rmdir(empty))
            finally:
                for handle in handles:native.close(handle)
            os.rename(held,Path(folder)/'renamed')
            os.rmdir(empty)

    def test_old_read_only_directory_share_blocks_child_saves(self):
        # Positive control: the pre-fix READ-only share mode refuses the same save.
        native=launch.Windows()
        with tempfile.TemporaryDirectory(dir=os.environ['COMICS_META_TEST_SCRATCH']) as folder:
            held=Path(folder)/'held';held.mkdir()
            (held/'state.json.tmp').write_text('new')
            with patch.object(native,'SHARE_WRITE',0):handle=native.hold(str(held),directory=True)
            try:
                self.sharing_violation(lambda:os.replace(held/'state.json.tmp',held/'state.json'))
            finally:
                native.close(handle)
            os.replace(held/'state.json.tmp',held/'state.json')

    def test_file_hold_still_freezes_payload_bytes_and_name(self):
        native=launch.Windows()
        with tempfile.TemporaryDirectory(dir=os.environ['COMICS_META_TEST_SCRATCH']) as folder:
            payload_file=Path(folder)/'payload.exe';payload_file.write_bytes(b'test')
            handle=native.hold(str(payload_file))
            try:
                with self.assertRaises(PermissionError):payload_file.open('r+b')  # CRT maps error 32 to EACCES.
                self.sharing_violation(lambda:os.replace(payload_file,Path(folder)/'other.exe'))
            finally:
                native.close(handle)
            self.assertEqual(payload_file.read_bytes(),b'test')


if __name__ == '__main__':
    unittest.main()
