'use strict';
const el=id=>document.getElementById(id);let initialized=false,ending=false;
el('cancel').onclick=()=>window.comicDesktop.action('cancelStop');el('force').onclick=()=>window.comicDesktop.action('forceQuit');
// Escape cancels while Cancel quit can, never once the ending has begun (Judy's Quit spec rev 2, R1): a hidden button
// is not a disabled one, so the state is tested.
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!ending&&!el('cancel').disabled)window.comicDesktop.action('cancelStop');});
// Ending (R1): the forced stop has begun, so Cancel quit cannot work and Quit now has nothing left to skip. The action
// row is hidden, not emptied; a focused button that disappears hands focus to the status line. The number is the
// engine's closure wait, sent by the shell; the second sentence comes at 10 s and is announced once.
// Every stage that waits states the longest time left from the moment it appears (Judy's Quit spec rev 3, C2). The
// number is always the shell's; 1 reads "1 second" (only a QA policy of 1 can give it).
const upTo=seconds=>'This can take up to '+seconds+' second'+(seconds===1?'':'s')+'.';
function showEnding(s){
  const hadFocus=el('actions').contains(document.activeElement);ending=true;initialized=true;
  el('actions').hidden=true;el('detail').setAttribute('role','status');
  const text='Stopping the local service…',detail=upTo(s.waitSeconds)+(s.late?' An interrupted write keeps its recovery backup.':'');
  if(el('status').textContent!==text)el('status').textContent=text;
  if(el('detail').textContent!==detail)el('detail').textContent=detail;
  if(hadFocus)el('status').focus();
}
window.comicDesktop.onState(state=>{const s=state.stopping;if(!s)return;const install=s.mode==='install',gpu=s.stage==='gpu',closing=s.stage==='closing';
el('title').textContent=install?'Installing v'+state.update.version:'Quitting Comic Metadata';
if(s.stage==='ending')return showEnding(s);
if(ending)return;  // Nothing follows the ending.
const control=s.control||{};  // Shown at 1.5 s before the first stage: the pausing state.
let text='Pausing — finishing the current operation. Progress is saved.';
if(gpu)text=s.gpuElapsed>=30000?'Still releasing Gemma from GPU.':'Paused. Releasing Gemma from GPU…';
if(!gpu&&s.elapsed>=60000)text='Still pausing. A comic write or search is taking longer than usual.';
if(closing)text=(control.error?'GPU release not confirmed.':'Gemma released from GPU.')+(install?' The app restarts to install.':' Closing…');
if(el('status').textContent!==text)el('status').textContent=text;
const waiting=(control.waiting_for||[]).map(name=>name==='metadata'?'comic processing':'browser search');
let detail=s.elapsed>=5000&&waiting.length?'Waiting for: '+waiting.join(' · '):'';
if(!install&&s.elapsed>=60000&&!gpu)detail+=' Quit now exits without waiting. An interrupted write keeps its recovery backup.';
if(!install&&gpu&&s.gpuElapsed>=30000)detail+=' Quit now exits without waiting. Gemma may stay on GPU.';
// Quit's Closing stage (Judy's Quit spec rev 3, C3 rows 1-3): the detail is only the time left, shown once the shell
// says Closing has lasted 5 s (late); "Waiting for" and the Quit now line are not shown, since Quit now is disabled.
// The 2 is the two waits of graceful-stop.cjs: Closing's own stop (at most one closure wait), then the ending's forced
// stop (one closure wait). The detail becomes a live region before its text is set, so the sentence is announced once.
const quitClosing=closing&&!install;
if(quitClosing){el('detail').setAttribute('role','status');detail=s.late&&Number.isFinite(s.waitSeconds)?upTo(2*s.waitSeconds):'';}
if(el('detail').textContent!==detail)el('detail').textContent=detail;
el('cancel').textContent=install?'Cancel install':'Cancel quit';el('cancel').title=install?'Stop the install. Processing resumes unless you had paused it.':quitClosing?'Cannot cancel: the app is already closing.':'Stop quitting. Processing resumes unless you had paused it.';
el('force').hidden=install;el('force').title=quitClosing?'The app is already closing and exits by itself.':gpu?'Exit without waiting. Gemma may stay on GPU.':'Exit without waiting. An interrupted write keeps its recovery backup.';
el('cancel').disabled=closing;el('force').disabled=closing;if(!initialized){initialized=true;el('cancel').focus();}
});
