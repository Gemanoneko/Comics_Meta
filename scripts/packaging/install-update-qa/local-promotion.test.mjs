// Negative controls over a real reviewed fixture; never publishes or launches an installer.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createLocalPromotion} from './create-local-promotion.mjs';
import {digest} from './common.mjs';

const configFile=process.argv[2],scratch=process.argv[3];
assert.ok(path.isAbsolute(configFile)&&path.isAbsolute(scratch)&&!fs.existsSync(scratch),'Absolute fresh test paths required');
const config=JSON.parse(fs.readFileSync(configFile));fs.mkdirSync(scratch);
function altered(ref,name,mutate){const original=JSON.parse(fs.readFileSync(ref.path));mutate(original);const file=path.join(scratch,name);fs.writeFileSync(file,JSON.stringify(original),{flag:'wx'});return {path:file,sha256:digest(fs.readFileSync(file))};}
function refuse(name,change,pattern){const c=structuredClone(config);c.outputRoot=path.join(scratch,'never-'+name);change(c);assert.throws(()=>createLocalPromotion(c),pattern);assert.equal(fs.existsSync(c.outputRoot),false);console.log('PASS '+name);}
refuse('version',c=>{c.version='0.0.0';},/version mismatch/);
refuse('source-membership',c=>{c.sourceManifest=altered(c.sourceManifest,'source.json',value=>value.files.pop());},/membership differs/);
refuse('owner',c=>{c.smokeOwned=altered(c.smokeOwned,'owner.json',value=>{value.native.complete=false;});},/smoke\/closure/);
refuse('installer-binding',c=>{c.packageBinding=altered(c.packageBinding,'binding.json',value=>{value.asarSha256='0'.repeat(64);});},/runtime binding/);
refuse('extraction-owner',c=>{const binding=JSON.parse(fs.readFileSync(c.packageBinding.path));binding.owner=altered(binding.owner,'extraction.json',value=>{value.result.native.zero=false;});const file=path.join(scratch,'binding-owner.json');fs.writeFileSync(file,JSON.stringify(binding));c.packageBinding={path:file,sha256:digest(fs.readFileSync(file))};},/extraction proof/);
refuse('smoke-identity',c=>{c.smokeEvidence=altered(c.smokeEvidence,'smoke.json',value=>{value.spec.sourceHead='0'.repeat(40);});},/smoke identity/);
refuse('bad-pinned-proof',c=>{c.smokeOwned.sha256='0'.repeat(64);},/Evidence byte drift/);
console.log('PASS 7 local-promotion rejection controls');
