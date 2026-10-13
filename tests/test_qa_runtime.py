"""Synthetic QA exclusion tests; no real socket/process is launched."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import qa_runtime

class QARuntimeTests(unittest.TestCase):
    def setUp(self):
        scratch=Path(os.environ['COMICS_META_TEST_SCRATCH'])
        self.root=Path(tempfile.mkdtemp(prefix='illuminati-cmo-qa-',dir=scratch))
        self.policy=self.root/'policy.json'
        raw=json.dumps({'root':str(self.root),'enginePort':18980}).encode()
        self.policy.write_bytes(raw)
        self.env={'COMICS_META_QA':'1','COMICS_META_QA_ROOT':str(self.root),'COMICS_META_QA_POLICY':str(self.policy),'COMICS_META_QA_POLICY_SHA256':hashlib.sha256(raw).hexdigest(),'COMICS_META_STATE_ROOT':str(self.root/'state')}
    def tearDown(self):
        assert self.root.parent.resolve()==Path(os.environ['COMICS_META_TEST_SCRATCH']).resolve()
        shutil.rmtree(self.root)
    def hook(self):
        with patch.dict(os.environ,self.env),patch.object(sys,'addaudithook') as add:
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
    def test_production_does_not_install_qa_exclusions(self):
        with patch.dict(os.environ,{'COMICS_META_QA':'0'}),patch.object(sys,'addaudithook') as add:
            qa_runtime.install();add.assert_not_called()
