#!/usr/bin/env python3
"""Independent declarative rules validation. No executable payloads or content publishing."""
import json,re
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
DOMAINS={'kolnovel':'kolnovel.com','cenele':'cenele.com','sunovels':'sunovels.com','seanovel':'seanovel.org'}
KEYS={'catalogCards','catalogTitle','catalogCover','detailsTitle','detailsCover','description','genres','chapterLinks','chapterTitle','text','originalTitle'}
def require(condition, message='Invalid declarative rules'):
 if not condition: raise ValueError(message)

def validate(bundle):
 require(isinstance(bundle,dict) and set(bundle)=={'schemaVersion','engineVersion','revision','sources'})
 require(type(bundle['schemaVersion']) is int and bundle['schemaVersion']==1)
 require(type(bundle['engineVersion']) is int and bundle['engineVersion'] in (1,2),'Incompatible engine')
 require(type(bundle['revision']) is int and 0<bundle['revision']<=2147483647,'Invalid revision')
 sources=bundle['sources'];require(isinstance(sources,list) and len(sources)==4)
 seen=set()
 for item in sources:
  require(isinstance(item,dict) and set(item)=={'id','domain','selectors'})
  name=item['id'].removeprefix('novel.') if isinstance(item['id'],str) else ''
  require(name in DOMAINS and item['id']=='novel.'+name and item['domain']==DOMAINS[name] and name not in seen)
  seen.add(name)
  selectors=item['selectors'];require(isinstance(selectors,dict) and 'text' in selectors and set(selectors)<=KEYS)
  for css in selectors.values():
   require(isinstance(css,str) and 1<=len(css)<=240 and not any(x in css for x in '<>\n\r:'))
   require(all(x.strip() not in ('body','html','*',':root') for x in css.split(',')))
   BeautifulSoup('<p></p>','html.parser').select(css)
 require(seen==set(DOMAINS))
 require(len(json.dumps(bundle,ensure_ascii=False,separators=(',',':')).encode())<=64*1024)
 return bundle

def build(revision):
 return validate({'schemaVersion':1,'engineVersion':2,'revision':revision,'sources':[
  json.loads((ROOT/'rules'/(name+'.json')).read_text()) for name in DOMAINS]})

def require_health(report,bundle):
 import hashlib
 digest=hashlib.sha256(json.dumps(validate(bundle),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
 require(isinstance(report,list) and len(report)==4 and {row.get('domain') for row in report}==set(DOMAINS.values()),'Incomplete health report')
 require(all(row.get('rulesSha256')==digest and all(row.get(x) is True for x in ('catalog','search','details','chapters','text')) for row in report),'Candidate did not pass all live checks')
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--revision',type=int,default=1);args=parser.parse_args()
 (ROOT/'bundle.json').write_text(json.dumps(build(args.revision),ensure_ascii=False,separators=(',',':')))
 print('Validated four sources; engine 2; revision',args.revision)
