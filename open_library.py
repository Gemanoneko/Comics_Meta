"""Stream downloaded Open Library dumps into a catalog-specific local index."""
import argparse
import gzip
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path
import app
INDEX=app.DATA/'open-library.sqlite'

def records(path):
    opener=gzip.open if str(path).endswith('.gz') else open
    with opener(path,'rt',encoding='utf-8') as stream:
        for line in stream:
            try:yield json.loads(line.rstrip('\n').split('\t',4)[-1])
            except json.JSONDecodeError:continue

def import_dump(path):
    import research
    with app.db() as catalog:rows=catalog.execute('SELECT series,metadata FROM comics').fetchall()
    titles=set();isbns=set()
    for row in rows:
        old=json.loads(row['metadata'])
        titles.update(research.normalize(v) for v in (row['series'],old.get('Title'),old.get('Series')) if v)
        if old.get('ISBN'):isbns.add(re.sub('[^0-9X]','',old['ISBN'].upper()))
    count=0
    with closing(sqlite3.connect(INDEX)) as con, con:
        con.execute('CREATE TABLE IF NOT EXISTS records(key TEXT PRIMARY KEY, value TEXT)')
        for record in records(path):
            ids=set(record.get('isbn_10',[])+record.get('isbn_13',[]))
            if research.normalize(record.get('title')) not in titles and not ids.intersection(isbns):continue
            key=record.get('key','')
            if not re.fullmatch(r'/(works|books)/OL\d+[WM]',key):continue
            con.execute('INSERT OR REPLACE INTO records VALUES (?,?)',(key,json.dumps(record)))
            count+=1
            if count%1000==0:con.commit()
    return count

def lookup(row,old):
    import providers
    isbn=re.sub('[^0-9X]','',old.get('ISBN','').upper())
    if not INDEX.exists() or not isbn or not providers.is_book(row,old):return None
    with closing(sqlite3.connect(INDEX)) as con:
        matches=[]
        for value, in con.execute('SELECT value FROM records'):
            record=json.loads(value)
            if isbn in set(record.get('isbn_10',[])+record.get('isbn_13',[])):matches.append(record)
        if len(matches)!=1:return None
        edition=matches[0];description=edition.get('description');source_key=edition['key']
        if not description:
            for work in edition.get('works',[]):
                result=con.execute('SELECT value FROM records WHERE key=?',(work.get('key'),)).fetchone()
                if result:
                    content=json.loads(result[0]);description=content.get('description');source_key=content['key']
                    if description:break
    if isinstance(description,dict):description=description.get('value','')
    return {'provider':'Open Library local index','fields':{'Title':edition.get('title',''),'ISBN':isbn},'sources':[{'url':'https://openlibrary.org'+source_key,'title':edition.get('title',''),'text':providers.text(description),'scope':'Exact ISBN; work description applies to verified edition'}] if description else [],'status':'edition_verified'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Import a downloaded works or editions dump; retain only catalog matches.')
    parser.add_argument('dump',type=Path)
    print('Matching records imported:',import_dump(parser.parse_args().dump))
