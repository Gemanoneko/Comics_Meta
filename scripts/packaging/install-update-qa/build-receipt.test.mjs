// Owned integration controls over the accepted real build; no build/installer launch.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {strictBuildReceipt} from './build-receipt.mjs';
import {digest,requireThat,writeJson} from './common.mjs';

requireThat(process.argv.length===4,'Usage: node build-receipt.test.mjs <input.json> <sha256>');
const raw=fs.readFileSync(process.argv[2]);requireThat(digest(raw)===process.argv[3],'Control input drift');
const input=JSON.parse(raw),options=input.options,scratch=path.resolve(input.scratch);
requireThat(path.isAbsolute(input.scratch)&&path.isAbsolute(process.env.COMICS_META_TEST_SCRATCH||'')&&
 scratch===path.resolve(process.env.COMICS_META_TEST_SCRATCH)&&!fs.existsSync(scratch),'Fresh exact owned control scratch required');
fs.mkdirSync(scratch);
const result=strictBuildReceipt(options);
assert.equal(result.receipt.profile,'production');
assert.deepEqual(result.receipt.nativeResult,{root_exit:0,active_after:0,reason:'completed'});
assert.equal(result.receipt.sourceHead,options.sourceHead);
assert.equal(result.receipt.sourceIdentity,options.sourceIdentity);
assert.equal(result.artifacts.length,3);
console.log('PASS actual accepted build/source/production/artifact translation');

assert.throws(()=>strictBuildReceipt({...options,version:'0.6.2'}),/Wrong accepted version\/source/);
console.log('PASS wrong requested version rejected');

const incomplete=JSON.parse(fs.readFileSync(options.owned.path));incomplete.native.complete=false;
const incompletePath=path.join(scratch,'incomplete-owner.json');writeJson(incompletePath,incomplete);
const incompleteRef={path:incompletePath,sha256:digest(fs.readFileSync(incompletePath))};
assert.throws(()=>strictBuildReceipt({...options,owned:incompleteRef}),/Complete successful native Job closure required/);
console.log('PASS incomplete actual-owner derivative rejected despite zero/exit0 flags');

const bad=path.join(scratch,'tampered-artifacts');fs.mkdirSync(bad);
for(const artifact of result.artifacts) {
 const target=path.join(bad,artifact.name);
 if(artifact.name.endsWith('.exe')){
  const fd=fs.openSync(target,'wx');
  try{fs.ftruncateSync(fd,artifact.size);fs.writeSync(fd,'tampered installer',0,'utf8');}finally{fs.closeSync(fd);}
  assert.equal(fs.statSync(target).size,artifact.size); // Hash must catch same-size tampering.
 }
 else fs.copyFileSync(path.join(options.artifactRoot,artifact.name),target,fs.constants.COPYFILE_EXCL);
}
assert.throws(()=>strictBuildReceipt({...options,artifactRoot:bad}),/Artifact differs from actual build/);
console.log('PASS tampered installer rejected with unchanged feed/blockmap');

// Emit only after every control passes; unchanged publisher consumes this schema.
writeJson(input.receipt,result.receipt);writeJson(input.artifacts,result.artifacts);
for(const artifact of result.artifacts)fs.unlinkSync(path.join(bad,artifact.name));
fs.rmdirSync(bad);fs.unlinkSync(incompletePath);fs.rmdirSync(scratch);
console.log(JSON.stringify({controls:4,pass:4,fail:0,receipt:input.receipt,receiptSha256:digest(fs.readFileSync(input.receipt)),
 artifacts:input.artifacts,artifactsSha256:digest(fs.readFileSync(input.artifacts)),sourceHead:options.sourceHead,sourceIdentity:options.sourceIdentity}));
