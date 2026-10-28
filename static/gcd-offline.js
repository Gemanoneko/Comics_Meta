/* GCDOffline_UXSpec_2026-10-28: isolated panel state, no automatic download or source deletion. */
window.GcdOffline=(()=>{
  'use strict';
  const panel=document.getElementById('gcdPanel');if(!panel)return {};
  const details=panel.querySelector('details'),summary=panel.querySelector('[data-summary]'),effective=panel.querySelector('[data-effective]'),operation=panel.querySelector('[data-operation]'),live=panel.querySelector('[data-live]');
  const stages=['Checking file','Unpacking','Reading series and issues','Reading credits and synopses','Checking index','Switching index'];
  const tips={choose:'Choose a GCD SQLite ZIP or database file to check before building an index.',check:'Check the selected GCD file and available disk space without building an index.',cancel:'Close this file preview without building an index.'};
  const errors={zip_missing:'The selected file cannot be read. Choose it again or select another GCD file.',not_a_zip:'This file is not a ZIP archive. Choose a GCD SQLite .zip or extracted .db.',not_gcd_dump:'This file does not contain one GCD SQLite database. Choose the SQLite download from GCD.',schema_unsupported:'This GCD database format is not supported. Check for an app update, then try again.',interrupted:'The GCD update was interrupted. Choose the file again to rebuild the index.',build_failed:'The GCD index could not be built. Choose the file again to retry.',cancelled:'GCD update cancelled.'};
  let snapshot=null,first=true,lastKey='',lastEffective='',selection=null,inspecting=false,epoch=0,submitting=false,cancelling=false,fallback=false,localError='',unavailable=false,lastChecked=null,polling=false,announced='',pendingFocus=false;
  const dismissed=new Set();
  const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
  const set=(node,text)=>{if(node.textContent!==text)node.textContent=text;};
  const date=value=>{if(!value)return 'Unknown';const d=new Date(value+'T12:00:00');return Number.isNaN(+d)?'Unknown':d.toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'});};
  const bytes=value=>Number.isFinite(value)?(value/1e9).toLocaleString(undefined,{maximumFractionDigits:2})+' GB':'Unknown';
  const pct=value=>Number.isFinite(value)?Math.max(0,Math.min(100,Math.round(value))):null;
  function button(label,title,run,secondary=false){const b=el('button',label);b.type='button';b.title=title;if(secondary)b.className='secondary';b.onclick=()=>{if(b.getAttribute('aria-disabled')!=='true')run(b);};return b;}
  function link(label,url,title){const a=el('a',label);a.href=url;a.target='_blank';a.rel='noopener noreferrer';a.title=title;return a;}
  function announce(text){if(text!==announced){announced=text;set(live,text);}}
  function facts(values){const dl=el('dl');dl.className='gcd-facts';for(const [label,value] of values){const box=el('div');box.append(el('dt',label),el('dd',value));dl.append(box);}return dl;}
  function actions(...buttons){const row=el('div');row.className='gcd-actions';row.append(...buttons);return row;}
  async function api(route='',body){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);try{const r=await fetch('/api/gcd-offline'+route,{signal:controller.signal,...(body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})});const value=await r.json();if(!r.ok)throw Object.assign(Error(value.code||'request_failed'),{data:value});return value;}finally{clearTimeout(timer);}}
  function sourceText(value=snapshot){if(!value||unavailable)return 'GCD offline: Status unavailable';const current=value.current,attempt=value.attempt,building=attempt?.state==='building',number=pct(attempt?.overall_percent);let text=current?'GCD offline: Ready (dump '+date(current.dump_date)+')':'GCD offline: No index';if(building)text=current?text+'; '+(cancelling?'cancelling':'updating')+(number===null?'':' '+number+'%'):'GCD offline: '+(cancelling?'Cancelling':'Building')+(number===null?'':' '+number+'%')+'; no index yet';else if(attempt?.state==='failed')text+='; update failed';return text;}
  function message(text,error=false){const p=el('p',text);if(error){p.className='gcd-warning';p.setAttribute('role','alert');}return p;}
  function errorText(code,data={}){return code==='disk_space'?data.drive+' has '+bytes(data.free)+' free; '+bytes(data.needed)+' is needed. Free space on that drive, then check the file again.':errors[code]||'Could not check this file. Try again.';}
  function cancelPreview(){epoch++;selection=null;inspecting=false;localError='';fallback=false;lastKey='';render();operation.querySelector('button')?.focus({preventScroll:true});}
  async function inspect(path){const request=++epoch;selection={path,file_name:path.split(/[\\/]/).pop()};inspecting=true;localError='';details.open=true;lastKey='';render();try{const value=await api('/inspect',{zip:path});if(request!==epoch)return;selection=value;}catch(e){if(request!==epoch)return;selection={...selection,...e.data,error:e.data?.code||'request_failed'};}finally{if(request===epoch){inspecting=false;lastKey='';render();operation.querySelector('h3')?.focus({preventScroll:true});}}}
  async function choose(){if(submitting)return;try{if(!window.comicDesktop?.browseGcd)throw Error('unavailable');const path=await window.comicDesktop.browseGcd();if(path)await inspect(path);}catch(_){fallback=true;localError='Could not open the file picker. Enter the file path below.';details.open=true;lastKey='';render();operation.querySelector('input')?.focus({preventScroll:true});}}
  async function build(b){if(submitting||!selection||selection.error)return;submitting=true;b.setAttribute('aria-disabled','true');const selected=selection;try{snapshot=await api('/build',{zip:selected.path,force:['same_dump','older_dump'].includes(selected.relation)});selection=null;cancelling=false;pendingFocus=true;}catch(e){if(['same_dump','older_dump'].includes(e.data?.code)){submitting=false;await inspect(selected.path);return;}if(e.data?.code==='busy'){selection=null;localError='A GCD update is running. Showing its progress.';}else localError=errorText(e.data?.code,e.data);await refresh();}finally{submitting=false;lastKey='';render();if(pendingFocus){operation.querySelector('h3')?.focus({preventScroll:true});pendingFocus=false;}}}
  async function cancelBuild(b){if(cancelling)return;cancelling=true;b.setAttribute('aria-disabled','true');render();try{snapshot=await api('/cancel',{});}catch(_){cancelling=false;localError='Could not cancel the update. Try again.';}render();}
  function render(){
    const current=snapshot?.current,attempt=snapshot?.attempt,building=attempt?.state==='building';
    if(!building)cancelling=false;
    if(first&&snapshot){details.open=!current||building||attempt?.state==='failed';panel.querySelector('.gcd-help').open=!current||current.age_days>=14;first=false;}
    panel.querySelector('[data-download]').hidden=building||Boolean(current&&current.age_days>=14);
    let label=unavailable?'Status unavailable':!snapshot?'Checking…':inspecting?'Checking file…':selection?'File ready to build':building?(cancelling?'Cancelling…':(current?'Updating':'Building')+(pct(attempt.overall_percent)===null?'':' · '+pct(attempt.overall_percent)+'%')):current?'Ready · dump '+date(current.dump_date):'No index';
    if(!unavailable&&!selection&&!building&&attempt?.state==='failed'&&!dismissed.has(attempt.id))label=current?'Ready · update failed':'No index · update failed';
    set(summary,label);
    const effectiveKey=JSON.stringify([current,unavailable,Boolean(selection)]);
    if(effectiveKey!==lastEffective){lastEffective=effectiveKey;effective.replaceChildren();if(current){if(selection||unavailable)effective.append(el('h3',unavailable?'Last known index':'Current index'));const age=Number.isFinite(current.age_days)?current.age_days+' '+(current.age_days===1?'day':'days')+' old':'Unknown';effective.append(facts([['Dump',date(current.dump_date)+' · '+age],['Built',current.built?new Date(current.built*1000).toLocaleString():'Unknown'],['Last file',current.file_name||'Unknown']]));if(current.age_days>=14){const reminder=message('This dump is '+current.age_days+' days old. Choose a newer dump when available.');reminder.className='gcd-warning';reminder.append(' ',link('Download SQLite dump','https://www.comics.org/download/','Open GCD downloads in your browser.'));effective.append(reminder);}}else effective.append(message(snapshot?'No GCD index yet. Choose a GCD SQLite .zip or extracted .db.':'Checking GCD index…'));}
    const mode=unavailable?'unavailable':inspecting?'inspect':selection?'preview':building?'build':!snapshot?'loading':'idle';
    const key=JSON.stringify([mode,selection,attempt?.id,mode==='idle'?attempt?.state:null,fallback,localError,dismissed.has(attempt?.id)]);
    if(key!==lastKey){
      const heldFocus=operation.contains(document.activeElement);lastKey=key;operation.replaceChildren();
      if(localError)operation.append(message(localError,true));
      if(mode==='unavailable'){operation.append(message('Could not check GCD status. Try again.',true));if(lastChecked)operation.append(message('Last checked '+lastChecked.toLocaleString()));operation.append(actions(button('Try again','Check the current GCD index and update status again.',refresh)));}
      else if(mode==='inspect'){operation.append(el('h3','Checking '+selection.file_name+'…'),actions(button('Cancel',tips.cancel,cancelPreview,true)));}
      else if(mode==='preview'){
        const relation=selection.relation,heading=relation==='same_dump'?'Rebuild GCD index?':relation==='older_dump'?'Use older GCD dump?':'Build GCD index?';
        const title=el('h3',heading);title.tabIndex=-1;operation.append(title);
        if(current)operation.append(el('h4','Selected file'));
        operation.append(facts([['File',selection.path],['Dump',date(selection.dump_date)],['File size',bytes(selection.size)],['Disk space',bytes(selection.needed)+' needed · '+bytes(selection.free)+' free on '+(selection.drive||'Unknown')]]));
        if(relation==='same_dump')operation.append(message('This dump is already in use.'));
        if(relation==='older_dump')operation.append(message('This replaces the index dated '+date(current?.dump_date)+' with '+date(selection.dump_date)+'.'));
        operation.append(message('Usually 2–3 minutes. The selected file is kept.'));
        if(selection.error)operation.append(message(errorText(selection.error,selection),true));
        const row=actions();
        if(!selection.error){const label=relation==='same_dump'?'Rebuild index':relation==='older_dump'?'Use older dump':'Build index',tip=relation==='same_dump'?'Build the index again from the dump already in use.':relation==='older_dump'?'Replace the current index with an index built from this older dump.':current?'Build a GCD index from this file; matching keeps using the current index until the new one is ready.':'Build a GCD index from this file for offline matching.';row.append(button(label,tip,build));}
        else if(selection.error==='disk_space'||selection.error==='request_failed')row.append(button('Check file again',tips.check,()=>inspect(selection.path)));
        row.append(button('Choose another file',tips.choose,choose,true),button('Cancel',tips.cancel,cancelPreview,true));operation.append(row);
      }else if(mode==='build'){
        const h=el('h3');h.tabIndex=-1;h.dataset.stage='';const p=el('p');p.dataset.stagePercent='';const bar=el('progress');bar.max=100;bar.setAttribute('aria-label','Overall progress');const timing=el('p');timing.className='gcd-time';timing.dataset.timing='';const explanation=message(current?'Matching uses dump '+date(current.dump_date)+'.':'GCD matching starts when the index is ready.');
        const cancel=button('Cancel update','Stop this index build and keep the current index, if one exists.',cancelBuild,true);cancel.dataset.cancel='';const waiting=message('');waiting.dataset.waiting='';operation.append(h,p,bar,timing,explanation,waiting,actions(cancel));
      }else if(mode==='idle'){
        if(attempt&&!dismissed.has(attempt.id)){
          if(attempt.state==='failed')operation.append(message(errorText(attempt.code),true),message(current?'Matching uses dump '+date(current.dump_date)+'.':'GCD matching is unavailable until an index is built.'));
          else if(attempt.state==='cancelled')operation.append(message('GCD update cancelled.'));
          else if(attempt.state==='ready')operation.append(message('GCD index ready.'));
        }
        const row=actions(button('Choose GCD file',tips.choose,choose));
        if(attempt&&['failed','cancelled'].includes(attempt.state)&&!dismissed.has(attempt.id))row.append(button('Dismiss','Hide this update notice.',()=>{dismissed.add(attempt.id);lastKey='';render();},true));operation.append(row);
      }
      if(fallback&&!building){const label=el('label','GCD file path'),input=el('input');input.type='text';input.title='Full path to a GCD SQLite ZIP or database file on this computer.';input.value=selection?.path||'';label.append(input);operation.append(label,message('Full path to a GCD .zip or .db on this computer.'),actions(button('Check file',tips.check,()=>inspect(input.value))));input.addEventListener('keydown',e=>{if(e.key==='Enter'&&input.value.trim())inspect(input.value);});}
      if(heldFocus&&!inspecting){const target=operation.querySelector('h3')||summary;target.tabIndex=-1;target.focus({preventScroll:true});}
    }
    if(mode==='build'){
      const stage=attempt.stage||1,percent=pct(attempt.stage_percent),overall=pct(attempt.overall_percent),elapsed=Math.max(0,attempt.elapsed_seconds||0);
      set(operation.querySelector('[data-stage]'),stage+' of 6 · '+stages[stage-1]);set(operation.querySelector('[data-stage-percent]'),percent===null?'Stage progress unavailable':'Stage '+percent+'%');
      const progress=operation.querySelector('progress');if(overall===null)progress.removeAttribute('value');else progress.value=overall;
      set(operation.querySelector('[data-timing]'),(overall===null?'Overall progress unavailable':'Overall '+overall+'%')+' · Elapsed '+Math.floor(elapsed/60)+':'+String(elapsed%60).padStart(2,'0'));
      const cancel=operation.querySelector('[data-cancel]'),finishing=stage===6;cancel.setAttribute('aria-disabled',String(cancelling||finishing));set(cancel,finishing?'Finishing update…':cancelling?'Cancelling…':'Cancel update');cancel.title=finishing?'The checked index is switching into use; wait for it to finish.':cancelling?'Waiting for the index build to stop.':'Stop this index build and keep the current index, if one exists.';set(operation.querySelector('[data-waiting]'),cancelling?'Waiting for the update to stop.':'');announce(stages[stage-1]);
    }else if(snapshot)announce(label);
  }
  async function refresh(){if(polling)return;polling=true;try{snapshot=await api();unavailable=false;lastChecked=new Date();}catch(_){unavailable=true;}finally{polling=false;render();}}
  render();refresh();const timer=setInterval(refresh,2000);window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});
  return {sourceText,refresh};
})();
