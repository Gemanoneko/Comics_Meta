'use strict';
/* Recovery backup location and Kept backups (UXSpec BackupLocation 2026-10-16 and its Amendment).
   The page never sends a path: every action names the opaque id the server issued for that backup.
   All text is set with textContent. In flight a control gets aria-disabled and ignores clicks
   (never disabled, which can drop keyboard focus). */
window.KeptBackups = (() => {
  const LIMIT = 500;
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const REASONS = {save_not_verified: 'Save not verified', delete_refused: 'Saved; backup could not be deleted',
                   not_saved: 'Not saved; file was not changed'};
  // Show in folder errors, per host: the location block shows the full path, a row only its comic's folder.
  const UNAVAILABLE = 'Folder is unavailable. Check that the library drive is connected.';
  const BLOCK_REVEAL = {not_found: 'Could not find this backup. Check the path above.', folder_unavailable: UNAVAILABLE,
                        failed: 'Could not open File Explorer. Use the path above.'};
  const ROW_REVEAL = {not_found: 'Backup not found. Use Refresh to update the list.', folder_unavailable: UNAVAILABLE,
                      failed: 'Could not open File Explorer. The backup is in the .comic-metadata-backups folder inside the folder above.'};
  const DELETE_ERRORS = {
    writing: 'This comic is being updated. Try again in a minute.',
    in_use: 'Could not delete this backup. Close any program using it, then try again.',
    refused: 'Not deleted. This is not a recovery backup in your library.',
    not_found: 'Backup not found. Use Refresh to update the list.',
    folder_unavailable: 'Folder is unavailable. Check that the library drive is connected.',
  };
  const DELETE_FAILED = 'Could not delete this backup. Try again.';
  const SHOW_TIP = 'Show this recovery backup file in File Explorer. Nothing is changed.';

  const el = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const busy = node => node.getAttribute('aria-disabled') === 'true';
  const setBusy = (nodes, value) => {
    for (const node of nodes) if (value) node.setAttribute('aria-disabled', 'true'); else node.removeAttribute('aria-disabled');
  };
  function button(label, title, onClick, className) {
    const node = el('button', label, className);
    node.type = 'button';
    node.title = title;
    node.onclick = event => { if (!busy(node)) onClick(event); };
    return node;
  }

  // Explorer's address-bar form: no \\?\ prefix, and \\?\UNC\srv\share shows as \\srv\share.
  function clean(path) {
    const text = String(path || '');
    if (text.startsWith('\\\\?\\UNC\\')) return '\\\\' + text.slice(8);
    if (text.startsWith('\\\\?\\')) return text.slice(4);
    return text;
  }
  // A break opportunity after each backslash. <wbr> adds nothing to copied text; U+200B would.
  function pathText(node, path) {
    const parts = clean(path).split('\\');
    parts.forEach((part, index) => {
      const last = index === parts.length - 1;
      node.append(document.createTextNode(last ? part : part + '\\'));
      if (!last) node.append(document.createElement('wbr'));
    });
    return node;
  }
  // Explorer style: 1024 base, three significant digits, truncated (412 MB, 41.2 MB, 3.19 GB).
  function size(bytes) {
    const units = ['bytes', 'KB', 'MB', 'GB', 'TB'];
    let value = Math.max(0, Number(bytes) || 0), unit = 0;
    while (unit < units.length - 1 && value >= (unit ? 1000 : 1024)) { value /= 1024; unit++; }  // 1000 KB shows as 0.97 MB.
    if (unit === 0) return Math.floor(value) + ' bytes';
    const digits = value >= 100 ? 0 : value >= 10 ? 1 : 2;
    return (Math.floor(value * 10 ** digits) / 10 ** digits).toFixed(digits) + ' ' + units[unit];
  }
  function age(created) {
    const seconds = Math.max(0, Date.now() / 1000 - created);
    if (seconds < 60) return 'just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return minutes + ' min ago';
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return hours + (hours === 1 ? ' hour ago' : ' hours ago');
    const days = Math.floor(hours / 24);
    if (days <= 30) return days + (days === 1 ? ' day ago' : ' days ago');
    const date = new Date(created * 1000);
    return date.getDate() + ' ' + MONTHS[date.getMonth()] + ' ' + date.getFullYear();
  }

  async function post(path, body) {
    const response = await fetch('/api/' + path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw Object.assign(Error(data.error || 'failed'), {code: data.code || 'failed'});
    return data;
  }

  // One error line per host, created on the first failure, cleared on the next action.
  function errorLine(host, className) {
    let line = null;
    return {
      show(text) { if (!line) { line = el('p', undefined, className); line.setAttribute('role', 'alert'); } line.textContent = text; host.append(line); },
      clear() { if (line) { line.remove(); line = null; } },
    };
  }

  function revealButton(id, label, line, messages, accessibleName) {
    const node = button(label, SHOW_TIP, async () => {
      line.clear();
      setBusy([node], true);
      try { await post('backups/reveal', {id}); }
      catch (error) { line.show(messages[error.code] || messages.failed); }
      finally { setBusy([node], false); }
    }, 'backup-button');
    if (accessibleName) node.setAttribute('aria-label', accessibleName);
    return node;
  }

  /* The location block (spec section 4): one component for the Details recovery outcome and the
     Lookup Apply outcome. Its host places it as a sibling after the live region, never inside it. */
  function block(kept) {
    const node = el('div', undefined, 'backup-location');
    node.append(el('p', 'Recovery backup', 'backup-location-label'), pathText(el('p', undefined, 'backup-location-path'), kept.path));
    if (kept.id) {
      const row = el('div', undefined, 'recovery-actions');
      row.append(revealButton(kept.id, 'Show backup in folder', errorLine(node, 'backup-location-error'), BLOCK_REVEAL));
      node.append(row);
    }
    return node;
  }

  /* Kept backups panel (Amendment A2-A5), the second <details> in the Live library panel. */
  let items = [], bounded = false, ticket = 0, confirm = null, working = false;
  let panel, summary, intro, toolbar, refreshButton, deleteAllButton, statusLine, note, list;
  const total = () => items.reduce((sum, item) => sum + item.size, 0);
  const toolbarButtons = () => [refreshButton, deleteAllButton];

  function setStatus(text, role) {
    if (!text) { statusLine.textContent = ''; statusLine.hidden = true; return; }
    statusLine.setAttribute('role', role);
    statusLine.hidden = false;
    statusLine.textContent = text;
  }
  function setSummary(text) { if (summary.textContent !== text) summary.textContent = text; }
  function summaryText() {
    if (!items.length) return 'Kept backups · none';
    if (bounded) return 'Kept backups · ' + LIMIT + '+';
    return 'Kept backups · ' + items.length + ' · ' + size(total());
  }

  async function read({announce = false} = {}) {
    const mine = ++ticket;
    if (announce) setStatus('Checking for kept backups…', 'status');
    let data;
    try {
      const response = await fetch('/api/backups');
      data = await response.json();
      if (!response.ok || !Array.isArray(data.items)) throw Error('unavailable');
    } catch (_) {
      if (mine !== ticket) return false;
      setSummary('Kept backups · unavailable');
      setStatus('Could not check for kept backups. Use Refresh to try again.', 'alert');
      return false;
    }
    if (mine !== ticket) return false;
    items = data.items;
    bounded = Boolean(data.bounded);
    setSummary(summaryText());
    if (announce) setStatus('', null);
    render();
    return true;
  }

  function closeConfirm(restore) {
    if (!confirm) return;
    const {box, opener} = confirm;
    confirm = null;
    box.remove();
    opener.setAttribute('aria-expanded', 'false');
    if (restore && document.contains(opener)) opener.focus();
  }
  function openConfirm(opener, place, lines, deleteLabel, deleteTip, keepLabel, onDelete) {
    closeConfirm(false);  // One confirm at a time.
    const box = el('div', undefined, 'kept-confirm');
    box.setAttribute('role', 'group');
    const [title, ...rest] = lines;
    const heading = el('p', title, 'kept-confirm-title');
    heading.id = 'keptConfirmTitle';
    box.setAttribute('aria-labelledby', heading.id);
    box.append(heading, ...rest.map(text => el('p', text)));
    const row = el('div', undefined, 'recovery-actions');
    const yes = button(deleteLabel, deleteTip, () => onDelete([yes, keep]), 'kept-danger');
    const keep = button(keepLabel, 'Go back. Nothing is deleted.', () => closeConfirm(true));
    row.append(yes, keep);
    box.append(row);
    box.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !busy(yes)) { event.preventDefault(); event.stopPropagation(); closeConfirm(true); }
    });
    place(box);
    opener.setAttribute('aria-expanded', 'true');
    confirm = {box, opener};
    keep.focus();  // The safe button.
  }

  function itemNode(item) {
    const node = el('div', undefined, 'kept-item');
    node.dataset.id = item.id;
    const when = age(item.created), stamp = new Date(item.created * 1000);
    const time = el('time', when);
    time.dateTime = stamp.toISOString();
    time.title = stamp.toLocaleString();
    const meta = el('p', undefined, 'kept-meta');
    meta.append(document.createTextNode(size(item.size) + ' · '), time, document.createTextNode(' · '),
                el('span', REASONS[item.reason] || 'Reason not recorded', 'kept-reason'));
    const text = el('div', undefined, 'kept-text');
    text.append(el('p', item.name, 'kept-name'), pathText(el('p', undefined, 'kept-folder'), item.folder), meta);
    const actions = el('div', undefined, 'recovery-actions kept-actions');
    const line = errorLine(node, 'kept-error');
    const show = revealButton(item.id, 'Show in folder', line, ROW_REVEAL, 'Show in folder: ' + item.name + ', ' + when);
    show.dataset.show = item.id;
    const remove = button('Delete', 'Delete this backup file. You are asked to confirm first.', () => {
      line.clear();
      const detail = item.reason === 'save_not_verified'
        ? 'The save to ' + item.name + ' was not verified, so this may be its only good copy. Deleting is permanent.'
        : item.reason === 'not_saved'
          ? 'The change to ' + item.name + ' was not saved and the file was not changed, so this is only an extra copy. Deleting is permanent.'
          : 'It is the only way to undo the change to ' + item.name + '. Deleting is permanent.';
      openConfirm(remove, box => actions.after(box), ['Delete this backup?', detail], 'Delete backup',
                  'Delete this backup file permanently.', 'Keep it', controls => deleteOne(item, [...controls, remove], line));
    });
    remove.setAttribute('aria-label', 'Delete: ' + item.name + ', ' + when);
    remove.setAttribute('aria-expanded', 'false');
    actions.append(show, remove);
    node.append(text, actions);
    return node;
  }

  function render() {
    closeConfirm(false);
    deleteAllButton.hidden = items.length < 2;
    note.removeAttribute('tabindex');
    note.hidden = !(bounded || !items.length);
    note.textContent = !items.length ? 'No kept backups' : bounded ? 'Showing the newest ' + LIMIT + '. Delete some to see the rest.' : '';
    if (!items.length) note.tabIndex = -1;
    list.replaceChildren(...items.map(itemNode));
  }

  async function deleteOne(item, controls, line) {
    if (working) return;
    working = true;
    const index = items.findIndex(other => other.id === item.id);
    const next = (items[index + 1] || items[index - 1] || {}).id;
    setBusy([...controls, ...toolbarButtons()], true);
    setStatus('Deleting…', 'status');
    let result;
    try { result = await post('backups/delete', {ids: [item.id]}); }
    catch (error) { result = {deleted: [], failed: [{id: item.id, code: error.code}]}; }
    setBusy([...controls, ...toolbarButtons()], false);
    working = false;
    if (result.deleted.includes(item.id)) {
      setStatus('Backup deleted.', 'status');
      await read();
      const target = (next && list.querySelector('[data-show="' + next + '"]')) || list.querySelector('[data-show]');
      (target || (items.length ? summary : note)).focus();
      return;
    }
    setStatus('', null);
    const opener = confirm?.opener;
    closeConfirm(false);
    line.show(DELETE_ERRORS[result.failed[0]?.code] || DELETE_FAILED);
    if (opener && document.contains(opener)) opener.focus();
  }

  function openDeleteAll() {
    const ids = items.map(item => item.id);  // Exactly the set this confirm counts (Amendment A7.5).
    const count = ids.length, bytes = total();
    const unverified = items.filter(item => item.reason === 'save_not_verified').length;
    const unchanged = items.filter(item => item.reason === 'not_saved').length;  // Extra copies, not counted as unverified.
    const lines = [bounded ? 'Delete the ' + count + ' listed backups (' + size(bytes) + ')?' : 'Delete all ' + count + ' kept backups (' + size(bytes) + ')?'];
    if (unchanged === count) lines.push('They are extra copies of files that were not changed. Deleting is permanent.');
    else {
      lines.push('They are the only way to undo those changes. Deleting is permanent.');
      if (unverified) lines.push(unverified === 1 ? '1 is from a save that was not verified.' : unverified + ' are from saves that were not verified.');
      if (unchanged) lines.push(unchanged === 1 ? '1 is a copy of a file that was not changed.' : unchanged + ' are copies of files that were not changed.');
    }
    openConfirm(deleteAllButton, box => toolbar.after(box), lines, 'Delete ' + count + ' backups',
                'Delete all listed backup files permanently.', 'Keep them', controls => deleteAll(ids, controls));
  }

  async function deleteAll(ids, controls) {
    if (working) return;
    working = true;
    const count = ids.length;
    setBusy([...controls, ...toolbarButtons()], true);
    setStatus('Deleting ' + count + ' backups…', 'status');
    let result;
    try { result = await post('backups/delete', {ids}); }
    catch (_) { result = {deleted: [], failed: ids.map(id => ({id, code: 'failed'})), freed: 0}; }
    setBusy([...controls, ...toolbarButtons()], false);
    working = false;
    const done = result.deleted.length, left = count - done;
    if (!left) setStatus('Deleted ' + count + ' backups. ' + size(result.freed) + ' freed.', 'status');
    else setStatus('Deleted ' + done + ' of ' + count + ' backups. ' + left + (left === 1 ? ' could not be deleted and is still listed.' : ' could not be deleted and are still listed.'), 'alert');
    await read();
    summary.focus();
  }

  function init() {
    panel = document.getElementById('keptBackups');
    if (!panel) return;
    summary = panel.querySelector('summary');
    const body = document.getElementById('keptBody');
    intro = el('p', 'Copies of comics from before a change. A copy is kept when the change did not verify or the copy could not be deleted.', 'kept-intro');
    toolbar = el('div', undefined, 'recovery-actions kept-toolbar');
    refreshButton = button('Refresh', 'Look for kept backups again. Nothing is changed.', () => {
      for (const line of list.querySelectorAll('.kept-error')) line.remove();
      read({announce: true});
    });
    deleteAllButton = button('Delete all', 'Delete every backup listed here. You are asked to confirm first.', openDeleteAll);
    deleteAllButton.setAttribute('aria-label', 'Delete all kept backups');
    deleteAllButton.setAttribute('aria-expanded', 'false');
    deleteAllButton.hidden = true;
    toolbar.append(refreshButton, deleteAllButton);
    statusLine = el('p', undefined, 'kept-status');
    statusLine.hidden = true;
    note = el('p', undefined, 'kept-note');
    note.hidden = true;
    list = el('div', undefined, 'kept-list');
    body.replaceChildren(intro, toolbar, statusLine, note, list);
    panel.addEventListener('toggle', () => { if (panel.open) read({announce: true}); });
    read();  // Page load: the summary.
  }

  init();
  // A save outcome that keeps a backup refreshes the summary in the background (Amendment A3).
  return {block, clean, size, age, refresh: () => (panel ? read() : Promise.resolve(false))};
})();
