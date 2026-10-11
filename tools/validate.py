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
 require(isinstance(bundle,dict))
 version=bundle.get('schemaVersion')
 require(type(version) is int and version in (1,2),'Unsupported schema')
 require(set(bundle)==({'schemaVersion','engineVersion','revision','sources'} if version==1 else {'schemaVersion','engineVersion','revision','mode','sources'}))
 require(type(bundle['engineVersion']) is int and bundle['engineVersion'] in ((1,2) if version==1 else (3,)),'Incompatible engine')
 if version==2:require(bundle['mode'] in ('PARTIAL','FULL'),'Unsupported update mode')
 require(type(bundle['revision']) is int and 0<bundle['revision']<=2147483647,'Invalid revision')
 sources=bundle['sources'];partial=version==2 and bundle['mode']=='PARTIAL'
 require(isinstance(sources,list) and (1<=len(sources)<=4 if partial else len(sources)==4))
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
 require(seen<=set(DOMAINS) if partial else seen==set(DOMAINS))
 require(len(json.dumps(bundle,ensure_ascii=False,separators=(',',':')).encode())<=64*1024)
 return bundle

def build(revision,sources=None):
 names=list(DOMAINS)
 if sources is not None:
  require(isinstance(sources,(list,tuple)) and sources and len(set(sources))==len(sources),'Invalid source subset')
  require(all(s in {'novel.'+name for name in DOMAINS} for s in sources),'Unknown source subset')
  names=[name for name in DOMAINS if 'novel.'+name in sources]
 bundle={'schemaVersion':1 if sources is None else 2,'engineVersion':2 if sources is None else 3,'revision':revision}
 if sources is not None:bundle['mode']='PARTIAL'
 bundle['sources']=[json.loads((ROOT/'rules'/(name+'.json')).read_text()) for name in names]
 return validate(bundle)

def manifest_path(bundle):
 return 'published/'+('v2/' if bundle['schemaVersion']==2 else '')+'manifest.json'

def require_health(report,bundle,*,current=None,source=None):
 import hashlib
 digest=hashlib.sha256(json.dumps(validate(bundle),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
 validate(bundle)
 required={row['domain'] for row in bundle['sources']}
 if source is not None:
  require(source in required and current is not None,'Authenticated current bundle required for source-scoped publication')
  validate(current)
  require(bundle['revision']>=current['revision'],'Revision decreased')
  require({k:v for k,v in bundle.items() if k not in {'sources','revision'}}=={k:v for k,v in current.items() if k not in {'sources','revision'}},'Engine change requires full acceptance')
  require([s for s in bundle['sources'] if s['domain']!=source]==[s for s in current['sources'] if s['domain']!=source],'Unrelated source changed')
  required={source}
 require(isinstance(report,list) and len(report)==len(required) and {row.get('domain') for row in report}==required,'Incomplete health report')
 require(all(row.get('rulesSha256')==digest and row.get('completeIndex') is True and (row.get('domain')!='seanovel.org' or row.get('attestationVerified') is True) and all(row.get(x) is True for x in ('catalog','search','details','chapters','text')) for row in report),'Candidate did not pass all live checks')

def require_staging(proof,bundle,source=None,*,manifest=None,envelope=None):
 """Publication authority is an independent signed receipt, never monitoring output."""
 import base64,time
 from verify import verify_signature
 from operations import fingerprint
 require(isinstance(proof,dict) and set(proof)=={'body','signature'},'Signed staging receipt required')
 raw=base64.b64decode(proof['body'],validate=True);require(len(raw)<=16384,'Oversized staging receipt')
 verify_signature(b'MangaroSourceOperationsV1\n'+raw,proof['signature'],ROOT/'keys/rules-public.der')
 receipt=json.loads(raw)
 expected={source} if source else {row['domain'] for row in validate(bundle)['sources']}
 require(receipt.get('purpose')=='SOURCE_STAGING_ACCEPTANCE_V1' and receipt.get('repository')=='abderrahimgourram/mangaro-novel-sources','Staging provenance mismatch')
 require(receipt.get('candidateHash')==fingerprint(bundle) and type(receipt.get('revision')) is int and receipt['revision']==bundle['revision'],'Staging candidate mismatch')
 require(isinstance(receipt.get('sources'),list) and len(receipt['sources'])==len(expected) and set(receipt['sources'])==expected,'Staging source scope mismatch')
 stamp=receipt.get('verifiedAt');require(type(stamp) is int and 0<=time.time()-stamp<=3600,'Staging receipt expired')
 require(receipt.get('producerRun') and receipt.get('independentRun') and receipt['producerRun']!=receipt['independentRun'],'Independent staging required')
 require(all(receipt.get(k) is True for k in ('accepted','independent','runtimeVerified')),'Staging not accepted')
 if manifest is not None or envelope is not None:
  import hashlib
  require(isinstance(manifest,bytes) and isinstance(envelope,bytes),'Exact staged bytes required')
  require(receipt.get('manifestSha256')==hashlib.sha256(manifest).hexdigest() and receipt.get('envelopeSha256')==hashlib.sha256(envelope).hexdigest(),'Staging artifact bytes mismatch')
 return receipt
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--revision',type=int,default=1);args=parser.parse_args()
 (ROOT/'bundle.json').write_text(json.dumps(build(args.revision),ensure_ascii=False,separators=(',',':')))
 print('Validated four sources; engine 2; revision',args.revision)
