'use strict';
/* Update statistics (UXSpec UpdateStats 2026-10-26). The server resolves every period, bar edge and
   count in local time (/api/update-stats); this file only formats and draws, so the browser never works
   out daylight saving. One request per selection, then one every 15 s while the period ends now and the
   page is visible; the page's 2 s poll never drives this panel. All text is set with textContent. */
window.UpdateStats = (() => {
  const $ = id => document.getElementById(id);
  const SVG = 'http://www.w3.org/2000/svg';
  const REFRESH_MS = 15000, SLOW_MS = 250;
  const LEFT = 44, RIGHT = 8, TOP = 8, BOTTOM = 152, HEIGHT = 192, LABEL_Y = 172, Y_LABEL_X = 36;
  const BAR = '#4776c6', BAR_ACTIVE = '#bcd8f9';
  const STEPS = [1, 2, 3, 4, 6, 12, 24, 48], LABEL_GAP = 16, EARLIEST = '2000-01-01';
  const UNITS = {five_minutes: 'Comics per 5 minutes', hour: 'Comics per hour', day: 'Comics per day', week: 'Comics per week',
                 month: 'Comics per month', year: 'Comics per year'};
  const LABELS = {hour: 'updated in the last hour', today: 'updated today', week: 'updated this week', month: 'updated this month',
                  year: 'updated this year', all: 'updated, all time', custom: 'updated in this range'};
  const PHRASES = {hour: 'last hour', today: 'today', week: 'this week', month: 'this month', year: 'this year', all: 'all time',
                   custom: 'this range'};
  const NOTE_SEVERAL = 'A comic updated in several bars counts once in the total.';
  // OS locale, like the rest of the page (no locale argument).
  const fmt = options => new Intl.DateTimeFormat(undefined, options);
  const F = {
    time: fmt({hour: 'numeric', minute: '2-digit'}), hour: fmt({hour: 'numeric'}),
    weekdayDay: fmt({weekday: 'short', day: 'numeric'}), day: fmt({day: 'numeric'}),
    dayMonth: fmt({day: 'numeric', month: 'short'}), dayMonthYear: fmt({day: 'numeric', month: 'short', year: 'numeric'}),
    weekdayDate: fmt({weekday: 'short', day: 'numeric', month: 'short'}),
    weekdayDateYear: fmt({weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'}),
    month: fmt({month: 'short'}), monthYear: fmt({month: 'short', year: 'numeric'}), longMonthYear: fmt({month: 'long', year: 'numeric'}),
    year: fmt({year: 'numeric'}), when: fmt({weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'}),
    // A wall-clock time held as UTC fields, so adding a slot's length never passes through the local zone.
    clock: fmt({hour: 'numeric', minute: '2-digit', timeZone: 'UTC'}),
  };
  const COMPACT = new Intl.NumberFormat(undefined, {notation: 'compact', maximumFractionDigits: 0});

  const picker = $('statsPeriod'), customRow = $('statsCustom'), from = $('statsFrom'), to = $('statsTo'), rangeError = $('statsRangeError');
  const head = $('statsHead'), total = $('statsTotal'), label = $('statsLabel'), range = $('statsRange'), unit = $('statsUnit');
  const chart = $('statsChart'), svg = chart.querySelector('svg'), tip = $('statsTip'), note = $('statsNote'), announce = $('statsAnnounce');
  const allTime = picker.querySelector('input[value="all"]').closest('label');
  const tipTitle = document.createElement('div'), tipCount = document.createElement('div');
  tipTitle.className = 'stats-tip-title';
  tip.append(tipTitle, tipCount);

  let shown = null, shownSignature = '', shownKey = '', geometry = null, active = null;
  let seq = 0, timer = null, slowTimer = null, prefilled = false, failed = false, stale = false, drawnWidth = 0;

  const set = (node, text) => { if (node.textContent !== text) node.textContent = text; };
  const pad = n => String(n).padStart(2, '0');
  const iso = d => d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
  const today = () => iso(new Date());
  const at = seconds => new Date(seconds * 1000);
  const sameDay = (a, b) => iso(a) === iso(b);
  const comics = n => n === 1 ? '1 comic' : n.toLocaleString() + ' comics';
  const period = () => picker.querySelector('input:checked')?.value || 'today';

  function dayRange(a, b, weekday) {
    const long = weekday ? F.weekdayDateYear : F.dayMonthYear, short = weekday ? F.weekdayDate : F.dayMonth;
    if (sameDay(a, b)) return long.format(a);
    return (a.getFullYear() === b.getFullYear() ? short : long).format(a) + ' – ' + long.format(b);
  }

  /* Custom range (spec section 4, Addendum A1): applies on change when both dates are valid; never fetched
     otherwise. One message, in this order. */
  function rangeProblem() {
    const first = from.value, last = to.value, now = today();
    if (!first || !last) return ['Pick both dates.', !first, !last];
    if (first > now || last > now) return ['Dates after today are not available.', first > now, last > now];
    if (first < EARLIEST || last < EARLIEST) return ['Dates before 2000 are not available.', first < EARLIEST, last < EARLIEST];
    if (last < first) return ['End date is before the start date.', false, true];
    return null;
  }
  function refuseRange(message) {  // A server refusal is not an outage (Addendum A1): no retry, data kept.
    set(rangeError, message);
    rangeError.hidden = false;
  }
  function paintRange() {
    const problem = period() === 'custom' ? rangeProblem() : null;
    set(rangeError, problem ? problem[0] : '');
    rangeError.hidden = !problem;
    for (const [input, bad] of [[from, problem && problem[1]], [to, problem && problem[2]]]) {
      if (bad) input.setAttribute('aria-invalid', 'true'); else input.removeAttribute('aria-invalid');
    }
    return !problem;
  }
  function selection() {
    const value = period();
    if (value !== 'custom') return 'period=' + value;
    return rangeProblem() ? null : 'period=custom&from=' + encodeURIComponent(from.value) + '&to=' + encodeURIComponent(to.value);
  }
  const endsNow = key => !key.startsWith('period=custom') || key.endsWith('&to=' + today());

  /* Requests: the latest selection wins; a selection change is never dropped for a fetch in flight. */
  async function refresh() {
    clearTimeout(timer);
    timer = null;
    from.max = to.max = today();
    const key = selection();
    if (!key) return;
    const mine = ++seq;
    clearTimeout(slowTimer);
    if (shown && key !== shownKey) slowTimer = setTimeout(() => { if (mine === seq) { stale = true; paintStatus(); } }, SLOW_MS);
    try {
      const data = await request('update-stats?' + key);
      if (mine !== seq) return;
      clearTimeout(slowTimer);
      render(data, key);
      schedule(endsNow(key));
    } catch (error) {
      if (mine !== seq) return;
      clearTimeout(slowTimer);
      stale = false;
      if (error && error.data && error.data.code === 'invalid_range') {
        failed = false;  // The server answered: no outage.
        refuseRange(error.message);
        paintStatus();
        return;
      }
      failed = true;
      paintStatus();
      schedule(true);
    }
  }
  function schedule(again) {
    clearTimeout(timer);
    timer = again && !document.hidden ? setTimeout(refresh, REFRESH_MS) : null;
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { clearTimeout(timer); timer = null; return; }
    const key = selection();
    if (key && (failed || endsNow(key))) refresh();
  });

  /* States (spec section 9). Heights never change: the chart keeps 192 px and the note 21 px. */
  function dataNote(data) {
    if (data.total === 0) {
      if (data.period === 'custom' && data.first_at != null && data.end <= data.first_at) {
        return 'Counting began on ' + F.dayMonthYear.format(at(data.first_at)) + '.';  // Addendum A3 row 6.
      }
      if (data.last_at == null) return 'No updates yet.';
      const last = at(data.last_at);
      return 'Last update: ' + (sameDay(last, new Date()) ? F.time.format(last) : F.when.format(last)) + '.';
    }
    const sum = data.slots.reduce((n, slot) => n + (slot[2] || 0), 0);
    return sum > data.total ? NOTE_SEVERAL : '';
  }
  function paintStatus() {
    const dim = Boolean(shown) && (stale || failed);
    for (const node of [head, unit, chart]) node.classList.toggle('stats-stale', dim);
    set(total, stale || !shown ? '–' : shown.total.toLocaleString());
    const error = failed && !stale;
    note.classList.toggle('stats-error', error);
    set(note, error ? 'Statistics unavailable. Retrying.' : stale || !shown ? 'Loading statistics…' : dataNote(shown));
  }
  function rangeText(data) {
    const start = at(data.start), lastDay = at(data.end - 0.001);
    if (data.period === 'hour') {  // Two equal times only happen when the clocks went back inside the window (A2 rule 5).
      const first = F.time.format(start), last = F.time.format(at(data.end));
      return first + '–' + last + (first === last ? ' (clocks went back)' : '');
    }
    if (data.period === 'today') return F.weekdayDateYear.format(start);
    if (data.period === 'week') return dayRange(start, lastDay, true);
    if (data.period === 'month') return F.longMonthYear.format(start);  // A named period, like the year (Addendum 2 B4).
    if (data.period === 'year') return F.year.format(start);
    if (data.period === 'all') return data.first_at == null ? 'Since counting began' : 'Since ' + F.dayMonthYear.format(at(data.first_at));
    return dayRange(start, lastDay, false);
  }
  function headline(data) {
    return (data.total === 1 ? 'comic ' : 'comics ') + LABELS[data.period];
  }
  function render(data, key) {
    const newSelection = key !== shownKey;
    failed = false;
    stale = false;
    const signature = JSON.stringify([data.period, data.unit, data.slots, data.current, data.total, data.first_at, data.last_at]);
    if (signature !== shownSignature) {
      const keep = active != null && shown && shown.slots.length === data.slots.length && shown.slots[0][0] === data.slots[0][0];
      shown = data;
      shownSignature = signature;
      set(label, headline(data));
      set(range, rangeText(data));
      set(unit, UNITS[data.unit] || '');
      chart.setAttribute('aria-label', (UNITS[data.unit] || 'Comics') + ', ' + PHRASES[data.period] + '. Left and right arrows read each bar.');
      allTime.title = data.first_at == null ? 'Every comic updated since counting began.' :
        'Every comic updated since counting began on ' + F.dayMonthYear.format(at(data.first_at)) + '.';
      draw();
      choose(keep && isActive(active) ? active : null, false);
    }
    shownKey = key;
    paintStatus();
    if (newSelection) set(announce, data.total.toLocaleString() + ' ' + headline(data));
  }

  /* Chart (spec section 7): 1 SVG unit = 1 CSS px; redrawn for new data or a new width only. */
  function scaleMax(top) {
    const need = Math.max(4, top);
    for (let power = 1; ; power *= 10) for (const m of [1, 2, 4, 6, 8]) if (m * power >= need) return m * power;
  }
  function make(tag, attributes, text) {
    const node = document.createElementNS(SVG, tag);
    for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
    if (text !== undefined) node.textContent = text;
    return node;
  }
  /* Daylight saving (Addendum A2), read from neighbouring slots' local clocks; the page computes no zone boundary. */
  const startClock = i => { const d = at(shown.slots[i][0]); return d.getHours() * 60 + d.getMinutes(); };
  function repeat(i) {  // 1 or 2 on the two copies of the hour the clocks went back over, else 0.
    if (shown.unit !== 'hour') return 0;
    if (i + 1 < shown.slots.length && startClock(i + 1) === startClock(i)) return 1;
    return i > 0 && startClock(i - 1) === startClock(i) ? 2 : 0;
  }
  function endClock(a, seconds) {  // The start clock plus the slot's length; never the end instant on its own (rule 1).
    const wall = Date.UTC(a.getFullYear(), a.getMonth(), a.getDate(), a.getHours(), a.getMinutes(), a.getSeconds());
    return F.clock.format(new Date(wall + seconds * 1000));
  }
  function labelText(i) {
    const slots = shown.slots, day = at(slots[i][0]);
    if (shown.unit === 'hour') return F.hour.format(day);
    if (shown.unit === 'day') return (slots.length <= 14 ? F.weekdayDay : i === 0 || day.getDate() === 1 ? F.dayMonth : F.day).format(day);
    if (shown.unit === 'week') return F.dayMonth.format(day);  // The week's first day inside the range (Addendum A3 row 7).
    if (shown.unit === 'year') return F.year.format(day);
    return (i === 0 || day.getMonth() === 0 ? F.monthYear : F.month).format(day);
  }
  function picks(step) {  // Every step-th slot from the first; hourly bars at clock hours divisible by step (A2 rule 4).
    const all = shown.slots.map((_, i) => i);
    if (shown.unit === 'hour') return all.filter(i => repeat(i) !== 2 && at(shown.slots[i][0]).getHours() % step === 0);
    return all.filter(i => i % step === 0);
  }
  function axisLabels(pitch, width, measure) {
    if (shown.unit === 'five_minutes') {
      return [[0, '−60 min'], [3, '−45'], [6, '−30'], [9, '−15'], [12, 'now']].map(([edge, text]) =>
        ({x: edge === 12 ? width - RIGHT : LEFT + edge * pitch, text, anchor: edge === 12 ? 'end' : 'middle'}));
    }
    // Thinning (Addendum A3 row 2): the smallest step whose spacing holds the widest drawn label plus 16 px.
    const texts = shown.slots.map((_, i) => labelText(i));
    let chosen = [0];
    for (const step of STEPS) {
      const candidate = picks(step);
      if (step * pitch >= Math.max(0, ...candidate.map(i => measure(texts[i]))) + LABEL_GAP) { chosen = candidate; break; }
    }
    return chosen.map(i => ({x: LEFT + (i + 0.5) * pitch, text: texts[i], anchor: 'middle'}));
  }
  function draw() {
    const width = chart.clientWidth;
    drawnWidth = width;
    if (!shown || width <= LEFT + RIGHT) { svg.replaceChildren(); geometry = null; return; }
    const slots = shown.slots, pitch = (width - LEFT - RIGHT) / slots.length, plot = BOTTOM - TOP;
    const max = scaleMax(Math.max(0, ...slots.map(slot => slot[2] || 0)));
    const y = value => BOTTOM - value / max * plot;
    const barWidth = Math.min(48, Math.max(2, pitch * 0.7));
    svg.setAttribute('width', width);
    svg.setAttribute('height', HEIGHT);
    svg.setAttribute('viewBox', '0 0 ' + width + ' ' + HEIGHT);
    const highlight = make('rect', {x: LEFT, y: TOP, width: pitch, height: plot, fill: '#242c3b', visibility: 'hidden'});
    const parts = [highlight];
    for (const value of [max / 2, max]) parts.push(make('line', {x1: LEFT, x2: width - RIGHT, y1: y(value) - 0.5, y2: y(value) - 0.5, stroke: '#303848', 'stroke-width': 1}));
    // Y labels 2 px above their line, so the digits (not the em box) centre on it; compact from 10,000 (Addendum A3 rows 4-5).
    const yText = value => max >= 10000 ? COMPACT.format(value) : value.toLocaleString();
    for (const value of [0, max / 2, max]) parts.push(make('text', {x: Y_LABEL_X, y: y(value) - 2, 'text-anchor': 'end', 'dominant-baseline': 'central'}, yText(value)));
    const tops = [];
    const bars = slots.map((slot, i) => {
      const value = slot[2];
      if (!(value >= 1)) { tops.push(BOTTOM); return null; }
      const height = Math.max(3, value / max * plot);
      tops.push(BOTTOM - height);
      const bar = make('rect', {x: LEFT + i * pitch + (pitch - barWidth) / 2, y: BOTTOM - height, width: barWidth, height, rx: 2, fill: BAR});
      parts.push(bar);
      return bar;
    });
    parts.push(make('line', {x1: LEFT, x2: width - RIGHT, y1: BOTTOM - 0.5, y2: BOTTOM - 0.5, stroke: '#485771', 'stroke-width': 1}));
    const probe = make('text', {x: 0, y: LABEL_Y, visibility: 'hidden'}), widths = new Map();
    svg.replaceChildren(probe);
    const measure = text => {  // Width as drawn (getBBox), once per distinct text.
      if (!widths.has(text)) { probe.textContent = text; widths.set(text, probe.getBBox().width); }
      return widths.get(text);
    };
    const labels = axisLabels(pitch, width, measure).map(item => make('text', {x: item.x, y: LABEL_Y, 'text-anchor': item.anchor}, item.text));
    parts.push(...labels);
    svg.replaceChildren(...parts);
    for (const text of labels) {  // Keep every label inside the SVG.
      const box = text.getBBox();
      if (box.x + box.width > width) { text.setAttribute('text-anchor', 'end'); text.setAttribute('x', width); }
      else if (box.x < 0) { text.setAttribute('text-anchor', 'start'); text.setAttribute('x', 0); }
    }
    geometry = {width, pitch, bars, tops, highlight, marked: null};
  }

  /* Hover and keyboard (spec section 8): one tooltip, never a native title on the chart. */
  const isActive = i => Boolean(shown) && i >= 0 && i < shown.slots.length && shown.slots[i][2] != null;
  const activeSlots = () => shown ? shown.slots.map((_, i) => i).filter(isActive) : [];
  function tipText(i) {
    const [start, end, count] = shown.slots[i], a = at(start), b = at(end), last = at(end - 0.001);
    let title;
    if (shown.unit === 'five_minutes') title = F.time.format(a) + '–' + endClock(a, end - start);
    else if (shown.unit === 'hour') {
      title = F.weekdayDate.format(a) + ', ' + F.time.format(a) + '–' + endClock(a, end - start) + ['', ' (first time)', ' (second time)'][repeat(i)];
    }
    else if (shown.unit === 'day') title = F.weekdayDateYear.format(a);
    else if (shown.unit === 'week') title = dayRange(a, last, true);
    else if (shown.unit === 'year') {
      const whole = a.getMonth() === 0 && a.getDate() === 1 && a.getHours() === 0 && b.getMonth() === 0 && b.getDate() === 1 && b.getHours() === 0;
      title = whole ? F.year.format(a) : dayRange(a, last, true);  // A clipped year names its dates, as a clipped month does.
    }
    else {
      const whole = a.getDate() === 1 && a.getHours() === 0 && b.getDate() === 1 && b.getHours() === 0;
      title = whole ? F.longMonthYear.format(a) : dayRange(a, last, true);  // A clipped month names its dates.
    }
    return [title, comics(count) + (i === shown.current ? ' so far' : '')];
  }
  function mark(i) {
    if (!geometry) return;
    const previous = geometry.marked;
    if (previous != null && geometry.bars[previous]) geometry.bars[previous].setAttribute('fill', BAR);
    geometry.marked = i;
    if (i == null) { geometry.highlight.setAttribute('visibility', 'hidden'); return; }
    geometry.highlight.setAttribute('x', LEFT + i * geometry.pitch);
    geometry.highlight.setAttribute('visibility', 'visible');
    if (geometry.bars[i]) geometry.bars[i].setAttribute('fill', BAR_ACTIVE);
  }
  function place(i) {
    const g = geometry, w = tip.offsetWidth, h = tip.offsetHeight, slotLeft = LEFT + i * g.pitch, top = g.tops[i];
    let left = slotLeft + g.pitch / 2 - w / 2, y = top - 8 - h;
    if (y < 0) {  // No room above: beside the slot, right first.
      y = Math.min(Math.max(0, top - h / 2), HEIGHT - h);
      left = slotLeft + g.pitch + 8;
      if (left + w > g.width) left = slotLeft - 8 - w;
    }
    left = Math.max(0, Math.min(g.width - w, left));
    tip.style.left = left + 'px';
    tip.style.top = y + 'px';
  }
  function choose(i, fromKeyboard) {
    active = i;
    mark(i);
    if (i == null || !geometry) { tip.hidden = true; return; }
    const [title, count] = tipText(i);
    set(tipTitle, title);
    set(tipCount, count);
    tip.hidden = false;
    place(i);
    if (fromKeyboard) set(announce, title + ', ' + count);
  }
  chart.addEventListener('pointermove', event => {
    if (!geometry) return;
    const box = chart.getBoundingClientRect(), x = event.clientX - box.left, y = event.clientY - box.top;
    const i = x >= LEFT && x < geometry.width - RIGHT && y >= TOP && y <= BOTTOM ? Math.floor((x - LEFT) / geometry.pitch) : null;
    const next = i != null && isActive(i) ? i : null;
    if (next !== active) choose(next, false);
  });
  chart.addEventListener('pointerleave', () => { if (active != null) choose(null, false); });
  chart.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      if (active != null) { event.preventDefault(); choose(null, false); }
      return;
    }
    const list = activeSlots(), position = list.indexOf(active);
    if (!list.length) return;
    let next;
    if (event.key === 'ArrowLeft') next = list[position < 0 ? list.length - 1 : Math.max(0, position - 1)];
    else if (event.key === 'ArrowRight') next = list[position < 0 ? list.length - 1 : Math.min(list.length - 1, position + 1)];
    else if (event.key === 'Home') next = list[0];
    else if (event.key === 'End') next = list[list.length - 1];
    else return;
    event.preventDefault();
    choose(next, true);
  });
  chart.addEventListener('focus', () => {
    if (!chart.matches(':focus-visible')) return;
    const list = activeSlots();
    if (list.length) choose(list[list.length - 1], true);  // The slot holding now, when the period includes it.
  });
  chart.addEventListener('blur', () => choose(null, false));
  new ResizeObserver(() => {
    if (chart.clientWidth === drawnWidth) return;
    draw();
    choose(active != null && isActive(active) ? active : null, false);
  }).observe(chart);

  /* Picker (spec section 4): native radios, one Tab stop; Today on every page load. */
  picker.addEventListener('change', () => {
    const custom = period() === 'custom';
    customRow.hidden = !custom;
    if (custom && !prefilled) {
      const start = new Date();
      start.setDate(start.getDate() - 29);
      from.value = iso(start);
      to.value = today();
      prefilled = true;
    }
    paintRange();
    refresh();
  });
  for (const input of [from, to]) input.addEventListener('change', () => { if (paintRange()) refresh(); });

  picker.querySelector('input[value="today"]').checked = true;
  customRow.hidden = true;
  paintStatus();
  refresh();
  return {refresh};
})();
