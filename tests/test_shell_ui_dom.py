"""Update banner while a pause-then-install is pending (DesktopShell spec §4 "Waiting and timeout", Revised 2026-10-26).

Updating 0.3.0 to 0.4.0, Sergei pressed Pause and install and was offered Install and restart again while the
pause was still running. The real static/shell-ui.js runs in a blank offline page with a stand-in desktop bridge;
each test pushes the shell states the updater publishes and reads the banner. The last class loads the real
dashboard page, to check that its own 2 s poll and click handler leave the locked Pause button alone.

Runs through the canonical headless harness (COMICS_TEST_CDP); skipped without it.
"""
import json
import os
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WAIT = 'Installing v0.4.0… Processing pauses first, then the app restarts.'
TIMEOUT = 'The installer for v0.4.0 did not start because processing did not finish pausing within 10 minutes.'
UNAVAILABLE = 'Unavailable while updating or quitting.'
PAUSE_TIP = 'Finish the current operation, then pause and release Gemma from the GPU.'
PAGE = ('<!doctype html><html lang="en"><head><meta charset="utf-8"></head><body><header><div class="header-controls">'
        '<span id="appVersion" class="badge">v0.4.0</span><button id="pauseControl" type="button" title="' + PAUSE_TIP + '">'
        'Pause &amp; release GPU</button></div></header><main></main></body></html>')
BRIDGE = """window.comicDesktop = {
  actions: [],
  action(name) { this.actions.push(name); return Promise.resolve(); },
  onState(callback) { window.pushShellState = callback; callback({service: 'ready', loadedShellVersion: '0.4.0', update: {phase: 'idle', check: 'idle', dismissed: false}}); return () => {}; },
  onRefresh() { return () => {}; },
};"""
READ = """() => {
  const notice = document.querySelector('.shell-notice'), active = document.activeElement, message = notice.querySelector('.copy p');
  const pause = document.getElementById('pauseControl');
  return {hidden: notice.hidden, message: message?.textContent ?? null, detail: notice.querySelectorAll('.copy p')[1]?.textContent ?? null,
          buttons: [...notice.querySelectorAll('button')].map(button => button.textContent),
          tips: [...notice.querySelectorAll('button')].map(button => button.title),
          actionsBox: notice.querySelector('.actions') !== null, failure: notice.classList.contains('failure'),
          check: [document.getElementById('updateCheck').disabled, document.getElementById('updateCheck').title],
          keys: [document.getElementById('apiKeys').disabled, document.getElementById('apiKeys').title],
          pause: [pause.disabled, pause.title],
          focus: active === message ? 'message' : active?.id || active?.textContent || active?.tagName,
          messageTabIndex: message ? message.tabIndex : null};
}"""


def shell(phase, stopping=None, **update):
    return {'service': 'ready', 'loadedShellVersion': '0.4.0', 'stopping': stopping,
            'update': {'phase': phase, 'version': '0.4.0', 'check': 'idle', 'dismissed': False, **update}}


class HeadlessPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        endpoint = os.environ['COMICS_TEST_CDP']
        parsed = urllib.parse.urlparse(endpoint)
        assert parsed.scheme == 'http' and parsed.hostname == '127.0.0.1' and parsed.port
        cls.runtime = sync_playwright().start()
        cls.browser = cls.runtime.chromium.connect_over_cdp(endpoint)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.runtime.stop()

    def setUp(self):
        self.context = self.browser.new_context()
        self.addCleanup(self.context.close)
        self.context.route('**/*', lambda route: route.abort())
        self.page = self.context.new_page()

    def push(self, state):
        self.page.evaluate('state => window.pushShellState(state)', state)
        return self.page.evaluate(READ)

    def press(self, label):
        self.page.evaluate("""label => { const button = [...document.querySelectorAll('.shell-notice button')].find(b => b.textContent === label);
                                       button.focus(); button.click(); }""", label)


@unittest.skipUnless(os.environ.get('COMICS_TEST_CDP'), 'Requires owned offline headless fixture')
class PendingInstallNoticeDOMTests(HeadlessPage):
    def setUp(self):
        super().setUp()
        self.page.set_content(PAGE)
        self.page.add_script_tag(content=BRIDGE)
        self.page.add_script_tag(content=(ROOT / 'static' / 'shell-ui.js').read_text(encoding='utf-8'))

    def wait_from_confirm(self):
        self.push(shell('confirm'))
        self.press('Pause and install')
        return self.push(shell('parking'))

    def test_waiting_banner_replaces_the_install_offer(self):
        self.assertIn('Install and restart', self.push(shell('ready'))['buttons'])
        self.press('Install and restart')
        self.assertIn('Pause and install', self.push(shell('confirm'))['buttons'])
        self.press('Pause and install')
        self.assertEqual(self.page.evaluate('window.comicDesktop.actions'), ['confirm', 'install'])
        seen = self.push(shell('parking'))
        self.assertFalse(seen['hidden'])
        self.assertEqual(seen['message'], WAIT)
        self.assertEqual(seen['buttons'], [])  # No Install offer, no Cancel, no dismiss.
        self.assertFalse(seen['actionsBox'])  # No empty actions box beside or under the text.
        self.assertFalse(seen['failure'])
        self.assertEqual(seen['check'], [True, UNAVAILABLE])
        self.assertEqual(seen['keys'], [True, UNAVAILABLE])
        self.assertEqual(seen['pause'], [True, UNAVAILABLE])  # Sergei: "Yes, lock it".

    def test_focus_moves_to_the_message_line_and_stays_through_both_phases(self):
        seen = self.wait_from_confirm()
        self.assertEqual(seen['focus'], 'message')
        self.assertEqual(seen['messageTabIndex'], -1)  # Focusable by script only, not a tab stop.
        self.page.evaluate("window.firstMessage = document.querySelector('.shell-notice .copy p')")
        # Same render key for 'parking' and 'installing': the banner is not rebuilt, so nothing is re-announced.
        for state in (shell('parking', {'mode': 'install', 'stage': 'pausing', 'elapsed': 2000}),
                      shell('parking', {'mode': 'install', 'stage': 'closing', 'elapsed': 9000}), shell('installing')):
            with self.subTest(phase=state['update']['phase'], stopping=state['stopping']):
                seen = self.push(state)
                self.assertEqual(seen['message'], WAIT)
                self.assertEqual(seen['focus'], 'message')
                self.assertTrue(self.page.evaluate("window.firstMessage === document.querySelector('.shell-notice .copy p')"))
                self.assertEqual(seen['pause'], [True, UNAVAILABLE])

    def test_downloading_has_no_empty_actions_box(self):
        self.push(shell('available'))
        self.press('Download')
        seen = self.push(shell('downloading', percent=40))
        self.assertEqual(seen['buttons'], [])
        self.assertFalse(seen['actionsBox'])
        self.assertEqual(seen['focus'], 'message')
        self.assertEqual(seen['pause'], [False, PAUSE_TIP])  # Only the install wait locks Pause.

    def test_timeout_says_why_and_try_again_returns_to_waiting(self):
        self.wait_from_confirm()
        seen = self.push(shell('installer-failed', installerStarted=False, restoreFailed=False, reason='pause_timeout', pauseMinutes=10))
        self.assertEqual(seen['message'], TIMEOUT)
        self.assertEqual(seen['detail'], 'The downloaded installer is kept. You can try installing again.')
        self.assertEqual(seen['buttons'], ['Try again', 'Open log folder', '×'])
        self.assertEqual(seen['tips'], ['Try starting the downloaded installer for v0.4.0 again.', 'Open the logs for this update attempt.',
                                        'Hide this notice until the app restarts.'])
        self.assertTrue(seen['failure'])
        self.assertEqual(seen['focus'], 'Try again')  # A failure puts focus on Try again.
        self.assertEqual(seen['pause'], [False, PAUSE_TIP])  # Processing is back to its earlier state; Pause is free again.
        self.press('Try again')
        seen = self.push(shell('parking'))
        self.assertEqual(self.page.evaluate('window.comicDesktop.actions')[-1], 'retryUpdate')
        self.assertEqual(seen['message'], WAIT)
        self.assertEqual(seen['focus'], 'message')
        restore = self.push(shell('installer-failed', installerStarted=False, restoreFailed=True, reason='pause_timeout', pauseMinutes=10))
        self.assertEqual(restore['detail'], 'The downloaded installer is kept. You can try installing again. '
                                            'The local service did not restart. Processing stays stopped.')

    def test_other_failures_keep_the_generic_title(self):
        self.wait_from_confirm()
        seen = self.push(shell('installer-failed', installerStarted=False, restoreFailed=False, reason=None, pauseMinutes=None))
        self.assertEqual(seen['message'], 'The installer for v0.4.0 did not start.')
        self.assertEqual(seen['buttons'], ['Try again', 'Open log folder', '×'])

    def test_cancel_install_returns_to_ready_with_focus_on_install(self):
        self.wait_from_confirm()
        seen = self.push(shell('ready'))
        self.assertEqual(seen['message'], 'Update ready — v0.4.0')
        self.assertEqual(seen['buttons'], ['Install and restart', '×'])
        self.assertEqual(seen['focus'], 'Install and restart')
        self.assertEqual(seen['pause'], [False, PAUSE_TIP])
        self.assertEqual(seen['keys'][0], False)


@unittest.skipUnless(os.environ.get('COMICS_TEST_CDP'), 'Requires owned offline headless fixture')
class DashboardPauseLockDOMTests(HeadlessPage):
    """The real dashboard page: its own poll (renderControl) and click handler must not undo the lock."""
    CONTROL = {'requested': False, 'user_requested': False, 'phase': 'running', 'gpu_released': False, 'error': '', 'waiting_for': []}

    def setUp(self):
        super().setUp()
        self.posts, self.held = [], []
        self.hold = False
        self.context.add_init_script('window.setInterval=()=>0;' + BRIDGE)
        self.page.route('https://comics-fixture.invalid/**', self.route)
        self.page.goto('https://comics-fixture.invalid/')
        self.page.wait_for_function("document.getElementById('pauseControl').title===" + json.dumps(PAUSE_TIP)
                                    + " && document.getElementById('updateCheck')")

    def route(self, route):
        path = urllib.parse.urlparse(route.request.url).path
        static = {'/': 'index.html', '/shell-ui.js': 'shell-ui.js', '/lens-control.js': 'lens-control.js'}
        if path in static:
            kind = 'text/html' if path == '/' else 'text/javascript'
            return route.fulfill(body=(ROOT / 'static' / static[path]).read_text(encoding='utf-8'), content_type=kind)
        if path.endswith('.js') or path.endswith('.css'):
            return route.fulfill(body='', content_type='text/javascript' if path.endswith('.js') else 'text/css')
        if path in ('/api/pause', '/api/resume'):
            self.posts.append(path)
            if self.hold:
                self.held.append(route)
                return
            return route.fulfill(json=self.CONTROL)
        if path == '/api/browser-verification':
            return route.fulfill(json={'engine': 'google_lens', 'phase': 'idle', 'human_verification': False, 'window': 'closed',
                                       'alive': True, 'updated': 1, 'control': self.CONTROL})
        if path == '/api/state':
            return route.fulfill(json={'version': '0.4.0', 'roots': [], 'job': {'message': 'Ready', 'running': False, 'visited': 0, 'changed': 0},
                                       'counts': {}, 'totals': {'updated': 0, 'total': 0, 'metadata_and_synopsis': 0, 'needs_information': 0}})
        if path == '/api/progress':
            return route.fulfill(json={'queue': {'alive': True}, 'timestamp': 1, 'research': {}, 'folders': {}, 'providers': {}})
        return route.abort()

    def pause(self):
        return self.page.evaluate("(() => { const p = document.getElementById('pauseControl'); return [p.disabled, p.title]; })()")

    def test_dashboard_poll_and_click_leave_the_lock_alone(self):
        self.push(shell('parking'))
        self.assertEqual(self.pause(), [True, UNAVAILABLE])
        self.page.evaluate('state => renderControl(state)', self.CONTROL)  # What the 2 s poll does.
        self.assertEqual(self.pause(), [True, UNAVAILABLE])
        self.page.evaluate("document.getElementById('pauseControl').onclick()")  # Even a direct call does nothing.
        self.page.wait_for_timeout(200)
        self.assertEqual(self.posts, [])
        self.push(shell('ready'))  # Cancel install.
        self.assertEqual(self.pause(), [False, PAUSE_TIP])

    def test_a_click_already_in_flight_does_not_unlock_on_completion(self):
        self.hold = True
        self.page.evaluate("document.getElementById('pauseControl').click()")
        self.page.wait_for_timeout(200)  # Lets the route handler receive the request (sync Playwright dispatches while waiting).
        self.assertEqual(self.posts, ['/api/pause'])
        self.assertEqual(self.pause()[0], True)  # The page's own in-flight disable.
        self.push(shell('parking'))
        for route in self.held:
            route.fulfill(json=self.CONTROL)
        self.page.wait_for_timeout(300)
        self.assertEqual(self.pause(), [True, UNAVAILABLE])


if __name__ == '__main__':
    unittest.main()
