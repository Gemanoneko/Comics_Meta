'use strict';
/* Folder help lines (UXSpec FolderHelpActions 2026-10-16 and its Amendment, Sergei's answers).
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
    backup_left: row => row.basis === 'original'
      ? 'A recovery backup is kept. The comic is exactly as it was before the write, so there is nothing to undo.'
      : row.basis === 'written'
        ? 'A recovery backup is kept. The comic was written and verified; the backup is the only way to undo that.'
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
    changed:'Nothing was deleted: a comic changed since the check, so its backup is kept. The list below is updated.',
  };
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
  function backupWords(entry) {
    const n = entry.offer && entry.offer.backups ? entry.offer.backups.length : 1;
    return {n, word: n === 1 ? 'the backup' : 'the backups'};
  }
  function paint(entry) {
    entry.note.hidden = !paused;
    state(entry.check, entry, blocked(entry, entry.op === 'check' ? TIP.checking : TIP.working, TIP.pausedCheck), TIP.check, true);
    if (entry.opener) {
      if (entry.offer.kind === 'close_recheck') {
        state(entry.opener, entry, blocked(entry, entry.op === 'close' ? TIP.closing : TIP.working, TIP.pausedClose), TIP.close, true);
      } else {
        const {n, word} = backupWords(entry);
        const pausedTip = 'Processing is paused. Resume processing to delete ' + word + ' and requeue.';
        state(entry.opener, entry, blocked(entry, TIP.working, pausedTip), n === 1
          ? "Delete this folder's kept recovery backup, then close this item and queue the unwritten comics again. You are asked to confirm first."
          : "Delete this folder's " + n + ' kept recovery backups, then close this item and queue the unwritten comics again. You are asked to confirm first.', true);
        if (entry.confirm) {
          state(entry.confirm.yes, entry, blocked(entry, entry.op === 'delete' ? 'Deleting ' + word + ', then checking again.' : TIP.working, pausedTip),
                n === 1 ? 'Delete the backup permanently, then requeue.' : 'Delete the ' + n + ' backups permanently, then requeue.', true);
          attr(entry.confirm.keep, 'aria-disabled', entry.op === 'delete' ? 'true' : null);  // In flight: every confirm button.
        }
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
    if (kind === 'delete_backup') return head + 'Delete the kept ' + (k === 1 ? 'backup' : 'backups') + ' to requeue, or check again.';
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
      || (offer.kind === 'delete_backup' && Array.isArray(offer.backups) && offer.backups.length > 0));
    entry.offer = valid ? offer : null;
    entry.offerBox.hidden = !valid;
    if (!valid) return;
    if (offer.kind === 'close_recheck') {
      entry.opener = button(entry, 'Close and recheck folder', 'help-secondary', () => runClose(entry));
    } else {
      entry.opener = button(entry, offer.backups.length === 1 ? 'Delete backup and requeue' : 'Delete backups and requeue', 'help-secondary', () => openConfirm(entry));
      entry.opener.setAttribute('aria-expanded', 'false');
      entry.opener.setAttribute('aria-controls', 'helpConfirm' + (++serial));
      entry.confirmId = entry.opener.getAttribute('aria-controls');
    }
    entry.offerBox.append(entry.opener);
    labels(entry);
    paint(entry);
  }

  function confirmLines(backups) {
    const n = backups.length;
    if (n === 1) {
      const comic = String(backups[0].name || '');
      return ['Delete this backup and requeue?', backups[0].basis === 'written'
        ? comic + ' was written and verified. The backup is the only way to undo that change. Deleting is permanent.'
        : comic + ' is exactly as it was before the app started writing, so there is nothing to undo. Deleting is permanent.'];
    }
    const group = basis => backups.filter(b => b.basis === basis);
    const comics = basis => new Set(group(basis).map(b => b.name)).size;
    const a = comics('original'), b = comics('written'), lines = ['Delete ' + n + ' backups and requeue?'];
    if (a > 0) lines.push(a === 1 ? '1 comic is exactly as it was before the app started writing; there is nothing to undo.'
      : a + ' comics are exactly as they were before the app started writing; there is nothing to undo.');
    // One comic with several backups: "its backups are" (Judy's wording verdict 2, 2026-10-16).
    if (b > 0) lines.push(b === 1 ? '1 comic was written and verified; ' + (group('written').length > 1 ? 'its backups are' : 'its backup is') + ' the only way to undo that change.'
      : b + ' comics were written and verified; their backups are the only way to undo those changes.');
    lines.push('Deleting is permanent.');
    return lines;
  }
  function openConfirm(entry) {
    if (!entry.offer || entry.offer.kind !== 'delete_backup' || blocked(entry, TIP.working, true)) return;
    closeConfirm(entry, false);
    const backups = entry.offer.backups, n = backups.length;
    const box = el('div', undefined, 'help-confirm');
    box.id = entry.confirmId;
    box.setAttribute('role', 'group');
    const [title, ...body] = confirmLines(backups);
    const heading = el('p', title, 'help-confirm-title');
    heading.id = box.id + 'Title';
    box.setAttribute('aria-labelledby', heading.id);
    box.append(heading, ...body.map(line => el('p', line)));
    const row = el('div', undefined, 'help-confirm-actions');
    const yes = button(entry, n === 1 ? 'Delete and requeue' : 'Delete ' + n + ' backups and requeue', 'help-danger', () => runDelete(entry, yes));
    const keep = button(entry, n === 1 ? 'Keep it' : 'Keep them', 'help-secondary', () => closeConfirm(entry, true));
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
    const backups = entry.offer.backups, n = backups.length;
    begin(entry, 'delete', n === 1
      ? "Deleting the backup, then checking this folder's comics again. This can take a few minutes."
      : 'Deleting ' + n + " backups, then checking this folder's comics again. This can take a few minutes.");
    const data = await post('attention/delete-backups', {ticket: entry.id, backups: backups.map(b => b.id)});
    end(entry);
    const move = focusAllowed(entry, pressed);
    if (data && (data.ok || Number(data.deleted) > 0) && window.KeptBackups) KeptBackups.refresh();
    if (data && data.ok) {
      const b = Number(data.deleted) || n;
      return succeed(entry, requeued(entry, data, b === 1 ? 'Backup deleted. ' : b + ' backups deleted. '), pressed);
    }
    if (data && data.code === 'gone') return succeed(entry, GONE, pressed);
    closeConfirm(entry, false);  // Every failure closes the confirm (A6).
    let text;
    if (!data) {
      text = n === 1
        ? 'No answer from the app. The backup may already be deleted. Use Check and requeue to see the current state.'
        : 'No answer from the app. Some or all of the backups may already be deleted. Use Check and requeue to see the current state.';
    } else if (data.code === 'changed') {
      if (isProblems(data.check)) showProblems(entry, data.check);
      else clearResult(entry);
      text = NOT_DELETED.changed;
    } else if (NOT_DELETED[data.code]) {
      text = NOT_DELETED[data.code];
    } else if (data.code === 'delete_failed') {
      const d = Number(data.deleted) || 0, total = Number(data.total) || n;
      if (d > 0) setOffer(entry, null);  // Some offered backups are gone: the offer is stale.
      text = d === 0
        ? (total === 1 ? 'Nothing was deleted: the backup could not be deleted. Close any program using it, then try again.'
          : 'Nothing was deleted: a backup could not be deleted. Close any program using them, then try again.')
        : 'Deleted ' + d + ' of ' + total + ' backups. ' + (total - d) + ' could not be deleted, so nothing was requeued. Close any program using them, then check again.';
    } else if (data.code === 'not_requeued') {
      const b = Number(data.deleted) || n;
      let reason = stop(data.error) || 'the check did not finish';
      if (data.reason === 'paused') reason = 'processing was paused';
      if (data.reason === 'problems' && isProblems(data.check)) {
        showProblems(entry, data.check);
        reason = 'the check found ' + count(data.check.total, 'problem', 'problems');
      } else {
        setOffer(entry, null);  // The deleted backups are gone: the offer is stale.
      }
      text = (b === 1 ? 'Backup deleted' : b + ' backups deleted') + ', but not requeued: ' + reason + '. Use Check and requeue to finish.';
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
