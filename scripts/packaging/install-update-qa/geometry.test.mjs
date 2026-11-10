import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {digest,rememberedGeometryMatches,settledRememberedGeometry,assertRememberedGeometryRestored,REQUEST_WINDOW_GEOMETRY_EXPRESSION,WINDOW_GEOMETRY_EXPRESSION} from './common.mjs';
function snapshot(width=900,savedWidth=width,mtimeMs=1000){
 const normal={x:40,y:40,width,height:600},parsed={...normal,width:savedWidth,maximized:false},raw=JSON.stringify(parsed);
 return {normal,outer:{...normal},content:{x:48,y:70,width:width-16,height:562},maximized:false,minimum:[640,480],display:{id:1,scaleFactor:2.5,workArea:{x:0,y:0,width:1280,height:800}},saved:{raw,parsed,sha256:digest(Buffer.from(raw)),mtimeMs}};
}
test('settling ignores stale immediate requested bounds and waits for actual native plus persisted agreement',async()=>{
 new vm.Script(REQUEST_WINDOW_GEOMETRY_EXPRESSION);new vm.Script(WINDOW_GEOMETRY_EXPRESSION);
 const immediateRequested=snapshot(900);let clock=1000,samples=0;
 const actual=await settledRememberedGeometry(async()=>{samples++;return clock<1200?snapshot(900,1280,900):clock<1400?snapshot(902,900,1200):snapshot(902,902,1400);},
   {deadlineEpochMs:4000,notBeforeEpochMs:1000,now:()=>clock,pause:async ms=>{clock+=ms;}});
 assert.equal(immediateRequested.normal.width,900);assert.equal(actual.normal.width,902);assert.equal(actual.saved.parsed.width,902);assert.ok(clock>=2000);assert.ok(samples>=6);
});
test('exact restoration rejects true two-DIP change and persisted byte mutation without any tolerance',()=>{
 assertRememberedGeometryRestored(snapshot(902),snapshot(902));
 assert.throws(()=>assertRememberedGeometryRestored(snapshot(900),snapshot(902)),/changed/);
 const altered=snapshot();altered.saved.raw=JSON.stringify(altered.saved.parsed,null,2);altered.saved.sha256=digest(Buffer.from(altered.saved.raw));
 assert.equal(rememberedGeometryMatches(altered),true);assert.throws(()=>assertRememberedGeometryRestored(snapshot(),altered),/changed/);
});
test('stale saved file or continually changing geometry cannot pass a bounded settlement',async()=>{
 let clock=1000;await assert.rejects(settledRememberedGeometry(async()=>snapshot(900,900,900),{deadlineEpochMs:2000,notBeforeEpochMs:1000,now:()=>clock,pause:async ms=>{clock+=ms;}}),/did not agree/);
 clock=1000;await assert.rejects(settledRememberedGeometry(async()=>snapshot(clock%400===0?900:902),{deadlineEpochMs:2200,now:()=>clock,pause:async ms=>{clock+=ms;}}),/did not agree/);
});
test('native/file mismatch, corrupt proof, invalid minimum and changed display are refused',()=>{
 assert.equal(rememberedGeometryMatches(snapshot(902,900)),false);
 const corrupt=snapshot();corrupt.saved.sha256='0'.repeat(64);assert.equal(rememberedGeometryMatches(corrupt),false);
 const noMinimum=snapshot();noMinimum.minimum=[];assert.equal(rememberedGeometryMatches(noMinimum),false);
 const differentDisplay=snapshot();differentDisplay.display.scaleFactor=2;assert.throws(()=>assertRememberedGeometryRestored(snapshot(),differentDisplay),/display changed/);
});
