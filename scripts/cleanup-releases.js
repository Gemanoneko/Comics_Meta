'use strict';
const {spawnSync}=require('node:child_process');
const path=require('node:path');
const args=process.argv.slice(2);
if(args.length!==1||!['--check','--apply'].includes(args[0]))throw new Error('Usage: cleanup-releases.js --check|--apply');
const REPO='Gemanoneko/Comics_Meta';
const executable=process.env.COMICS_META_GH_EXECUTABLE;
if(!executable||!path.isAbsolute(executable)||(args[0]==='--apply'&&process.env.COMICS_META_HELD_PUBLICATION!=='1'))throw new Error('Held fixed GitHub executable/publication supervisor required');
function gh(argv){const r=spawnSync(executable,argv,{encoding:'utf8',windowsHide:true,timeout:30000,maxBuffer:1048576});if(r.error||r.status!==0)throw new Error('GitHub command failed');return r.stdout;}
const releases=JSON.parse(gh(['api','repos/'+REPO+'/releases?per_page=100']));
if(releases.length===100)throw new Error('Pagination required; refuse partial release cleanup');
const managed=releases.filter(r=>!r.draft&&!r.prerelease&&/^v[0-9]+[.][0-9]+[.][0-9]+$/.test(r.tag_name)&&r.assets.some(a=>/^Comic-Metadata-Setup-[0-9]+[.][0-9]+[.][0-9]+[.]exe$/.test(a.name)));
managed.sort((a,b)=>Date.parse(b.published_at)-Date.parse(a.published_at));
const remove=managed.slice(4);
if(remove.some(r=>r.assets.some(a=>! /^Comic-Metadata-Setup-[0-9]+[.][0-9]+[.][0-9]+[.]exe(?:[.]blockmap)?$|^latest[.]yml$/.test(a.name))))throw new Error('Older release includes unmanaged assets; cleanup refused');
console.log(JSON.stringify({repository:REPO,keep:managed.slice(0,4).map(r=>r.tag_name),remove:remove.map(r=>r.tag_name),mode:args[0]}));
if(args[0]==='--apply')for(const r of remove)gh(['release','delete',r.tag_name,'--repo',REPO,'--yes']);
