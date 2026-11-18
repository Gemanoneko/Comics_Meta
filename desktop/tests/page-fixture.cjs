'use strict';
// Runs a real shell page script (stopping.js, startup.js) against a minimal DOM built from its real HTML: every element
// with an id, its text, its attributes and, for buttons, the action row it sits in. A stand-in desktop bridge pushes
// shell states; timers and Date.now() follow a controlled clock. Layout is not modelled (Futaba measures rects).
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const desktop=path.join(__dirname,'..');
class Element{
  constructor(doc,tag,attributes,text){this.doc=doc;this.tagName=tag.toUpperCase();this.attributes=new Map(Object.entries(attributes));this.id=attributes.id;
    this.textContent=text;this.hidden='hidden' in attributes;this.disabled='disabled' in attributes;this.title=attributes.title||'';this.style={visibility:''};this.parent=null;this.onclick=null;
    this.tabIndex='tabindex' in attributes?Number(attributes.tabindex):(tag==='button'?0:-1);}
  setAttribute(name,value){this.attributes.set(name,String(value));}getAttribute(name){return this.attributes.has(name)?this.attributes.get(name):null;}
  removeAttribute(name){this.attributes.delete(name);}hasAttribute(name){return this.attributes.has(name);}
  focus(){this.doc.activeElement=this;}contains(other){for(let node=other;node;node=node.parent)if(node===this)return true;return false;}
  click(){if(!this.disabled&&this.onclick)return this.onclick();}
}
function page(name,{bridgeResult}={}){
  const html=fs.readFileSync(path.join(desktop,name+'.html'),'utf8');
  const listeners={},actions=[];let push=null,clock=Date.parse('2026-11-18T14:32:07Z'),nextTimer=1;const timers=new Map();
  const doc={activeElement:null,elements:new Map(),order:[],getElementById:id=>doc.elements.get(id)||null,addEventListener(type,fn){(listeners[type]??=[]).push(fn);},hasFocus:()=>true};
  for(const match of html.matchAll(/<(\w+)\s([^>]*\bid="[^"]+"[^>]*)>([^<]*)/g)){
    const attributes={};for(const [,key,value] of match[2].matchAll(/([\w-]+)(?:="([^"]*)")?/g))attributes[key]=value??'';
    const element=new Element(doc,match[1],attributes,match[3]);doc.elements.set(element.id,element);doc.order.push(element);
  }
  const row=doc.elements.get('actions');for(const element of doc.order)if(element.tagName==='BUTTON'&&row)element.parent=row;
  class PageDate extends Date{constructor(...args){super(...(args.length?args:[clock]));}static now(){return clock;}}
  const script=fs.readFileSync(path.join(desktop,name+'.js'),'utf8');
  vm.runInNewContext(script,{document:doc,Date:PageDate,Error,
    setTimeout(fn,ms){const id=nextTimer++;timers.set(id,{fn,at:clock+Math.max(0,ms||0)});return id;},clearTimeout:id=>timers.delete(id),
    window:{comicDesktop:{action(name){actions.push(name);return Promise.resolve(bridgeResult?.(name));},onState(callback){push=callback;return ()=>{};}}}});
  return {doc,actions,el:id=>doc.elements.get(id),buttons:()=>doc.order.filter(element=>element.tagName==='BUTTON'),
    push:state=>push(structuredClone(state)),key:key=>{for(const fn of listeners.keydown||[])fn({key});},
    get now(){return clock;},tick(ms){const until=clock+ms;for(;;){const due=[...timers].filter(([,t])=>t.at<=until).sort((a,b)=>a[1].at-b[1].at)[0];if(!due)break;timers.delete(due[0]);clock=Math.max(clock,due[1].at);due[1].fn();}clock=until;}};
}
module.exports={page};
