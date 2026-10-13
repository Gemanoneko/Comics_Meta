import json
import os
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import Mock, patch
import app
import credential_store
import library_lock
import setup_state
from test_worker import scratch_directory


class SetupStateTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.state = self.root / 'state'
        self.state.mkdir()
        self.library = self.root / 'library'
        self.library.mkdir()
        self.enterContext(patch.object(app, 'STATE_ROOT', self.state))
        self.enterContext(patch.object(app, 'DATA', self.state / 'data'))
        self.enterContext(patch.dict(os.environ))
        for name in credential_store.ALLOWED_KEYS:
            os.environ.pop(name, None)
        # Atomicity/priority tests need no real OS credentials. Ciphertext is opaque
        # to plaintext sentinel checks; the separate Windows test covers real DPAPI.
        self.enterContext(patch.object(credential_store, '_crypt', side_effect=lambda data, protect: b'fixture:' + data[::-1] if protect else data.removeprefix(b'fixture:')[::-1]))
        self.claim = Mock()
        self.acquire = self.enterContext(patch.object(library_lock, 'acquire', return_value=self.claim))

    def config(self, value):
        (self.state / 'config.json').write_text(json.dumps(value), encoding='utf-8')

    def error(self, code, callback):
        with self.assertRaises(setup_state.SetupError) as result:
            callback()
        self.assertEqual(result.exception.code, code)

    def test_first_run_is_read_only_and_does_not_create_a_pause(self):
        result = setup_state.status()
        self.assertFalse(result['configured'])
        self.assertFalse(result['user_paused'])
        self.assertEqual(set(result['saved_keys']), set(credential_store.ALLOWED_KEYS))
        self.assertFalse(any(result['saved_keys'].values()))
        self.assertFalse((self.state / 'data').exists())
        self.assertFalse((self.state / 'config.json').exists())
        self.acquire.assert_not_called()

    def test_save_preserves_unknown_settings_sources_env_and_saved_pause(self):
        original = {'automatic': {'enabled': False, 'interval': 91}, 'unknown': {'keep': 7},
                    'web_search': {'provider': 'free'}, 'browser_search': {'enabled': False}}
        self.config(original)
        env = b'GCD_EMAIL=fixture@example.invalid\n'
        (self.state / '.env').write_bytes(env)
        app.DATA.mkdir()
        with sqlite3.connect(app.DATA / 'catalog.sqlite') as connection:
            connection.execute('CREATE TABLE processing_control(id INTEGER PRIMARY KEY, paused INTEGER)')
            connection.execute('INSERT INTO processing_control VALUES(1,1)')
        before = (app.DATA / 'catalog.sqlite').read_bytes()
        result = setup_state.save(str(self.library), {})
        self.assertTrue(result['configured'] and result['user_paused'])
        config = app.load_config()
        self.assertTrue(config['automatic']['enabled'])
        self.assertEqual(config['automatic']['interval'], 91)
        self.assertEqual(config['automatic']['root'], config['automatic']['library_root'])
        for name in ('unknown', 'web_search', 'browser_search'):
            self.assertEqual(config[name], original[name])
        self.assertEqual((self.state / '.env').read_bytes(), env)
        self.assertEqual((app.DATA / 'catalog.sqlite').read_bytes(), before)
        self.acquire.assert_called_once()
        self.claim.release.assert_called_once()

    def test_secret_replacement_blank_preservation_and_priority(self):
        name = 'COMICVINE_API_KEY'
        sentinel = 'synthetic-only-alpha-credential'
        setup_state.save(str(self.library), {name: '  ' + sentinel + '  '})
        self.assertTrue(credential_store.setting(name) == sentinel, 'Saved replacement must be readable')
        config_bytes = (self.state / 'config.json').read_bytes()
        self.assertTrue(sentinel.encode() not in config_bytes, 'Config must not contain a key')
        for path in (self.state / 'credentials').glob('*'):
            self.assertTrue(sentinel.encode() not in path.read_bytes(), 'Credential file must be encrypted')
        pointer = app.load_config()[credential_store.POINTER]
        setup_state.save(str(self.library), {name: '   '})
        self.assertEqual(app.load_config()[credential_store.POINTER], pointer)
        self.assertTrue(credential_store.setting(name) == sentinel)
        self.assertTrue(setup_state.status()['saved_keys'][name])
        public = json.dumps(setup_state.status())
        self.assertTrue(sentinel not in public, 'Public status must not contain a key')
        os.environ[name] = 'synthetic-environment-override'
        self.assertTrue(credential_store.setting(name) == os.environ[name])

    def test_empty_legacy_comicvine_value_does_not_hide_later_configured_env_file(self):
        self.config({'env_file': 'secondary.env'})
        (self.state / '.env').write_text('COMICVINE_API_KEY=\n', encoding='utf-8')
        (self.state / 'secondary.env').write_text('COMICVINE_API_KEY=synthetic-secondary-only\n', encoding='utf-8')
        self.assertTrue(credential_store.setting('COMICVINE_API_KEY') == 'synthetic-secondary-only')

    def test_folder_and_key_validation_make_no_config_or_claim_changes(self):
        for folder, code in [('', 'folder_required'), ('relative', 'folder_invalid'),
                             (str(self.root / 'missing'), 'folder_missing')]:
            self.error(code, lambda: setup_state.save(folder, {}))
        for value in ('one\ntwo', 'one\rtwo', 'one\0two', None):
            self.error('key_invalid', lambda: setup_state.save(str(self.library), {'SERPAPI_API_KEY': value}))
        self.error('key_invalid', lambda: setup_state.save(str(self.library), {'GCD_PASSWORD': 'unsupported'}))
        self.acquire.assert_not_called()
        self.assertFalse((self.state / 'config.json').exists())

    def test_unreadable_and_existing_missing_folder_are_errors_not_empty_first_run(self):
        with patch.object(setup_state.os, 'scandir', side_effect=PermissionError()):
            self.error('folder_unreadable', lambda: setup_state.save(str(self.library), {}))
        self.config({'automatic': {'library_root': str(self.root / 'missing')}})
        self.error('folder_missing', setup_state.status)

    def test_overlap_and_encryption_failure_never_commit_configuration(self):
        self.config({'unknown': 2})
        before = (self.state / 'config.json').read_bytes()
        self.acquire.side_effect = library_lock.LibraryBusy('synthetic overlap')
        self.error('library_busy', lambda: setup_state.save(str(self.library), {}))
        self.assertEqual((self.state / 'config.json').read_bytes(), before)
        self.acquire.side_effect = None
        with patch.object(credential_store, 'encrypt', side_effect=credential_store.CredentialError()):
            self.error('save_failed', lambda: setup_state.save(str(self.library), {'METRON_API_TOKEN': 'synthetic-only'}))
        self.assertEqual((self.state / 'config.json').read_bytes(), before)

    def test_atomic_commit_failure_keeps_previous_config_and_encrypted_generation(self):
        name = 'SERPAPI_API_KEY'
        setup_state.save(str(self.library), {name: 'synthetic-first-value'})
        before = (self.state / 'config.json').read_bytes()
        with patch.object(setup_state, '_replace', side_effect=OSError('fixture failure')):
            self.error('save_failed', lambda: setup_state.save(str(self.library), {name: 'synthetic-second-value'}))
        self.assertEqual((self.state / 'config.json').read_bytes(), before)
        self.assertTrue(credential_store.setting(name) == 'synthetic-first-value')
        self.assertFalse(list(self.state.glob('config.*.tmp')))
        self.assertEqual(len(list((self.state / 'credentials').glob('*.dpapi'))), 2)  # Preserve unresolved encrypted evidence.

    def test_invalid_or_corrupt_secret_pointer_fails_closed(self):
        self.config({credential_store.POINTER: '../outside.dpapi'})
        self.error('save_failed', setup_state.status)
        self.error('save_failed', lambda: setup_state.save(str(self.library), {}))


@unittest.skipUnless(os.name == 'nt', 'Windows DPAPI only')
class NativeDpapiTests(unittest.TestCase):
    def test_user_bound_dpapi_roundtrip_with_synthetic_value(self):
        values = {'METRON_API_TOKEN': 'synthetic-dpapi-test-only'}
        encrypted = credential_store.encrypt(values)
        self.assertTrue(values['METRON_API_TOKEN'].encode() not in encrypted, 'DPAPI must encrypt the synthetic value')
        recovered = json.loads(credential_store._crypt(encrypted, False).decode('utf-8'))
        self.assertTrue(recovered == values, 'Synthetic DPAPI roundtrip failed')
        with self.assertRaises(credential_store.CredentialError):
            credential_store._crypt(b'not-a-dpapi-blob', False)
