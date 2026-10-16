'use strict';
// Source24 legacy-path preflight. Synthetic trees only; optional read-only actual23 evidence.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {LIMIT,measureNsisPaths,assertNsisPathBound}=require('../../scripts/packaging/nsis-path-bound.cjs');
function fixture(action){
  const scratch=process.env.COMICS_META_TEST_SCRATCH;assert.ok(scratch&&path.isAbsolute(scratch));
  const base=fs.mkdtempSync(path.join(scratch,'nsis-'));
  try{
    const root=path.join(base,'job','source'),nsisRoot=path.join(base,'native','nsis'),nsisPlugins=path.join(base,'native','nsis-resources');
    const templates=path.join(root,'node_modules','app-builder-lib','templates','nsis');
    for(const [file,bytes] of [[path.join(templates,'installer.nsi'),'t'],[path.join(templates,'include','allowOnlyOneInstallerInstance.nsh'),'i'],
      [path.join(root,'desktop','assets','icon.ico'),'ico'],[path.join(nsisRoot,'Bin','makensis.exe'),'m'],[path.join(nsisRoot,'Include','MUI2.nsh'),'h'],
      [path.join(nsisPlugins,'plugins','x86-unicode','nsProcess.dll'),'p']]){fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,bytes);}
    const installer=path.join(root,'dist','Comic-Metadata-Setup-0.2.1.exe');
    const options={root,nsisRoot,nsisPlugins,tempRoot:path.join(base,'job'),installer,uninstaller:path.join(root,'dist','Comic-Metadata-Setup-0.2.1.__uninstaller.exe'),packageName:'comic-metadata',version:'0.2.1'};
    action({base,root,templates,options});
  }finally{fs.rmSync(base,{recursive:true});}
}
test('measures every materialized template, resource, native file, enumeration pattern and output role',()=>fixture(({templates,options})=>{
  const measured=measureNsisPaths(options);
  // 6 files + 9 directory patterns (2 template, 1 assets, 3 nsis, 3 resources) + 3 output roles + 2 temp roles.
  assert.equal(measured.count,20);
  const deepest=path.join(templates,'include','allowOnlyOneInstallerInstance.nsh');
  const uninstaller=options.uninstaller;
  assert.equal(measured.max,Math.max(deepest.length,uninstaller.length));
  assert.equal(assertNsisPathBound(options,measured.max).max,measured.max);
}));
test('refuses one character over the bound and names the path (positive control)',()=>fixture(({options})=>{
  const measured=measureNsisPaths(options);
  assert.throws(()=>assertNsisPathBound(options,measured.max-1),e=>e.message.includes(measured.longest)&&e.message.includes(String(measured.max)));
  assert.equal(LIMIT,254);
}));
test('reparse members, missing trees and split output roles fail closed',()=>fixture(({base,templates,options})=>{
  const target=path.join(base,'elsewhere');fs.mkdirSync(target);
  fs.symlinkSync(target,path.join(templates,'linked'),'junction');
  assert.throws(()=>measureNsisPaths(options),/no reparse member/);
  fs.rmSync(path.join(templates,'linked'));
  assert.throws(()=>measureNsisPaths({...options,nsisPlugins:path.join(base,'absent')}),/ENOENT/);
  assert.throws(()=>measureNsisPaths({...options,uninstaller:path.join(base,'other','x__uninstaller.exe')}),/share one directory/);
  assert.throws(()=>assertNsisPathBound(options,0),/positive integer limit/);
}));
// Read-only cross-check on the retained actual23 job root: the bound would have
// refused 23 before the builder loaded, at the same 285/264 lengths observed.
const actual23=process.env.COMICS_META_TEST_ACTUAL23_JOBROOT;
test('actual23 retained snapshot measures 285 and is refused at 254',{skip:!actual23&&'COMICS_META_TEST_ACTUAL23_JOBROOT not set'},()=>{
  const contract=JSON.parse(fs.readFileSync(path.join(path.dirname(actual23),'compiler-control','build-contract.json'),'utf8'));
  const rpc=fs.readdirSync(actual23).filter(name=>name.startsWith('nsis-io-rpc-'));assert.equal(rpc.length,1);
  const roles=JSON.parse(fs.readFileSync(path.join(actual23,rpc[0],'config.json'),'utf8'));
  assert.equal(path.resolve(contract.jobRoot),path.resolve(actual23));
  const options={root:contract.snapshotRoot,nsisRoot:contract.nsisRoot,nsisPlugins:contract.nsisPlugins,tempRoot:contract.jobRoot,installer:roles.installer,uninstaller:roles.uninstaller,packageName:'comic-metadata',version:contract.version};
  const measured=measureNsisPaths(options);
  assert.equal(measured.max,285);assert.match(measured.longest,/allowOnlyOneInstallerInstance\.nsh$/);
  assert.equal(path.join(contract.snapshotRoot,'node_modules','app-builder-lib','templates','nsis','include','StdUtils.nsh').length,264);
  assert.throws(()=>assertNsisPathBound(options),/285 characters exceeds 254/);
});
