"""Update statistics panel in the real page, offline (UXSpec UpdateStats 2026-10-26).

/api/update-stats is answered by the real update_stats.report() over a throwaway fixture catalog,
at one fixed moment (Wednesday 28 October 2026, 12:30 local) that the page's clock also reads.
Every other request is fulfilled locally or refused. Layout is measured, not eyeballed.

Runs through the canonical headless harness (COMICS_TEST_CDP); skipped without it.
"""
import datetime
import json
import os
import time
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch
import app
import update_stats as stats
from test_update_stats import CentralEurope
from test_worker import scratch_directory
from test_yandex_dom import YandexDOMTests

WALL = CentralEurope()

ROOT = 'D:\\Comics'
NOW = time.mktime((2026, 10, 28, 12, 30, 0, 0, 0, -1))
NOTE = 'A comic updated in several bars counts once in the total.'


def local(day, hour=0, minute=0):
    return time.mktime((2026, 10, day, hour, minute, 0, 0, 0, -1))


# Today: 4 comics at 08, 2 at 09 (one also at 08), 1 at 11, 1 at 12 (now): 7 comics, bars add up to 8.
BUSY = [(ROOT + '\\A.cbz', local(28, 8, 10)), (ROOT + '\\B.cbz', local(28, 8, 30)), (ROOT + '\\C.cbz', local(28, 8, 40)),
        ('\\\\?\\D:\\Comics\\D.cbz', local(28, 8, 50)), ('d:\\comics\\a.CBZ', local(28, 9, 20)), (ROOT + '\\E.cbz', local(28, 9, 30)),
        (ROOT + '\\F.cbz', local(28, 11, 0)), (ROOT + '\\G.cbz', local(28, 12, 5)), (ROOT + '\\H.cbz', local(26, 9)),
        (ROOT + '\\I.cbz', local(2, 15)), ('E:\\Elsewhere\\X.cbz', local(28, 10))]

GEOMETRY = r"""() => {
  const box = n => { const r = n.getBoundingClientRect(); return {l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height}; };
  const overlap = (a, b) => a.l < b.r - 0.5 && b.l < a.r - 0.5 && a.t < b.b - 0.5 && b.t < a.b - 0.5;
  const chips = [...document.querySelectorAll('#statsPeriod .chip')].map(box);
  const clashes = [];
  for (let i = 0; i < chips.length; i++) for (let j = i + 1; j < chips.length; j++) if (overlap(chips[i], chips[j])) clashes.push([i, j]);
  const rows = ['#statsPeriod', '#statsCustom', '#statsRangeError', '#statsHead', '#statsUnit', '#statsChart', '#statsNote']
    .map(s => document.querySelector(s)).filter(n => !n.hidden).map(box);
  for (let i = 0; i + 1 < rows.length; i++) if (rows[i].b > rows[i + 1].t + 0.5) clashes.push(['rows', i]);
  const panel = box(document.getElementById('statsPanel')), chart = box(document.getElementById('statsChart'));
  return {chips, clashes, panel, chart, note: box(document.getElementById('statsNote')),
          from: box(document.getElementById('statsFrom')), to: box(document.getElementById('statsTo')),
          page: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          svg: document.querySelector('#statsChart svg').getBoundingClientRect().width};
}"""


@unittest.skipUnless(os.environ.get('COMICS_TEST_CDP'), 'Requires owned offline headless fixture')
class UpdateStatsDOMTests(YandexDOMTests):
    def setUp(self):
        super().setUp()
        self.root = Path(__file__).resolve().parents[1]
        directory = self.enterContext(scratch_directory())
        self.enterContext(patch.object(app, 'DATA', Path(directory) / 'catalog'))
        self.enterContext(patch.object(app, 'live_root', return_value=ROOT))
        stats._cache.clear()
        with app.db():
            pass
        self.requests, self.held, self.failing, self.stub, self.refuse = [], None, False, None, None
        self.context.add_init_script('window.setInterval=()=>0;')
        self.page.clock.set_fixed_time(datetime.datetime.fromtimestamp(NOW, datetime.timezone.utc))
        self.page.route('https://comics-fixture.invalid/**', self.route)
        self.page.set_viewport_size({'width': 1280, 'height': 900})

    def route(self, route):
        parsed = urllib.parse.urlparse(route.request.url)
        path = parsed.path
        static = {'/': 'static/index.html', '/update-stats.js': 'static/update-stats.js', '/lens-control.js': 'static/lens-control.js'}
        if path in static:
            kind = 'text/html' if path == '/' else 'text/javascript'
            return route.fulfill(body=(self.root / static[path]).read_text(encoding='utf-8'), content_type=kind)
        if path in ('/reverse-image.js', '/shell-ui.js'):
            return route.fulfill(body='', content_type='text/javascript')
        if path == '/api/update-stats':
            self.requests.append(parsed.query)
            if self.held is not None:
                self.held.append(route)
                return
            return self.answer(route)
        if path == '/api/state':
            data = {'version': '0.3.0', 'roots': [ROOT], 'job': {'message': 'Ready', 'running': False, 'visited': 0, 'changed': 0},
                    'counts': {'tagged': 5, 'embedded': 3}, 'totals': {'updated': 5, 'total': 8, 'metadata_and_synopsis': 2, 'needs_information': 6}}
        elif path == '/api/comics':
            data = {'rows': [{'id': 1, 'path': ROOT + '\\A.cbz', 'series': 'A', 'number': '1', 'year': '2020', 'status': 'tagged',
                              'metadata': json.dumps({'Series': 'A'}), 'has_synopsis': False, 'has_metadata': True, 'error': ''}], 'total': 1}
        elif path == '/api/progress':
            data = {'queue': {'alive': True}, 'timestamp': 1, 'research': {}, 'folders': {}, 'providers': {}}
        elif path == '/api/browser-verification':
            data = {'engine': 'google_lens', 'phase': 'idle', 'human_verification': False, 'window': 'closed', 'alive': True, 'updated': 1, 'control': {}}
        else:
            return route.abort()
        route.fulfill(json=data)

    def answer(self, route):
        if self.failing:
            return route.fulfill(status=500, json={'error': 'fixture failure'})
        if self.refuse:
            return route.fulfill(status=400, json={'error': self.refuse, 'code': 'invalid_range'})
        query = urllib.parse.parse_qs(urllib.parse.urlparse(route.request.url).query, keep_blank_values=True)
        if self.stub:
            return route.fulfill(json=self.stub(query))
        try:
            return route.fulfill(json=stats.report(query, now=NOW))
        except stats.StatsError as exc:
            return route.fulfill(status=400, json={'error': str(exc), 'code': exc.code})

    def open(self, rows=BUSY):
        with app.db() as con:
            con.executemany('INSERT INTO history(path,backup,source,timestamp) VALUES(?,?,?,?)', [(p, '', 'fixture', t) for p, t in rows])
        self.page.goto('https://comics-fixture.invalid/')
        self.page.wait_for_function("document.querySelector('#statsTotal').textContent!=='–'")

    def text(self, selector):
        return self.page.locator(selector).text_content()

    def intl(self, epoch, options):
        return self.page.evaluate('([e,o])=>new Intl.DateTimeFormat(undefined,o).format(new Date(e*1000))', [epoch, options])

    def bars(self):
        return self.page.evaluate("document.querySelectorAll('#statsChart rect[rx]').length")  # Bars only: the slot highlight has no rx.

    def wait_unit(self, unit):
        self.page.wait_for_function('u=>document.querySelector("#statsUnit").textContent===u', arg=unit)

    def test_default_today_panel(self):
        self.open()
        order = self.page.evaluate("[...document.querySelectorAll('section.panel')].map(s=>s.querySelector('h2')?.textContent||s.className)")
        self.assertEqual(order[:3], ['Live enrichment progress', 'Update statistics', 'Live library'])
        self.assertEqual(self.page.evaluate("document.querySelector('#statsPeriod input:checked').value"), 'today')
        self.assertEqual(self.requests, ['period=today'])
        self.assertEqual((self.text('#statsTotal'), self.text('#statsLabel')), ('7', 'comics updated today'))
        self.assertEqual(self.text('#statsRange'), self.intl(NOW, {'weekday': 'short', 'day': 'numeric', 'month': 'short', 'year': 'numeric'}))
        self.assertEqual((self.text('#statsUnit'), self.text('#statsNote')), ('Comics per hour', NOTE))
        self.assertEqual(self.bars(), 4)  # 08, 09, 11, 12; hours after now draw nothing.
        self.assertEqual(self.page.locator('#statsChart').get_attribute('aria-label'), 'Comics per hour, today. Left and right arrows read each bar.')
        self.assertEqual(self.page.locator('#statsHead').get_attribute('title'), 'Every comic updated in this period, each counted once.')
        self.assertIsNone(self.page.locator('#statsChart').get_attribute('title'))
        y = self.page.evaluate("[...document.querySelectorAll('#statsChart text')].slice(0,3).map(t=>t.textContent)")
        self.assertEqual(y, ['0', '2', '4'])

    def test_chip_tooltips_and_all_time(self):
        self.open()
        chips = self.page.evaluate("[...document.querySelectorAll('#statsPeriod .chip')].map(c=>[c.textContent,c.title])")
        first = self.intl(local(2, 15), {'day': 'numeric', 'month': 'short', 'year': 'numeric'})
        self.assertEqual(chips, [['Last hour', 'Comics updated in the last 60 minutes.'], ['Today', 'Comics updated since midnight today.'],
                                 ['This week', 'Comics updated since Monday this week.'], ['This month', 'Comics updated since the 1st of this month.'],
                                 ['This year', 'Comics updated since 1 January this year.'],
                                 ['All time', 'Every comic updated since counting began on ' + first + '.'], ['Custom', 'Pick the first and last day to count.']])
        self.page.locator('#statsPeriod .chip', has_text='All time').click()
        self.wait_unit('Comics per day')
        self.assertEqual((self.text('#statsTotal'), self.text('#statsLabel'), self.text('#statsRange')), ('9', 'comics updated, all time', 'Since ' + first))
        self.assertEqual(self.requests[-1], 'period=all')

    def test_each_period(self):
        self.open()
        for label, unit, words, query in (('Last hour', 'Comics per 5 minutes', 'comic updated in the last hour', 'period=hour'),  # One comic: singular.
                                          ('This week', 'Comics per day', 'comics updated this week', 'period=week'),
                                          ('This year', 'Comics per month', 'comics updated this year', 'period=year')):
            self.page.locator('#statsPeriod .chip', has_text=label).click()
            self.wait_unit(unit)
            self.assertEqual((self.text('#statsLabel'), self.requests[-1]), (words, query))
        self.assertEqual(self.text('#statsRange'), '2026')
        self.page.locator('#statsPeriod .chip', has_text='Last hour').click()
        self.wait_unit('Comics per 5 minutes')
        self.assertEqual((self.text('#statsTotal'), self.text('#statsLabel')), ('1', 'comic updated in the last hour'))
        x = self.page.evaluate("[...document.querySelectorAll('#statsChart text')].slice(3).map(t=>t.textContent)")
        self.assertEqual(x, ['−60 min', '−45', '−30', '−15', 'now'])
        self.page.locator('#statsPeriod .chip', has_text='This week').click()
        self.wait_unit('Comics per day')
        # Monday 26 Oct to Sunday 1 Nov: the year once, on the end.
        self.assertEqual(self.text('#statsRange'), self.intl(local(26), {'weekday': 'short', 'day': 'numeric', 'month': 'short'}) + ' – ' +
                         self.intl(time.mktime((2026, 11, 1, 12, 0, 0, 0, 0, -1)), {'weekday': 'short', 'day': 'numeric', 'month': 'short', 'year': 'numeric'}))

    def test_this_month(self):
        """Addendum 2: the fourth chip; one daily bar per day of the month; future days inert; today says so far."""
        self.open()
        self.page.locator('#statsPeriod .chip', has_text='This week').click()
        self.page.wait_for_function("document.querySelector('#statsLabel').textContent.endsWith('this week')")
        self.page.focus('#statsPeriod input:checked')
        self.page.keyboard.press('ArrowRight')  # From This week, one press reaches This month (B5).
        self.page.wait_for_function("document.querySelector('#statsLabel').textContent.endsWith('this month')")
        self.assertEqual(self.requests[-1], 'period=month')
        self.assertEqual((self.text('#statsTotal'), self.text('#statsLabel'), self.text('#statsUnit')), ('9', 'comics updated this month', 'Comics per day'))
        self.assertEqual(self.text('#statsRange'), self.intl(NOW, {'month': 'long', 'year': 'numeric'}))
        self.assertEqual(self.page.locator('#statsChart').get_attribute('aria-label'), 'Comics per day, this month. Left and right arrows read each bar.')
        self.assertEqual(self.bars(), 3)  # 2, 26 and 28 October.
        labels = self.page.evaluate("[...document.querySelectorAll('#statsChart text')].slice(3).map(t=>t.textContent)")
        self.assertEqual(labels[0], self.intl(local(1, 12), {'day': 'numeric', 'month': 'short'}))  # The first label carries the month.
        self.page.locator('#statsChart').scroll_into_view_if_needed()
        chart = self.page.locator('#statsChart').bounding_box()
        pitch = (chart['width'] - 52) / 31  # 31 slots: the axis spans the whole month.
        self.page.mouse.move(chart['x'] + 44 + 29.5 * pitch, chart['y'] + 140)  # 30 October, in the future.
        self.page.wait_for_timeout(100)
        self.assertTrue(self.page.locator('#statsTip').is_hidden())
        self.page.mouse.move(chart['x'] + 44 + 27.5 * pitch, chart['y'] + 140)  # Today.
        self.page.wait_for_function("!document.querySelector('#statsTip').hidden")
        self.assertEqual(self.page.evaluate("[...document.querySelectorAll('#statsTip div')].map(d=>d.textContent)"),
                         [self.intl(NOW, {'weekday': 'short', 'day': 'numeric', 'month': 'short', 'year': 'numeric'}), '7 comics so far'])
        self.page.mouse.move(0, 0)
        self.page.focus('#statsPeriod input:checked')
        self.page.keyboard.press('Tab')
        self.page.wait_for_function("document.activeElement.id==='statsChart' && !document.querySelector('#statsTip').hidden")
        self.page.keyboard.press('ArrowRight')  # Today is the last active day; the future days are skipped.
        self.assertEqual(self.page.evaluate("document.querySelectorAll('#statsTip div')[1].textContent"), '7 comics so far')
        self.page.keyboard.press('Home')
        self.assertEqual(self.page.evaluate("[...document.querySelectorAll('#statsTip div')].map(d=>d.textContent)"),
                         [self.intl(local(1, 12), {'weekday': 'short', 'day': 'numeric', 'month': 'short', 'year': 'numeric'}), '0 comics'])

    def test_custom_range(self):
        self.open()
        self.page.locator('#statsPeriod .chip', has_text='Custom').click()
        self.page.wait_for_function("!document.querySelector('#statsCustom').hidden")
        self.assertEqual((self.page.input_value('#statsFrom'), self.page.input_value('#statsTo')), ('2026-09-29', '2026-10-28'))
        self.assertEqual(self.page.locator('#statsFrom').get_attribute('max'), '2026-10-28')
        self.wait_unit('Comics per day')
        self.assertEqual(self.requests[-1], 'period=custom&from=2026-09-29&to=2026-10-28')
        self.assertEqual(self.text('#statsLabel'), 'comics updated in this range')
        self.page.fill('#statsTo', '2026-10-19')
        self.page.wait_for_function('()=>document.querySelector("#statsRange").textContent.includes("19")')
        sent = len(self.requests)
        for selector, value, message, invalid in (('#statsFrom', '2026-10-20', 'End date is before the start date.', [None, 'true']),
                                                  ('#statsFrom', '', 'Pick both dates.', ['true', None]),
                                                  ('#statsFrom', '2026-10-20', 'End date is before the start date.', [None, 'true']),
                                                  ('#statsTo', '2026-10-30', 'Dates after today are not available.', [None, 'true'])):
            self.page.fill(selector, value)
            self.page.wait_for_function('m=>document.querySelector("#statsRangeError").textContent===m', arg=message)
            self.assertFalse(self.page.locator('#statsRangeError').is_hidden())
            self.assertEqual([self.page.locator(s).get_attribute('aria-invalid') for s in ('#statsFrom', '#statsTo')], invalid)
        self.assertEqual(len(self.requests), sent)  # Nothing fetched for an invalid range.
        self.assertEqual(self.text('#statsLabel'), 'comic updated in this range')  # The last good data (29 Sep-19 Oct: 1 comic) stays.
        self.page.fill('#statsTo', '2026-10-28')
        self.page.fill('#statsFrom', '2026-10-28')
        self.wait_unit('Comics per hour')  # A one-day range is hourly.
        self.assertTrue(self.page.locator('#statsRangeError').is_hidden())
        self.assertEqual(self.text('#statsRange'), self.intl(NOW, {'day': 'numeric', 'month': 'short', 'year': 'numeric'}))
        self.page.locator('#statsPeriod .chip', has_text='Today').click()
        self.page.wait_for_function("document.querySelector('#statsCustom').hidden")
        self.page.locator('#statsPeriod .chip', has_text='Custom').click()
        self.assertEqual(self.page.input_value('#statsFrom'), '2026-10-28')  # This page session's last values come back.

    def test_hover_keyboard_and_announce(self):
        self.open()
        self.page.locator('#statsChart').scroll_into_view_if_needed()
        chart = self.page.locator('#statsChart').bounding_box()
        pitch = (chart['width'] - 52) / 24
        self.page.mouse.move(chart['x'] + 44 + 8.5 * pitch, chart['y'] + 140)
        self.page.wait_for_function("!document.querySelector('#statsTip').hidden")
        first = self.intl(local(28, 8), {'weekday': 'short', 'day': 'numeric', 'month': 'short'}) + ', ' + \
            self.intl(local(28, 8), {'hour': 'numeric', 'minute': '2-digit'}) + '–' + self.intl(local(28, 9), {'hour': 'numeric', 'minute': '2-digit'})
        self.assertEqual(self.page.evaluate("[...document.querySelectorAll('#statsTip div')].map(d=>d.textContent)"), [first, '4 comics'])
        tip = self.page.locator('#statsTip').bounding_box()
        self.assertGreaterEqual(tip['x'], chart['x'] - 0.5)
        self.assertLessEqual(tip['x'] + tip['width'], chart['x'] + chart['width'] + 0.5)
        self.assertEqual(self.page.evaluate("getComputedStyle(document.querySelector('#statsTip')).pointerEvents"), 'none')
        self.assertEqual(self.text('#statsAnnounce'), '7 comics updated today')  # Hover does not announce.
        self.page.mouse.move(chart['x'] + 44 + 20.5 * pitch, chart['y'] + 140)  # A future hour: nothing.
        self.page.wait_for_function("document.querySelector('#statsTip').hidden")
        self.page.mouse.move(0, 0)
        self.page.focus('#statsPeriod input:checked')
        self.page.keyboard.press('Tab')
        self.page.wait_for_function("document.activeElement.id==='statsChart' && !document.querySelector('#statsTip').hidden")
        self.assertEqual(self.page.evaluate("document.querySelectorAll('#statsTip div')[1].textContent"), '1 comic so far')
        self.page.keyboard.press('ArrowRight')  # Already the last active slot.
        self.assertTrue(self.text('#statsAnnounce').endswith('1 comic so far'))
        self.page.keyboard.press('Home')
        self.assertEqual(self.page.evaluate("document.querySelectorAll('#statsTip div')[1].textContent"), '0 comics')
        self.page.keyboard.press('ArrowLeft')
        self.assertTrue(self.text('#statsAnnounce').endswith('0 comics'))
        self.page.keyboard.press('End')
        self.page.keyboard.press('ArrowLeft')
        self.assertEqual(self.page.evaluate("document.querySelectorAll('#statsTip div')[1].textContent"), '1 comic')
        self.page.keyboard.press('Escape')
        self.assertTrue(self.page.locator('#statsTip').is_hidden())
        self.assertEqual(self.page.evaluate('document.activeElement.id'), 'statsChart')
        outline = self.page.evaluate("getComputedStyle(document.querySelector('#statsChart')).outlineStyle")
        self.assertEqual(outline, 'solid')

    def test_empty_and_no_history(self):
        self.open([(ROOT + '\\J.cbz', local(27, 22, 14))])
        self.assertEqual((self.text('#statsTotal'), self.text('#statsLabel')), ('0', 'comics updated today'))
        when = self.intl(local(27, 22, 14), {'weekday': 'short', 'month': 'short', 'day': 'numeric', 'hour': 'numeric', 'minute': '2-digit'})
        self.assertEqual(self.text('#statsNote'), 'Last update: ' + when + '.')
        self.assertEqual(self.bars(), 0)
        self.assertEqual(self.page.evaluate("[...document.querySelectorAll('#statsChart text')].slice(0,3).map(t=>t.textContent)"), ['0', '2', '4'])
        self.page.locator('#statsChart').scroll_into_view_if_needed()
        chart = self.page.locator('#statsChart').bounding_box()
        self.page.mouse.move(chart['x'] + 44 + 3.5 * (chart['width'] - 52) / 24, chart['y'] + 100)
        self.page.wait_for_function("!document.querySelector('#statsTip').hidden")
        self.assertEqual(self.page.evaluate("document.querySelectorAll('#statsTip div')[1].textContent"), '0 comics')
        with app.db() as con:
            con.execute('DELETE FROM history')
        stats._cache.clear()
        self.page.evaluate('UpdateStats.refresh()')
        self.page.wait_for_function("document.querySelector('#statsNote').textContent==='No updates yet.'")

    def test_loading_error_and_height(self):
        self.held = []
        self.page.goto('https://comics-fixture.invalid/')
        self.page.wait_for_function("document.querySelector('#statsNote').textContent==='Loading statistics…'")
        loading = self.page.evaluate(GEOMETRY)
        self.assertEqual((self.text('#statsTotal'), self.page.evaluate("document.querySelectorAll('#statsChart svg *').length")), ('–', 0))
        with app.db() as con:
            con.executemany('INSERT INTO history(path,backup,source,timestamp) VALUES(?,?,?,?)', [(p, '', 'f', t) for p, t in BUSY])
        held, self.held = self.held, None
        for route in held:
            self.answer(route)
        self.page.wait_for_function("document.querySelector('#statsTotal').textContent==='7'")
        normal = self.page.evaluate(GEOMETRY)
        self.held = []
        self.page.locator('#statsPeriod .chip', has_text='This week').click()
        self.page.wait_for_function("document.querySelector('#statsTotal').textContent==='–'")  # Still pending after 250 ms.
        self.assertEqual(self.page.evaluate("getComputedStyle(document.querySelector('#statsChart')).opacity"), '0.6')
        self.assertEqual(self.text('#statsNote'), 'Loading statistics…')
        slow = self.page.evaluate(GEOMETRY)
        self.failing = True
        held, self.held = self.held, None
        for route in held:
            self.answer(route)
        self.page.wait_for_function("document.querySelector('#statsNote').textContent==='Statistics unavailable. Retrying.'")
        self.assertEqual(self.text('#statsTotal'), '7')  # The last good number stays.
        self.assertEqual(self.page.evaluate("getComputedStyle(document.querySelector('#statsNote')).color"), 'rgb(255, 214, 151)')
        self.assertEqual(self.page.evaluate("getComputedStyle(document.querySelector('#error')).display"), 'none')
        error = self.page.evaluate(GEOMETRY)
        for state in (loading, normal, slow, error):
            self.assertEqual(state['panel']['h'], normal['panel']['h'])
            self.assertEqual((state['chart']['h'], state['note']['h']), (192, 21))
        self.failing = False
        self.page.evaluate('UpdateStats.refresh()')
        self.wait_unit('Comics per day')
        self.assertEqual(self.page.evaluate("getComputedStyle(document.querySelector('#statsChart')).opacity"), '1')

    def test_relabelled_counter_and_rows(self):
        self.open()
        tile = self.page.evaluate("(()=>{const t=document.querySelector('#comicCounter').parentElement;return [t.lastChild.textContent,t.title]})()")
        self.assertEqual(tile, ['Currently tagged by this app', 'Comics tagged by this app right now; the number can go down. '
                                'Update statistics below counts every comic updated in a period.'])
        self.assertTrue(self.text('.live-counters + small').startswith('Tagged overlaps the other counters. Present means'))
        self.page.wait_for_function("document.querySelector('#rows td:nth-child(3)')")
        self.assertEqual(self.text('#rows td:nth-child(3)'), 'Tagged by this app · Synopsis missing')
        self.page.wait_for_function("document.querySelector('#comicCounter').textContent==='5'")

    def test_layout_at_every_width(self):
        self.open()
        for width in (640, 700, 1000, 1280):
            self.page.set_viewport_size({'width': width, 'height': 900})
            self.page.locator('#statsPeriod .chip', has_text='Custom').click()
            self.page.wait_for_function("!document.querySelector('#statsCustom').hidden")
            found = self.page.evaluate(GEOMETRY)
            self.assertEqual(found['clashes'], [], width)
            self.assertLessEqual(found['page'], 0, width)
            self.assertTrue(all(abs(c['h'] - 32) < 0.5 for c in found['chips']), (width, found['chips']))
            self.assertEqual((round(found['from']['w']), round(found['from']['h']), round(found['to']['w'])), (176, 32, 176), width)
            self.assertLessEqual(abs(found['svg'] - found['chart']['w']), 0.5, width)
            # Seven chips (Addendum 2 B6/B7): one row from about 604 px of inner width; at the 640 window `Custom`
            # wraps alone to a second row 40 px lower. 700 is borderline and not asserted. 8 px between chips.
            tops = [round(c['t']) for c in found['chips']]
            rows = sorted(set(tops))
            if width >= 1000:
                self.assertEqual(len(rows), 1, width)
            if width == 640:
                self.assertEqual((len(rows), rows[1] - rows[0], tops.count(rows[1]), tops[-1]), (2, 40, 1, rows[1]), width)
            for a, b in zip(found['chips'], found['chips'][1:]):
                if round(a['t']) == round(b['t']):
                    self.assertLess(abs(b['l'] - a['r'] - 8), 0.6, width)
            self.page.locator('#statsPeriod .chip', has_text='Today').click()
            self.page.wait_for_function("document.querySelector('#statsCustom').hidden")

    def x_labels(self):
        return self.page.evaluate("[...document.querySelectorAll('#statsChart text')].slice(3).map(t=>t.textContent)")

    def y_labels(self):
        return self.page.evaluate("[...document.querySelectorAll('#statsChart text')].slice(0,3).map(t=>t.textContent)")

    def test_addendum_visual_values(self):
        """Addendum A3 rows 1, 3, 4: tooltip shadow, chart margin, y labels 2 px above their lines."""
        self.open()
        self.assertEqual(self.page.evaluate("getComputedStyle(document.querySelector('#statsChart')).marginTop"), '8px')
        self.assertIn('0px 2px 6px', self.page.evaluate("getComputedStyle(document.querySelector('#statsTip')).boxShadow"))
        self.assertEqual(self.page.evaluate("[...document.querySelectorAll('#statsChart text')].slice(0,3).map(t=>+t.getAttribute('y'))"), [150, 78, 6])

    def test_label_thinning_by_measured_width(self):
        """Addendum A3 row 2: at 640 the week labels all seven days, Today every third hour."""
        self.open()
        self.page.set_viewport_size({'width': 640, 'height': 900})
        self.page.wait_for_function("document.querySelectorAll('#statsChart text').length===11")  # 3 y + hours 0, 3 ... 21.
        self.assertEqual(self.x_labels()[:2], [self.intl(local(28, 0), {'hour': 'numeric'}), self.intl(local(28, 3), {'hour': 'numeric'})])
        self.page.locator('#statsPeriod .chip', has_text='This week').click()
        self.wait_unit('Comics per day')
        self.assertEqual(len(self.x_labels()), 7)

    def test_date_floor_and_server_refusal(self):
        """Addendum A1: min 2000-01-01, the client message with no request, and a 400 invalid_range shown inline."""
        self.open()
        self.page.locator('#statsPeriod .chip', has_text='Custom').click()
        self.wait_unit('Comics per day')
        self.assertEqual([self.page.locator(s).get_attribute('min') for s in ('#statsFrom', '#statsTo')], ['2000-01-01'] * 2)
        sent = len(self.requests)
        self.page.fill('#statsFrom', '1999-12-31')
        self.page.wait_for_function('()=>document.querySelector("#statsRangeError").textContent==="Dates before 2000 are not available."')
        self.assertEqual([self.page.locator(s).get_attribute('aria-invalid') for s in ('#statsFrom', '#statsTo')], ['true', None])
        self.assertEqual(len(self.requests), sent)
        self.refuse = 'Dates after today are not available.'
        self.page.fill('#statsFrom', '2026-10-01')
        self.page.wait_for_function('n=>document.querySelector("#statsRangeError").textContent==="Dates after today are not available."'
                                    ' && !document.querySelector("#statsRangeError").hidden')
        self.assertEqual(len(self.requests), sent + 1)
        self.assertEqual((self.text('#statsTotal'), self.text('#statsNote')), ('9', ''))  # Last good data; no outage note.
        self.assertFalse(self.page.evaluate("document.querySelector('#statsNote').classList.contains('stats-error')"))
        self.refuse = None
        self.page.fill('#statsTo', '2026-10-27')
        self.page.wait_for_function("document.querySelector('#statsRangeError').hidden")

    def test_year_bars_and_counting_began_note(self):
        """Addendum A1 year unit and A3 row 6: 1 Jan 2021 - 1 Jan 2026 is 6 yearly bars, before counting began."""
        self.open()
        self.page.locator('#statsPeriod .chip', has_text='Custom').click()
        self.wait_unit('Comics per day')
        self.page.fill('#statsFrom', '2021-01-01')
        self.page.fill('#statsTo', '2026-01-01')
        self.page.wait_for_function("document.querySelector('#statsNote').textContent.startsWith('Counting began on ')")
        first = self.intl(local(2, 15), {'day': 'numeric', 'month': 'short', 'year': 'numeric'})
        self.assertEqual((self.text('#statsUnit'), self.text('#statsTotal'), self.text('#statsNote')),
                         ('Comics per year', '0', 'Counting began on ' + first + '.'))
        self.assertEqual(self.x_labels(), ['2021', '2022', '2023', '2024', '2025', '2026'])
        self.page.focus('#statsTo')  # Tab order: picker, From, To, chart; Tab first walks the date's own fields.
        for _ in range(4):
            if self.page.evaluate('document.activeElement.id') == 'statsChart':
                break
            self.page.keyboard.press('Tab')
        self.page.wait_for_function("document.activeElement.id==='statsChart' && !document.querySelector('#statsTip').hidden")
        last = time.mktime((2026, 1, 1, 12, 0, 0, 0, 0, -1))
        self.assertEqual(self.page.evaluate("document.querySelector('#statsTip div').textContent"),
                         self.intl(last, {'weekday': 'short', 'day': 'numeric', 'month': 'short', 'year': 'numeric'}))  # Clipped: its one day.
        self.page.keyboard.press('Home')
        self.assertEqual(self.page.evaluate("document.querySelector('#statsTip div').textContent"), '2021')

    def test_compact_y_labels_from_10000(self):
        """Addendum A3 row 5: 0 / 10K / 20K for 12,000; 0 / 5K / 10K for 9,000; full numbers below 10,000."""
        self.open()
        self.page.locator('#statsPeriod .chip', has_text='This year').click()
        self.wait_unit('Comics per month')
        frame = stats.resolve('year', NOW)
        compact = "v=>new Intl.NumberFormat(undefined,{notation:'compact',maximumFractionDigits:0}).format(v)"
        for top, axis, compacted in ((12000, (0, 10000, 20000), True), (9000, (0, 5000, 10000), True), (7900, (0, 4000, 8000), False)):
            self.stub = lambda query, top=top: payload('year', NOW, frame, [top if i == 9 else 100 for i in range(12)], total=top)
            self.page.evaluate('UpdateStats.refresh()')
            expected = [self.page.evaluate(compact, v) if compacted else self.page.evaluate('v=>v.toLocaleString()', v) for v in axis]
            self.page.wait_for_function('e=>JSON.stringify([...document.querySelectorAll("#statsChart text")].slice(0,3).map(t=>t.textContent))===JSON.stringify(e)', arg=expected)
            self.assertEqual(self.text('#statsTotal'), self.page.evaluate('v=>v.toLocaleString()', top))  # The headline keeps full numbers.
            self.assertGreaterEqual(min(self.page.evaluate("[...document.querySelectorAll('#statsChart text')].slice(0,3).map(t=>t.getBBox().x)")), 0)


def payload(period, now, frame, counts, total=None, first_at=None, last_at=None):
    """A hand-built /api/update-stats answer for frame (unit, edges); bars that start after now get None."""
    unit, edges = frame
    slots = [[edges[i], edges[i + 1], None if edges[i] > now else counts[i]] for i in range(len(edges) - 1)]
    return {'period': period, 'now': now, 'start': edges[0], 'end': edges[-1], 'unit': unit, 'slots': slots,
            'current': stats.current_slot(edges, now), 'total': sum(s[2] for s in slots if s[2]) if total is None else total,
            'first_at': edges[0] if first_at is None else first_at, 'last_at': now - 60 if last_at is None else last_at, 'revision': 1}


@unittest.skipUnless(os.environ.get('COMICS_TEST_CDP'), 'Requires owned offline headless fixture')
class UpdateStatsDaylightDOMTests(YandexDOMTests):
    """Spec Addendum A2 test vectors in Europe/Berlin with a 24-hour (en-GB) clock. Answers are stubbed, built
    from the server's own bar edges on a fixed Central European wall clock (test_update_stats.CentralEurope)."""
    route = UpdateStatsDOMTests.route
    answer = UpdateStatsDOMTests.answer
    text = UpdateStatsDOMTests.text
    wait_unit = UpdateStatsDOMTests.wait_unit

    def setUp(self):
        self.context = self.browser.new_context(timezone_id='Europe/Berlin', locale='en-GB')
        self.addCleanup(self.context.close)
        self.context.route('**/*', lambda route: route.abort())
        self.context.add_init_script('window.setInterval=()=>0;')
        self.page = self.context.new_page()
        self.root = Path(__file__).resolve().parents[1]
        self.requests, self.held, self.failing, self.stub, self.refuse = [], None, False, None, None
        self.page.set_viewport_size({'width': 640, 'height': 900})

    def open(self, now, answers):
        self.stub = lambda query: answers[query['period'][0]]
        self.page.clock.set_fixed_time(datetime.datetime.fromtimestamp(now, datetime.timezone.utc))
        self.page.route('https://comics-fixture.invalid/**', self.route)
        self.page.goto('https://comics-fixture.invalid/')
        self.page.wait_for_function("document.querySelector('#statsTotal').textContent!=='–'")

    def keyboard(self, count):
        """Tooltip line 1 and the announcement for the first `count` bars, read with Home and then the right arrow."""
        self.page.focus('#statsPeriod input:checked')
        self.page.keyboard.press('Tab')
        self.page.keyboard.press('Home')
        found = []
        for _ in range(count):
            found.append((plain(self.page.evaluate("document.querySelector('#statsTip div').textContent")), plain(self.text('#statsAnnounce'))))
            self.page.keyboard.press('ArrowRight')
        return found

    def vectors(self):
        """Addendum A2's 24-hour vectors when the page runs en-GB; the en-US form it names otherwise."""
        locale = self.page.evaluate('Intl.DateTimeFormat().resolvedOptions().locale')
        self.assertIn(locale, VECTORS, 'No vector table for the page locale ' + locale)
        return VECTORS[locale]

    def assert_clock_aligned(self, missing=()):
        """Hourly labels sit on clock hours divisible by the step, each hour once (A2 rule 4)."""
        hours = [hour_of(t) for t in self.page.evaluate("[...document.querySelectorAll('#statsChart text')].slice(3).map(t=>t.textContent)")]
        step = min(b - a for a, b in zip(hours, hours[1:]))  # A clock change can remove one aligned hour.
        self.assertEqual(hours, [h for h in range(0, 24, step) if h not in missing], hours)
        return step

    def test_autumn_repeated_hour(self):
        now = WALL.local(2026, 10, 25, 20)
        self.open(now, {'today': payload('today', now, stats.resolve('today', now, wall=WALL), [1] * 25)})
        expected = self.vectors()['autumn']
        found = self.keyboard(5)
        self.assertEqual([title for title, _ in found], expected)
        self.assertEqual([spoken for _, spoken in found], [title + ', 1 comic' for title in expected])  # Suffix announced too.
        self.assert_clock_aligned()
        self.page.set_viewport_size({'width': 1280, 'height': 900})
        self.page.wait_for_function("+document.querySelector('#statsChart svg').getAttribute('width')===document.querySelector('#statsChart').clientWidth")
        self.assertIn(self.assert_clock_aligned(), (1, 2))  # The repeated 02 is labelled once, on its first copy.

    def test_spring_missing_hour(self):
        now = WALL.local(2026, 3, 29, 20)
        self.open(now, {'today': payload('today', now, stats.resolve('today', now, wall=WALL), [1] * 23)})
        found = self.keyboard(3)
        self.assertEqual([title for title, _ in found], self.vectors()['spring'])
        self.page.set_viewport_size({'width': 1280, 'height': 900})
        self.page.wait_for_function("+document.querySelector('#statsChart svg').getAttribute('width')===document.querySelector('#statsChart').clientWidth")
        self.assertIn(self.assert_clock_aligned(missing=(2,)), (1, 2))  # No 02:00 slot, so no 02 label.

    def test_last_hour_across_the_clock_change(self):
        now = WALL.local(2026, 10, 25, 2, 10, fold=1)  # 02:10 winter time, 60 minutes after 02:10 summer time.
        self.open(now, {'today': payload('today', now, stats.resolve('today', now, wall=WALL), [1] * 25),
                        'hour': payload('hour', now, stats.resolve('hour', now, wall=WALL), [1] * 12)})
        self.page.locator('#statsPeriod .chip', has_text='Last hour').click()
        self.wait_unit('Comics per 5 minutes')
        dates, spanning, after = self.vectors()['hour']
        self.assertEqual(plain(self.text('#statsRange')), dates)
        found = self.keyboard(11)
        self.assertEqual((found[9][0], found[10][0]), (spanning, after))


def plain(text):
    """Chromium may put a narrow or no-break space before AM/PM; compare with plain spaces."""
    return text.replace('\u202f', ' ').replace('\u00a0', ' ')


def hour_of(label):
    parts = label.split()
    hour = int(parts[0])
    return hour % 12 + (12 if parts[1].upper().startswith('P') else 0) if len(parts) > 1 else hour


VECTORS = {
    'en-GB': {'autumn': ['Sun 25 Oct, 00:00–01:00', 'Sun 25 Oct, 01:00–02:00', 'Sun 25 Oct, 02:00–03:00 (first time)',
                         'Sun 25 Oct, 02:00–03:00 (second time)', 'Sun 25 Oct, 03:00–04:00'],
              'spring': ['Sun 29 Mar, 00:00–01:00', 'Sun 29 Mar, 01:00–02:00', 'Sun 29 Mar, 03:00–04:00'],
              'hour': ('02:10–02:10 (clocks went back)', '02:55–03:00', '02:00–02:05')},
    'en-US': {'autumn': ['Sun, Oct 25, 12:00 AM–1:00 AM', 'Sun, Oct 25, 1:00 AM–2:00 AM', 'Sun, Oct 25, 2:00 AM–3:00 AM (first time)',
                         'Sun, Oct 25, 2:00 AM–3:00 AM (second time)', 'Sun, Oct 25, 3:00 AM–4:00 AM'],
              'spring': ['Sun, Mar 29, 12:00 AM–1:00 AM', 'Sun, Mar 29, 1:00 AM–2:00 AM', 'Sun, Mar 29, 3:00 AM–4:00 AM'],
              'hour': ('2:10 AM–2:10 AM (clocks went back)', '2:55 AM–3:00 AM', '2:00 AM–2:05 AM')},
}


if __name__ == '__main__':
    unittest.main()
