"""Folder help lines (FolderHelpActions 2026-10-16 and its Amendment) in the real page, offline: every
request is fulfilled locally, nothing reaches an engine, and File Explorer is never launched. Layout is
measured (rects, overflow, target sizes, focus ring room) at 320, 640 and 1280 px, 100% and 200% zoom.

Runs through the canonical headless harness (COMICS_TEST_CDP); skipped without it.
"""
import json
import os
import time
import unittest
import urllib.parse
from pathlib import Path
from test_yandex_dom import YandexDOMTests

LONG = '\\\\?\\D:\\Comics\\' + 'Very Long Folder Name With Spaces ' * 5 + 'Сага [Том 1]\\' + 'Unbrokensegment' * 5
SHOWN = 'D:\\Comics\\' + 'Very Long Folder Name With Spaces ' * 5 + 'Сага [Том 1]\\' + 'Unbrokensegment' * 5
REASONS = {
    'interrupted': 'Interrupted: the app stopped while writing this folder, so some comics may be unwritten.',
    'comic_changed': 'Stopped: a comic already written in this folder does not match what was verified.',
    'outside_folder': 'Stopped: the saved plan names a file outside this folder.',
    'not_verified': 'Stopped: a write could not be verified. The comic and its recovery backup need checking.',
    'backup_kept': 'Stopped: a recovery backup could not be removed after a write.',
    'library_busy': 'Stopped: this library was in use by another copy of the app.',
    'other': 'Stopped: this batch hit an error.',
}
CHECK_TIP = "Check this folder's comics without changing them. If all is in order, close this item and queue the unwritten comics again."
GEOMETRY = r"""() => {
  const host = document.querySelector('#queueAttention');
  const rect = n => n.getBoundingClientRect();
  const box = n => { const r = rect(n); return [r.left, r.top, r.right, r.bottom]; };
  const overlap = (a, b) => a[0] < b[2] - 0.5 && b[0] < a[2] - 0.5 && a[1] < b[3] - 0.5 && b[1] < a[3] - 0.5;
  const visible = n => !n.hidden && n.getClientRects().length > 0 && rect(n).height > 0;
  const name = n => n.className + ':' + n.textContent.slice(0, 30);
  const clashes = [];
  const cards = [...host.querySelectorAll('.help-card')];
  for (const card of cards) {
    const pieces = [];
    for (const child of card.children) {
      if (!visible(child)) continue;
      if (child.matches('.help-actions, .help-offer')) pieces.push(...[...child.children].filter(visible));
      else if (child.matches('.help-confirm')) pieces.push(...[...child.querySelectorAll('p, button')].filter(visible));
      else if (child.matches('.help-list')) for (const row of child.children) pieces.push(...[...row.querySelectorAll('.help-row-name, .help-row-finding, button, .help-error')].filter(visible));
      else pieces.push(child);
    }
    const c = box(card);
    for (let i = 0; i < pieces.length; i++) {
      const a = box(pieces[i]);
      if (a[0] < c[0] - 0.5 || a[2] > c[2] + 0.5) clashes.push(['outside card', name(pieces[i])]);
      for (let j = i + 1; j < pieces.length; j++) if (overlap(a, box(pieces[j]))) clashes.push([name(pieces[i]), name(pieces[j])]);
    }
  }
  for (let i = 0; i < cards.length; i++) for (let j = i + 1; j < cards.length; j++) if (overlap(box(cards[i]), box(cards[j]))) clashes.push(['cards', i, j]);
  const buttons = [...host.querySelectorAll('button')].filter(visible).map(b => {
    const r = rect(b), c = rect(b.closest('.help-card'));
    return {label: b.textContent, confirm: Boolean(b.closest('.help-confirm')), w: r.width, h: r.height, ring: r.left - 4 >= c.left - 0.5 && r.right + 4 <= c.right + 0.5 && r.top - 4 >= c.top - 0.5 && r.bottom + 4 <= c.bottom + 0.5};
  });
  const doneBox = document.getElementById('attentionDone');
  return {clashes, buttons, cards: cards.length, overflow: host.scrollWidth - host.clientWidth,
          page: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          done: visible(doneBox) && cards.some(card => overlap(box(card), box(doneBox)))};
}"""


def item(ident, code='interrupted', folder='D:\\Comics\\Marvel\\X-Men', error='Interrupted batch; inspect results and retained backups before requeuing.'):
    return {'id': ident, 'code': code, 'folder': folder, 'error': error}


def problems(total, offer=None, finding='zip_failed', basis=None):
    rows = [{'id': '%032x' % (n + 1), 'name': 'Batman %03d (2019).cbz' % n, 'finding': finding, 'file': 'Batman %03d (2019).cbz' % n}
            for n in range(min(total, 20))]
    if basis:
        for row in rows:
            row['basis'] = basis
    reply = {'code': 'problems', 'total': total, 'problems': rows}
    if offer:
        reply['offer'] = offer
    return reply


def temp_problems(comics, backups=1):
    """A check with the Delete offer of Amendment 2: per comic its temporary file, then `backups` backups."""
    rows, offer_backups, offer_temps = [], [], []
    for n in range(comics):
        name = 'Batman %03d (2019).cbz' % n
        ident = '%032x' % (len(rows) + 1)
        rows.append({'id': ident, 'name': name, 'finding': 'temp_left', 'file': name + '.metadata-tmp'})
        offer_temps.append({'id': ident, 'name': name, 'file': name + '.metadata-tmp'})
        for k in range(backups):
            ident = '%032x' % (len(rows) + 1)
            rows.append({'id': ident, 'name': name, 'finding': 'backup_left', 'file': name + '.17600000000000%05d.bak' % k, 'basis': 'original'})
            offer_backups.append({'id': ident, 'name': name, 'basis': 'original'})
    return {'code': 'problems', 'total': len(rows), 'problems': rows,
            'offer': {'kind': 'delete_backup', 'unwritten': 2, 'backups': offer_backups, 'temps': offer_temps}}


CHANGED = 'Nothing was deleted: a comic or one of its files changed since the check. The list below is updated.'
ONE = 'Batman 000 (2019).cbz'


@unittest.skipUnless(os.environ.get('COMICS_TEST_CDP'), 'Requires owned offline headless fixture')
class FolderHelpDOMTests(YandexDOMTests):
    def setUp(self):
        super().setUp()
        self.root = Path(__file__).resolve().parents[1]
        self.attention = [item('1'), item('2', 'other', 'D:\\Comics\\DC\\Batman', '')]
        self.control = {}
        self.posts, self.held, self.pending = [], set(), {}
        self.replies = {'/api/attention/check': (200, problems(3)), '/api/attention/reveal': (200, {'ok': True}),
                        '/api/attention/delete-backups': (200, {'ok': True, 'unwritten': 2, 'written': 0, 'deleted': 1}),
                        '/api/attention/close': (200, {'ok': True})}
        self.context.add_init_script('window.setInterval=()=>0;')
        self.page.route('https://comics-fixture.invalid/**', self.route)
        self.page.set_viewport_size({'width': 1280, 'height': 900})
        self.page.goto('https://comics-fixture.invalid/')
        self.page.wait_for_function('document.querySelectorAll("#queueAttention .help-card").length===2')

    def route(self, route):
        path = urllib.parse.urlparse(route.request.url).path
        static = {'/': ('static/index.html', 'text/html'), '/comic-recovery.js': ('static/comic-recovery.js', 'text/javascript'),
                  '/kept-backups.js': ('static/kept-backups.js', 'text/javascript'), '/folder-help.js': ('static/folder-help.js', 'text/javascript'),
                  '/comic-recovery.css': ('static/comic-recovery.css', 'text/css'), '/lens-control.js': ('static/lens-control.js', 'text/javascript')}
        if path in static:
            name, kind = static[path]
            return route.fulfill(body=(self.root / name).read_text(encoding='utf-8'), content_type=kind)
        if path in ('/reverse-image.js', '/shell-ui.js'):
            return route.fulfill(body='', content_type='text/javascript')
        if path.startswith('/api/attention/'):
            self.posts.append((path, json.loads(route.request.post_data or 'null')))
            if path in self.held:
                self.pending[path] = route
                return
            if self.replies[path] is None:
                return route.abort()  # No answer from the app.
            status, body = self.replies[path]
            return route.fulfill(status=status, json=body)
        if path == '/api/backups':
            data = {'items': [], 'count': 0, 'bytes': 0, 'bounded': False}
        elif path == '/api/state':
            data = {'version': '0.2.5', 'roots': ['D:\\Comics'], 'job': {'message': 'Ready', 'running': False, 'visited': 0, 'changed': 0}, 'counts': {}, 'totals': {}}
        elif path == '/api/comics':
            data = {'rows': [], 'total': 0}
        elif path == '/api/progress':
            data = {'queue': {'alive': True, 'attention': self.attention}, 'timestamp': 1, 'research': {}, 'folders': {}, 'providers': {}, 'control': self.control}
        elif path == '/api/browser-verification':
            data = {'engine': 'google_lens', 'phase': 'idle', 'human_verification': False, 'window': 'closed', 'alive': True, 'updated': 1, 'control': self.control}
        else:
            return route.abort()
        route.fulfill(json=data)

    def card(self, ident):
        return self.page.locator('#queueAttention .help-card[data-ticket="%s"]' % ident)

    def poll(self, times=2):
        for _ in range(times):
            self.page.evaluate('async()=>{await verification();await progress()}')

    def active(self, expression='document.activeElement'):
        return self.page.evaluate('() => { const a = ' + expression + '; return a ? [a.tagName, a.className, a.textContent] : null; }')

    def wait_for(self, predicate, timeout=5.0):
        end = time.monotonic() + timeout
        while not predicate():
            self.assertLess(time.monotonic(), end, 'timed out')
            self.page.wait_for_timeout(20)

    def release(self, path, status, body):
        self.wait_for(lambda: path in self.pending)
        self.held.discard(path)
        self.pending.pop(path).fulfill(status=status, json=body)

    @staticmethod
    def press_blocked(locator):
        # Playwright waits for an aria-disabled button to become actionable; a person's click does not.
        locator.evaluate('button => button.click()')

    def test_reason_copy_last_error_tooltips_and_names(self):
        codes = list(REASONS)
        self.attention = [item(str(n), code, LONG if n == 0 else 'D:\\Comics\\Folder %d' % n, 'Raw text %d.' % n) for n, code in enumerate(codes)]
        self.attention += [item('7', 'other', 'D:\\Comics\\Empty', ''), item('8', 'unknown_code', 'D:\\Comics\\Long', 'x' * 400)]
        self.poll(1)
        found = self.page.evaluate("""() => [...document.querySelectorAll('#queueAttention .help-card')].map(c => ({
            id: c.dataset.ticket, head: c.querySelector('.help-head').textContent, reason: c.querySelector('.help-reason').textContent,
            last: c.querySelector('.help-last').hidden ? null : c.querySelector('.help-last').textContent,
            paused: c.querySelector('.help-paused').hidden, status: [c.querySelector('.help-status').getAttribute('role'), c.querySelector('.help-status').textContent],
            buttons: [...c.querySelectorAll('button')].map(b => [b.textContent, b.title, b.getAttribute('aria-label'), b.hasAttribute('aria-disabled'), b.disabled])}))""")
        self.assertEqual([f['id'] for f in found], [str(n) for n in range(9)])
        self.assertEqual(found[0]['head'], 'Your help is needed: ' + SHOWN)  # No \\?\ prefix.
        self.assertEqual(self.page.evaluate("document.querySelector('.help-path wbr') !== null"), True)
        for card, code in zip(found, codes):
            self.assertEqual(card['reason'], REASONS[code])
            self.assertEqual(card['last'], None if code == 'interrupted' else 'Last error: Raw text %s.' % card['id'])
        self.assertEqual((found[7]['reason'], found[7]['last']), ('Stopped: this batch hit an error with no details.', None))
        self.assertEqual((found[8]['reason'], found[8]['last']), (REASONS['other'], 'Last error: ' + 'x' * 300 + '…'))
        name = 'Unbrokensegment' * 5
        self.assertEqual(found[0]['buttons'], [
            ['Check and requeue', CHECK_TIP, 'Check and requeue: ' + name, False, False],
            ['Open folder', 'Open this folder in File Explorer to check its comics. Nothing is changed.', 'Open folder: ' + name, False, False]])
        self.assertTrue(all(card['paused'] and card['status'] == ['status', ''] for card in found))

    def test_card_and_failure_list_survive_polls_and_keep_focus(self):
        check = self.card('1').locator('button', has_text='Check and requeue')
        check.focus()
        self.page.evaluate("document.activeElement.dataset.marker='kept'")
        self.poll()
        self.assertEqual(self.page.evaluate('document.activeElement.dataset.marker'), 'kept')
        check.press('Enter')
        self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] .help-status').textContent.startsWith('Not requeued')")
        status = self.card('1').locator('.help-status')
        self.assertEqual(status.text_content(), 'Not requeued: 3 problems found, and nothing was changed. Fix them, then check again.')
        self.assertEqual(self.active()[1], 'help-status')
        self.page.evaluate("document.querySelector('[data-ticket=\"1\"] .help-row').dataset.marker='row'")
        self.poll()
        self.assertEqual(self.page.evaluate("document.querySelector('[data-ticket=\"1\"] .help-row').dataset.marker"), 'row')
        self.assertEqual(self.active()[1], 'help-status')
        self.page.keyboard.press('Tab')
        self.assertEqual(self.page.evaluate('document.activeElement.getAttribute("aria-label")'), 'Show in folder: Batman 000 (2019).cbz')
        self.assertEqual(self.card('1').locator('.help-row-finding').first.text_content(), 'Failed the zip test. The archive is damaged.')
        self.assertEqual(self.posts, [('/api/attention/check', {'ticket': '1'})])
        # Singular, then the 21-problem cap.
        self.replies['/api/attention/check'] = (200, problems(1))
        check.click()
        self.page.wait_for_function("document.querySelectorAll('[data-ticket=\"1\"] .help-row').length===1")
        self.assertEqual(status.text_content(), 'Not requeued: 1 problem found, and nothing was changed. Fix it, then check again.')
        self.replies['/api/attention/check'] = (200, problems(21))
        check.click()
        self.page.wait_for_function("document.querySelectorAll('[data-ticket=\"1\"] .help-row').length===20")
        self.assertEqual(self.card('1').locator('.help-more').text_content(), '1 more not shown. Fix these first, then check again.')
        self.assertEqual(status.text_content(), 'Not requeued: 21 problems found, and nothing was changed. Fix them, then check again.')

    def test_one_check_at_a_time_and_focus_left_alone_elsewhere(self):
        self.held.add('/api/attention/check')
        first = self.card('1').locator('button', has_text='Check and requeue')
        first.click()
        self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] .help-status').textContent!==''")
        self.assertEqual(self.card('1').locator('.help-status').text_content(), "Checking this folder's comics. This can take a few minutes.")
        self.assertEqual((first.get_attribute('aria-disabled'), first.get_attribute('title')), ('true', 'Checking now. Nothing is changed.'))
        second = self.card('2').locator('button', has_text='Check and requeue')
        self.assertEqual((second.get_attribute('aria-disabled'), second.get_attribute('title')), ('true', 'Another folder is being checked. Wait for it to finish.'))
        self.wait_for(lambda: '/api/attention/check' in self.pending)
        self.press_blocked(first)
        self.press_blocked(second)
        self.page.wait_for_timeout(200)
        self.assertEqual(len(self.posts), 1)
        self.poll()
        self.assertEqual(first.get_attribute('aria-disabled'), 'true')
        self.page.focus('#query')  # Sergei moved on while the check ran.
        self.release('/api/attention/check', 200, problems(2))
        self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] .help-status').textContent.startsWith('Not requeued')")
        self.assertEqual(self.page.evaluate('document.activeElement.id'), 'query')
        self.assertEqual((first.get_attribute('aria-disabled'), first.get_attribute('title')), (None, CHECK_TIP))
        self.assertEqual(second.get_attribute('aria-disabled'), None)

    def test_paused_blocks_the_check_but_not_open_or_show(self):
        check = self.card('1').locator('button', has_text='Check and requeue')
        check.click()
        self.page.wait_for_function("document.querySelectorAll('[data-ticket=\"1\"] .help-row').length===3")
        self.control = {'requested': True, 'phase': 'paused'}
        self.poll(1)
        note = self.card('1').locator('.help-paused')
        self.assertEqual((note.is_visible(), note.text_content()), (True, 'Paused. Resume processing to requeue or recheck this folder.'))
        self.assertEqual((check.get_attribute('aria-disabled'), check.get_attribute('title'), check.get_attribute('aria-describedby')),
                         ('true', 'Processing is paused. Resume processing to check and requeue.', note.get_attribute('id')))
        posts = len(self.posts)
        self.press_blocked(check)
        self.page.wait_for_timeout(200)
        self.assertEqual(len(self.posts), posts)
        self.card('1').locator('button', has_text='Open folder').click()
        self.page.wait_for_function('n=>document.querySelector("[data-ticket=\\"1\\"] button.help-secondary").getAttribute("aria-disabled")===null', arg=0)
        self.assertEqual(self.posts[-1], ('/api/attention/reveal', {'ticket': '1'}))
        self.replies['/api/attention/reveal'] = (400, {'error': 'x', 'code': 'not_found'})
        self.card('1').locator('.help-row button').first.click()
        self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] .help-row .help-error')")
        self.assertEqual(self.posts[-1], ('/api/attention/reveal', {'ticket': '1', 'problem': '%032x' % 1}))
        self.assertEqual(self.card('1').locator('.help-row .help-error').text_content(), 'File not found. Check again to update this list.')
        self.replies['/api/attention/reveal'] = (400, {'error': 'x', 'code': 'folder_unavailable'})
        self.card('1').locator('button', has_text='Open folder').click()
        self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] > .help-error')")
        self.assertEqual(self.card('1').locator('.help-error').all_text_contents(), ['Folder is unavailable. Check that the library drive is connected.'])
        self.replies['/api/attention/reveal'] = (400, {'error': 'x', 'code': 'failed'})
        self.card('1').locator('button', has_text='Open folder').click()
        self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] > .help-error')?.textContent.startsWith('Could not')")
        self.assertEqual(self.card('1').locator('.help-error').all_text_contents(), ['Could not open File Explorer. Use the path above.'])

    def test_delete_backup_offer_confirm_keyboard_and_success(self):
        offer = {'kind': 'delete_backup', 'unwritten': 2, 'backups': [{'id': '%032x' % 1, 'name': 'Batman 000 (2019).cbz', 'basis': 'written'}]}
        self.replies['/api/attention/check'] = (200, problems(1, offer, 'backup_left', 'written'))
        check = self.card('1').locator('button', has_text='Check and requeue')
        check.focus()
        check.press('Enter')
        self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] .help-offer button')")
        self.assertEqual(self.card('1').locator('.help-status').text_content(),
                         'Not requeued: 1 problem found, and nothing was changed. Delete the kept backup to requeue, or check again.')
        self.assertEqual(self.card('1').locator('.help-row-finding').text_content(),
                         'A recovery backup is kept. The comic was written and verified; the backup is the only way to undo that.')
        self.page.keyboard.press('Tab')
        opener = self.card('1').locator('.help-offer button')
        self.assertEqual(self.page.evaluate('document.activeElement.textContent'), 'Delete backup and requeue')
        self.assertEqual((opener.get_attribute('aria-label'), opener.get_attribute('aria-expanded'), opener.get_attribute('title')),
                         ('Delete backup and requeue: X-Men', 'false', "Delete this folder's kept recovery backup, then close this item and queue the unwritten comics again. You are asked to confirm first."))
        self.page.keyboard.press('Enter')
        self.assertEqual(self.page.evaluate('document.activeElement.textContent'), 'Keep it')
        self.assertEqual(self.page.evaluate("[...document.querySelectorAll('.help-confirm p')].map(p=>p.textContent)"),
                         ['Delete this backup and requeue?', 'Batman 000 (2019).cbz was written and verified. The backup is the only way to undo that change. Deleting is permanent.'])
        self.poll()
        self.assertEqual(self.page.evaluate('document.activeElement.textContent'), 'Keep it')  # The poll never closes the confirm.
        self.page.keyboard.press('Escape')
        self.assertEqual((self.page.evaluate('document.activeElement.textContent'), opener.get_attribute('aria-expanded')), ('Delete backup and requeue', 'false'))
        self.page.keyboard.press('Enter')
        self.control = {'requested': True, 'phase': 'paused'}
        self.poll(1)
        yes = self.card('1').locator('.help-confirm button', has_text='Delete and requeue')
        self.assertEqual((yes.get_attribute('aria-disabled'), yes.get_attribute('title')),
                         ('true', 'Processing is paused. Resume processing to delete the backup and requeue.'))
        self.assertTrue(self.card('1').locator('.help-confirm').is_visible())  # Stays open under the pointer.
        self.control = {}
        self.poll(1)
        self.page.keyboard.press('Shift+Tab')
        self.assertEqual(self.page.evaluate('document.activeElement.textContent'), 'Delete and requeue')
        self.page.keyboard.press('Enter')
        self.page.wait_for_function("!document.querySelector('[data-ticket=\"1\"]')")
        self.assertEqual(self.posts[-1], ('/api/attention/delete-backups', {'ticket': '1', 'backups': ['%032x' % 1], 'temps': []}))
        done = self.page.locator('#attentionDone')
        self.assertEqual((done.text_content(), done.get_attribute('role')),
                         ('Backup deleted. Requeued X-Men: 2 unwritten comics will be checked at the next folder pass.', 'status'))
        self.assertEqual(self.page.evaluate('document.activeElement.id'), 'attentionDone')
        self.poll()  # A stale payload still lists the closed ticket: the card does not come back.
        self.assertEqual(self.card('1').count(), 0)
        self.page.keyboard.press('Tab')
        self.assertEqual(self.page.evaluate('document.activeElement.getAttribute("aria-label")'), 'Check and requeue: Batman')
        self.attention = [self.attention[1]]
        self.poll(1)
        self.assertTrue(done.is_visible())  # Stays until the next check starts.
        self.replies['/api/attention/check'] = (400, {'error': 'x', 'code': 'paused'})
        self.card('2').locator('button', has_text='Check and requeue').click()
        self.page.wait_for_function("document.querySelector('[data-ticket=\"2\"] .help-status').textContent.startsWith('Not requeued: processing')")
        self.assertTrue(done.is_hidden())

    def test_delete_failures_and_mixed_confirm(self):
        backups = [{'id': '%032x' % (n + 1), 'name': 'Batman %03d (2019).cbz' % n, 'basis': 'original' if n else 'written'} for n in range(3)]
        offer = {'kind': 'delete_backup', 'unwritten': 1, 'backups': backups}
        reply = problems(3, offer, 'backup_left')
        for row, backup in zip(reply['problems'], backups):
            row['basis'] = backup['basis']
        self.replies['/api/attention/check'] = (200, reply)
        status = self.card('1').locator('.help-status')
        cases = [((400, {'error': 'x', 'code': 'delete_failed', 'deleted': 1, 'total': 3}),
                  'Deleted 1 of 3 backups. 2 could not be deleted, so nothing was requeued. Close any program using them, then check again.'),
                 ((400, {'error': 'x', 'code': 'delete_failed', 'deleted': 0, 'total': 3}),
                  'Nothing was deleted: a backup could not be deleted. Close any program using them, then try again.'),
                 ((400, {'error': 'the check found problems', 'code': 'not_requeued', 'deleted': 3, 'reason': 'problems', 'check': problems(2)}),
                  '3 backups deleted, but not requeued: the check found 2 problems. Use Check and requeue to finish.'),
                 ((400, {'error': 'processing is paused.', 'code': 'not_requeued', 'deleted': 3, 'reason': 'paused'}),
                  '3 backups deleted, but not requeued: processing was paused. Use Check and requeue to finish.'),
                 ((400, {'error': 'x', 'code': 'changed', 'check': problems(1)}), CHANGED),
                 # Amendment 2 B5, backups only: file_gone (Futaba m1) and writing.
                 ((400, {'error': 'x', 'code': 'file_gone', 'check': problems(1)}),
                  'Nothing was deleted: a backup from the check is no longer there. The list below is updated.'),
                 ((400, {'error': 'x', 'code': 'writing', 'deleted': 0, 'total': 3}),
                  'Nothing was deleted: a comic in this folder is being written now. Wait for it to finish, then try again.'),
                 ((400, {'error': 'x', 'code': 'writing', 'deleted': 1, 'total': 3}),
                  'Deleted 1 of 3 backups. A comic in this folder is being written now, so nothing was requeued. Wait for it to finish, then check again.')]
        for answer, text in cases:
            with self.subTest(text=text):
                self.card('1').locator('button', has_text='Check and requeue').click()
                self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] .help-offer button')")
                self.assertEqual(status.text_content(), 'Not requeued: 3 problems found, and nothing was changed. Delete the kept backups to requeue, or check again.')
                self.card('1').locator('.help-offer button').click()
                self.assertEqual(self.page.evaluate("[...document.querySelectorAll('.help-confirm p')].map(p=>p.textContent)"),
                                 ['Delete 3 backups and requeue?', '2 comics are exactly as they were before the app started writing; there is nothing to undo.',
                                  '1 comic was written and verified; its backup is the only way to undo that change.', 'Deleting is permanent.'])
                self.assertEqual(self.page.evaluate('document.activeElement.textContent'), 'Keep them')
                self.replies['/api/attention/delete-backups'] = answer
                self.card('1').locator('.help-confirm button', has_text='Delete 3 backups and requeue').click()
                self.page.wait_for_function('t=>document.querySelector("[data-ticket=\\"1\\"] .help-status").textContent===t', arg=text)
                self.assertEqual(self.card('1').locator('.help-confirm').count(), 0)
                self.assertEqual(self.active()[1], 'help-status')

    def test_unreadable_plan_offers_close_and_recheck(self):
        self.replies['/api/attention/check'] = (400, {'error': 'x', 'code': 'plan_unreadable', 'offer': {'kind': 'close_recheck'}})
        self.card('1').locator('button', has_text='Check and requeue').click()
        self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] .help-offer button')")
        self.assertEqual(self.card('1').locator('.help-status').text_content(),
                         'Not checked: the saved plan for this folder cannot be read, and nothing was changed. Check its comics in the folder, then close this item to recheck the folder.')
        button = self.card('1').locator('.help-offer button')
        self.assertEqual((button.text_content(), button.get_attribute('aria-label'), button.get_attribute('title')),
                         ('Close and recheck folder', 'Close and recheck folder: X-Men',
                          'Close this item and have this folder checked again at the next folder pass. No comic or backup file is changed.'))
        self.replies['/api/attention/close'] = (400, {'error': 'x', 'code': 'library_busy'})
        button.click()
        self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] .help-status').textContent.startsWith('Not closed')")
        self.assertEqual(self.card('1').locator('.help-status').text_content(),
                         'Not closed: another copy of the app is using this library, and nothing was changed. Close it, then try again.')
        self.replies['/api/attention/close'] = (200, {'ok': True})
        button.click()
        self.page.wait_for_function("!document.querySelector('[data-ticket=\"1\"]')")
        self.assertEqual(self.page.locator('#attentionDone').text_content(),
                         'Closed X-Men: the folder will be checked again at the next folder pass. No comic or backup file was changed.')
        self.assertEqual(self.posts[-1], ('/api/attention/close', {'ticket': '1'}))

    def test_close_offer_when_every_finding_changed_after_planning(self):
        close = {'kind': 'close_recheck'}
        self.replies['/api/attention/check'] = (200, problems(1, close, 'unwritten_changed'))
        check = self.card('1').locator('button', has_text='Check and requeue')
        status = self.card('1').locator('.help-status')
        check.focus()
        check.press('Enter')
        self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] .help-offer button')")
        self.assertEqual(status.text_content(), 'Not requeued: 1 problem found, and nothing was changed. The comic changed after this batch '
                         'was planned. Close this item to have the folder checked again at the next folder pass.')
        self.assertEqual(self.card('1').locator('.help-row-finding').text_content(), 'Does not match the file this batch planned.')
        self.assertEqual(self.active()[1], 'help-status')
        self.page.keyboard.press('Tab')
        button = self.card('1').locator('.help-offer button')
        self.assertEqual(self.page.evaluate('document.activeElement.textContent'), 'Close and recheck folder')
        self.assertEqual((button.get_attribute('class'), button.get_attribute('aria-label'), button.get_attribute('title'), button.get_attribute('aria-expanded')),
                         ('help-secondary', 'Close and recheck folder: X-Men',
                          'Close this item and have this folder checked again at the next folder pass. No comic or backup file is changed.', None))
        self.replies['/api/attention/check'] = (200, problems(3, close, 'unwritten_changed'))
        check.click()
        self.page.wait_for_function("document.querySelectorAll('[data-ticket=\"1\"] .help-row').length===3")
        self.assertEqual(status.text_content(), 'Not requeued: 3 problems found, and nothing was changed. These comics changed after this batch '
                         'was planned. Close this item to have the folder checked again at the next folder pass.')
        # The folder changed between the check and the click: refused, and the dead button goes.
        self.replies['/api/attention/close'] = (400, {'error': 'x', 'code': 'plan_readable'})
        button.focus()
        button.press('Enter')
        self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] .help-status').textContent.startsWith('Not closed')")
        self.assertEqual(status.text_content(), 'Not closed: this folder changed since the check, and nothing was changed. Use Check and requeue.')
        self.assertEqual((self.card('1').locator('.help-offer button').count(), self.card('1').locator('.help-offer').is_hidden()), (0, True))
        self.assertEqual(self.active()[1], 'help-status')
        self.assertEqual(self.card('1').locator('.help-row').count(), 3)  # The last check's list stays.
        self.assertEqual(self.posts[-1], ('/api/attention/close', {'ticket': '1'}))
        check.click()
        self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] .help-offer button')")
        self.replies['/api/attention/close'] = (200, {'ok': True})
        self.card('1').locator('.help-offer button').click()
        self.page.wait_for_function("!document.querySelector('[data-ticket=\"1\"]')")
        self.assertEqual(self.page.locator('#attentionDone').text_content(),
                         'Closed X-Men: the folder will be checked again at the next folder pass. No comic or backup file was changed.')

    def test_outside_library_no_answer_and_several_backups_of_one_comic(self):
        status = self.card('1').locator('.help-status')
        check = self.card('1').locator('button', has_text='Check and requeue')
        outside = (400, {'error': 'this folder is not in the current library.', 'code': 'outside_library'})
        self.replies['/api/attention/check'] = outside
        check.click()
        self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] .help-status').textContent.startsWith('Not checked')")
        self.assertEqual(status.text_content(), 'Not checked: this folder is not in the current library, and nothing was changed. '
                         'Set the library back to the one that holds it, then check again.')
        self.replies['/api/attention/reveal'] = outside
        self.card('1').locator('button', has_text='Open folder').click()
        self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] > .help-error')")
        self.assertEqual(self.card('1').locator('.help-error').all_text_contents(), ['This folder is not in the current library.'])
        self.replies['/api/attention/check'] = (400, {'error': 'x', 'code': 'plan_unreadable', 'offer': {'kind': 'close_recheck'}})
        check.click()
        self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] .help-offer button')")
        self.replies['/api/attention/close'] = outside
        self.card('1').locator('.help-offer button').click()
        self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] .help-status').textContent.startsWith('Not closed')")
        self.assertEqual(status.text_content(), 'Not closed: this folder is not in the current library, and nothing was changed. '
                         'Set the library back to the one that holds it, then try again.')
        # Two backups of one written comic and one of an unchanged comic.
        backups = [{'id': '%032x' % 1, 'name': 'Batman 000 (2019).cbz', 'basis': 'written'},
                   {'id': '%032x' % 2, 'name': 'Batman 000 (2019).cbz', 'basis': 'written'},
                   {'id': '%032x' % 3, 'name': 'Batman 001 (2019).cbz', 'basis': 'original'}]
        self.replies['/api/attention/check'] = (200, problems(3, {'kind': 'delete_backup', 'unwritten': 1, 'backups': backups}, 'backup_left', 'written'))
        for answer, text in ((outside, 'Nothing was deleted: this folder is not in the current library. Set the library back to the one that holds it, then try again.'),
                             (None, 'No answer from the app. Some or all of the backups may already be deleted. Use Check and requeue to see the current state.')):
            with self.subTest(text=text):
                check.click()
                self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] .help-offer button')")
                self.card('1').locator('.help-offer button').click()
                self.assertEqual(self.page.evaluate("[...document.querySelectorAll('.help-confirm p')].map(p=>p.textContent)"),
                                 ['Delete 3 backups and requeue?', '1 comic is exactly as it was before the app started writing; there is nothing to undo.',
                                  '1 comic was written and verified; its backups are the only way to undo that change.', 'Deleting is permanent.'])
                self.replies['/api/attention/delete-backups'] = answer
                self.card('1').locator('.help-confirm button', has_text='Delete 3 backups and requeue').click()
                self.page.wait_for_function('t=>document.querySelector("[data-ticket=\\"1\\"] .help-status").textContent===t', arg=text)
                self.assertEqual(self.active()[1], 'help-status')
        # One backup, no answer: the singular stays.
        one = [{'id': '%032x' % 1, 'name': 'Batman 000 (2019).cbz', 'basis': 'original'}]
        self.replies['/api/attention/check'] = (200, problems(1, {'kind': 'delete_backup', 'unwritten': 1, 'backups': one}, 'backup_left', 'original'))
        check.click()
        self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] .help-offer button')")
        self.card('1').locator('.help-offer button').click()
        self.replies['/api/attention/delete-backups'] = None
        self.card('1').locator('.help-confirm button', has_text='Delete and requeue').click()
        text = 'No answer from the app. The backup may already be deleted. Use Check and requeue to see the current state.'
        self.page.wait_for_function('t=>document.querySelector("[data-ticket=\\"1\\"] .help-status").textContent===t', arg=text)

    def confirm_text(self, ident='1'):
        return self.page.evaluate('i=>[...document.querySelectorAll(`[data-ticket="${i}"] .help-confirm p`)].map(p=>p.textContent)', ident)

    def offered(self, reply, ident='1'):
        self.replies['/api/attention/check'] = (200, reply)
        self.card(ident).locator('button', has_text='Check and requeue').click()
        self.page.wait_for_function('i=>document.querySelector(`[data-ticket="${i}"] .help-offer button`)', arg=ident)

    def test_temp_offer_labels_tooltips_and_confirm(self):
        """Amendment 2 B3, B4 and B7: every (b, t) shape of the offer with the app's temporary files."""
        status = self.card('1').locator('.help-status')
        opener = self.card('1').locator('.help-offer button')
        two_backups = temp_problems(1, backups=2)
        cases = [
            (temp_problems(1), 'Delete backup and temporary file, then requeue', '1 backup and 1 temporary file',
             'Not requeued: 2 problems found, and nothing was changed. Delete the kept backup and leftover temporary file to requeue, or check again.',
             ['Delete 1 backup and 1 temporary file, then requeue?', ONE + ' is exactly as it was before the app started writing, so there is nothing to undo. '
              'Left beside it: ' + ONE + '.metadata-tmp, a temporary file made by the app. Deleting is permanent.'],
             'Delete 2 files and requeue', 'Keep them'),
            (temp_problems(3), 'Delete backups and temporary files, then requeue', '3 backups and 3 temporary files',
             'Not requeued: 6 problems found, and nothing was changed. Delete the kept backups and leftover temporary files to requeue, or check again.',
             ['Delete 3 backups and 3 temporary files, then requeue?', '3 comics are exactly as they were before the app started writing; there is nothing to undo.',
              'Left beside them: 3 temporary files made by the app (listed below).', 'Deleting is permanent.'],
             'Delete 6 files and requeue', 'Keep them'),
            (two_backups, 'Delete backups and temporary file, then requeue', '2 backups and 1 temporary file',
             'Not requeued: 3 problems found, and nothing was changed. Delete the kept backups and leftover temporary file to requeue, or check again.',
             ['Delete 2 backups and 1 temporary file, then requeue?', '1 comic is exactly as it was before the app started writing; there is nothing to undo.',
              'Left beside them: 1 temporary file made by the app (listed below).', 'Deleting is permanent.'],
             'Delete 3 files and requeue', 'Keep them'),
            (temp_problems(1, backups=0), 'Delete temporary file, then requeue', '1 temporary file',
             'Not requeued: 1 problem found, and nothing was changed. Delete the leftover temporary file to requeue, or check again.',
             ['Delete 1 temporary file, then requeue?', ONE + ' is exactly as it was before the app started writing. Beside it: ' + ONE
              + '.metadata-tmp, a temporary file made by the app. Deleting is permanent.'],
             'Delete and requeue', 'Keep it'),
            (temp_problems(2, backups=0), 'Delete temporary files, then requeue', '2 temporary files',
             'Not requeued: 2 problems found, and nothing was changed. Delete the leftover temporary files to requeue, or check again.',
             ['Delete 2 temporary files, then requeue?', '2 comics are exactly as they were before the app started writing. Beside them: '
              '2 temporary files made by the app (listed below). Deleting is permanent.'],
             'Delete 2 files and requeue', 'Keep them'),
        ]
        for reply, label, files, summary, lines, face, keep in cases:
            with self.subTest(label=label, files=files):
                self.offered(reply)
                self.assertEqual(status.text_content(), summary)
                self.assertEqual((opener.text_content(), opener.get_attribute('aria-label'), opener.get_attribute('title')),
                                 (label, label + ': X-Men', 'Delete ' + files + ' left in this folder, then close this item and queue the '
                                  'unwritten comics again. You are asked to confirm first.'))
                opener.click()
                self.assertEqual(self.confirm_text(), lines)
                yes = self.card('1').locator('.help-confirm .help-danger')
                self.assertEqual((yes.text_content(), yes.get_attribute('title')), (face, 'Delete ' + files + ' permanently, then requeue.'))
                self.assertEqual(self.active()[2], keep)
                self.assertEqual(self.card('1').locator('.help-confirm .help-secondary').get_attribute('title'), 'Go back. Nothing is deleted.')
                self.page.keyboard.press('Escape')
                self.assertEqual(self.active()[2], label)
        rows = self.card('1').locator('.help-row-finding').all_text_contents()
        self.assertEqual(rows, ['A leftover temporary file is next to this comic: ' + ONE + '.metadata-tmp.',
                                'A leftover temporary file is next to this comic: Batman 001 (2019).cbz.metadata-tmp.'])

    def test_temp_offer_paused_in_flight_and_success(self):
        opener = self.card('1').locator('.help-offer button')
        self.offered(temp_problems(1))
        self.assertEqual(self.card('1').locator('.help-row-finding').all_text_contents(), [
            'A leftover temporary file is next to this comic: ' + ONE + '.metadata-tmp.',
            'A recovery backup is kept. The comic is exactly as it was before the write, so there is nothing to undo.'])
        opener.click()
        yes = self.card('1').locator('.help-confirm .help-danger')
        keep = self.card('1').locator('.help-confirm .help-secondary')
        self.control = {'requested': True, 'phase': 'paused'}
        self.poll(1)
        paused = 'Processing is paused. Resume processing to delete 1 backup and 1 temporary file, then requeue.'
        for node in (opener, yes):
            self.assertEqual((node.get_attribute('aria-disabled'), node.get_attribute('title')), ('true', paused))
        self.assertEqual((keep.get_attribute('aria-disabled'), self.active()[2]), (None, 'Keep them'))
        self.control = {}
        self.poll(1)
        self.held.add('/api/attention/delete-backups')
        yes.click()
        status = self.card('1').locator('.help-status')
        self.page.wait_for_function("document.querySelector('[data-ticket=\"1\"] .help-status').textContent.startsWith('Deleting')")
        self.assertEqual(status.text_content(), "Deleting 1 backup and 1 temporary file, then checking this folder's comics again. This can take a few minutes.")
        own = 'Deleting 1 backup and 1 temporary file, then checking again.'
        for node in (opener, yes):
            self.assertEqual((node.get_attribute('aria-disabled'), node.get_attribute('title')), ('true', own))
        self.assertEqual(keep.get_attribute('aria-disabled'), 'true')
        self.release('/api/attention/delete-backups', 200, {'ok': True, 'unwritten': 2, 'written': 0, 'deleted': 2, 'deleted_backups': 1, 'deleted_temps': 1})
        self.page.wait_for_function("!document.querySelector('[data-ticket=\"1\"]')")
        self.assertEqual(self.page.locator('#attentionDone').text_content(),
                         '1 backup and 1 temporary file deleted. Requeued X-Men: 2 unwritten comics will be checked at the next folder pass.')
        self.assertEqual(self.posts[-1], ('/api/attention/delete-backups', {'ticket': '1', 'backups': ['%032x' % 2], 'temps': ['%032x' % 1]}))
        # This click removed nothing (every file was already gone): no prefix (B5).
        self.offered(temp_problems(1, backups=0), '2')
        self.card('2').locator('.help-offer button').click()
        self.replies['/api/attention/delete-backups'] = (200, {'ok': True, 'unwritten': 0, 'written': 3, 'deleted': 0, 'deleted_backups': 0, 'deleted_temps': 0})
        self.card('2').locator('.help-confirm .help-danger').click()
        self.page.wait_for_function("!document.querySelector('[data-ticket=\"2\"]')")
        self.assertEqual(self.page.locator('#attentionDone').text_content(), 'Closed Batman: all 3 comics in the batch were written and verified.')
        self.assertEqual(self.posts[-1][1], {'ticket': '2', 'backups': [], 'temps': ['%032x' % 1]})

    def test_temp_offer_failures_and_unproved_backup_rows(self):
        status = self.card('1').locator('.help-status')
        cases = [((400, {'error': 'x', 'code': 'changed', 'check': problems(1)}), CHANGED),
                 ((400, {'error': 'x', 'code': 'file_gone', 'check': problems(1)}),
                  'Nothing was deleted: a file from the check is no longer there. The list below is updated.'),
                 ((400, {'error': 'x', 'code': 'writing', 'deleted': 0, 'total': 2}),
                  'Nothing was deleted: a comic in this folder is being written now. Wait for it to finish, then try again.'),
                 ((400, {'error': 'x', 'code': 'writing', 'deleted': 1, 'total': 2, 'deleted_temps': 1}),
                  'Deleted 1 of 2 files. A comic in this folder is being written now, so nothing was requeued. Wait for it to finish, then check again.'),
                 ((400, {'error': 'x', 'code': 'delete_failed', 'deleted': 0, 'total': 2}),
                  'Nothing was deleted: a file could not be deleted. Close any program using it, then try again.'),
                 ((400, {'error': 'x', 'code': 'delete_failed', 'deleted': 1, 'total': 2, 'deleted_temps': 1}),
                  'Deleted 1 of 2 files. 1 could not be deleted, so nothing was requeued. Close any program using them, then check again.'),
                 ((400, {'error': 'the check found problems', 'code': 'not_requeued', 'deleted': 2, 'deleted_backups': 1, 'deleted_temps': 1,
                         'reason': 'problems', 'check': problems(1)}),
                  '1 backup and 1 temporary file deleted, but not requeued: the check found 1 problem. Use Check and requeue to finish.'),
                 ((400, {'error': 'processing is paused.', 'code': 'not_requeued', 'deleted': 1, 'deleted_backups': 0, 'deleted_temps': 1, 'reason': 'paused'}),
                  '1 temporary file deleted, but not requeued: processing was paused. Use Check and requeue to finish.'),
                 ((400, {'error': 'x', 'code': 'paused'}), 'Nothing was deleted: processing is paused. Resume processing, then try again.'),
                 (None, 'No answer from the app. The files may already be deleted. Use Check and requeue to see the current state.')]
        for answer, text in cases:
            with self.subTest(text=text):
                self.offered(temp_problems(1))
                self.card('1').locator('.help-offer button').click()
                self.replies['/api/attention/delete-backups'] = answer
                self.card('1').locator('.help-confirm .help-danger').click()
                self.page.wait_for_function('t=>document.querySelector("[data-ticket=\\"1\\"] .help-status").textContent===t', arg=text)
                self.assertEqual(self.card('1').locator('.help-confirm').count(), 0)
                self.assertEqual(self.active()[1], 'help-status')
                if answer and answer[1]['code'] in ('changed', 'file_gone'):  # The fresh check replaces the list and the offer.
                    self.assertEqual((self.card('1').locator('.help-row').count(), self.card('1').locator('.help-offer').is_hidden()), (1, True))
        # B6: a backup that is not proved says what was found.
        reply = problems(3, finding='backup_left')
        for row, unproved in zip(reply['problems'], ('comic', 'backup', 'unread')):
            row['unproved'] = unproved
        self.replies['/api/attention/check'] = (200, reply)
        self.card('1').locator('button', has_text='Check and requeue').click()
        self.page.wait_for_function("document.querySelectorAll('[data-ticket=\"1\"] .help-row').length===3")
        self.assertEqual(self.card('1').locator('.help-row-finding').all_text_contents(), [
            'A recovery backup is kept. Do not delete it until the comic is checked.',
            'A recovery backup is kept. It is not a copy of this comic, so it may hold another version. Decide in Kept backups.',
            'A recovery backup is kept, but the app could not read it to compare it with the comic. Check again.'])
        self.assertEqual(status.text_content(), 'Not requeued: 3 problems found, and nothing was changed. Fix them, then check again.')

    def test_layout_rects_at_every_width_and_zoom(self):
        output = Path(os.environ['COMICS_TEST_EVIDENCE']) / 'folder-help'
        output.mkdir(parents=True, exist_ok=True)
        self.attention = [item('1', folder=LONG), item('2', 'other', 'D:\\Comics\\DC\\Batman [1940]', 'Readback verification failed for ' + 'Characters' * 12),
                          item('3', 'not_verified', 'D:\\Comics\\Сага', 'Archive validation failed.'), item('4'), item('5'),
                          item('6', folder='D:\\Comics\\Temp'), item('7', folder='D:\\Comics\\Writing')]
        self.poll(1)
        # Card 2: three problems with a row error. Card 3: the offer with its confirm open.
        # Card 4: the Close and recheck offer and a line error. Card 5: idle.
        # Card 6 (Amendment 2 B8, B10): the longest label, 3 backups and 3 temporary files, its confirm open.
        # Card 7: a partial delete stopped by a write (the longest new failure line).
        self.offered(temp_problems(3), '6')
        self.assertEqual(self.card('6').locator('.help-offer button').text_content(), 'Delete backups and temporary files, then requeue')
        self.card('6').locator('.help-offer button').click()
        self.offered(temp_problems(1), '7')
        self.card('7').locator('.help-offer button').click()
        self.replies['/api/attention/delete-backups'] = (400, {'error': 'x', 'code': 'writing', 'deleted': 1, 'total': 2, 'deleted_temps': 1})
        self.card('7').locator('.help-confirm .help-danger').click()
        self.page.wait_for_function("document.querySelector('[data-ticket=\"7\"] .help-status').textContent.startsWith('Deleted 1 of 2 files')")
        self.replies['/api/attention/check'] = (200, problems(3))
        self.card('2').locator('button', has_text='Check and requeue').click()
        self.page.wait_for_function("document.querySelectorAll('[data-ticket=\"2\"] .help-row').length===3")
        self.replies['/api/attention/reveal'] = (400, {'error': 'x', 'code': 'not_found'})
        self.card('2').locator('.help-row button').first.click()
        self.page.wait_for_function("document.querySelector('[data-ticket=\"2\"] .help-row .help-error')")
        backups = [{'id': '%032x' % (n + 1), 'name': 'Batman %03d (2019).cbz' % n, 'basis': 'original' if n else 'written'} for n in range(3)]
        self.replies['/api/attention/check'] = (200, problems(3, {'kind': 'delete_backup', 'unwritten': 1, 'backups': backups}, 'backup_left', 'original'))
        self.card('3').locator('button', has_text='Check and requeue').click()
        self.page.wait_for_function("document.querySelector('[data-ticket=\"3\"] .help-offer button')")
        self.card('3').locator('.help-offer button').click()
        self.replies['/api/attention/check'] = (400, {'error': 'x', 'code': 'plan_unreadable', 'offer': {'kind': 'close_recheck'}})
        self.card('4').locator('button', has_text='Check and requeue').click()
        self.page.wait_for_function("document.querySelector('[data-ticket=\"4\"] .help-offer button')")
        self.replies['/api/attention/reveal'] = (400, {'error': 'x', 'code': 'failed'})
        self.card('4').locator('button', has_text='Open folder').click()
        self.page.wait_for_function("document.querySelector('[data-ticket=\"4\"] > .help-error')")
        rows = []
        for paused in (False, True):
            self.control = {'requested': True, 'phase': 'paused'} if paused else {}
            self.poll(1)
            for width in (320, 640, 1280):
                for zoom in (1, 2):
                    with self.subTest(width=width, zoom=zoom, paused=paused):
                        self.page.set_viewport_size({'width': width, 'height': 900})
                        self.page.evaluate('z=>document.body.style.zoom=z', str(zoom))
                        found = self.page.evaluate(GEOMETRY)
                        rows.append({'width': width, 'zoom': zoom, 'paused': paused, **found})
                        self.assertEqual(found['cards'], 7)
                        self.assertEqual(found['clashes'], [])
                        self.assertLessEqual(found['overflow'], 0)
                        if zoom == 1:
                            self.assertLessEqual(found['page'], 0)
                        for button in found['buttons']:
                            self.assertGreaterEqual(button['w'], 24, button)
                            self.assertGreaterEqual(button['h'], 40, button)
                            self.assertTrue(button['ring'], button)
                        confirm = [button for button in found['buttons'] if button['confirm']]
                        self.assertEqual(len(confirm), 4)  # Cards 3 and 6.
                        if zoom == 1:  # Judy's wording verdict 4: break-word keeps the 100 px minimum.
                            for button in confirm:
                                self.assertGreaterEqual(button['w'], 100, button)
                        if not paused:
                            self.page.screenshot(path=str(output / ('cards-%d-%d.png' % (width, zoom))), full_page=True)
        self.page.evaluate("document.body.style.zoom='1'")
        # Success with a card remaining: the message sits above the cards and touches none.
        self.control = {}
        self.poll(1)
        self.replies['/api/attention/check'] = (200, {'ok': True, 'unwritten': 1, 'written': 0})
        self.card('5').locator('button', has_text='Check and requeue').click()
        self.page.wait_for_function("document.querySelector('#attentionDone').textContent!==''")
        self.assertEqual(self.page.locator('#attentionDone').text_content(), 'Requeued X-Men: 1 unwritten comic will be checked at the next folder pass.')
        for width in (320, 1280):
            self.page.set_viewport_size({'width': width, 'height': 900})
            found = self.page.evaluate(GEOMETRY)
            rows.append({'width': width, 'zoom': 1, 'state': 'success', **found})
            self.assertEqual((found['clashes'], found['done']), ([], False))
            self.assertLessEqual(found['page'], 0)
        (output / 'rects.json').write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    unittest.main()
