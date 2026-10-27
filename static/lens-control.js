/* Authoritative Lens outcomes are independent of slow general progress. */
window.LensControl = (() => {
  const button = document.getElementById('browserResume');
  const status = document.getElementById('browserStatus');
  const help = document.getElementById('browserHelp');
  let last = null, submitting = false, focusAfter = false;
  const phases = new Set(['idle','required','queued','opening','open','closing','verified','failed','paused']);
  const set = (node, text) => { if (node.textContent !== text) node.textContent = text; };
  document.addEventListener('focusin', e => {
    if (![button, status, document.body].includes(e.target)) focusAfter = false;
  });
  function paint(text, label = '', disabled = false, unavailable = false) {
    status.hidden = false;
    set(status, text);
    if (!label && (document.activeElement === button || (focusAfter && document.activeElement === document.body))) {
      status.focus({preventScroll:true}); focusAfter = false;
    }
    button.hidden = !label; button.disabled = disabled; set(button, label);
    const tooltip = unavailable ? 'Google Lens status unavailable. Waiting for the local service.' :
      label === 'Closing Google Lens verification…' ? 'Waiting for the Google Lens verification window to close.' :
      label === 'Google Lens window open' ? 'Complete verification in the Google Lens window.' :
      disabled ? 'Google Lens verification has been requested. No further clicks are needed.' :
      'Open the dedicated Google Lens window for cover search verification.';
    button.title = tooltip; set(help, tooltip);
  }
  // Lens switched off (DesktopShell spec §12.2): the line, its button and its help text leave the screen.
  function off() {
    set(status, ''); status.hidden = true;
    button.hidden = true; button.title = ''; set(help, '');
  }
  function unavailable() {
    if (last && last.enabled === false) { off(); return; }  // A failed poll after an "off" answer stays hidden.
    paint('Google Lens status unavailable. Waiting for the local service.', button.hidden ? '' : button.textContent, true, true);
  }
  function render(state) {
    if (state && state.enabled === false) { last = state; off(); return; }  // First: paused or failed states do not apply.
    if (!state || state.engine !== 'google_lens' || !phases.has(state.phase)) { unavailable(); return; }
    if (last && Number(state.updated) < Number(last.updated)) return;
    last = state;
    if (state.paused || state.phase === 'paused') { paint('Paused; cover queue retained.'); return; }
    if (submitting || state.phase === 'queued') {
      paint('Google Lens verification queued. No further clicks needed.', 'Google Lens verification queued', true); return;
    }
    if (state.phase === 'failed') {
      const copy = {open:'The Google Lens verification window could not open. Try again.',
        load:'The Google Lens verification page could not load. Try again.',
        interrupted:'Google Lens verification was interrupted. Try again when ready.'};
      const actionable = state.human_verification && state.alive && state.window === 'closed' && !state.verification_pending;
      paint(copy[state.failure] || 'Google Lens verification did not finish. Try again when ready.',
        state.human_verification ? 'Retry Google Lens verification' : '', !actionable);
      if (!actionable) {
        const tooltip = state.window !== 'closed' ? 'Google Lens verification cannot restart until its window is confirmed closed.' :
          !state.alive ? 'Google Lens verification is unavailable. Waiting for its browser to become ready.' :
          'Google Lens verification cannot restart yet.';
        button.title = tooltip; set(help, tooltip);
      }
      return;
    }
    if (!state.alive) { unavailable(); return; }
    if (state.phase === 'opening') paint('Opening the Google Lens verification window.', 'Opening Google Lens verification…', true);
    else if (state.phase === 'open') paint('Complete Google Lens verification in the browser window.', 'Google Lens window open', true);
    else if (state.phase === 'closing') paint('Closing the Google Lens verification window.', 'Closing Google Lens verification…', true);
    else if (state.human_verification) paint('Google Lens needs your verification. Other processing continues.', 'Open Google Lens verification');
    else if (state.phase === 'verified' && state.window === 'minimized') paint('Google Lens verification complete. Keep its window open; it can stay minimized.');
    else if (state.phase === 'verified' && state.window === 'open') paint('Google Lens verification complete. You can minimize its window; keep it open for automatic cover searches.');
    else {
      const cover = state.cover || {};
      paint('Cover search: ' + (cover.state || 'waiting') + (cover.current ? ' · ' + cover.current : '') + ' · ' + (cover.detail || ''));
    }
  }
  function connect(request, refresh, invalidate) {
    button.onclick = async () => {
      if (submitting || button.disabled || !last?.human_verification || !last.alive) return;
      focusAfter = document.activeElement === button;
      submitting = true; invalidate(); render(last);
      try { await request('browser-resume', {}, 12000); submitting = false; await refresh(); }
      catch (_) { submitting = false; await refresh(); }
    };
  }
  return {render, unavailable, connect};
})();
