"""SOURCE ONLY: parent lease-callback RPC, no process/service or execution entry.

All native calls use the reviewed parent's library. Caller owns Job, clock,
existing held mutable directory anchors, final strong seals and failure records.
"""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import re
import time

MAX_REQUESTS=20
MAX_JSON=4096
MAX_JSON_TOTAL=65536
MAX_FILE=32*1024**2
MAX_RPC_BINARY=128*1024**2


def decode_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError('Duplicate RPC JSON key')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs)


class NativeIoLease:
    def __init__(self,lib,sealing,held,lifetime,config,started,deadline,owner_lease):
        self.lib=lib;self.sealing=sealing;self.held=held
        self.deadline=deadline;self.owner_lease=owner_lease
        if not callable(owner_lease) or not started<deadline<=started+600:
            raise ValueError('Original owner lease and startup-inclusive deadline required')
        expected={'schema','jobRoot','rpcRoot','outDir','installer','uninstaller','template',
                  'templateSha256','nonce','deadlineUnixMs','allowSignerReplacement'}
        if set(config)!=expected or config['schema']!=1: raise ValueError('Exact RPC configuration schema')
        if not re.fullmatch('[0-9a-f]{64}',config['nonce']): raise ValueError('RPC nonce')
        if not re.fullmatch('[0-9a-f]{64}',config['templateSha256']): raise ValueError('Template pin')
        if type(config['deadlineUnixMs']) is not int or type(config['allowSignerReplacement']) is not bool:
            raise ValueError('Fixed RPC clock/signing policy')
        self.config=dict(config)
        self.paths={k:Path(config[k]) for k in ('jobRoot','rpcRoot','outDir','installer','uninstaller','template')}
        for key,path in self.paths.items():
            if (not isinstance(config[key],str) or config[key]!=str(path) or not path.is_absolute() or
                    '..' in path.parts or str(path)!=str(path.absolute())):
                raise ValueError('Canonical lexical absolute Windows RPC paths')
        p=self.paths
        if (p['rpcRoot']!=p['jobRoot']/('nsis-io-rpc-'+config['nonce'][:12]) or
                p['outDir']!=p['jobRoot']/'source'/'dist' or
                p['installer'].parent!=p['outDir'] or not p['installer'].name.endswith('.exe') or
                p['uninstaller']!=p['outDir']/(p['installer'].name[:-3]+'__uninstaller.exe') or
                p['template']!=p['jobRoot']/'source'/'node_modules'/'app-builder-lib'/'templates'/'nsis'/'installer.nsi'):
            raise ValueError('RPC paths outside exact fixed build roles')
        self.next=1;self.json_bytes=0;self.binary_bytes=0;self.handles={}
        self.proofs={};self.events=[];self.fatal=None;self.busy=False
        self.state='new';self.paths_asserted=False;self.template_read=False;self.compiled_released=False
        self.sign_token=None;self.expected_files=set();self.finalized=False
        self._budget();self._outdir()
        tkey=self._key(p['template'])
        if tkey not in held.handles or tkey in held.directory_keys: raise ValueError('Template must already be immutable held input')
        held._validate(p['template'],held.handles[tkey],False,held.identities[tkey])
        held.mkdir(p['rpcRoot'],True)
        lifetime.callback(self.close)
        public={**config,'limits':{'requests':MAX_REQUESTS,'jsonEach':MAX_JSON,
            'jsonTotal':MAX_JSON_TOTAL,'fileBytes':MAX_FILE,'rpcBinaryBytes':MAX_RPC_BINARY}}
        raw=(json.dumps(public,sort_keys=True)+'\n').encode()
        if len(raw)>MAX_JSON: raise ValueError('Fixed RPC configuration JSON bound')
        self.json_bytes=len(raw)
        self.config_receipt=self._write(p['rpcRoot']/'config.json',raw,immutable=True)
        self.public=public

    def _key(self,path): return os.path.normcase(str(path))
    def _budget(self):
        if time.monotonic()>=self.deadline-5: raise TimeoutError('Original RPC/owned Job deadline')
    def _outdir(self):
        p=self.paths['outDir'];key=self._key(p)
        if key not in self.held.anchors or self.held.policies.get(key)!='mutable':
            raise RuntimeError('Output directory must retain its existing owned anchor')
        anchor,akey=self.held.anchors[key]
        self.held._validate(p,self.held.handles[key],True,self.held.identities[key])
        self.held._validate(anchor,self.held.handles[akey],False,self.held.identities[akey])
        # All exact lexical ancestors are owned by the existing supervisor guard.
        for parent in p.parents:
            k=self._key(parent)
            if k not in self.held.directory_keys: raise RuntimeError('Held output chain incomplete')
            self.held._validate(parent,self.held.handles[k],True,self.held.identities[k])

    def _bytes(self,path,handle,maximum):
        lib=self.lib;self._budget()
        identity=lib['handle_identity'](handle)
        self.held._validate(path,handle,False,identity)
        lib['require'](lib['seek_file'](handle,0,None,0),'Rewind RPC-held data')
        chunks=[];size=0;sha=hashlib.sha256()
        while True:
            self._budget();buffer=C.create_string_buffer(65536);count=C.c_uint32()
            lib['require'](lib['read_file'](handle,buffer,len(buffer),C.byref(count),None),'Read RPC-held data')
            if not count.value: break
            size+=count.value
            if size>maximum: raise ValueError('RPC data byte bound')
            data=buffer.raw[:count.value];sha.update(data);chunks.append(data)
        self.held._validate(path,handle,False,identity)
        return b''.join(chunks),{'path':str(path),'size':size,'sha256':sha.hexdigest(),'identity':identity}

    def _open_rpc(self,path,maximum):
        # Native share-READ acquisition rejects any still-open WRITE request or
        # payload producer, regardless of a client's closure assertion.
        self.held.hold(path)
        self.expected_files.add(path.name)
        return self._bytes(path,self.held.handles[self._key(path)],maximum)

    def _hold_leaf(self,role,maximum):
        self._outdir() if role!='template' else self._budget()
        if role in self.handles: raise RuntimeError('Leaf already leased')
        path=self.paths[role]
        if role!='template' and self._key(path) in self.held.handles:
            raise RuntimeError('External leaf hold would defeat controlled release')
        h=self.sealing['opened'](self.lib,path)
        self.handles[role]=h
        raw,proof=self._bytes(path,h,maximum);self.proofs[role]=proof
        return raw,proof

    def _release(self,role):
        self._outdir()
        if role not in self.handles: raise RuntimeError('Leaf release without owned lease')
        _,proof=self._bytes(self.paths[role],self.handles[role],MAX_FILE)
        if proof!=self.proofs[role]: raise RuntimeError('Leaf changed before authorized release')
        self.lib['require'](self.lib['close'](self.handles.pop(role)),'Release exact RPC leaf lease')
        self.events.append({'event':'release','role':role,**proof})
        return proof

    def _write(self,path,raw,immutable,role=None):
        self._budget();lib=self.lib
        if len(raw)>MAX_FILE: raise ValueError('RPC write bound')
        writer=lib['create_file'](str(path),0xC0000000,1,None,1,0x00200000,None)
        if writer==lib['INVALID']: raise OSError(C.get_last_error(),'Exclusive RPC write')
        weak=None
        try:
            identity=lib['handle_identity'](writer)
            for offset in range(0,len(raw),65536): self._budget();lib['handle_write'](writer,raw[offset:offset+65536])
            weak=self.sealing['opened'](lib,path,sharing=3)
            if lib['handle_identity'](weak)!=identity: raise RuntimeError('RPC writer/name identity differs')
        except BaseException:
            if weak is not None: lib['close'](weak);weak=None
            raise
        finally: lib['require'](lib['close'](writer),'Close RPC writer')
        try:
            if immutable:
                self.held.hold(path);h=self.held.handles[self._key(path)]
            else:
                if role in self.handles: raise RuntimeError('Existing mutable leaf lease')
                h=self.sealing['opened'](lib,path);self.handles[role]=h
            actual,proof=self._bytes(path,h,len(raw))
            if proof['identity']!=identity or actual!=raw: raise RuntimeError('RPC strong bytes/identity differ')
            if not immutable: self.proofs[role]=proof
            if path.parent==self.paths['rpcRoot']: self.expected_files.add(path.name)
            return proof
        finally:
            if weak is not None: lib['require'](lib['close'](weak),'Close transient RPC overlap')

    def _copy_evidence(self,name,raw,source):
        self.binary_bytes+=len(raw)
        if self.binary_bytes>MAX_RPC_BINARY: raise ValueError('RPC aggregate binary evidence bound')
        proof=self._write(self.paths['rpcRoot']/name,raw,True)
        self.events.append({'event':'retained-copy','source':source,'copy':proof})
        return proof

    def _dispatch(self,op,args,seq):
        p=self.paths
        if op=='read-template':
            if args!={'path':str(p['template']),'maximum':4*1024**2} or self.template_read:
                raise ValueError('Exact one template read only')
            raw,proof=self._hold_leaf('template',4*1024**2)
            if proof['sha256']!=self.config['templateSha256']: raise ValueError('Template source pin differs')
            self.template_read=True;return proof
        if op=='assert-paths':
            if self.paths_asserted or args!={k:str(p[k]) for k in ('installer','uninstaller','outDir','template')}:
                raise ValueError('Exact fixed path assertion only')
            self._outdir();self.paths_asserted=True;return {'verified':True}
        if op=='read-compiled':
            if args!={'path':str(p['installer']),'maximum':MAX_FILE} or not self.paths_asserted or not self.template_read or self.state!='new':
                raise ValueError('Compiled read state/path')
            raw,proof=self._hold_leaf('installer',MAX_FILE)
            self._copy_evidence('compiled-bootstrap.evidence.bin',raw,proof)
            self.state='compiled';return proof
        if op=='begin-reference':
            if args!={'path':str(p['installer'])} or self.state!='compiled': raise ValueError('Reference decode state/path')
            _,proof=self._bytes(p['installer'],self.handles['installer'],MAX_FILE)
            if proof!=self.proofs['installer']: raise RuntimeError('Reference input differs from bounded-decoder input')
            reference=p['rpcRoot']/'upstream-reference.evidence.bin'
            try: reference.lstat()
            except FileNotFoundError: pass
            else: raise RuntimeError('Reference output must be fresh absent owned name')
            self.state='reference-writing'
            self.events.append({'event':'reference-output-phase','input':proof,'output':str(reference),
                                'scope':'Pinned pure upstream reader writes fresh owned bytes; no strong output leaf hold claimed yet.'})
            return {'input':proof,'output':str(reference)}
        if op=='end-reference':
            reference=p['rpcRoot']/'upstream-reference.evidence.bin'
            if self.state!='reference-writing' or set(args)!={'path','output','payload','size','sha256'} or args['path']!=str(p['installer']) or args['output']!=str(reference):
                raise ValueError('Reference completion state/path/schema')
            payload=p['rpcRoot']/('%04d.payload.bin'%seq)
            if args['payload']!=str(payload) or type(args['size']) is not int or not 0<args['size']<=MAX_FILE or not re.fullmatch('[0-9a-f]{64}',args['sha256']):
                raise ValueError('Reference exact bounded comparison payload')
            expected,source=self._open_rpc(payload,MAX_FILE)
            actual,reference_proof=self._open_rpc(reference,MAX_FILE)
            self.binary_bytes+=len(expected)+len(actual)
            if self.binary_bytes>MAX_RPC_BINARY or source['size']!=args['size'] or source['sha256']!=args['sha256'] or actual!=expected:
                raise RuntimeError('Actual upstream pure decoder differs from bounded decoder, or aggregate bound')
            self.reference_payload=source;self.state='reference-verified'
            self.events.append({'event':'actual-pure-reference-equality','compiledInput':self.proofs['installer'],
                'reference':reference_proof,'decodedPayload':source,'exactBytesEqual':True})
            return {'equal':True,'reference':reference_proof,'decodedPayload':source}
        if op=='stage-decoded':
            if self.state!='reference-verified' or set(args)!={'path','payload','size','sha256'} or args['path']!=str(p['uninstaller']):
                raise ValueError('Decoded stage state/path')
            expected=Path(self.reference_payload['path'])
            if args['payload']!=str(expected) or type(args['size']) is not int or not 0<args['size']<=MAX_FILE or not re.fullmatch('[0-9a-f]{64}',args['sha256']):
                raise ValueError('Exact bounded stage payload descriptor')
            raw,source=self._open_rpc(expected,MAX_FILE)
            if source!=self.reference_payload or source['size']!=args['size'] or source['sha256']!=args['sha256']:
                raise ValueError('Stage payload bytes/hash or aggregate bound')
            proof=self._write(p['uninstaller'],raw,False,'uninstaller');self.state='staged'
            self.events.append({'event':'stage-decoded','payload':source,'output':proof});return proof
        if op=='begin-sign':
            if args!={'path':str(p['uninstaller'])} or self.state!='staged': raise ValueError('Begin sign state/path')
            before=self._release('uninstaller');self.state='signing'
            self.sign_token=hashlib.sha256((self.config['nonce']+':sign:'+str(seq)).encode()).hexdigest()
            self.sign_before=before
            return {'token':self.sign_token,'before':before,'transition':'authorized signer writer phase; no strong leaf hold claimed'}
        if op=='end-sign':
            if args!={'path':str(p['uninstaller']),'token':self.sign_token,'signCalls':1} or self.state!='signing':
                raise ValueError('End sign state/token/call count')
            raw,after=self._hold_leaf('uninstaller',MAX_FILE)
            changed=after['identity']!=self.sign_before['identity']
            if changed and not self.config['allowSignerReplacement']: raise RuntimeError('Signer replaced file contrary to exact contract')
            copy=self._copy_evidence('signed-uninstaller.evidence.bin',raw,after)
            self.events.append({'event':'sign-complete','before':self.sign_before,'after':after,
                                'identityChanged':changed,'retainedCopy':copy})
            self.state='signed';return after
        if op=='release-held':
            if args=={'path':str(p['installer'])} and self.state=='signed' and not self.compiled_released:
                proof=self._release('installer');self.compiled_released=True;return proof
            if args=={'path':str(p['uninstaller'])} and self.state=='final-reading':
                proof=self._release('uninstaller');self.state='final-released';return proof
            raise ValueError('Release not at declared compiler/cleanup seam')
        if op=='final-compiler':
            if args!={'path':str(p['installer'])} or self.state!='signed' or not self.compiled_released:
                raise ValueError('Final compiler state/path')
            self._outdir()
            _,proof=self._bytes(p['uninstaller'],self.handles['uninstaller'],MAX_FILE)
            if proof!=self.proofs['uninstaller']: raise RuntimeError('Signed compiler input drift')
            self.state='final-reading';return {'verified':True,'signedInput':proof}
        raise ValueError('Operation outside finite NSIS I/O protocol')

    def service(self):
        """Pass directly as owned_job lease; no thread/server/new deadline."""
        if self.fatal is not None: return False
        if not self.owner_lease(): self.fatal='Original owner lease closed';return False
        if self.busy: self.fatal='RPC lease reentry';return False
        self.busy=True
        try:
            self._budget()
            path=self.paths['rpcRoot']/('%04d.request.json'%self.next)
            if not path.exists(): return True
            if self.next>MAX_REQUESTS: raise ValueError('RPC request count')
            raw,proof=self._open_rpc(path,MAX_JSON)
            self.json_bytes+=len(raw)
            if self.json_bytes>MAX_JSON_TOTAL: raise ValueError('RPC aggregate JSON bound')
            request=decode_json(raw)
            if (set(request)!={'schema','nonce','sequence','deadlineUnixMs','operation','arguments'} or
                    type(request['schema']) is not int or request['schema']!=1 or request['nonce']!=self.config['nonce'] or
                    type(request['sequence']) is not int or request['sequence']!=self.next or
                    type(request['deadlineUnixMs']) is not int or request['deadlineUnixMs']!=self.config['deadlineUnixMs'] or
                    not isinstance(request['operation'],str) or not isinstance(request['arguments'],dict)):
                raise ValueError('RPC request exact schema/nonce/sequence/deadline')
            result=self._dispatch(request['operation'],request['arguments'],self.next)
            response={'schema':1,'nonce':self.config['nonce'],'sequence':self.next,
                      'deadlineUnixMs':self.config['deadlineUnixMs'],'ok':True,'result':result}
            encoded=(json.dumps(response,sort_keys=True)+'\n').encode()
            self.json_bytes+=len(encoded)
            if len(encoded)>MAX_JSON or self.json_bytes>MAX_JSON_TOTAL: raise ValueError('RPC response JSON bound')
            base=self.paths['rpcRoot']/('%04d.response.json'%self.next)
            receipt=self._write(base,encoded,True)
            # Client polls a separate zero-byte ready marker. Response writer is
            # already CLOSED and exact strong bytes held before marker creation.
            self._write(self.paths['rpcRoot']/('%04d.response.ready'%self.next),b'',True)
            self.events.append({'event':'rpc','operation':request['operation'],'sequence':self.next,
                                'request':proof,'response':receipt})
            self.next+=1;return True
        except BaseException as error:
            self.fatal=type(error).__name__+': '+str(error)[:2048]
            return False  # owning Job closes every admitted child; no retry/fallback
        finally: self.busy=False

    def receipt(self,require_complete=False):
        complete=(self.fatal is None and self.state=='final-released' and self.compiled_released and
                  self.template_read and self.paths_asserted)
        if require_complete and not complete: raise RuntimeError('NSIS I/O protocol incomplete: '+str(self.fatal or self.state))
        return {'schema':1,'state':self.state,'complete':complete,'fatal':self.fatal,
                'requests':self.next-1,'jsonBytes':self.json_bytes,'rpcBinaryBytes':self.binary_bytes,
                'events':self.events,'config':self.config_receipt,
                'rpcFinalized':self.finalized,
                'scope':'Parent native file leases only; final Job closure and compiled artifact validation belong to caller.'}

    def finalize_after_closure(self,native_result):
        """Caller invokes only AFTER actual owned_job return, before final seals.

        These fields must be its direct native API result, not reconstructed
        status. This component does not independently recreate a closed Job.
        """
        if self.finalized: raise RuntimeError('RPC finalization repeated')
        if (native_result.get('reason')!='completed' or native_result.get('root_exit')!=0 or
                native_result.get('active_after')!=0): raise RuntimeError('Actual successful native closure required')
        self.receipt(require_complete=True)
        root=self.paths['rpcRoot'];key=self._key(root)
        anchor=self.held.anchors[key][0]
        actual={p.name for p in root.iterdir()}
        if actual!=self.expected_files|{anchor.name}: raise RuntimeError('RPC exact membership differs; no temporary/unowned files may be excluded')
        # Every actual child is retained as strong normal file before retirement.
        inventory=[]
        for name in sorted(self.expected_files):
            path=root/name;self.held.hold(path)
            _,proof=self._bytes(path,self.held.handles[self._key(path)],MAX_FILE)
            inventory.append(proof)
        self.held.retire_anchors(root,recursive=False)
        self.held.seal_tree(root);self.finalized=True
        return {'schema':1,'root':str(root),'files':inventory,'directories':[],
                'state':'Exact anchor-free RPC evidence; caller final strong-seal/ACK still required'}

    def close(self):
        for role,h in list(self.handles.items()):
            self.lib['close'](h);del self.handles[role]
