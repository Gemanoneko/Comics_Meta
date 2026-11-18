'use strict';
// Quit always closes the app (Sergei 2026-11-18): the refused Quit and its guard are gone from the shell and the
// dashboard (Judy's Quit spec rev 2, R4 item 6; Futaba's check 22 repeats this on the built files).
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..','..');
const GONE=['could not be stopped','Task Manager','CLOSURE_UNCONFIRMED'];
function files(folder){
  return fs.readdirSync(folder,{withFileTypes:true}).flatMap(entry=>{
    const file=path.join(folder,entry.name);
    if(entry.isDirectory())return ['tests','assets'].includes(entry.name)?[]:files(file);
    return /\.(?:c?js|mjs|html|css)$/.test(entry.name)?[file]:[];
  });
}
const hits=text=>GONE.filter(phrase=>text.includes(phrase));
test('no refused-Quit string remains in desktop/ or static/',()=>{
  // Positive control: the search finds each phrase where it is present.
  assert.deepEqual(hits("status.textContent='The local service could not be stopped.';// Task Manager CLOSURE_UNCONFIRMED"),GONE);
  const scanned=[...files(path.join(root,'desktop')),...files(path.join(root,'static'))];
  for(const name of ['main.cjs','engine.cjs','startup.js','stopping.js','shell-ui.js'])assert.ok(scanned.some(file=>path.basename(file)===name),name+' scanned');
  for(const file of scanned)assert.deepEqual(hits(fs.readFileSync(file,'utf8')),[],path.relative(root,file));
});
