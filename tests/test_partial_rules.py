"""Partial-format regression fixtures are never real source acceptance evidence."""
import base64,copy,hashlib,json,sys,tempfile,time,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from validate import build,validate,require_health,manifest_path,require_staging
from verify import verify_pair,manifest_bytes
from prepare import prepare
from operations import scoped_candidate,rollback_candidate
FIXTURE=Path(__file__).parent/'fixtures/partial'
IDS=['novel.kolnovel','novel.cenele','novel.seanovel']
class PartialRulesTest(unittest.TestCase):
 def report(self,bundle):
  digest=hashlib.sha256(json.dumps(bundle,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
  return [dict(domain=s['domain'],rulesSha256=digest,completeIndex=True,attestationVerified=True,**{k:True for k in ['catalog','search','details','chapters','text']}) for s in bundle['sources']]
 def pair(self,name):return verify_pair((FIXTURE/(name+'-manifest.json')).read_bytes(),(FIXTURE/(name+'-envelope.json')).read_bytes(),FIXTURE/'public.der')
 def test_legacy_three_and_one_formats_and_feed_isolation(self):
  self.assertEqual(len(build(3)['sources']),4)
  for ids in [IDS,['novel.cenele']]:
   b=build(3,ids);self.assertEqual(b['mode'],'PARTIAL');self.assertEqual(len(b['sources']),len(ids));require_health(self.report(b),b)
   self.assertEqual(manifest_path(b),'published/v2/manifest.json')
  self.assertEqual(manifest_path(build(3)),'published/manifest.json')
 def test_included_failure_missing_or_extra_report_fails(self):
  b=build(3,IDS);report=self.report(b)
  for field in ['completeIndex','text','attestationVerified']:
   r=copy.deepcopy(report);r[-1][field]=False
   with self.assertRaises(ValueError):require_health(r,b)
  for r in [report[:-1],report+[dict(report[0],domain='sunovels.com')]]:
   with self.assertRaises(ValueError):require_health(r,b)
 def test_invalid_subsets_modes_domains_and_duplicate_ids_fail(self):
  for ids in [[],['novel.other'],['novel.cenele','novel.cenele']]:
   with self.assertRaises(ValueError):build(3,ids)
  for key,value in [('mode','DELETE'),('schemaVersion',3),('engineVersion',2)]:
   b=build(3,IDS);b[key]=value
   with self.assertRaises(ValueError):validate(b)
  b=build(3,IDS);b['sources'][0]['domain']='evil.test'
  with self.assertRaises(ValueError):validate(b)
  b=build(3,IDS);b['sources'].append(copy.deepcopy(b['sources'][0]))
  with self.assertRaises(ValueError):validate(b)
 def test_signed_partial_hash_revision_and_manifest_binding(self):
  self.assertEqual(self.pair('three')['sources'][0]['id'],'novel.kolnovel')
  m=(FIXTURE/'three-manifest.json').read_bytes();e=(FIXTURE/'three-envelope.json').read_bytes()
  for manifest,envelope in [(m,e+b' '),(m,(FIXTURE/'one-envelope.json').read_bytes()),(m.replace(b'"revision": 3',b'"revision": 4'),e)]:
   with self.assertRaises(ValueError):verify_pair(manifest,envelope,FIXTURE/'public.der')
  with self.assertRaises(ValueError):verify_pair(m,e) # Test key never satisfies production trust.
 def test_explicit_genesis_creates_no_current_or_last_good(self):
  with tempfile.TemporaryDirectory() as t,patch('prepare.ROOT',Path(t)):
   with self.assertRaises(ValueError):prepare(3,sources=IDS)
   self.assertEqual(prepare(3,initial=True,sources=IDS),build(3,IDS))
   with self.assertRaises(ValueError):prepare(3,rollback=2,initial=True,sources=IDS)
   self.assertFalse((Path(t)/'published').exists())
 def test_next_partial_preserves_authenticated_unselected_mappings(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);p=root/'published/v2';p.mkdir(parents=True)
   (p/'manifest.json').write_bytes((FIXTURE/'three-manifest.json').read_bytes());(p/'rules-3.json').write_bytes((FIXTURE/'three-envelope.json').read_bytes())
   with patch('prepare.ROOT',root),patch('prepare.verify_pair',side_effect=lambda m,e:verify_pair(m,e,FIXTURE/'public.der')):
    b=prepare(4,sources=['novel.cenele'])
   old=self.pair('three')
   self.assertEqual([s for s in b['sources'] if s['domain']!='cenele.com'],[s for s in old['sources'] if s['domain']!='cenele.com'])
   require_health([r for r in self.report(b) if r['domain']=='cenele.com'],b,current=old,source='cenele.com')
 def test_scoped_rollback_of_partial_never_changes_another_source(self):
  old=self.pair('three');current=copy.deepcopy(old);current['revision']=4;current['sources'][1]['selectors']['text']='.replacement'
  restored=rollback_candidate(current,old,'cenele.com',5);scoped_candidate(current,restored,'cenele.com')
  self.assertEqual(restored['sources'],old['sources'])
  changed=copy.deepcopy(restored);changed['sources'][0]['selectors']['text']='.foreign'
  with self.assertRaises(ValueError):scoped_candidate(current,changed,'cenele.com')
 def test_unsigned_or_unscoped_staging_cannot_authorize_publication(self):
  with self.assertRaises(ValueError):require_staging({},build(3,IDS))
  with self.assertRaises(ValueError):require_staging({'body':base64.b64encode(b'{}').decode(),'signature':'AA=='},build(3,IDS))
 def test_signed_receipt_requires_exact_scope_revision_freshness_and_independence(self):
  from operations import fingerprint
  b=build(3,IDS)
  receipt=dict(purpose='SOURCE_STAGING_ACCEPTANCE_V1',repository='abderrahimgourram/mangaro-novel-sources',candidateHash=fingerprint(b),revision=3,sources=[s['domain'] for s in b['sources']],verifiedAt=int(time.time()),producerRun='fixture-producer',independentRun='fixture-verifier',accepted=True,independent=True,runtimeVerified=True)
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'keys').mkdir();key=root/'disposable.pem'
   subprocess.run(['openssl','ecparam','-name','prime256v1','-genkey','-noout','-out',str(key)],check=True)
   (root/'keys/rules-public.der').write_bytes(subprocess.check_output(['openssl','pkey','-in',str(key),'-pubout','-outform','DER']))
   def proof(r):
    raw=json.dumps(r,separators=(',',':')).encode();sig=subprocess.check_output(['openssl','dgst','-sha256','-sign',str(key)],input=b'MangaroSourceOperationsV1\n'+raw)
    return dict(body=base64.b64encode(raw).decode(),signature=base64.b64encode(sig).decode())
   with patch('validate.ROOT',root):
    require_staging(proof(receipt),b)
    for k,v in [('candidateHash','0'*64),('revision',2),('sources',['sunovels.com']),('verifiedAt',0),('independentRun','fixture-producer'),('runtimeVerified',False)]:
     with self.subTest(field=k),self.assertRaises(ValueError):require_staging(proof(dict(receipt,**{k:v})),b)
if __name__=='__main__':unittest.main()
