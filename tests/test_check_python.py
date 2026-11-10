"""The real check launcher's interpreter flags preserve Unicode under -I."""
import base64
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


class CheckPythonOutputTests(unittest.TestCase):
    def test_isolated_launcher_preserves_utf8_and_ignores_environment_control(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'The reviewed check environment must provide pinned Node')
        script = Path(__file__).resolve().parents[1] / 'scripts' / 'check-python.cjs'
        # Evaluate the actual launcher with only the expensive unittest payload
        # replaced. Its real flags launch real embedded Python. The negative
        # control removes its UTF-8 option while leaving PYTHONUTF8=1 in place.
        probe = r"""
const fs=require('node:fs'),vm=require('node:vm'),cp=require('node:child_process');
const filename=process.argv[1],python=process.argv[2],results=[];
for(const negative of [false,true]){
 const fakeProcess={env:{...process.env,COMICS_META_HELD_TEST:'1',COMICS_META_TEST_PYTHON:python,PYTHONUTF8:'1'}};
 const requireProbe=name=>name==='node:child_process'?{spawnSync:(exe,args,options)=>{
  let actual=[...args];
  if(negative)actual=actual.filter((a,i)=>!(a==='-X'&&args[i+1]==='utf8')&&!(a==='utf8'&&args[i-1]==='-X'));
  actual[actual.indexOf('-c')+1]="import json,sys; print(json.dumps({'mode':sys.flags.utf8_mode,'encoding':sys.stdout.encoding}),flush=True); print('Comics: 日本語 🧪')";
  const result=cp.spawnSync(exe,actual,{...options,stdio:'pipe',timeout:10000});
  results.push({negative,status:result.status,error:result.error?.message||null,out:result.stdout.toString('base64')});
  return result;
 }}:require(name);
 vm.runInNewContext(fs.readFileSync(filename,'utf8'),{require:requireProbe,process:fakeProcess,__dirname:require('node:path').dirname(filename)});
}
console.log(JSON.stringify(results));
"""
        result = subprocess.run([node, '-e', probe, str(script), sys.executable],
                                capture_output=True, text=True, timeout=30, check=True)
        positive, negative = json.loads(result.stdout)
        output = base64.b64decode(positive['out']).decode('utf-8')
        flags = json.loads(output.splitlines()[0])
        self.assertEqual((positive['status'], positive['error']), (0, None))
        self.assertEqual(flags['mode'], 1)
        self.assertEqual(flags['encoding'].lower(), 'utf-8')
        self.assertEqual(output.splitlines()[1], 'Comics: 日本語 🧪')
        # This demonstrates why setting an environment variable was insufficient.
        without_option = json.loads(base64.b64decode(negative['out']).splitlines()[0])
        self.assertEqual(without_option['mode'], 0)
