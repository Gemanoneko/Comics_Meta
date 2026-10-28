'use strict';
const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('comicDesktop',Object.freeze({
  keys:()=>ipcRenderer.invoke('keys-status'),
  saveKeys:keys=>ipcRenderer.invoke('keys-save',keys),
  browse:()=>ipcRenderer.invoke('setup-browse'),
  browseGcd:()=>ipcRenderer.invoke('gcd-browse'),
  saveSetup:(folder,keys)=>ipcRenderer.invoke('setup-save',{folder,keys}),
  setup:()=>ipcRenderer.invoke('setup-status'),
  action:name=>ipcRenderer.invoke('shell-action',name),
  onState:callback=>{const listener=(_event,state)=>callback(state);ipcRenderer.on('shell-state',listener);ipcRenderer.invoke('shell-snapshot').then(callback);return()=>ipcRenderer.removeListener('shell-state',listener);},
  onRefresh:callback=>{const listener=()=>callback();ipcRenderer.on('shell-refresh',listener);return()=>ipcRenderer.removeListener('shell-refresh',listener);}
}));
