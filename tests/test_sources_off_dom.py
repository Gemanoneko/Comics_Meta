"""DesktopShell spec §12 (Judy, 2026-10-27): switched-off sources and Lens leave the screen. Headless DOM only, no mouse.

The real dashboard page, lens-control.js, comic-recovery.js and first-run setup run offline with a stand-in desktop
bridge; every request is answered locally. Runs through the canonical headless harness (COMICS_TEST_CDP); skipped
without it."""
import json
import os
import unittest
import urllib.parse
from pathlib import Path
from test_shell_ui_dom import HeadlessPage

ROOT = Path(__file__).resolve().parents[1]
OFF_NAMES = ('GCD', 'Google Books', 'Open Library', 'Dark Horse', 'PREVIEWSworld', 'GetComics', 'switched')
KEYS = ('COMICVINE_API_KEY', 'METRON_API_TOKEN', 'GOOGLE_BOOKS_API_KEY', 'BRAVE_SEARCH_API_KEY')
BRIDGE = """window.comicDesktop = {
  submitted: [],
  keys() { return Promise.resolve(window.keyStatus); },
  saveKeys(keys) { this.submitted.push(keys); return Promise.resolve({saved_keys: {}}); },
  setup() { return Promise.resolve(window.setupStatus); },
  saveSetup(folder, keys) { this.submitted.push(keys); return Promise.resolve({error: 'folder_required'}); },
  browse() { return Promise.resolve(''); },
  action() { return Promise.resolve(); },
  onState(callback) { return () => {}; },
  onRefresh() { return () => {}; },
};"""
HIDDEN = """id => { const node = document.getElementById(id), box = node.getBoundingClientRect();
                return box.width === 0 && box.height === 0; }"""


def providers(google_books_on=False):
    off = {'status': 'switched_off'}
    return {'comicvine': {'status': 'configured', 'requests_last_hour': 0, 'hourly_application_budget': 180}, 'metron': {'status': 'available'},
            'gcd': off, 'google_books': {'status': 'available'} if google_books_on else off, 'open_library': off,
            'getcomics': off, 'darkhorse_catalog': off, 'image_catalog': {'status': 'available'}, 'previews_catalog': off,
            'free_web': off, 'wikipedia': off}


@unittest.skipUnless(os.environ.get('COMICS_TEST_CDP'), 'Requires owned offline headless fixture')
class DashboardSourcesOffDOMTests(HeadlessPage):
    def setUp(self):
        super().setUp()
        self.lens = {'enabled': False, 'engine': 'google_lens', 'phase': 'idle', 'human_verification': False, 'window': 'closed',
                     'alive': False, 'paused': False, 'failure': '', 'verification_pending': False, 'updated': 1,
                     'cover': {'state': 'disabled', 'detail': 'Browser cover research is disabled.'}, 'control': {}}
        self.progress = {'queue': {'alive': True}, 'timestamp': 1, 'providers': providers(),
                         'research': {'needs_identity_lookup': 712}, 'folders': {'passes_complete': 3, 'total': 8084}}
        self.context.add_init_script('window.setInterval=()=>0;' + BRIDGE)
        self.page.route('https://comics-fixture.invalid/**', self.route)
        self.page.goto('https://comics-fixture.invalid/')
        self.page.wait_for_function("document.getElementById('providerStatus').textContent.includes('Metron')"
                                    " && document.getElementById('researchStatus').textContent.includes('comics still need research')")

    def route(self, route):
        path = urllib.parse.urlparse(route.request.url).path
        static = {'/': 'index.html', '/lens-control.js': 'lens-control.js', '/comic-recovery.js': 'comic-recovery.js',
                  '/reverse-image.js': 'reverse-image.js'}
        if path in static:
            kind = 'text/html' if path == '/' else 'text/javascript'
            return route.fulfill(body=(ROOT / 'static' / static[path]).read_text(encoding='utf-8'), content_type=kind)
        if path.endswith('.js') or path.endswith('.css'):
            return route.fulfill(body='', content_type='text/javascript' if path.endswith('.js') else 'text/css')
        if path == '/api/browser-verification':
            return route.fulfill(json=self.lens)
        if path == '/api/progress':
            return route.fulfill(json=self.progress)
        if path == '/api/state':
            return route.fulfill(json={'version': '0.5.0', 'roots': [], 'job': {'message': 'Ready', 'running': False, 'visited': 0, 'changed': 0},
                                       'counts': {}, 'totals': {}})
        if path == '/api/comics':
            return route.fulfill(json={'rows': [], 'total': 0})
        return route.abort()

    def text(self, id):
        return self.page.evaluate('id => document.getElementById(id).textContent', id)

    def lens_hidden(self):
        return (self.page.evaluate(HIDDEN, 'browserStatus'), self.page.evaluate(HIDDEN, 'browserResume'),
                self.text('browserHelp'), self.page.evaluate("document.getElementById('browserResume').title"))

    def test_switched_off_sources_leave_the_source_line(self):
        line = self.text('providerStatus')
        for name in OFF_NAMES:
            self.assertNotIn(name, line)  # Before: "GCD: switched_off | Google Books: switched_off | …".
        self.assertIn('Metron: Connected', line)  # Positive control: sources that are on keep today's wording.
        self.assertIn('Image Comics: Connected', line)
        self.assertFalse(line.startswith(' | ') or line.endswith(' | ') or ' |  | ' in line)  # No stray separator.

    def test_lens_off_leaves_no_line_button_or_help(self):
        self.assertEqual(self.lens_hidden(), (True, True, '', ''))  # Before: "Cover search: disabled · …".
        paused = dict(self.lens, phase='paused', paused=True, updated=2)
        self.page.evaluate('v => LensControl.render(v)', paused)
        self.assertEqual(self.lens_hidden(), (True, True, '', ''))  # Not "Paused; cover queue retained."
        self.page.evaluate('LensControl.unavailable()')  # A failed poll after an "off" answer.
        self.assertEqual(self.lens_hidden(), (True, True, '', ''))
        # Positive control: Lens switched on shows its line again, from its own state.
        self.page.evaluate('v => LensControl.render(v)', dict(self.lens, enabled=True, alive=True, updated=3,
                                                                cover={'state': 'waiting', 'detail': 'Watching for unresolved covers.'}))
        self.assertFalse(self.page.evaluate(HIDDEN, 'browserStatus'))
        self.assertIn('Cover search', self.text('browserStatus'))

    def test_research_line_drops_the_queue_clause_at_zero(self):
        line = self.text('researchStatus')
        self.assertNotIn('browser cover', line)  # Before: "· 0 browser cover searches queued."
        self.assertIn('712 comics still need research. A checked folder is not a completeness guarantee.', line)
        self.progress['cover_research'] = {'pending': 5}
        self.page.evaluate('progress()')
        self.page.wait_for_function("document.getElementById('researchStatus').textContent.includes('browser cover')")
        self.assertIn('712 comics still need research · 5 browser cover searches queued. A checked folder', self.text('researchStatus'))

    def test_identify_by_cover_panel_no_longer_promises_automatic_lens(self):
        panel = self.page.evaluate("[imagePanel.querySelector('p').textContent, [...imagePanel.querySelectorAll('a')].map(a => a.textContent)]")
        self.assertEqual(panel, ['Download the cover, then search it in Google Lens.', ['Download selected cover', 'Open Google Lens']])

    def keys_rows(self, hidden):
        status = {'saved_keys': {name: name == 'GOOGLE_BOOKS_API_KEY' for name in KEYS}, 'hidden_keys': hidden}
        self.page.evaluate('s => { window.keyStatus = s; }', status)
        self.page.evaluate("() => { const d = document.getElementById('review'); if (d.open) d.close(); return ComicRecovery.openKeys(document.body); }")
        self.page.wait_for_function("document.querySelectorAll('#review .recovery-key-row').length > 0")
        return self.page.evaluate("[...document.querySelectorAll('#review .recovery-key-row input')].map(i => i.dataset.key)")

    def test_keys_screen_lists_google_books_only_while_it_is_on(self):
        self.assertEqual(self.keys_rows(['GOOGLE_BOOKS_API_KEY']), ['COMICVINE_API_KEY', 'METRON_API_TOKEN', 'BRAVE_SEARCH_API_KEY'])
        self.page.evaluate("document.querySelectorAll('#review [data-key]').forEach(input => { input.value = 'synthetic-key'; })")
        self.page.evaluate("document.querySelector('#review form').requestSubmit()")
        self.page.wait_for_function('window.comicDesktop.submitted.length === 1')
        self.assertNotIn('GOOGLE_BOOKS_API_KEY', self.page.evaluate('window.comicDesktop.submitted[0]'))  # Nothing submitted.
        self.assertEqual(self.keys_rows([]), list(KEYS))  # Source on: the fourth row returns.


@unittest.skipUnless(os.environ.get('COMICS_TEST_CDP'), 'Requires owned offline headless fixture')
class SetupSourcesOffDOMTests(HeadlessPage):
    def open(self, hidden):
        status = {'configured': False, 'user_paused': False, 'library': '', 'hidden_keys': hidden,
                  'saved_keys': {name: name == 'GOOGLE_BOOKS_API_KEY' for name in KEYS}}
        self.context.add_init_script(BRIDGE + 'window.setupStatus = ' + json.dumps(status) + ';')
        self.page.route('https://setup-fixture.invalid/**', self.route)
        self.page.goto('https://setup-fixture.invalid/')
        self.page.wait_for_function("document.activeElement === document.getElementById('library')")  # setup() answered.
        return self.page.evaluate("[...document.querySelectorAll('.key-row input')].map(i => i.id)")

    def route(self, route):
        path = urllib.parse.urlparse(route.request.url).path
        files = {'/': ('setup.html', 'text/html'), '/setup.js': ('setup.js', 'text/javascript'),
                 '/setup.css': ('setup.css', 'text/css'), '/shell.css': ('shell.css', 'text/css')}
        if path in files:
            name, kind = files[path]
            return route.fulfill(body=(ROOT / 'desktop' / name).read_text(encoding='utf-8'), content_type=kind)
        return route.abort()

    def test_first_run_setup_lists_three_key_rows_while_google_books_is_off(self):
        self.assertEqual(self.open(['GOOGLE_BOOKS_API_KEY']), ['COMICVINE_API_KEY', 'METRON_API_TOKEN', 'BRAVE_SEARCH_API_KEY'])
        self.page.evaluate("document.getElementById('setupForm').requestSubmit()")
        self.page.wait_for_function('window.comicDesktop.submitted.length === 1')
        self.assertNotIn('GOOGLE_BOOKS_API_KEY', self.page.evaluate('window.comicDesktop.submitted[0]'))  # Nothing submitted.

    def test_first_run_setup_lists_four_key_rows_while_google_books_is_on(self):
        self.assertEqual(self.open([]), list(KEYS))


if __name__ == '__main__':
    unittest.main()
