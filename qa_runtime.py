"""Private QA policy and finite Python audit exclusions; no OS firewall claim.

Normal mode installs no audit hook and keeps the normal model address. Private
QA uses the existing hook for CPython socket/process interfaces, plus explicit
model request factories. Native code and Electron networking are separate owners.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.parse
import urllib.request

_POLICY = None
_INSTALLED = False


def _fail():
    raise RuntimeError('Private QA policy is invalid') from None


def _safe(value, root, existing=False):
    if not isinstance(value, str) or '\0' in value:
        _fail()
    path = Path(value)
    if not path.is_absolute():
        _fail()
    path = Path(os.path.abspath(path))
    if path != root and not path.is_relative_to(root):
        _fail()
    for candidate in (path, *path.parents):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            if existing and candidate == path:
                _fail()
            continue
        if candidate.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            _fail()
        if os.path.normcase(os.path.realpath(candidate)) != os.path.normcase(str(candidate)):
            _fail()
    return path


def policy():
    """Independently validate pinned QA policy before state or network access."""
    global _POLICY
    if _POLICY is not None:
        if time.time()*1000 > _POLICY['expires']:
            _fail()
        return _POLICY
    if os.environ.get('COMICS_META_QA') != '1':
        return None
    try:
        temp_value = os.environ.get('TEMP', '')
        if not Path(temp_value).is_absolute():
            _fail()
        temp = Path(os.path.abspath(temp_value))
        root = _safe(os.environ.get('COMICS_META_QA_ROOT', ''), temp, True)
        if root == temp or not root.is_dir() or not root.name.startswith('illuminati-cmo-qa-'):
            _fail()
        filename = _safe(os.environ.get('COMICS_META_QA_POLICY', ''), root, True)
        if not filename.is_file():
            _fail()
        expected = os.environ.get('COMICS_META_QA_POLICY_SHA256', '')
        if not re.fullmatch('[a-f0-9]{64}', expected):
            _fail()
        with filename.open('rb') as stream:
            raw = stream.read(32769)
        if len(raw) > 32768 or hashlib.sha256(raw).hexdigest() != expected:
            _fail()
        value = json.loads(raw)
        if not isinstance(value, dict) or type(value.get('schema')) is not int or value.get('schema') != 1 or value.get('root') != str(root):
            _fail()
        versions = [value.get('priorVersion'), value.get('nextVersion')]
        if any(not isinstance(v, str) or not re.fullmatch(r'\d+\.\d+\.\d+', v) for v in versions) or versions[0] == versions[1]:
            _fail()
        version_file = Path(__file__).absolute().with_name('VERSION')
        with version_file.open('r', encoding='utf-8') as stream:
            version = stream.read(128).strip()
        if version not in versions:
            _fail()
        now = time.time()*1000
        if type(value.get('expires')) is not int or not now <= value['expires'] <= now+86400000:
            _fail()
        engine, model = value.get('enginePort'), value.get('modelPort')
        if any(type(port) is not int or not 1024 <= port <= 65535 or port in (8765, 11434) for port in (engine, model)):
            _fail()
        feed = urllib.parse.urlsplit(value.get('feedURL', ''))
        port = feed.port
        if (feed.scheme != 'http' or feed.hostname != '127.0.0.1' or feed.netloc != '127.0.0.1:'+str(port)
                or type(port) is not int or not 1024 <= port <= 65535 or port in (8765, 11434)
                or len({engine, model, port}) != 3 or feed.query or feed.fragment
                or not re.fullmatch('/feed/[a-f0-9]{32}/', feed.path)
                or not isinstance(value.get('feedToken'), str) or not re.fullmatch('[a-f0-9]{64}', value['feedToken'])):
            _fail()
        _safe(value.get('installDirectory'), root)
        state = _safe(os.environ.get('COMICS_META_STATE_ROOT', ''), root)
        if state != root/'state':
            _fail()
        if 'COMICS_META_LOCK_DIR' in os.environ and _safe(os.environ['COMICS_META_LOCK_DIR'], root) != root/'locks':
            _fail()
        artifact = value.get('artifact')
        if (not isinstance(artifact, dict) or artifact.get('version') != versions[1]
                or artifact.get('name') != 'Comic-Metadata-Setup-'+versions[1]+'.exe'
                or type(artifact.get('size')) is not int or not 1 <= artifact['size'] <= 2*1024**3
                or not isinstance(artifact.get('sha512'), str)):
            _fail()
        digest = base64.b64decode(artifact['sha512'], validate=True)
        if len(digest) != 64 or base64.b64encode(digest).decode('ascii') != artifact['sha512']:
            _fail()
        _POLICY = {**value, '_feedPort': port}
        return _POLICY
    except Exception:
        # Do not put fixture tokens, paths or provider credentials in errors.
        _fail()


def model_address():
    value = policy()
    return '127.0.0.1', 11434 if value is None else value['modelPort']


def model_request(endpoint, data=None, headers=None):
    if endpoint not in ('/api/tags', '/api/chat', '/api/generate', '/api/ps'):
        raise ValueError('Unsupported model endpoint')
    host, port = model_address()
    copied = dict(headers or {})
    value = policy()
    if value is not None:
        copied['X-ComicsMeta-QA'] = value['feedToken']
    return urllib.request.Request('http://'+host+':'+str(port)+endpoint, data=data, headers=copied)


def launched_program(executable, command):
    """The program a subprocess.Popen audit event will start, or None if unclear.

    POSIX and an explicit executable= give it directly. On Windows Popen passes
    executable=None and one command-line string; CreateProcess then runs the
    quoted text up to the next quote, or else the text before the first space
    or tab. Anything unclear (no closing quote, a non-string) is None, which
    the caller refuses.
    """
    if executable is not None:
        try:return os.fsdecode(executable)
        except TypeError:return None
    if not isinstance(command, str):
        return None
    if command.startswith('"'):
        end = command.find('"', 1)
        return command[1:end] if end > 0 else None
    return re.split('[ \t]', command, maxsplit=1)[0]


def install():
    global _INSTALLED
    value = policy()
    if value is None or _INSTALLED:
        return
    port=value['enginePort']
    allowed_ports={port,value['modelPort'],value['_feedPort']}
    allowed_python=os.path.normcase(os.path.abspath(sys.executable))
    sevenzip=os.environ.get('COMICS_META_7ZIP')
    allowed_native=os.path.normcase(os.path.abspath(sevenzip)) if sevenzip else None
    def address_allowed(address, ports):
        return (isinstance(address,tuple) and len(address)==2 and address[0]=='127.0.0.1'
                and type(address[1]) is int and address[1] in ports)
    def audit(event,args):
        if event in ('socket.connect','socket.sendto'):
            policy()  # Expired private policy never falls back to production.
            address=args[1]
            if not address_allowed(address,allowed_ports):raise PermissionError('Private QA external connection refused')
        elif event=='socket.getaddrinfo':
            policy()
            if args[0]!='127.0.0.1' or str(args[1]) not in {str(p) for p in allowed_ports}:raise PermissionError('Private QA external lookup refused')
        elif event in ('socket.gethostbyname','socket.gethostbyaddr'):
            if args[0]!='127.0.0.1':raise PermissionError('Private QA external lookup refused')
        elif event=='socket.bind':
            address=args[1]
            if not address_allowed(address,{port}):raise PermissionError('Private QA socket binding refused')
        elif event=='subprocess.Popen':
            # args[0] is None on Windows unless executable= was passed; the
            # program is then the first command-line token (installed 0.2.1 QA, M1).
            program=launched_program(args[0],args[1])
            # A bare or relative name would be searched for; only a full path is compared.
            if not program or not os.path.isabs(program):raise PermissionError('Private QA native child refused')
            executable=os.path.normcase(os.path.abspath(program))
            if executable not in (allowed_python,allowed_native):raise PermissionError('Private QA native child refused')
            child_env=args[3]
            if child_env is not None and any(child_env.get(key)!=os.environ.get(key) for key in ('COMICS_META_QA','COMICS_META_QA_ROOT','COMICS_META_QA_POLICY','COMICS_META_QA_POLICY_SHA256','COMICS_META_STATE_ROOT','COMICS_META_LOCK_DIR')):raise PermissionError('Private QA child exclusions missing')
        elif event in ('os.system','os.exec','os.posix_spawn'):raise PermissionError('Private QA alternate process launch refused')
    sys.addaudithook(audit)
    _INSTALLED = True
