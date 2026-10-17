'use strict';
/* Folder help lines (UXSpec FolderHelpActions 2026-10-16, its Amendment with Sergei's answers, and
   Amendment 2: the app's own leftover temporary files in the Delete offer, 2026-10-17).
   One card per "Your help is needed" ticket, updated in place by ticket id: the 2-second poll never
   rebuilds a card, so focus, an operation in flight, a check result and an open confirm survive it.
   The page sends ticket ids and the problem or backup ids a check issued, never a path. Every outcome
   is worded here from a server code; nothing goes to the page's sticky error banner. Blocked buttons
   get aria-disabled and ignore clicks (never disabled, which drops keyboard focus); labels never change. */
window.FolderHelp = (() => {
  const REASONS = {
    interrupted: 'Interrupted: the app stopped while writing this folder, so some comics may be unwritten.',
    comic_changed: 'Stopped: a comic already written in this folder does not match what was verified.',
    outside_folder: 'Stopped: the saved plan names a file outside this folder.',
    not_verified: 'Stopped: a write could not be verified. The comic and its recovery backup need checking.',
    backup_kept: 'Stopped: a recovery backup could not be removed after a write.',
    library_busy: 'Stopped: this library was in use by another copy of the app.',
    other: 'Stopped: this batch hit an error.',
  };
  const NO_DETAILS = 'Stopped: this batch hit an error with no details.';
  const FINDINGS = {
    zip_failed: () => 'Failed the zip test. The archive is damaged.',
    written_changed: () => 'Does not match what was written and verified.',
    unwritten_changed: () => 'Does not match the file this batch planned.',
    missing: () => 'Not found in this folder.',
    temp_left: row => 'A leftover temporary file is next to this comic: ' + row.file + '.',
    // A proved backup by its basis (A6); one that is not proved by what was found (Amendment 2 B6).
    backup_left: row => row.basis === 'original'
      ? 'A recovery backup is kept. The comic is exactly as it was before the write, so there is nothing to undo.'
      : row.basis === 'written'
        ? 'A recovery backup is kept. The comic was written and verified; the backup is the only way to undo that.'
        : row.unproved === 'backup'
          ? 'A recovery backup is kept. It is not a copy of this comic, so it may hold another version. Decide in Kept backups.'
          : row.unproved === 'unread'
            ? 'A recovery backup is kept, but the app could not read it to compare it with the comic. Check again.'
            : 'A recovery backup is kept. Do not delete it until the comic is checked.',
  };
  const TIP = {
    check: "Check this folder's comics without changing them. If all is in order, close this item and queue the unwritten comics again.",
    checking: 'Checking now. Nothing is changed.',
    another: 'Another folder is being checked. Wait for it to finish.',
    working: 'This folder is being worked on. Wait for it to finish.',
    pausedCheck: 'Processing is paused. Resume processing to check and requeue.',
    open: 'Open this folder in File Explorer to check its comics. Nothing is changed.',
    show: 'Show this file in File Explorer. Nothing is changed.',
    close: 'Close this item and have this folder checked again at the next folder pass. No comic or backup file is changed.',
    closing: 'Closing this item.',
    pausedClose: 'Processing is paused. Resume processing to close and recheck.',
    keep: 'Go back. Nothing is deleted.',
  };
  const PAUSED_NOTE = 'Paused. Resume processing to requeue or recheck this folder.';
  const GONE = 'This folder is not waiting for help.';
  const CHECKING = "Checking this folder's comics. This can take a few minutes.";
  const NOT_CHECKED = {
    paused: 'Not requeued: processing is paused, and nothing was changed. Resume processing, then check again.',
    busy: 'Not checked: this folder is already being checked. Wait for it to finish.',
    folder_unavailable: 'Not checked: this folder is unavailable, and nothing was changed. Check that the library drive is connected.',
    library_busy: 'Not checked: another copy of the app is using this library, and nothing was changed. Close it, then check again.',
    outside_library: 'Not checked: this folder is not in the current library, and nothing was changed. Set the library back to the one that holds it, then check again.',
    plan_unreadable:'Not checked: the saved plan for this folder cannot be read, and nothing was changed. Check its comics in the folder, then close this item to recheck the folder.',
  };
  const NOT_DELETED = {
    paused: 'Nothing was deleted: processing is paused. Resume processing, then try again.',
    busy: 'Nothing was deleted: this folder is already being checked. Wait for it to finish.',
    folder_unavailable: 'Nothing was deleted: this folder is unavailable. Check that the library drive is connected.',
    library_busy: 'Nothing was deleted: another copy of the app is using this library. Close it, then try again.',
    outside_library: 'Nothing was deleted: this folder is not in the current library. Set the library back to the one that holds it, then try again.',
  };
  // Amendment 2 B5: "changed" now means a comic or one of its files; a file that is gone is file_gone.
  const CHANGED = 'Nothing was deleted: a comic or one of its files changed since the check. The list below is updated.';
  const NOT_CLOSED = {
    paused: 'Not closed: processing is paused, and nothing was changed. Resume processing, then try again.',
    busy: 'Not closed: this folder is already being checked. Wait for it to finish.',
    folder_unavailable: 'Not closed: this folder is unavailable, and nothing was changed. Check that the library drive is connected.',
    library_busy: 'Not closed: another copy of the app is using this library, and nothing was changed. Close it, then try again.',
    outside_library: 'Not closed: this folder is not in the current library, and nothing was changed. Set the library back to the one that holds it, then try again.',
    plan_readable: 'Not closed: this folder changed since the check, and nothing was changed. Use Check and requeue.',
  };
  const REVEAL = {
    folder_unavailable: () => 'Folder is unavailable. Check that the library drive is connected.',
    outside_library: () => 'This folder is not in the current library.',
    gone: () => GONE,
    not_found: row => row ? 'File not found. Check again to update this list.' : null,
  };

  const cards = new Map();   // ticket id -> entry; cleared when the ticket leaves
  const closed = new Set();  // closed from this page; skipped until the payload drops them
  let host = null, done = null, paused = false, running = null, serial = 0;

  const el = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const setText = (node, text) => { if (node.textContent !== text) node.textContent = text; };
  const tip = (node, text) => { if (node.title !== text) node.title = text; };
  const attr = (node, name, value) => {
    if (value === null) { if (node.hasAttribute(name)) node.removeAttribute(name); }
    else if (node.getAttribute(name) !== value) node.setAttribute(name, value);
  };
  const busy = node => node.getAttribute('aria-disabled') === 'true';
  const stop = text => String(text || '').trim().replace(/\.$/, '');
  const count = (n, one, many) => n === 1 ? '1 ' + one : n + ' ' + many;
  const noun = (n, one, many) => n === 1 ? one : many;
  // {P} (Amendment 2 B3): the counts joined by "and", a zero part dropped, each noun singular at 1.
  function filesText(b, t) {
    const parts = [];
    if (b > 0) parts.push(count(b, 'backup', 'backups'));
    if (t > 0) parts.push(count(t, 'temporary file', 'temporary files'));
    return parts.join(' and ');
  }
  // b backups and t temporary files in the Delete offer; t = 0 keeps every shipped A2 string.
  function sizes(offer) {
    const b = offer && Array.isArray(offer.backups) ? offer.backups.length : 0;
    const t = offer && Array.isArray(offer.temps) ? offer.temps.length : 0;
    return {b, t, total: b + t, P: filesText(b, t)};
  }
  const clean = path => window.KeptBackups ? KeptBackups.clean(path) : String(path || '');
  function folderName(path) {
    const text = clean(path).replace(/[\\/]+$/, '');
    return text.split(/[\\/]/).pop() || text;
  }
  function pathInto(node, path) {
    node.replaceChildren();
    if (window.KeptBackups && KeptBackups.pathText) KeptBackups.pathText(node, path);
    else node.textContent = clean(path);
  }

  async function post(path, body) {
    try {
      const response = await fetch('/api/' + path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
      const data = await response.json();
      return data && typeof data === 'object' ? data : null;
    } catch (_) {
      return null;  // No answer.
    }
  }

  function clearErrors(entry) { for (const line of entry.card.querySelectorAll('.help-error')) line.remove(); }
  function showError(where, text) {
    const line = el('p', text, 'help-error');
    line.setAttribute('role', 'alert');
    where.append(line);
  }
  // Every button in a card clears that card's error lines when a click is accepted (section 6).
  function button(entry, label, className, onClick) {
    const node = el('button', label, className);
    node.type = 'button';
    node.onclick = event => { if (busy(node)) return; clearErrors(entry); onClick(event); };
    return node;
  }

  /* Blocked states (sections 2, A2): this card's own operation, another line's, then the pause. */
  function blocked(entry, own, pausedTip) {
    if (entry.op) return own;
    if (running && running !== entry.id) return TIP.another;
    if (paused) return pausedTip;
    return null;
  }
  function state(node, entry, blockedTip, enabledTip, describedByNote) {
    attr(node, 'aria-disabled', blockedTip ? 'true' : null);
    tip(node, blockedTip || enabledTip);
    attr(node, 'aria-describedby', describedByNote && paused ? entry.note.id : null);
  }
  function paint(entry) {
    entry.note.hidden = !paused;
    state(entry.check, entry, blocked(entry, entry.op === 'check' ? TIP.checking : TIP.working, TIP.pausedCheck), TIP.check, true);
    if (entry.opener) {
      if (entry.offer.kind === 'close_recheck') {
        state(entry.opener, entry, blocked(entry, entry.op === 'close' ? TIP.closing : TIP.working, TIP.pausedClose), TIP.close, true);
      } else {
        const {b, t, P} = sizes(entry.offer);
        if (t === 0) {  // Backups alone: the A2 strings as shipped.
          const word = b === 1 ? 'the backup' : 'the backups';
          const pausedTip = 'Processing is paused. Resume processing to delete ' + word + ' and requeue.';
          state(entry.opener, entry, blocked(entry, TIP.working, pausedTip), b === 1
            ? "Delete this folder's kept recovery backup, then close this item and queue the unwritten comics again. You are asked to confirm first."
            : "Delete this folder's " + b + ' kept recovery backups, then close this item and queue the unwritten comics again. You are asked to confirm first.', true);
          if (entry.confirm) {
            state(entry.confirm.yes, entry, blocked(entry, entry.op === 'delete' ? 'Deleting ' + word + ', then checking again.' : TIP.working, pausedTip),
                  b === 1 ? 'Delete the backup permanently, then requeue.' : 'Delete the ' + b + ' backups permanently, then requeue.', true);
          }
        } else {  // With the app's temporary files (Amendment 2 B3, B7): the offer and the face alike.
          const pausedTip = 'Processing is paused. Resume processing to delete ' + P + ', then requeue.';
          const own = entry.op === 'delete' ? 'Deleting ' + P + ', then checking again.' : TIP.working;
          state(entry.opener, entry, blocked(entry, own, pausedTip),
                'Delete ' + P + ' left in this folder, then close this item and queue the unwritten comics again. You are asked to confirm first.', true);
          if (entry.confirm) state(entry.confirm.yes, entry, blocked(entry, own, pausedTip), 'Delete ' + P + ' permanently, then requeue.', true);
        }
        if (entry.confirm) attr(entry.confirm.keep, 'aria-disabled', entry.op === 'delete' ? 'true' : null);  // In flight: every confirm button.
      }
    }
  }
  const paintAll = () => { for (const entry of cards.values()) paint(entry); };

  function labels(entry) {
    const name = folderName(entry.folder);
    attr(entry.check, 'aria-label', 'Check and requeue: ' + name);
    attr(entry.open, 'aria-label', 'Open folder: ' + name);
    if (entry.opener) attr(entry.opener, 'aria-label', entry.opener.textContent + ': ' + name);
  }

  function create(item) {
    const entry = {id: item.id, folder: null, op: null, offer: null, opener: null, confirm: null, result: null};
    const card = entry.card = el('div', undefined, 'help-card');
    card.dataset.ticket = item.id;
    const head = el('p', undefined, 'help-head');
    entry.path = el('span', undefined, 'help-path');
    head.append(el('span', 'Your help is needed: ', 'help-stem'), entry.path);
    entry.reason = el('p', undefined, 'help-reason');
    entry.last = el('p', undefined, 'help-last');
    const actions = el('div', undefined, 'help-actions');
    entry.check = button(entry, 'Check and requeue', 'help-primary', () => runCheck(entry));
    entry.open = button(entry, 'Open folder', 'help-secondary', () => reveal(entry, entry.open, null));
    tip(entry.open, TIP.open);
    actions.append(entry.check, entry.open);
    entry.note = el('p', PAUSED_NOTE, 'help-paused');
    entry.note.id = 'helpPaused' + (++serial);
    entry.status = el('p', undefined, 'help-status');
    entry.status.setAttribute('role', 'status');
    entry.status.tabIndex = -1;
    entry.offerBox = el('div', undefined, 'help-offer');
    entry.offerBox.hidden = true;
    entry.list = el('div', undefined, 'help-list');
    entry.more = el('p', undefined, 'help-more');
    entry.more.hidden = true;
    card.append(head, entry.reason, entry.last, actions, entry.note, entry.status, entry.offerBox, entry.list, entry.more);
    cards.set(item.id, entry);
    return entry;
  }

  function update(entry, item) {
    if (entry.folder !== item.folder) {
      entry.folder = item.folder;
      pathInto(entry.path, item.folder);
      labels(entry);
    }
    const code = Object.hasOwn(REASONS, item.code) ? item.code : 'other';
    const raw = typeof item.error === 'string' ? item.error : '';
    const empty = raw.trim() === '';
    setText(entry.reason, code === 'other' && empty ? NO_DETAILS : REASONS[code]);
    entry.last.hidden = code === 'interrupted' || empty;
    if (!entry.last.hidden) setText(entry.last, 'Last error: ' + (raw.length > 300 ? raw.slice(0, 300) + '…' : raw));
  }

  function remove(entry) {
    entry.card.remove();
    cards.delete(entry.id);
  }

  /* The keyed render, every poll. New cards go in queue order; existing ones never move or rebuild. */
  function render(items, control) {
    host = host || document.getElementById('queueAttention');
    done = done || document.getElementById('attentionDone');
    if (!host) return;
    paused = Boolean(control && control.requested);
    const list = (Array.isArray(items) ? items : []).filter(item => item && typeof item.id === 'string' && item.id);
    const present = new Set(list.map(item => item.id));
    for (const id of [...closed]) if (!present.has(id)) closed.delete(id);
    for (const entry of [...cards.values()]) if (!present.has(entry.id) && !entry.op) remove(entry);
    let previous = null;
    for (const item of list) {
      if (closed.has(item.id)) continue;
      let entry = cards.get(item.id);
      if (!entry) {
        entry = create(item);
        host.insertBefore(entry.card, previous ? previous.card.nextSibling : host.firstChild);
      }
      update(entry, item);
      previous = entry;
    }
    paintAll();
  }
  function setControl(control) {
    paused = Boolean(control && control.requested);
    paintAll();
  }

  /* Results */
  function setStatus(entry, text) { setText(entry.status, text); }
  function focusAllowed(entry, pressed) {
    const active = document.activeElement;
    return !active || active === document.body || active === pressed || entry.card.contains(active);
  }
  function showDone(text) {
    done.hidden = false;
    setText(done, text);
  }
  function clearDone() {
    if (!done) return;
    setText(done, '');
    done.hidden = true;
  }
  function succeed(entry, text, pressed) {
    const move = focusAllowed(entry, pressed);
    closed.add(entry.id);
    remove(entry);
    showDone(text);
    if (move) done.focus();
  }
  function settle(entry, text, pressed, move) {
    setStatus(entry, text);
    if (move && entry.card.isConnected) entry.status.focus();
  }
  function requeued(entry, data, prefix = '') {
    const name = folderName(entry.folder), n = Number(data.unwritten) || 0, w = Number(data.written) || 0;
    if (n > 0) return prefix + 'Requeued ' + name + ': ' + (n === 1 ? '1 unwritten comic will be' : n + ' unwritten comics will be') + ' checked at the next folder pass.';
    if (w > 0) return prefix + 'Closed ' + name + ': ' + (w === 1 ? 'the comic in the batch was written and verified.' : 'all ' + w + ' comics in the batch were written and verified.');
    return prefix + 'Closed ' + name + ': the batch had nothing left to write.';
  }
  const isProblems = data => data && data.code === 'problems' && Array.isArray(data.problems) && Number.isFinite(data.total);

  function clearResult(entry) {
    closeConfirm(entry, false);
    entry.result = null;
    setOffer(entry, null);
    entry.list.replaceChildren();
    entry.more.hidden = true;
  }
  function showProblems(entry, data) {
    clearResult(entry);
    entry.result = data;
    entry.list.replaceChildren(...data.problems.map(row => problemRow(entry, row)));
    const left = data.total - data.problems.length;
    entry.more.hidden = left <= 0;
    if (left > 0) setText(entry.more, left + ' more not shown. Fix these first, then check again.');
    setOffer(entry, data.offer);
  }
  function summary(data) {
    const k = data.total, kind = data.offer && data.offer.kind;
    const head = 'Not requeued: ' + count(k, 'problem', 'problems') + ' found, and nothing was changed. ';
    if (kind === 'delete_backup') {
      const {b, t} = sizes(data.offer);
      if (t === 0) return head + 'Delete the kept ' + (k === 1 ? 'backup' : 'backups') + ' to requeue, or check again.';
      return head + 'Delete the ' + (b > 0 ? 'kept ' + noun(b, 'backup', 'backups') + ' and ' : '')
        + 'leftover temporary ' + noun(t, 'file', 'files') + ' to requeue, or check again.';  // B3, B7
    }
    if (kind === 'close_recheck') {  // Every finding is a comic changed after the batch was planned (Sergei's 2a).
      return head + (k === 1 ? 'The comic changed' : 'These comics changed')
        + ' after this batch was planned. Close this item to have the folder checked again at the next folder pass.';
    }
    return head + (k === 1 ? 'Fix it' : 'Fix them') + ', then check again.';
  }
  function problemRow(entry, row) {
    const node = el('div', undefined, 'help-row');
    const text = el('div', undefined, 'help-row-text');
    const finding = FINDINGS[row.finding] ? FINDINGS[row.finding](row) : '';
    text.append(el('p', String(row.name || ''), 'help-row-name'), el('p', finding, 'help-row-finding'));
    const show = button(entry, 'Show in folder', 'help-secondary', () => reveal(entry, show, row.id, node));
    tip(show, TIP.show);
    show.setAttribute('aria-label', 'Show in folder: ' + String(row.file || row.name || ''));
    node.append(text, show);
    return node;
  }

  /* The offer block (Amendment A3, A4): only what the server offered, never inferred. */
  function setOffer(entry, offer) {
    closeConfirm(entry, false);
    entry.offerBox.replaceChildren();
    entry.opener = null;
    const valid = offer && (offer.kind === 'close_recheck'
      || (offer.kind === 'delete_backup' && Array.isArray(offer.backups) && (offer.temps === undefined || Array.isArray(offer.temps))
          && offer.backups.length + (offer.temps || []).length > 0));
    entry.offer = !valid ? null : offer.kind === 'delete_backup' ? {...offer, temps: offer.temps || []} : offer;
    entry.offerBox.hidden = !valid;
    if (!valid) return;
    if (offer.kind === 'close_recheck') {
      entry.opener = button(entry, 'Close and recheck folder', 'help-secondary', () => runClose(entry));
    } else {
      entry.opener = button(entry, openerLabel(sizes(entry.offer)), 'help-secondary', () => openConfirm(entry));
      entry.opener.setAttribute('aria-expanded', 'false');
      entry.opener.setAttribute('aria-controls', 'helpConfirm' + (++serial));
      entry.confirmId = entry.opener.getAttribute('aria-controls');
    }
    entry.offerBox.append(entry.opener);
    labels(entry);
    paint(entry);
  }

  // The offer's visible label (A2; Amendment 2 B3 and B7: each noun plural by its own count).
  function openerLabel({b, t}) {
    if (t === 0) return b === 1 ? 'Delete backup and requeue' : 'Delete backups and requeue';
    const temps = noun(t, 'temporary file', 'temporary files');
    return 'Delete ' + (b > 0 ? noun(b, 'backup', 'backups') + ' and ' : '') + temps + ', then requeue';
  }
  // The confirm face never reads the same as the label; with a temporary file it repeats the total (B3).
  function faceLabel({b, t, total}) {
    if (t === 0) return b === 1 ? 'Delete and requeue' : 'Delete ' + b + ' backups and requeue';
    return total === 1 ? 'Delete and requeue' : 'Delete ' + total + ' files and requeue';
  }
  function confirmLines(offer) {
    const backups = offer.backups, temps = offer.temps, {b: n, t, P} = sizes(offer);
    const names = list => list.map(item => String(item.name || ''));
    const comics = new Set([...names(backups), ...names(temps)]);
    if (t > 0 && comics.size === 1 && n <= 1) {  // One comic: its own sentence (B4, B7).
      const comic = names(temps)[0], temp = String(temps[0].file || '');
      return ['Delete ' + P + ', then requeue?', n === 1
        ? comic + ' is exactly as it was before the app started writing, so there is nothing to undo. Left beside it: ' + temp + ', a temporary file made by the app. Deleting is permanent.'
        : comic + ' is exactly as it was before the app started writing. Beside it: ' + temp + ', a temporary file made by the app. Deleting is permanent.'];
    }
    if (t > 0 && n === 0) {  // B7, several comics.
      return ['Delete ' + P + ', then requeue?', comics.size + ' comics are exactly as they were before the app started writing. Beside them: '
        + count(t, 'temporary file', 'temporary files') + ' made by the app (listed below). Deleting is permanent.'];
    }
    if (t === 0 && n === 1) {
      const comic = String(backups[0].name || '');
      return ['Delete this backup and requeue?', backups[0].basis === 'written'
        ? comic + ' was written and verified. The backup is the only way to undo that change. Deleting is permanent.'
        : comic + ' is exactly as it was before the app started writing, so there is nothing to undo. Deleting is permanent.'];
    }
    // Counted by comics, once per comic: a temporary file is offered only beside a comic proved untouched.
    const group = basis => backups.filter(b => b.basis === basis);
    const a = new Set([...names(group('original')), ...names(temps)]).size, b = new Set(names(group('written'))).size;
    const lines = [t === 0 ? 'Delete ' + n + ' backups and requeue?' : 'Delete ' + P + ', then requeue?'];
    if (a > 0) lines.push(a === 1 ? '1 comic is exactly as it was before the app started writing; there is nothing to undo.'
      : a + ' comics are exactly as they were before the app started writing; there is nothing to undo.');
    // One comic with several backups: "its backups are" (Judy's wording verdict 2, 2026-10-16).
    if (b > 0) lines.push(b === 1 ? '1 comic was written and verified; ' + (group('written').length > 1 ? 'its backups are' : 'its backup is') + ' the only way to undo that change.'
      : b + ' comics were written and verified; their backups are the only way to undo those changes.');
    if (t > 0) lines.push('Left beside them: ' + count(t, 'temporary file', 'temporary files') + ' made by the app (listed below).');
    lines.push('Deleting is permanent.');
    return lines;
  }
  function openConfirm(entry) {
    if (!entry.offer || entry.offer.kind !== 'delete_backup' || blocked(entry, TIP.working, true)) return;
    closeConfirm(entry, false);
    const size = sizes(entry.offer);
    const box = el('div', undefined, 'help-confirm');
    box.id = entry.confirmId;
    box.setAttribute('role', 'group');
    const [title, ...body] = confirmLines(entry.offer);
    const heading = el('p', title, 'help-confirm-title');
    heading.id = box.id + 'Title';
    box.setAttribute('aria-labelledby', heading.id);
    box.append(heading, ...body.map(line => el('p', line)));
    const row = el('div', undefined, 'help-confirm-actions');
    const yes = button(entry, faceLabel(size), 'help-danger', () => runDelete(entry, yes));
    const keep = button(entry, size.total === 1 ? 'Keep it' : 'Keep them', 'help-secondary', () => closeConfirm(entry, true));
    tip(keep, TIP.keep);
    row.append(yes, keep);
    box.append(row);
    box.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !entry.op) { event.preventDefault(); event.stopPropagation(); closeConfirm(entry, true); }
    });
    entry.offerBox.after(box);
    entry.confirm = {box, yes, keep};
    entry.opener.setAttribute('aria-expanded', 'true');
    paint(entry);
    keep.focus();  // The safe button.
  }
  function closeConfirm(entry, restore) {
    if (!entry.confirm) return;
    entry.confirm.box.remove();
    entry.confirm = null;
    if (entry.opener) {
      entry.opener.setAttribute('aria-expanded', 'false');
      if (restore) entry.opener.focus();
    }
  }

  /* Operations: one at a time across all lines. */
  function begin(entry, op, text) {
    running = entry.id;
    entry.op = op;
    clearDone();
    setStatus(entry, text);
    paintAll();
  }
  function end(entry) {
    if (running === entry.id) running = null;
    entry.op = null;
    paintAll();
  }

  async function runCheck(entry) {
    const pressed = entry.check;
    clearResult(entry);
    begin(entry, 'check', CHECKING);
    const data = await post('attention/check', {ticket: entry.id});
    end(entry);
    const move = focusAllowed(entry, pressed);
    if (data && data.ok) return succeed(entry, requeued(entry, data), pressed);
    if (data && data.code === 'gone') return succeed(entry, GONE, pressed);
    if (isProblems(data)) { showProblems(entry, data); return settle(entry, summary(data), pressed, move); }
    if (data && data.code === 'plan_unreadable') setOffer(entry, data.offer);
    const text = data && NOT_CHECKED[data.code]
      || 'Not checked: ' + (data ? stop(data.error) || 'the app did not answer' : 'the app did not answer') + ', and nothing was changed. Try again.';
    settle(entry, text, pressed, move);
  }

  async function runDelete(entry, pressed) {
    const offer = entry.offer, {b: n, t, total: offered, P} = sizes(offer);
    begin(entry, 'delete', t > 0
      ? 'Deleting ' + P + ", then checking this folder's comics again. This can take a few minutes."
      : n === 1
        ? "Deleting the backup, then checking this folder's comics again. This can take a few minutes."
        : 'Deleting ' + n + " backups, then checking this folder's comics again. This can take a few minutes.");
    const data = await post('attention/delete-backups', {ticket: entry.id, backups: offer.backups.map(b => b.id), temps: offer.temps.map(x => x.id)});
    end(entry);
    const move = focusAllowed(entry, pressed);
    if (data && (data.ok || Number(data.deleted) > 0) && window.KeptBackups) KeptBackups.refresh();
    // What this click removed, by kind; a file already gone at its own delete is not counted (B5, B9.3).
    const d = data ? Number(data.deleted) || 0 : 0, total = data ? Number(data.total) || offered : offered;
    const db = t === 0 ? d : data ? Number(data.deleted_backups) || 0 : 0, dt = t === 0 ? 0 : data ? Number(data.deleted_temps) || 0 : 0;
    if (data && data.ok) {
      const prefix = db + dt === 0 ? '' : t > 0 ? filesText(db, dt) + ' deleted. ' : db === 1 ? 'Backup deleted. ' : db + ' backups deleted. ';
      return succeed(entry, requeued(entry, data, prefix), pressed);
    }
    if (data && data.code === 'gone') return succeed(entry, GONE, pressed);
    closeConfirm(entry, false);  // Every failure closes the confirm (A6).
    const fresh = () => { if (isProblems(data.check)) showProblems(entry, data.check); else clearResult(entry); };
    const unit = t > 0 ? ' files' : ' backups';
    let text;
    if (!data) {
      text = t > 0
        ? 'No answer from the app. The files may already be deleted. Use Check and requeue to see the current state.'
        : n === 1
          ? 'No answer from the app. The backup may already be deleted. Use Check and requeue to see the current state.'
          : 'No answer from the app. Some or all of the backups may already be deleted. Use Check and requeue to see the current state.';
    } else if (data.code === 'changed') {
      fresh();
      text = CHANGED;
    } else if (data.code === 'file_gone') {  // Futaba m1: a file the check offered is no longer there.
      fresh();
      text = t > 0 ? 'Nothing was deleted: a file from the check is no longer there. The list below is updated.'
        : 'Nothing was deleted: a backup from the check is no longer there. The list below is updated.';
    } else if (data.code === 'writing') {
      if (d > 0) setOffer(entry, null);  // Some offered files are gone: the offer is stale.
      text = d === 0 ? 'Nothing was deleted: a comic in this folder is being written now. Wait for it to finish, then try again.'
        : 'Deleted ' + d + ' of ' + total + unit + '. A comic in this folder is being written now, so nothing was requeued. Wait for it to finish, then check again.';
    } else if (NOT_DELETED[data.code]) {
      text = NOT_DELETED[data.code];
    } else if (data.code === 'delete_failed') {
      if (d > 0) setOffer(entry, null);  // Some offered files are gone: the offer is stale.
      if (d > 0) {
        text = 'Deleted ' + d + ' of ' + total + unit + '. ' + (total - d) + ' could not be deleted, so nothing was requeued. Close any program using them, then check again.';
      } else if (t > 0) {
        text = 'Nothing was deleted: a file could not be deleted. Close any program using it, then try again.';
      } else {
        text = total === 1 ? 'Nothing was deleted: the backup could not be deleted. Close any program using it, then try again.'
          : 'Nothing was deleted: a backup could not be deleted. Close any program using them, then try again.';
      }
    } else if (data.code === 'not_requeued') {
      let reason = stop(data.error) || 'the check did not finish';
      if (data.reason === 'paused') reason = 'processing was paused';
      if (data.reason === 'problems' && isProblems(data.check)) {
        showProblems(entry, data.check);
        reason = 'the check found ' + count(data.check.total, 'problem', 'problems');
      } else {
        setOffer(entry, null);  // The deleted files are gone: the offer is stale.
      }
      let head;
      if (t > 0) {
        head = db + dt > 0 ? filesText(db, dt) : P;
      } else {
        const b = d || n;
        head = b === 1 ? 'Backup' : b + ' backups';
      }
      text = head + ' deleted, but not requeued: ' + reason + '. Use Check and requeue to finish.';
    } else {
      text = 'Could not finish: ' + (stop(data.error) || 'the app did not answer') + '. Use Check and requeue to see what was changed.';
    }
    settle(entry, text, pressed, move);
  }

  async function runClose(entry) {
    const pressed = entry.opener;
    begin(entry, 'close', TIP.closing);
    const data = await post('attention/close', {ticket: entry.id});
    end(entry);
    const move = focusAllowed(entry, pressed);
    if (data && data.ok) return succeed(entry, 'Closed ' + folderName(entry.folder) + ': the folder will be checked again at the next folder pass. No comic or backup file was changed.', pressed);
    if (data && data.code === 'gone') return succeed(entry, GONE, pressed);
    if (data && data.code === 'plan_readable') setOffer(entry, null);  // The folder changed: the button is dead.
    const text = data && NOT_CLOSED[data.code] || 'Not closed: ' + (data ? stop(data.error) || 'the app did not answer' : 'the app did not answer') + '. Try again.';
    settle(entry, text, pressed, move);
  }

  /* Open folder (row null) and Show in folder (row: the problem row's node). */
  async function reveal(entry, node, problem, row) {
    node.setAttribute('aria-disabled', 'true');
    const data = await post('attention/reveal', problem ? {ticket: entry.id, problem} : {ticket: entry.id});
    node.removeAttribute('aria-disabled');
    if (data && data.ok) return;
    const words = data && REVEAL[data.code] && REVEAL[data.code](row);
    const text = words || (row ? 'Could not open File Explorer. The folder is shown above.' : 'Could not open File Explorer. Use the path above.');
    if (entry.card.isConnected) showError(row || entry.card, text);
  }

  return {render, control: setControl};
})();
