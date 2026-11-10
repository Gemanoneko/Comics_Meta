"""Guest-only synthetic update fixture. Never imports or reads host state."""
import base64
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import struct
import sys
import time
import zipfile
import zlib

ROOT = Path(os.environ.get('CMO_SANDBOX_CASE_ROOT', ''))
if (os.name != 'nt' or os.environ.get('USERNAME', '').lower() != 'wdagutilityaccount'
        or not ROOT.is_absolute() or ROOT.parent != Path('C:/Q')
        or not ROOT.name.startswith('illuminati-cmo-qa-') or os.environ.get('COMICS_META_QA')):
    raise RuntimeError('Guest-only fixture refused')
import app
import credential_store
import gcd_offline
import pause_control
if app.STATE_ROOT != Path(os.environ['LOCALAPPDATA'])/'ComicsMeta':
    raise RuntimeError('Fixture is not using ordinary isolated guest state')

LIBRARY = ROOT / 'library'
MANUAL = LIBRARY / 'Preserved Human Choice 001 (2020).cbz'
def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data) & 0xffffffff)
PNG = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB',1,1,8,2,0,0,0)) + chunk(b'IDAT',zlib.compress(b'\x00\xff\x00\x00')) + chunk(b'IEND',b'')
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def prepare():
    LIBRARY.mkdir(exist_ok=True)
    app.STATE_ROOT.mkdir(exist_ok=True)
    config = {'sources': {'disabled': ['ComicVine', 'Metron', 'Google Lens', 'Google Books', 'GCD',
        'Dark Horse', 'Open Library local index', 'General free web', 'Wikipedia/wiki',
        'Saved lead re-checks', 'GetComics', 'PREVIEWSworld', 'Publisher web'], 'enabled': ['GCD offline']},
        'in_book': {'cover': False, 'publisher_agreement': False, 'credits_pages': False},
        'browser_search': {'enabled': False, 'lens': False},
        'qa_preserved_unknown': {'marker': 'synthetic-update-preservation', 'value': [7, 19, 31]}}
    (app.STATE_ROOT / 'config.json').write_text(json.dumps(config), encoding='utf-8')
    (app.STATE_ROOT / '.env').write_text('QA_LEGACY_SENTINEL=synthetic-only\n', encoding='utf-8')
    source = ROOT / '2026-10-16.db'
    with sqlite3.connect(source) as con:
        for table, columns in gcd_offline.SCHEMA.items():
            con.execute('CREATE TABLE '+table+' ('+', '.join(c+(' INTEGER' if c=='id' or c.endswith('_id') or c in
                ('deleted','year_began','year_ended','issue_count','is_singleton') else ' TEXT') for c in columns.split())+')')
        con.execute("INSERT INTO gcd_publisher VALUES(1,'QA Synthetic Publisher')")
        con.execute("INSERT INTO stddata_language VALUES(1,'en')")
        con.execute("INSERT INTO stddata_country VALUES(1,'us')")
        con.execute("INSERT INTO gcd_series_publication_type VALUES(1,'comic book')")
        con.execute("INSERT INTO gcd_series VALUES(1,'Sandbox QA Fixture','Sandbox QA Fixture',2020,2020,1,1,1,500,1,'comic book',0,0)")
        for number in range(1,501):
            con.execute("INSERT INTO gcd_issue(id,series_id,number,key_date,on_sale_date,title,barcode,valid_isbn,deleted) VALUES(?,1,?,'2020-01-01','2020-01-01',?,'','',0)",
                (number,str(number),'Synthetic issue '+str(number)))
    before = sha(source)
    gcd_offline.start(str(source))
    gcd_offline._thread.join(200)
    if gcd_offline._thread.is_alive() or not gcd_offline.current() or sha(source) != before:
        raise RuntimeError('Actual synthetic GCD index build failed or altered its source')
    for number in range(1,501):
        with zipfile.ZipFile(LIBRARY / ('Sandbox QA Fixture %03d (2020).cbz' % number), 'x') as archive:
            archive.writestr('cover.png',PNG)
    with zipfile.ZipFile(MANUAL,'x') as archive:
        archive.writestr('cover.png',PNG)
        archive.writestr('ComicInfo.xml','<ComicInfo><Series>Preserved Human Choice</Series><Number>1</Number><Year>2020</Year><Title>Human title sentinel</Title><Writer>Human writer</Writer></ComicInfo>')
    with app.db() as con:
        stat = MANUAL.stat()
        metadata = json.dumps({'Series':'Preserved Human Choice','Number':'1','Year':'2020','Title':'Human title sentinel','Writer':'Human writer'})
        con.execute("INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,error,seen) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (str(MANUAL),str(LIBRARY),stat.st_size,stat.st_mtime_ns,'Preserved Human Choice','1','2020',metadata,'embedded','',1))
        cursor=con.execute('INSERT INTO history(path,backup,source,timestamp) VALUES(?,?,?,?)',
            (str(MANUAL),'','QA synthetic historical manual decision',1600000000.0))
        con.execute('INSERT INTO write_ledger(history_id,path,source,writer,fields,input_size,input_mtime,output_size,output_mtime,origin) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (cursor.lastrowid,str(MANUAL),'QA synthetic historical manual decision','human',json.dumps({'Series':'Preserved Human Choice','Number':'1','Title':'Human title sentinel','Writer':'Human writer'}),stat.st_size,stat.st_mtime_ns,stat.st_size,stat.st_mtime_ns,'human'))
        pause_control.table(con)
    recovery=app.STATE_ROOT / 'work' / 'recovery-sentinel.bin'
    recovery.parent.mkdir(exist_ok=True)
    recovery.write_bytes(b'owned synthetic update recovery evidence\x00\x01')
    (ROOT/'fixture-cover.png').write_bytes(PNG)
    return {'prepared':True,'library':str(LIBRARY),'fixtures':500,'gcdSourceSha256':before,'manualSha256':sha(MANUAL),
        'conversionCover':str(ROOT/'fixture-cover.png'),'conversionArchive':str(LIBRARY/'Bundled Conversion 001.cb7')}

def snapshot():
    with app.db() as con:
        manual=con.execute('SELECT path,root,series,number,year,metadata FROM comics WHERE path=?',(str(MANUAL),)).fetchone()
        history=[list(row) for row in con.execute('SELECT id,path,backup,source,timestamp FROM history ORDER BY id')]
        ledger=[list(row) for row in con.execute('SELECT * FROM write_ledger WHERE origin=\'human\' ORDER BY history_id')]
        rows=con.execute("SELECT COUNT(*) FROM comics WHERE path LIKE ? AND status='tagged'",(str(LIBRARY/'Sandbox QA Fixture')+'%',)).fetchone()[0]
        pending=con.execute("SELECT COUNT(*) FROM comics WHERE path LIKE ? AND status!='tagged'",(str(LIBRARY/'Sandbox QA Fixture')+'%',)).fetchone()[0]
        paused=con.execute('SELECT paused FROM processing_control WHERE id=1').fetchone()[0]
    config=app.load_config()
    credentials=credential_store.saved(config)
    return {'configSha256':sha(app.STATE_ROOT/'config.json'),'legacySha256':sha(app.STATE_ROOT/'.env'),
        'credentialSha256':hashlib.sha256(json.dumps(credentials,sort_keys=True).encode()).hexdigest(),
        'credentialFileSha256':sha(app.STATE_ROOT/config[credential_store.POINTER]),
        'credentialPresence':{key:bool(credentials.get(key)) for key in credential_store.ALLOWED_KEYS},
        'credentialsMatchExpected':credentials=={name:'synthetic-sandbox-key-'+str(i) for i,name in enumerate(('COMICVINE_API_KEY','METRON_API_TOKEN','GOOGLE_BOOKS_API_KEY','BRAVE_SEARCH_API_KEY'))},
        'manual':list(manual) if manual else None,'manualArchiveSha256':sha(MANUAL),
        'history':history,'manualLedger':ledger,'recoverySha256':sha(app.STATE_ROOT/'work/recovery-sentinel.bin'),
        'taggedFixtures':rows,'pendingFixtures':pending,'userPaused':bool(paused)}

if sys.argv[1:] not in (['prepare'],['snapshot']):
    raise RuntimeError('Exact fixture action required')
print(json.dumps(prepare() if sys.argv[1]=='prepare' else snapshot(),ensure_ascii=True))
