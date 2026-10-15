'use strict';
// Pure data decoder. No filesystem, network, process or native executable API.
const {inflateRawSync}=require('node:zlib');
const {createHash}=require('node:crypto');
const LIMITS=Object.freeze({input:32*1024**2,inflate:32*1024**2,
  aggregate:64*1024**2,blocks:8192,sections:96,output:32*1024**2});
// NSIS-Dev fileform.h: FH_SIG=0xDEADBEEF + "NullsoftInst";
// FH_FLAGS_MASK=15, FH_FLAGS_UNINSTALL=1. CRC bytes are preserved, not verified.
const SIGNATURE=Buffer.from('efbeadde4e756c6c736f6674496e7374','hex');
const sha256=b=>createHash('sha256').update(b).digest('hex');
function fail(message){throw new Error('NSIS data decode: '+message);}
function range(b,offset,size){
  if(!Number.isSafeInteger(offset)||!Number.isSafeInteger(size)||offset<0||size<0||offset>b.length-size)fail('bounded read');
}
function u16(b,o){range(b,o,2);return b.readUInt16LE(o);}
function u32(b,o){range(b,o,4);return b.readUInt32LE(o);}
function firstHeader(b,uninstall){
  range(b,0,28);
  const flags=u32(b,0);
  if((flags&~15)!==0 || Boolean(flags&1)!==uninstall)fail('first-header flags');
  if(!b.subarray(4,20).equals(SIGNATURE))fail('first-header signature');
  const headerSize=u32(b,20),total=u32(b,24);
  if(headerSize>LIMITS.inflate||total!==b.length)fail('first-header lengths');
  return {flags,headerSize,total};
}
function decodeUninstaller(input,checkBudget=()=>{}){
  if(!Buffer.isBuffer(input)||input.length<64||input.length>LIMITS.input)fail('input bound/type');
  if(typeof checkBudget!=='function')fail('budget callback');
  checkBudget();
  if(u16(input,0)!==0x5a4d)fail('MZ signature');
  const pe=u32(input,0x3c);
  if(pe<64)fail('PE header offset');
  range(input,pe,24);
  if(u32(input,pe)!==0x00004550)fail('PE signature');
  const machine=u16(input,pe+4),sectionCount=u16(input,pe+6),optionalSize=u16(input,pe+20);
  if(!sectionCount||sectionCount>LIMITS.sections)fail('section count');
  const optional=pe+24;
  range(input,optional,optionalSize);
  const magic=u16(input,optional);
  if(!((machine===0x14c&&magic===0x10b&&optionalSize>=96)||
       (machine===0x8664&&magic===0x20b&&optionalSize>=112)))fail('PE machine/optional header');
  const table=optional+optionalSize,tableEnd=table+sectionCount*40;
  range(input,table,sectionCount*40);
  const headersSize=u32(input,optional+60);
  if(headersSize<tableEnd||headersSize>input.length)fail('PE header size');
  const intervals=[],sections=[],allowed=new Set(['.text','.rdata','.data','.rsrc']);
  let highwater=0;
  for(let i=0;i<sectionCount;i++){
    checkBudget(); const p=table+i*40,nameBytes=input.subarray(p,p+8);
    const zero=nameBytes.indexOf(0),name=nameBytes.subarray(0,zero<0?8:zero).toString('ascii');
    const size=u32(input,p+16),offset=u32(input,p+20);
    // Match the pinned upstream highwater calculation even for an allowed
    // zero-size section. Its nonzero pointer still contributes to the stub end.
    if(allowed.has(name)){range(input,offset,size);highwater=Math.max(highwater,offset+size);}
    if(size){
      if(!offset||offset<headersSize||!allowed.has(name))fail('unsupported PE section/range');
      range(input,offset,size); intervals.push([offset,offset+size]);
    }
    sections.push({name,offset,size});
  }
  intervals.sort((a,b)=>a[0]-b[0]);
  for(let i=1;i<intervals.length;i++)if(intervals[i][0]<intervals[i-1][1])fail('overlapping PE sections');
  if(highwater<headersSize||highwater>input.length-28)fail('PE/NSIS highwater');
  const stub=input.subarray(0,highwater),outer=input.subarray(highwater);
  const outerHeader=firstHeader(outer,false);
  let cursor=28,aggregate=0,blocks=0,inner=null,innerReceipt=null;
  while(outer.length-cursor>4){
    checkBudget();
    if(++blocks>LIMITS.blocks)fail('block count');
    const word=u32(outer,cursor);cursor+=4;
    const compressed=Boolean(word&0x80000000),size=word&0x7fffffff;
    if(!size)fail('zero-length block');
    range(outer,cursor,size);
    let data=outer.subarray(cursor,cursor+size);cursor+=size;
    if(compressed){
      const remaining=Math.min(LIMITS.inflate,LIMITS.aggregate-aggregate);
      if(remaining<=0)fail('inflate aggregate');
      data=inflateRawSync(data,{maxOutputLength:remaining});
      checkBudget();
    }
    aggregate+=data.length;
    if(data.length>LIMITS.inflate||aggregate>LIMITS.aggregate)fail('decoded aggregate');
    if(data.length>=20&&data.subarray(4,20).equals(SIGNATURE)){
      if(inner!==null)fail('multiple inner blocks');
      const header=firstHeader(data,true);
      inner=Buffer.from(data); // Preserve EVERY inner byte, including opaque CRC.
      innerReceipt={...header,block:blocks,compressed,size:data.length,sha256:sha256(data)};
    }
  }
  const trailer=outer.subarray(cursor);
  if(trailer.length!==0&&trailer.length!==4)fail('outer trailer bound');
  if(inner===null)fail('inner uninstaller block absent');
  if(stub.length+inner.length>LIMITS.output)fail('output bound');
  checkBudget(); const output=Buffer.concat([stub,inner]);
  return {bytes:output,receipt:{schema:1,inputSize:input.length,inputSha256:sha256(input),
    stubSize:stub.length,stubSha256:sha256(stub),sections,outerHeader,blocks,
    decodedBytes:aggregate,inner:innerReceipt,outerOpaqueTrailerHex:trailer.toString('hex'),
    outputSize:output.length,outputSha256:sha256(output),crcVerified:false,
    scope:'Pure byte reconstruction; no execution or CRC-semantic verification.'}};
}
module.exports={decodeUninstaller,LIMITS};
