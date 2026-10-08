#!/usr/bin/env python3
"""Independent declarative rules validation. No executable payloads or content publishing."""
import json,re
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
DOMAINS={'kolnovel':'kolnovel.com','cenele':'cenele.com','sunovels':'sunovels.com','seanovel':'seanovel.org'}
KEYS={'catalogCards','catalogTitle','catalogCover','detailsTitle','detailsCover','description','genres','chapterLinks','chapterTitle','text'}
def build(revision):
 sources=[]
 for name,domain in DOMAINS.items():
  item=json.loads((ROOT/'rules'/(name+'.json')).read_text())
  assert set(item)=={'id','domain','selectors'} and item['id']=='novel.'+name and item['domain']==domain
  assert 'text' in item['selectors'] and set(item['selectors'])<=KEYS
  for css in item['selectors'].values():
   assert isinstance(css,str) and 1<=len(css)<=240 and not any(x in css for x in '<>\n:')
   assert all(x.strip() not in ('body','html','*',':root') for x in css.split(','))
   BeautifulSoup('<p></p>','html.parser').select(css)
  sources.append(item)
 assert isinstance(revision,int) and revision>0
 return {'schemaVersion':1,'engineVersion':1,'revision':revision,'sources':sources}
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--revision',type=int,default=1);args=parser.parse_args()
 (ROOT/'bundle.json').write_text(json.dumps(build(args.revision),ensure_ascii=False,separators=(',',':')))
 print('Validated four sources; engine 1; revision',args.revision)
