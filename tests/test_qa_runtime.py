"""QA exclusion tests: synthetic audit events, plus one child Python that runs the
real hook and the real supervisor launch (its only real child is a stand-in worker)."""
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest.mock import patch
import qa_runtime

class QARuntimeTests(unittest.TestCase):
    def setUp(self):
        scratch=Path(os.environ['COMICS_META_TEST_SCRATCH'])
        self.root=Path(tempfile.mkdtemp(prefix='illuminati-cmo-qa-',dir=scratch))
        self.policy=self.root/'policy.json'
        # The full policy qa_runtime.policy() validates; same shape as desktop/tests/qa-policy.test.cjs.
        version=Path(qa_runtime.__file__).with_name('VERSION').read_text(encoding='utf-8').strip()
        prior='0.0.0' if version!='0.0.0' else '0.0.1'
        raw=json.dumps({'schema':1,'root':str(self.root),'priorVersion':prior,'nextVersion':version,
                        'expires':int(time.time()*1000)+600000,'enginePort':18980,'modelPort':18982,
                        'feedURL':'http://127.0.0.1:18981/feed/'+'a'*32+'/','feedToken':'b'*64,
                        'installDirectory':str(self.root/'install'),
                        'artifact':{'version':version,'name':'Comic-Metadata-Setup-'+version+'.exe','size':7,
                                    'sha512':base64.b64encode(bytes([1])*64).decode('ascii')}}).encode()
        self.policy.write_bytes(raw)
        self.env={'TEMP':str(scratch),'COMICS_META_QA':'1','COMICS_META_QA_ROOT':str(self.root),'COMICS_META_QA_POLICY':str(self.policy),'COMICS_META_QA_POLICY_SHA256':hashlib.sha256(raw).hexdigest(),'COMICS_META_STATE_ROOT':str(self.root/'state'),'COMICS_META_LOCK_DIR':str(self.root/'locks')}
        # qa_runtime caches the validated policy and the installed flag per process.
        for name,value in (('_POLICY',None),('_INSTALLED',False)):
            patcher=patch.object(qa_runtime,name,value);patcher.start();self.addCleanup(patcher.stop)
    def tearDown(self):
        assert self.root.parent.resolve()==Path(os.environ['COMICS_META_TEST_SCRATCH']).resolve()
        shutil.rmtree(self.root)
    def hook(self,python=None):
        with patch.dict(os.environ,self.env),patch.object(sys,'addaudithook') as add,patch.object(sys,'executable',python or sys.executable),patch.object(qa_runtime,'_INSTALLED',False):
            qa_runtime.install()
            return add.call_args.args[0]
    def test_provider_gpu_and_browser_are_excluded_without_network_or_launch(self):
        hook=self.hook()
        hook('socket.connect',(None,('127.0.0.1',18980)))
        for address in [('127.0.0.1',11434),('127.0.0.1',8765),('comicvine.gamespot.com',443)]:
            with self.assertRaises(PermissionError):hook('socket.connect',(None,address))
        with self.assertRaises(PermissionError):hook('subprocess.Popen',('chrome.exe',[],None,None))
        with self.assertRaises(PermissionError):hook('os.system',('synthetic',))
    def test_child_python_must_preserve_exclusions(self):
        hook=self.hook()
        with patch.dict(os.environ,self.env):
            hook('subprocess.Popen',(sys.executable,[],None,dict(os.environ)))
            changed=dict(os.environ,COMICS_META_QA='0')
            with self.assertRaises(PermissionError):hook('subprocess.Popen',(sys.executable,[],None,changed))
    def test_changed_policy_or_state_fails_before_installing_audit(self):
        for changed in [{'COMICS_META_QA_POLICY_SHA256':'0'*64},{'COMICS_META_STATE_ROOT':str(self.root.parent)}]:
            with patch.dict(os.environ,dict(self.env,**changed)),patch.object(sys,'addaudithook') as add:
                with self.assertRaises(RuntimeError):qa_runtime.install()
                add.assert_not_called()
        # Positive control: the unchanged fixture installs, so the refusals above came from the changes.
        with patch.dict(os.environ,self.env),patch.object(sys,'addaudithook') as add:
            qa_runtime.install();add.assert_called_once()
    def test_production_does_not_install_qa_exclusions(self):
        with patch.dict(os.environ,{'COMICS_META_QA':'0'}),patch.object(sys,'addaudithook') as add:
            qa_runtime.install();add.assert_not_called()
    def test_windows_worker_launch_is_allowed_by_its_command_line(self):
        # On Windows the audit event carries executable=None and one command-line
        # string; the hook reads the program from it (installed 0.2.1 QA, M1).
        for python in (sys.executable,SPACED_PYTHON):
            with self.subTest(python=python):
                hook=self.hook(python)
                worker=subprocess.list2cmdline([python,str(self.root/'code dir'/'worker.py')])
                with patch.dict(os.environ,self.env):
                    hook('subprocess.Popen',(None,worker,str(self.root),dict(os.environ)))
                    hook('subprocess.Popen',(None,worker,None,None))
                    hook('subprocess.Popen',(python,worker,None,None))  # executable= given, or POSIX
    def test_windows_launch_of_anything_else_is_still_refused(self):
        python=SPACED_PYTHON
        hook=self.hook(python)
        cmd=os.path.join(os.environ.get('SystemRoot','C:\\Windows'),'System32','cmd.exe')
        refused=[
            (None,subprocess.list2cmdline([cmd,'/c','exit']),None,None),   # another program
            (None,'chrome.exe --headless',None,None),                      # bare name: searched for
            (None,'runtime\\python\\python.exe worker.py',None,None),      # relative name
            (None,python[2:]+' worker.py',None,None),                      # root-relative name
            (None,python+' worker.py',None,None),                          # unquoted spaces: C:\Program runs
            (None,'"'+python+' worker.py',None,None),                      # no closing quote
            (None,' "'+python+'" worker.py',None,None),                    # program not at the start
            (None,'',None,None),(None,None,None,None),(None,[python],None,None),
            (cmd,subprocess.list2cmdline([python,'worker.py']),None,None), # executable= wins over the text
            (cmd,cmd+' /c "'+python+' worker.py"',None,None),              # shell=True shape
            (3,python,None,None),                                          # not a path
        ]
        with patch.dict(os.environ,self.env):
            for args in refused:
                with self.subTest(args=args),self.assertRaisesRegex(PermissionError,'native child refused'):
                    hook('subprocess.Popen',args)
            allowed=subprocess.list2cmdline([python,'worker.py'])
            stripped={key:value for key,value in os.environ.items() if key!='COMICS_META_QA'}
            with self.assertRaisesRegex(PermissionError,'exclusions missing'):
                hook('subprocess.Popen',(None,allowed,None,stripped))
            # Positive control: the same hook allows the quoted allowed program.
            hook('subprocess.Popen',(None,allowed,None,None))
    def test_supervisor_spawns_the_worker_in_qa_mode_and_other_children_stay_refused(self):
        # The real hook in a child Python, not a synthetic event.
        base=self.root/'code dir';base.mkdir()
        # Stand-in worker: records that it ran with the QA exclusions, then exits.
        (base/'worker.py').write_text("import os,sys\nfrom pathlib import Path\n"
                                      "Path(sys.argv[0]).with_name('worker-ran.txt').write_text(os.environ.get('COMICS_META_QA',''))\n",encoding='utf-8')
        env=dict(os.environ,**self.env)
        result=subprocess.run([sys.executable,'-B','-c',CHILD,str(base)],cwd=Path(qa_runtime.__file__).parent,
                              env=env,capture_output=True,text=True,timeout=120)
        self.assertEqual(result.returncode,0,result.stderr)
        outcome=json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(outcome['worker_exit'],0,result.stderr)
        self.assertEqual((base/'worker-ran.txt').read_text(encoding='utf-8'),'1')
        self.assertNotIn('Could not start',result.stderr)
        # Controls through the same installed hook: refused before anything starts.
        self.assertEqual(outcome['other'],'Private QA native child refused')
        self.assertFalse((base/'other-ran.txt').exists())
        self.assertEqual(outcome['stripped'],'Private QA child exclusions missing')


SPACED_PYTHON='C:\\Program Files\\Comic Metadata\\resources\\runtime\\python\\python.exe'

# Runs in a child Python with the QA environment: the real hook, the real supervisor launch.
CHILD=textwrap.dedent('''
    import json, os, subprocess, sys, threading
    from pathlib import Path
    import qa_runtime
    qa_runtime.install()
    import supervisor
    base = Path(sys.argv[1]); stop = threading.Event(); started = []
    def launch(*args, **kwargs):
        try:
            started.append(subprocess.Popen(*args, **kwargs)); return started[-1]
        finally:
            stop.set()  # One supervisor pass, launched or refused.
    supervisor.supervise(base, stop, launch, 'worker.py', baseline=lambda: 0)
    result = {'worker_exit': started[0].wait(60) if started else None}
    cmd = os.path.join(os.environ.get('SystemRoot', 'C:\\\\Windows'), 'System32', 'cmd.exe')
    stripped = {k: v for k, v in os.environ.items() if k != 'COMICS_META_QA'}
    for name, args, env in (('other', [cmd, '/c', 'echo>' + str(base / 'other-ran.txt')], None),
                            ('stripped', [sys.executable, str(base / 'worker.py')], stripped)):
        try:
            subprocess.Popen(args, cwd=base, env=env).wait(60); result[name] = 'launched'
        except PermissionError as exc:
            result[name] = str(exc)
    print(json.dumps(result))
''')

