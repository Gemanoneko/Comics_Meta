"""BackupLocation 2026-10-16 and its Amendment in the real page, offline: every request is fulfilled
locally, nothing reaches an engine, and File Explorer is never launched (the reveal route is a stub).
Layout is measured: rects, overflow, target sizes, focus, and what a copy of the path yields.

Runs through the canonical headless harness (COMICS_TEST_CDP); skipped without it.
"""
import json
import os
import time
import unittest
import urllib.parse
from pathlib import Path
from test_yandex_dom import YandexDOMTests

NOW = time.time()
LONG = 'Сага о героях [Том 1] ' + 'Exceptionally Long Series Title With Spaces ' * 4 + 'Unbrokensegment' * 5 + '.cbz'
BACKUP = '\\\\?\\D:\\Comics\\Batman [1940]\\.comic-metadata-backups\\Batman 003 (2019).cbz.1760000000000000000.bak'
SHOWN = 'D:\\Comics\\Batman [1940]\\.comic-metadata-backups\\Batman 003 (2019).cbz.1760000000000000000.bak'
NOT_VERIFIED = 'The change was not verified. Check the file and retained recovery backup before trying again.'
GEOMETRY = r"""sel => {
  const host = document.querySelector(sel);
  const rect = n => n.getBoundingClientRect();
  const box = n => { const r = rect(n); return [r.left, r.top, r.right, r.bottom]; };
  const overlap = (a, b) => a[0] < b[2] - 0.5 && b[0] < a[2] - 0.5 && a[1] < b[3] - 0.5 && b[1] < a[3] - 0.5;
  const visible = n => !n.hidden && n.getClientRects().length > 0;
  const groups = [...(host.matches('.kept-item, .backup-location') ? [host] : []), ...host.querySelectorAll('.kept-item, .backup-location')].map(item => [...item.children].filter(visible)
    .flatMap(child => child.matches('.recovery-actions, .kept-confirm') ? [...child.querySelectorAll('button')].concat(child.matches('.kept-confirm') ? [...child.querySelectorAll('p')] : []) : [child]).map(box));
  const clashes = [];
  for (const group of groups) for (let i = 0; i < group.length; i++) for (let j = i + 1; j < group.length; j++) if (overlap(group[i], group[j])) clashes.push([group[i], group[j]]);
  const items = [...host.querySelectorAll('.kept-item')].map(box);
  for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) if (overlap(items[i], items[j])) clashes.push(['items', i, j]);
  const buttons = [...host.querySelectorAll('button')].filter(visible).map(b => ({label: b.textContent, w: rect(b).width, h: rect(b).height, confirm: Boolean(b.closest('.kept-confirm'))}));
  const summaries = [...document.querySelectorAll('.library-panel summary')].map(s => rect(s).height);
  const outer = rect(host.parentElement.closest('dialog') || document.documentElement), own = rect(host);
  const inside = own.left >= outer.left - 0.5 && own.right <= outer.right + 0.5;
  return {clashes, buttons, summaries, inside, overflow: host.scrollWidth - host.clientWidth, page: document.documentElement.scrollWidth - document.documentElement.clientWidth};
}"""


def backups():
    items = []
    names = ['Batman 003 (2019).cbz', LONG, 'Spawn 112.cbz', 'X-Men [Vol. 2] 001.cbz']
    folders = ['D:\\Comics\\Batman', '\\\\?\\D:\\Comics\\' + 'Very Long Folder Name ' * 6 + 'Ünïcode [Brackets]', '\\\\?\\UNC\\nas\\share\\Comics', 'D:\\' + 'Segment' * 12]
    reasons = ['save_not_verified', 'delete_refused', None, 'not_saved']
    for index in range(17):
        items.append({'id': '%032x' % (index + 1), 'name': names[index % 4], 'folder': folders[index % 4],
                      'size': [431_000_000, 43_200_000, 999, 3_400_000_000][index % 4], 'created': NOW - [30, 720, 3 * 3600, 4 * 86400, 40 * 86400][index % 5],
                      'reason': reasons[index % 4]})
    return items


@unittest.skipUnless(os.environ.get('COMICS_TEST_CDP'), 'Requires owned offline headless fixture')
class KeptBackupsDOMTests(YandexDOMTests):
    def setUp(self):
        super().setUp()
        self.root = Path(__file__).resolve().parents[1]
        self.items = backups()
        self.posts = []
        self.reveal_status = 200
        self.reveal_code = 'not_found'
        self.confirm_result = {'ok': False, 'verified': False, 'backup': BACKUP, 'backup_id': 'b' * 32, 'message': NOT_VERIFIED}
        self.apply_result = (200, {'ok': True, 'verified': True, 'backup': BACKUP, 'backup_id': 'c' * 32, 'backup_retained': True, 'backup_removed_after_verification': False})
        self.context.add_init_script('window.setInterval=()=>0;')
        self.page.route('https://comics-fixture.invalid/**', self.route)
        self.page.set_viewport_size({'width': 1280, 'height': 900})
        self.page.goto('https://comics-fixture.invalid/')
        self.page.wait_for_function("document.querySelector('#keptBackups summary').textContent.startsWith('Kept backups · 17')")

    def route(self, route):
        parsed = urllib.parse.urlparse(route.request.url)
        path = parsed.path
        static = {'/': ('static/index.html', 'text/html'), '/comic-recovery.js': ('static/comic-recovery.js', 'text/javascript'),
                  '/kept-backups.js': ('static/kept-backups.js', 'text/javascript'), '/comic-recovery.css': ('static/comic-recovery.css', 'text/css'),
                  '/lens-control.js': ('static/lens-control.js', 'text/javascript')}
        if path in static:
            name, kind = static[path]
            return route.fulfill(body=(self.root / name).read_text(encoding='utf-8'), content_type=kind)
        if path in ('/reverse-image.js', '/shell-ui.js'):
            return route.fulfill(body='', content_type='text/javascript')
        if route.request.method == 'POST':
            self.posts.append((path, json.loads(route.request.post_data or 'null')))
        if path == '/api/backups':
            return route.fulfill(json={'items': self.items, 'count': len(self.items), 'bytes': sum(i['size'] for i in self.items), 'bounded': False})
        if path == '/api/backups/reveal':
            return route.fulfill(status=self.reveal_status, json={'ok': True} if self.reveal_status == 200 else {'error': self.reveal_code, 'code': self.reveal_code})
        if path == '/api/backups/delete':
            ids = json.loads(route.request.post_data)['ids']
            self.items = [i for i in self.items if i['id'] not in ids]
            return route.fulfill(json={'deleted': ids, 'failed': [], 'freed': 1000})
        if path == '/api/state':
            data = {'version': '0.2.4', 'roots': ['D:\\Comics'], 'job': {'message': 'Ready', 'running': False, 'visited': 0, 'changed': 0}, 'counts': {}, 'totals': {}}
        elif path == '/api/comics':
            data = {'rows': [{'id': 1, 'path': 'D:\\Comics\\Batman\\Batman 003 (2019).cbz', 'series': 'Batman', 'number': '3', 'year': '2019', 'status': 'embedded',
                              'metadata': json.dumps({'Series': 'Batman'}), 'has_synopsis': False, 'has_metadata': True, 'error': '',
                              'problem': {'code': 'dead_link', 'issue_id': '123'}}], 'total': 1}
        elif path == '/api/progress':
            data = {'queue': {'alive': True}, 'timestamp': 1, 'research': {}, 'folders': {}, 'providers': {}}
        elif path == '/api/browser-verification':
            data = {'engine': 'google_lens', 'phase': 'idle', 'human_verification': False, 'window': 'closed', 'alive': True, 'updated': 1, 'control': {}}
        elif path == '/api/recovery/evidence':
            data = {'comic': 1, 'path': 'D:\\Comics\\Batman\\Batman 003 (2019).cbz', 'signature': [1, 2], 'record_revision': 'r',
                    'embedded': {'Series': 'Batman', 'Number': '3', 'Year': '2019', 'Web': 'https://comicvine.gamespot.com/x/4000-123/'},
                    'filename': {'Series': 'Batman', 'Number': '3', 'Year': '2019'}, 'problem': {'code': 'dead_link', 'issue_id': '123'},
                    'provider': None, 'provider_error': {'message': 'ComicVine could not find this issue.'}, 'paused': False}
        elif path == '/api/recovery/preview':
            data = {'token': 't', 'action': 'remove_link', 'changes': [{'field': 'Web', 'before': 'https://comicvine.gamespot.com/x/4000-123/', 'after': ''}],
                    'source': None, 'filename': 'Batman 003 (2019).cbz'}
        elif path == '/api/recovery/confirm':
            return route.fulfill(json=self.confirm_result)
        elif path == '/api/apply':
            status, body = self.apply_result
            return route.fulfill(status=status, json=body)
        else:
            return route.abort()
        route.fulfill(json=data)

    def geometry(self, selector):
        return self.page.evaluate(GEOMETRY, selector)

    def assert_layout(self, selector, width):
        found = self.geometry(selector)
        self.assertEqual(found['clashes'], [], (selector, width))
        self.assertLessEqual(found['overflow'], 0, (selector, width))
        self.assertLessEqual(found['page'], 0, (selector, width))
        self.assertTrue(found['inside'], (selector, width))
        for button in found['buttons']:
            self.assertGreaterEqual(button['w'], 24, (width, button))
            self.assertGreaterEqual(button['h'], 40 if button['confirm'] else 32, (width, button))
        return found

    def open_panel(self):
        self.page.click('#keptBackups summary')
        self.page.wait_for_function("document.querySelectorAll('#keptBackups .kept-item').length===17 && document.querySelector('.kept-status').hidden")

    def test_panel_text_states_and_layout_at_every_width(self):
        summary = self.page.locator('#keptBackups summary')
        self.assertEqual(summary.get_attribute('title'), 'Show or hide the recovery backups the app has kept.')
        self.assertRegex(summary.text_content(), r'^Kept backups · 17 · [0-9.]+ GB$')
        self.open_panel()
        first = self.page.evaluate("""() => { const i = document.querySelector('.kept-item');
            return [...i.querySelectorAll('.kept-name,.kept-folder,.kept-meta')].map(n => n.textContent).concat(
              [...i.querySelectorAll('button')].map(b => [b.textContent, b.title, b.getAttribute('aria-label')].join('|'))); }""")
        self.assertEqual(first[:2], ['Batman 003 (2019).cbz', 'D:\\Comics\\Batman'])
        self.assertEqual(first[2], '411 MB · just now · Save not verified')
        self.assertEqual(first[3:], ['Show in folder|Show this recovery backup file in File Explorer. Nothing is changed.|Show in folder: Batman 003 (2019).cbz, just now',
                                     'Delete|Delete this backup file. You are asked to confirm first.|Delete: Batman 003 (2019).cbz, just now'])
        folders = self.page.evaluate("[...document.querySelectorAll('.kept-folder')].slice(0,4).map(n=>n.textContent)")
        self.assertEqual(folders[1][:12], 'D:\\Comics\\Ve')  # \\?\ removed
        self.assertEqual(folders[2], '\\\\nas\\share\\Comics')  # \\?\UNC\ shown as \\
        for width in (320, 640, 1280):
            with self.subTest(width=width):
                self.page.set_viewport_size({'width': width, 'height': 900})
                found = self.assert_layout('#keptBackups', width)
                self.assertTrue(all(height >= 32 for height in found['summaries']), found['summaries'])
                self.page.click('.kept-item button[aria-label^="Delete:"]')
                self.assert_layout('#keptBackups', width)
                self.page.keyboard.press('Escape')
                self.page.click('.kept-toolbar button:has-text("Delete all")')
                self.assert_layout('#keptBackups', width)
                self.page.keyboard.press('Escape')

    def test_keyboard_confirm_and_row_delete_send_ids_only(self):
        self.open_panel()
        delete = self.page.locator('.kept-item').nth(1).locator('button[aria-label^="Delete:"]')
        delete.click()
        self.assertEqual(self.page.evaluate('document.activeElement.textContent'), 'Keep it')
        self.assertEqual(delete.get_attribute('aria-expanded'), 'true')
        confirm = self.page.evaluate("[...document.querySelectorAll('.kept-confirm p')].map(p=>p.textContent)")
        self.assertEqual(confirm, ['Delete this backup?', 'It is the only way to undo the change to ' + LONG + '. Deleting is permanent.'])
        self.page.keyboard.press('Escape')
        self.assertEqual((self.page.evaluate('document.activeElement.getAttribute("aria-label")'), delete.get_attribute('aria-expanded')),
                         ('Delete: ' + LONG + ', 12 min ago', 'false'))
        self.page.locator('.kept-item').first.locator('button[aria-label^="Delete:"]').click()
        confirm = self.page.evaluate("[...document.querySelectorAll('.kept-confirm p')].map(p=>p.textContent)")
        self.assertEqual(confirm[1], 'The save to Batman 003 (2019).cbz was not verified, so this may be its only good copy. Deleting is permanent.')
        self.page.click('.kept-confirm button:has-text("Delete backup")')
        self.page.wait_for_function("document.querySelectorAll('.kept-item').length===16")
        self.assertEqual(self.posts[-1], ('/api/backups/delete', {'ids': ['%032x' % 1]}))
        self.assertEqual(self.page.locator('.kept-status').text_content(), 'Backup deleted.')
        self.assertEqual(self.page.evaluate('document.activeElement.dataset.show'), '%032x' % 2)  # The next item's Show in folder.
        self.page.click('.kept-toolbar button:has-text("Delete all")')
        lines = self.page.evaluate("[...document.querySelectorAll('.kept-confirm p')].map(p=>p.textContent)")
        self.assertRegex(lines[0], r'^Delete all 16 kept backups \([0-9.]+ GB\)\?$')
        self.assertEqual(lines[1:], ['They are the only way to undo those changes. Deleting is permanent.', '4 are from saves that were not verified.',
                                     '4 are copies of files that were not changed.'])  # Not counted as unverified.
        self.assertEqual(self.page.evaluate('document.activeElement.textContent'), 'Keep them')
        ids = [item['id'] for item in self.items]
        self.page.click('.kept-confirm button:has-text("Delete 16 backups")')
        self.page.wait_for_function("document.querySelector('.kept-note').textContent==='No kept backups'")
        self.assertEqual(self.posts[-1], ('/api/backups/delete', {'ids': ids}))
        self.assertEqual(self.page.locator('.kept-status').text_content(), 'Deleted 16 backups. 1000 bytes freed.')
        self.assertEqual(self.page.evaluate('document.activeElement.tagName'), 'SUMMARY')
        self.assertEqual(self.page.locator('#keptBackups summary').text_content(), 'Kept backups · none')
        self.assertTrue(self.page.locator('.kept-toolbar button:has-text("Delete all")').is_hidden())

    def confirm_lines(self):
        return self.page.evaluate("[...document.querySelectorAll('.kept-confirm p')].map(p=>p.textContent)")

    def refresh_with(self, items):
        self.items = items
        self.page.click('.kept-toolbar button:has-text("Refresh")')
        self.page.wait_for_function('n=>document.querySelectorAll(".kept-item").length===n', arg=len(items))

    def test_not_saved_copies_and_row_reveal_errors(self):
        self.open_panel()
        row = self.page.locator('.kept-item').nth(3)
        self.assertEqual(row.locator('.kept-reason').text_content(), 'Not saved; file was not changed')
        row.locator('button[aria-label^="Delete:"]').click()
        self.assertEqual(self.confirm_lines(), ['Delete this backup?', 'The change to X-Men [Vol. 2] 001.cbz was not saved and the file was not changed, '
                                                'so this is only an extra copy. Deleting is permanent.'])
        self.page.keyboard.press('Escape')
        self.reveal_status = 400
        for code, text in (('not_found', 'Backup not found. Use Refresh to update the list.'),
                           ('failed', 'Could not open File Explorer. The backup is in the .comic-metadata-backups folder inside the folder above.')):
            self.reveal_code = code
            row.locator('button[aria-label^="Show in folder:"]').click()
            self.page.wait_for_function('t=>document.querySelector(".kept-item:nth-child(4) .kept-error")?.textContent===t', arg=text)
        self.assertEqual(self.page.locator('.kept-error').count(), 1)
        mixed = self.items[:4]  # One of each reason.
        self.refresh_with(mixed)
        self.page.click('.kept-toolbar button:has-text("Delete all")')
        self.assertEqual(self.confirm_lines()[1:], ['They are the only way to undo those changes. Deleting is permanent.',
                                                    '1 is from a save that was not verified.', '1 is a copy of a file that was not changed.'])
        self.page.keyboard.press('Escape')
        self.refresh_with([item for item in backups() if item['reason'] == 'not_saved'])
        self.page.click('.kept-toolbar button:has-text("Delete all")')
        lines = self.confirm_lines()
        self.assertRegex(lines[0], r'^Delete all 4 kept backups \([0-9.]+ GB\)\?$')
        self.assertEqual(lines[1:], ['They are extra copies of files that were not changed. Deleting is permanent.'])

    def save_recovery(self):
        self.page.wait_for_function("document.querySelector('#rows button')")
        self.page.click('#rows button:has-text("Details")')
        self.page.click('#problemDetail button:has-text("Remove this ComicVine link")')
        self.page.click('#problemDetail button:has-text("Save this change")')
        self.page.click('#problemDetail button:has-text("Save and verify")')
        self.page.wait_for_function("document.querySelector('#problemDetail .backup-location')")

    def test_recovery_outcome_block_reveal_and_copy(self):
        self.page.set_viewport_size({'width': 320, 'height': 900})
        self.save_recovery()
        found = self.page.evaluate("""() => { const status = document.querySelector('#problemDetail .recovery-status'), block = status.nextElementSibling;
            const path = block.querySelector('.backup-location-path'); const range = document.createRange(); range.selectNodeContents(path);
            const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
            return {role: status.getAttribute('role'), text: status.textContent, block: block.className, inside: status.contains(block),
                    label: block.querySelector('.backup-location-label').textContent, copied: selection.toString(), path: path.textContent,
                    focus: document.activeElement === status, button: [...block.querySelectorAll('button')].map(b => [b.textContent, b.title])}; }""")
        self.assertEqual(found, {'role': 'alert', 'text': NOT_VERIFIED, 'block': 'backup-location', 'inside': False, 'label': 'Recovery backup',
                                 'copied': SHOWN, 'path': SHOWN, 'focus': True,
                                 'button': [['Show backup in folder', 'Show this recovery backup file in File Explorer. Nothing is changed.']]})
        self.assert_layout('#problemDetail .backup-location', 320)
        button = self.page.locator('#problemDetail .backup-location button')
        button.click()
        self.page.wait_for_function("!document.querySelector('#problemDetail .backup-location button').hasAttribute('aria-disabled')")
        self.assertEqual(self.posts[-1], ('/api/backups/reveal', {'id': 'b' * 32}))
        self.reveal_status = 400
        button.click()
        self.page.wait_for_function("document.querySelector('#problemDetail .backup-location-error')")
        self.assertEqual(self.page.locator('#problemDetail .backup-location-error').text_content(), 'Could not find this backup. Check the path above.')
        self.reveal_code = 'failed'
        button.click()
        self.page.wait_for_function("document.querySelector('#problemDetail .backup-location-error')?.textContent.startsWith('Could not open')")
        self.assertEqual(self.page.locator('#problemDetail .backup-location-error').text_content(), 'Could not open File Explorer. Use the path above.')
        self.assertEqual(self.page.evaluate('document.activeElement.textContent'), 'Show backup in folder')
        self.assertEqual(self.page.locator('#problemDetail .recovery-status').text_content(), NOT_VERIFIED)  # Never through status().
        self.assert_layout('#problemDetail .backup-location', 320)
        self.page.click('#close')
        self.page.wait_for_function("!document.querySelector('.backup-location')")  # Removed when the dialog closes.

    def test_retained_on_success_is_a_status_and_no_backup_has_no_block(self):
        self.confirm_result = {'ok': True, 'verified': True, 'backup': BACKUP, 'backup_id': 'b' * 32, 'backup_retained': True,
                               'backup_removed_after_verification': False, 'metadata': {'Series': 'Batman'}, 'problem': None,
                               'message': 'Change saved and verified. The recovery backup could not be deleted and was retained.'}
        self.save_recovery()
        status = self.page.locator('#problemDetail .recovery-status')
        self.assertEqual((status.get_attribute('role'), status.text_content()), ('status', self.confirm_result['message']))
        self.page.click('#close')
        self.confirm_result = {'ok': False, 'verified': False, 'backup': None, 'message': 'The change was not verified. No recovery backup was made. Check the file before trying again.'}
        self.page.click('#rows button:has-text("Details")')
        self.page.click('#problemDetail button:has-text("Remove this ComicVine link")')
        self.page.click('#problemDetail button:has-text("Save this change")')
        self.page.click('#problemDetail button:has-text("Save and verify")')
        self.page.wait_for_function("document.querySelector('#problemDetail .recovery-status').textContent.includes('No recovery backup')")
        self.assertEqual(self.page.locator('.backup-location').count(), 0)

    def test_lookup_apply_outcomes(self):
        self.page.set_viewport_size({'width': 320, 'height': 900})
        self.page.wait_for_function("document.querySelector('#rows button')")
        self.page.click('#rows button:has-text("Details")')
        apply = "issue=5;$('apply').hidden=false;$('apply').click()"
        self.page.evaluate(apply)
        self.page.wait_for_function("document.getElementById('lookupBackup')")
        found = self.page.evaluate("""() => { const m = document.getElementById('lookupMessage'), b = document.getElementById('lookupBackup');
            return [m.textContent, m.nextElementSibling === b, m.contains(b), document.activeElement === m, b.querySelector('.backup-location-path').textContent]; }""")
        self.assertEqual(found, ['Metadata saved and verified. The recovery backup could not be deleted and was retained.', True, False, True, SHOWN])
        self.assert_layout('#lookupBackup', 320)
        self.page.evaluate("$('lookupMessage').textContent='Searching; new requests may take 20 seconds or more.'")
        self.page.wait_for_function("!document.getElementById('lookupBackup')")
        self.apply_result = (400, {'error': NOT_VERIFIED, 'verified': False, 'backup': BACKUP, 'backup_id': 'd' * 32})
        self.page.evaluate(apply)
        self.page.wait_for_function("document.getElementById('lookupBackup')")
        self.assertEqual(self.page.locator('#lookupMessage').text_content(), NOT_VERIFIED)
        self.apply_result = (200, {'ok': True, 'verified': True, 'backup': BACKUP, 'backup_retained': False, 'backup_removed_after_verification': True})
        self.page.evaluate(apply)
        self.page.wait_for_function("document.getElementById('lookupMessage').textContent==='Metadata saved and verified. Recovery backup deleted.'")
        self.assertEqual(self.page.locator('#lookupBackup').count(), 0)


if __name__ == '__main__':
    unittest.main()
