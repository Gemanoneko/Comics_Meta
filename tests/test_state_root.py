import json
import os
import re
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import app
import app_paths
import batch
import browser_search
import metron
import providers
import server_host
import web_search
from test_worker import scratch_directory

CODE = Path(__file__).resolve().parents[1]
SECRETS = ('COMICVINE_API_KEY', 'METRON_API_TOKEN', 'GCD_EMAIL', 'SERPAPI_API_KEY', 'BRAVE_SEARCH_API_KEY')


class StateRootSelectionTests(unittest.TestCase):
    def test_default_is_the_code_folder_so_the_live_checkout_is_unchanged(self):
        self.assertEqual(app_paths.CODE_ROOT, app.BASE)
        self.assertEqual(app_paths.state_root({}), app_paths.CODE_ROOT)
        self.assertEqual(app_paths.state_root({app_paths.STATE_ROOT_ENV: '   '}), app_paths.CODE_ROOT)

    def test_absolute_root_is_used_and_relative_root_is_refused(self):
        with scratch_directory() as folder:
            chosen = Path(folder) / 'ComicsMeta'
            self.assertEqual(app_paths.state_root({app_paths.STATE_ROOT_ENV: str(chosen)}), chosen)
        for relative in ('ComicsMeta', 'state/ComicsMeta'):
            with self.subTest(value=relative), self.assertRaises(ValueError):
                app_paths.state_root({app_paths.STATE_ROOT_ENV: relative})

    def test_every_process_derives_all_state_paths_from_the_root(self):
        with scratch_directory() as folder:
            state = Path(folder) / 'state'
            script = ('import json,app,worker,server_host,research,scheduler,metron,open_library,automatic;'
                      'print(json.dumps({"state":str(app.STATE_ROOT),"data":str(app.DATA),"queue":str(worker.QUEUE),'
                      '"host":str(server_host.STATE_ROOT),"research":str(research.CACHE),"folders":str(scheduler.STATE),'
                      '"metron":str(metron.STATE),"index":str(open_library.INDEX),"automatic":str(automatic.STATE),'
                      '"code":str(app.BASE)}))')
            env = dict(os.environ, COMICS_META_STATE_ROOT=str(state), COMICS_META_LOCK_DIR=str(Path(folder) / 'locks'))
            result = subprocess.run([sys.executable, '-c', script], cwd=CODE, env=env, capture_output=True,
                                    text=True, timeout=120, check=True)
            paths = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(Path(paths.pop('code')), CODE)
            self.assertEqual(Path(paths.pop('state')), state)
            for name, value in paths.items():
                with self.subTest(path=name):
                    self.assertTrue(Path(value).is_relative_to(state), value)


class StateFilesTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        # Shaped like Studio/WIP/<tool>, so BASE.parents[1] is a real folder.
        self.code = self.root / 'studio' / 'WIP' / 'tool'
        self.code.mkdir(parents=True)
        self.state = self.root / 'state'
        self.state.mkdir()
        self.enterContext(patch.object(app, 'BASE', self.code))
        self.enterContext(patch.object(app, 'STATE_ROOT', self.state))
        self.enterContext(patch.object(app, 'DATA', self.state / 'data'))
        self.enterContext(patch.dict(os.environ))
        for name in SECRETS:
            os.environ.pop(name, None)

    def secrets(self, path, prefix):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(f'{name}={prefix}-{name.lower()}\n' for name in SECRETS), encoding='utf-8')

    def lookups(self):
        return {'comicvine': app.api_key(), 'metron': metron.token(), 'gcd': providers.setting('GCD_EMAIL'),
                'serpapi': browser_search.api_key(), 'brave': web_search.key()}

    def test_config_and_secrets_come_from_the_state_root_only(self):
        # Neither the code folder nor the studio root two levels up is a secrets source any more.
        self.secrets(self.code / '.env', 'code')
        self.secrets(self.code.parents[1] / '.env', 'studio')
        self.assertEqual(set(self.lookups().values()), {''})  # Also: no config.json is not an error.
        self.secrets(self.state / '.env', 'state')
        self.assertEqual(self.lookups(), {'comicvine': 'state-comicvine_api_key', 'metron': 'state-metron_api_token',
                                          'gcd': 'state-gcd_email', 'serpapi': 'state-serpapi_api_key',
                                          'brave': 'state-brave_search_api_key'})
        (self.state / 'config.json').write_text(json.dumps({'automatic': {'root': 'X:\\Comics'},
                                                            'web_search': {'provider': 'free'}}), encoding='utf-8')
        self.assertEqual(app.live_root(), 'X:\\Comics')
        self.assertEqual(web_search.config(), {'provider': 'free'})

    def test_env_file_setting_relative_to_state_root_or_absolute(self):
        (self.state / '.env').unlink(missing_ok=True)
        (self.state / 'config.json').write_text(json.dumps({'env_file': 'secrets/keys.env'}), encoding='utf-8')
        self.assertEqual(app.env_files(), [self.state / '.env', self.state / 'secrets' / 'keys.env'])
        self.secrets(self.state / 'secrets' / 'keys.env', 'relative')
        self.assertEqual(app.api_key(), 'relative-comicvine_api_key')
        elsewhere = self.root / 'elsewhere' / 'keys.env'
        self.secrets(elsewhere, 'absolute')
        (self.state / 'config.json').write_text(json.dumps({'env_file': str(elsewhere)}), encoding='utf-8')
        self.assertEqual(app.env_files()[-1], elsewhere)
        self.assertEqual(metron.token(), 'absolute-metron_api_token')

    def test_batch_plans_and_progress_are_written_under_the_state_root(self):
        folder = self.root / 'comics'
        folder.mkdir()
        for name, xml in (('Reference 001.cbz', b'<ComicInfo><Series>Example</Series></ComicInfo>'), ('Copy 001.cbz', None)):
            with zipfile.ZipFile(folder / name, 'w') as archive:
                archive.writestr('001.jpg', b'same page')
                if xml:
                    archive.writestr('ComicInfo.xml', xml)
        batch.prepare(folder, folder / 'Reference 001.cbz')
        batch.progress(phase='Fixture')
        plans = list((self.state / 'batches').glob('*/plan.json'))
        self.assertEqual(len(plans), 1)
        self.assertTrue((self.state / 'data' / 'progress.json').exists())
        self.assertFalse((self.code / 'batches').exists())
        self.assertFalse((self.code / 'data').exists())

    def test_server_host_logs_to_state_but_runs_code(self):
        with patch.object(server_host, 'BASE', self.code), patch.object(server_host, 'STATE_ROOT', self.state), \
                patch.object(server_host.subprocess, 'Popen') as launch:
            launch.return_value.wait.return_value = 0
            self.assertEqual(server_host.main(), 0)
        self.assertTrue((self.state / 'data' / 'server-exit.json').exists())
        self.assertFalse((self.code / 'data').exists())
        self.assertEqual(launch.call_args.kwargs['cwd'], self.code)
        self.assertEqual(launch.call_args.args[0][2], str(self.code / 'app.py'))


class NoCodeFolderStateTests(unittest.TestCase):
    PATTERN = re.compile(r'''BASE\s*/\s*['"](?:data|batches|work|config\.json|\.env)['"]|parents\[1\]''')

    def test_no_module_reads_state_from_the_code_folder(self):
        # The check itself must catch the old spellings.
        for old in ("app.BASE/'config.json'", "BASE / 'data'", "app.BASE / 'batches'", "BASE.parents[1] / '.env'"):
            self.assertRegex(old, self.PATTERN)
        offenders = [f'{path.name}:{number}' for path in sorted(CODE.glob('*.py'))
                     for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1)
                     if self.PATTERN.search(line)]
        self.assertEqual(offenders, [])


if __name__ == '__main__':
    unittest.main()
