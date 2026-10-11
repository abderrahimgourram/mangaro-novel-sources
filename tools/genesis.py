#!/usr/bin/env python3
"""Explicit owner-reviewed genesis; never manufactures rollback authority.

Native acceptance is owner-attested LOCAL emulator evidence, not a claim that
GitHub ran Android. Independent source acceptance runs again in protected CI.
"""
import argparse,base64,hashlib,json,os,re,subprocess,time
from pathlib import Path
from validate import ROOT,build,require,require_health,require_staging
from verify import verify_pair,verify_signature,verify_public_feed
from operations import GitJournal,fingerprint
from operation_adapter import api,REPOSITORY

def sha(raw):return hashlib.sha256(raw).hexdigest()
def open_journal(value):
 raw=base64.b64decode(value['body'],validate=True)
 verify_signature(b'MangaroSourceOperationsV1\n'+raw,value['signature'],ROOT/'keys/rules-public.der')
 return json.loads(raw)
def owner_gate():
 require(os.environ.get('GITHUB_REPOSITORY')==REPOSITORY and os.environ.get('GITHUB_REF')=='refs/heads/main','Untrusted genesis environment')
 require(os.environ.get('GITHUB_ACTOR')==REPOSITORY.split('/')[0],'Genesis requires the repository owner')
 require(os.environ.get('INITIAL_RELEASE')=='true' and not os.environ.get('PUBLICATION_SOURCE'),'Explicit all-included genesis required')
 require(os.environ.get('MANGARO_AUTOPUBLISH_ENABLED')!='true','Genesis cannot enable automatic publishing')

def native_gate(evidence,manifest,envelope):
 require(isinstance(evidence,dict) and set(evidence)=={'method','consumerCommit','manifestSha256','envelopeSha256','keySha256','resultSha256','passed','failed','emulatorSerial','androidApi','performedAt'},'Exact native evidence contract required')
 require(evidence['method']=='OWNER_ATTESTED_LOCAL_EMULATOR','Unknown native evidence origin')
 require(re.fullmatch('[0-9a-f]{40}',evidence['consumerCommit']) and re.fullmatch('[0-9a-f]{64}',evidence['resultSha256']),'Invalid native provenance')
 require(evidence['manifestSha256']==sha(manifest) and evidence['envelopeSha256']==sha(envelope) and evidence['keySha256']==sha((ROOT/'keys/rules-public.der').read_bytes()),'Native acceptance does not bind exact pinned staging bytes')
 require(type(evidence['passed']) is int and evidence['passed']>=7 and type(evidence['failed']) is int and evidence['failed']==0,'Native consumer acceptance failed')
 require(re.fullmatch('emulator-[0-9]+',evidence['emulatorSerial']) and type(evidence['androidApi']) is int and evidence['androidApi']>=26,'Invalid native test platform')
 require(type(evidence['performedAt']) is int and 0<=time.time()-evidence['performedAt']<=3600,'Native acceptance expired')
 return evidence

def compare_health(candidate,producer,independent):
 require_health(producer,candidate);require_health(independent,candidate)
 prior={r['domain']:r for r in producer}
 for row in independent:
  old=prior[row['domain']]
  for field in ('identityHash','indexHash'):
   require(re.fullmatch('[0-9a-f]{64}',str(row.get(field,''))) and row[field]==old.get(field),'Independent source identity/index mismatch')
  count=row.get('verifiedChapterCount') or row.get('chapterCount') or row.get('chapter_count')
  before=old.get('verifiedChapterCount') or old.get('chapterCount') or old.get('chapter_count')
  require(type(count) is int and count>0 and count==before,'Independent chapter count changed')

def restore():
 owner_gate();run=os.environ['STAGING_RUN'];require(re.fullmatch('[0-9]+',run) and run!=os.environ['GITHUB_RUN_ID'],'Distinct producer required')
 meta=api('GET',f'repos/{REPOSITORY}/actions/runs/{run}')
 require(meta.get('status')=='completed' and meta.get('conclusion')=='success' and meta.get('event')=='workflow_dispatch' and meta.get('head_branch')=='main','Untrusted/failed staging run')
 workflow=api('GET',f'repos/{REPOSITORY}/actions/workflows/publish.yml')
 require(meta.get('workflow_id')==workflow['id'] and meta.get('actor',{}).get('login')==REPOSITORY.split('/')[0],'Wrong staging workflow/actor')
 stage=ROOT/'staging';stage.mkdir(exist_ok=True)
 for name,folder in [(f'signed-novel-staging-{run}',stage),('publication-health-no-content',ROOT/'staging/producer-health')]:
  subprocess.run(['gh','run','download',run,'--repo',REPOSITORY,'--name',name,'--dir',str(folder)],check=True,capture_output=True,timeout=60)
 manifest=(stage/'manifest.json').read_bytes();data=json.loads(manifest)
 envelope=(stage/f"rules-{data['revision']}.json").read_bytes();candidate=verify_pair(manifest,envelope)
 require(candidate['revision']==int(os.environ['RULE_REVISION']) and candidate['schemaVersion']==2 and candidate['mode']=='PARTIAL','Wrong genesis format/revision')
 ids=['novel.kolnovel','novel.cenele','novel.seanovel']
 require(candidate==build(candidate['revision'],ids),'Genesis must use exact reviewed three-source mappings')
 prior=ROOT/'published/v2/manifest.json'
 if prior.exists():
  pair=dict(manifest=base64.b64encode(manifest).decode(),envelope=base64.b64encode(envelope).decode())
  state=GitJournal(api,REPOSITORY,lambda _:None,open_journal).read()
  require(not state.get('sources') and state.get('pendingGenesis',{}).get('pairHash')==fingerprint(pair),'Genesis cannot replace authenticated CURRENT/history')
  require(prior.read_bytes()==manifest and (ROOT/data['envelopePath']).read_bytes()==envelope,'Interrupted genesis CURRENT mismatch')
 native_gate(json.loads(os.environ['NATIVE_EVIDENCE']),manifest,envelope)
 (ROOT/'bundle.json').write_text(json.dumps(candidate,ensure_ascii=False,separators=(',',':')))
 print('Authenticated producer staging and owner-attested native byte bindings; no publication')

def signing():
 key=os.environ.pop('RULE_SIGNING_KEY','');require(bool(key),'Signing credential unavailable')
 import tempfile
 f=tempfile.NamedTemporaryFile(prefix='novel-genesis-key-',delete=False);os.chmod(f.name,0o600);f.write(key.encode());f.close()
 def seal(value):
  raw=json.dumps(value,sort_keys=True,separators=(',',':')).encode()
  sig=subprocess.check_output(['openssl','dgst','-sha256','-sign',f.name],input=b'MangaroSourceOperationsV1\n'+raw)
  verify_signature(b'MangaroSourceOperationsV1\n'+raw,base64.b64encode(sig).decode(),ROOT/'keys/rules-public.der')
  return dict(body=base64.b64encode(raw).decode(),signature=base64.b64encode(sig).decode())
 return Path(f.name),seal

def candidate_files():
 stage=ROOT/'staging';manifest=(stage/'manifest.json').read_bytes();meta=json.loads(manifest)
 envelope=(stage/f"rules-{meta['revision']}.json").read_bytes();return manifest,envelope,verify_pair(manifest,envelope)

def accept():
 owner_gate();manifest,envelope,candidate=candidate_files()
 native=native_gate(json.loads(os.environ['NATIVE_EVIDENCE']),manifest,envelope)
 producer=json.loads((ROOT/'staging/producer-health/health.json').read_text());independent=json.loads((ROOT/'health.json').read_text())
 compare_health(candidate,producer,independent)
 key,seal=signing()
 try:
  receipt=dict(purpose='SOURCE_STAGING_ACCEPTANCE_V1',repository=REPOSITORY,candidateHash=fingerprint(candidate),revision=candidate['revision'],sources=[s['domain'] for s in candidate['sources']],verifiedAt=int(time.time()),producerRun=os.environ['STAGING_RUN'],independentRun=os.environ['GITHUB_RUN_ID'],accepted=True,independent=True,runtimeVerified=True,nativeEvidence=native,manifestSha256=sha(manifest),envelopeSha256=sha(envelope))
  proof=seal(receipt);require_staging(proof,candidate,manifest=manifest,envelope=envelope)
  (ROOT/'staging/acceptance.json').write_text(json.dumps(proof,separators=(',',':')))
 finally:key.unlink()
 print('Independent real-source acceptance and exact owner-attested Android acceptance signed; rollback NOT_READY')

def publish():
 owner_gate();manifest,envelope,candidate=candidate_files();proof=json.loads((ROOT/'staging/acceptance.json').read_text())
 require_staging(proof,candidate,manifest=manifest,envelope=envelope);require_health(json.loads((ROOT/'health.json').read_text()),candidate)
 key,seal=signing()
 journal=GitJournal(api,REPOSITORY,seal,open_journal)
 pair=dict(manifest=base64.b64encode(manifest).decode(),envelope=base64.b64encode(envelope).decode())
 try:
  ref=api('GET',f'repos/{REPOSITORY}/git/ref/heads/source-operations-state',allow_missing=True)
  if ref is None:
   state=dict(purpose='SOURCE_OPERATIONS_V1',repository=REPOSITORY,sources={},stagingReceipts={fingerprint(candidate):proof},pendingGenesis=dict(revision=candidate['revision'],pairHash=fingerprint(pair),at=int(time.time())))
   journal.initialize(state)
  else:
   state=journal.read();pending=state.get('pendingGenesis')
   require(not state.get('sources') and pending and pending.get('pairHash')==fingerprint(pair),'Existing authenticated history cannot be overwritten')
  os.environ['GENESIS_RESERVATION_HASH']=fingerprint(pair)
  prior=ROOT/'published/v2/manifest.json'
  if prior.exists():
   require(prior.read_bytes()==manifest and (ROOT/json.loads(manifest)['envelopePath']).read_bytes()==envelope,'Cannot reconcile a different CURRENT')
  else:subprocess.run([os.sys.executable,str(ROOT/'tools/publish.py')],check=True)
  verify_public_feed(manifest,envelope)
  report=json.loads((ROOT/'health.json').read_text())
  witness={r['domain']:dict(identityHash=r['identityHash'],chapterCount=r.get('verifiedChapterCount') or r.get('chapterCount') or r.get('chapter_count'),indexHash=r['indexHash']) for r in report}
  for source in candidate['sources']:
   domain=source['domain'];state['sources'][domain]=dict(approved=False,current=pair,publishedHash=fingerprint(pair),revisionFloor=candidate['revision'],witness=dict(complete=True,novelWitness=witness),audit=[dict(kind='GENESIS',revision=candidate['revision'],at=int(time.time()))])
  state.pop('pendingGenesis');state['genesis']=dict(revision=candidate['revision'],pairHash=fingerprint(pair),at=int(time.time()),rollbackReady=False)
  journal.write(state)
 finally:key.unlink()
 print('GENESIS_PUBLISHED_AND_JOURNALED; authentic CURRENT only; automatic publication/rollback DISABLED')

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['restore','accept','publish']);args=parser.parse_args()
 {'restore':restore,'accept':accept,'publish':publish}[args.action]()
