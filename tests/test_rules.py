import base64,copy,hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from validate import ROOT,build,validate,require_health,DOMAINS
from verify import manifest_bytes,verify_pair,verify_envelope
from prepare import prepare

FIXTURE=ROOT/'tests/fixtures'
class RuleSecurityTest(unittest.TestCase):
 def setUp(self):
  self.manifest=(FIXTURE/'manifest.json').read_bytes()
  self.envelope=(FIXTURE/'rules-2.json').read_bytes()
 def test_android_pinned_key_verifies_real_pair(self):
  bundle=verify_pair(self.manifest,self.envelope)
  self.assertEqual(bundle['revision'],2)
  self.assertEqual(len(bundle['sources']),4)
 def test_manifest_metadata_tamper_is_rejected(self):
  for field,value in [('revision',3),('engineVersion',1),('sha256','0'*64),('envelopePath','published/rules-3.json')]:
   data=json.loads(self.manifest);data[field]=value
   with self.subTest(field=field),self.assertRaises(ValueError):verify_pair(json.dumps(data).encode(),self.envelope)
 def test_tampered_envelope_and_rehashed_payload_are_rejected(self):
  with self.assertRaises(ValueError):verify_pair(self.manifest,self.envelope+b' ')
  data=json.loads(self.envelope);payload=base64.b64decode(data['payload']).replace(b'kolnovel.com',b'foreign.com')
  data['payload']=base64.b64encode(payload).decode();data['sha256']=hashlib.sha256(payload).hexdigest()
  with self.assertRaises(ValueError):verify_envelope(json.dumps(data).encode())
 def test_untrusted_and_incompatible_schemas_fail(self):
  for change in [lambda x:x.update(engineVersion=3),lambda x:x.update(revision=True),lambda x:x.update(revision=2147483648),lambda x:x['sources'].append(x['sources'][0]),lambda x:x['sources'][0].update(domain='evil.test'),lambda x:x['sources'][1].update(id='novel.kolnovel'),lambda x:x['sources'][0]['selectors'].update(text='body'),lambda x:x['sources'][0]['selectors'].update(text=True),lambda x:x['sources'][0]['selectors'].update(script='eval(code)')]:
   data=build(2);change(data)
   with self.assertRaises((ValueError,TypeError)):validate(data)
 def test_manifest_domain_and_numeric_types_are_strict(self):
  for value in ['https://evil.test/rules-2.json','published/../rules-2.json','published/rules-1.json']:
   data=json.loads(self.manifest);data['envelopePath']=value
   with self.assertRaises(ValueError):manifest_bytes(data)
  data=json.loads(self.manifest);data['revision']='2'
  with self.assertRaises(ValueError):manifest_bytes(data)
 def test_empty_staging_never_succeeds(self):
  with tempfile.TemporaryDirectory() as directory:
   result=subprocess.run([sys.executable,str(ROOT/'tools/verify.py'),'--directory',directory],capture_output=True)
   self.assertNotEqual(result.returncode,0)
 def test_rollback_requires_new_revision_and_keeps_prior_artifacts(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);published=root/'published';published.mkdir()
   (published/'manifest.json').write_bytes(self.manifest);(published/'rules-2.json').write_bytes(self.envelope)
   with patch('prepare.ROOT',root):
    with self.assertRaises(ValueError):prepare(2,2)
    with self.assertRaises(ValueError):prepare(1,2)
    candidate=prepare(3,2)
    self.assertEqual(candidate['revision'],3)
    self.assertEqual(candidate['sources'],verify_envelope(self.envelope)['sources'])
    with self.assertRaises((ValueError,FileNotFoundError)):prepare(3,999)
   self.assertEqual((published/'manifest.json').read_bytes(),self.manifest)
   self.assertEqual((published/'rules-2.json').read_bytes(),self.envelope)
 def test_broken_candidate_cannot_be_packaged(self):
  from package import package
  candidate=build(3);candidate['sources'][0]['selectors']['text']='html'
  with self.assertRaises(ValueError):package(candidate,Path('/nonexistent-key'))
 def test_failed_or_stale_health_cannot_authorize_signing(self):
  bundle=build(2);digest=hashlib.sha256(json.dumps(bundle,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
  report=[dict(domain=domain,rulesSha256=digest,catalog=True,search=True,details=True,chapters=True,text=True) for domain in DOMAINS.values()]
  require_health(report,bundle)
  for mutation in [lambda x:x[0].update(text=False),lambda x:x[0].update(rulesSha256='0'*64),lambda x:x.pop(),lambda x:x[1].update(domain=x[0]['domain'])]:
   bad=copy.deepcopy(report);mutation(bad)
   with self.assertRaises(ValueError):require_health(bad,bundle)
 def test_loading_placeholder_is_not_successful_chapter_text(self):
  import health
  from bs4 import BeautifulSoup
  from types import SimpleNamespace
  def public_response(url,data=None):
   value=[{'title_ar':'تيرا'}] if '/api/novels?' in url else {'description':'Test metadata','chapters':[{'id':1}]}
   return SimpleNamespace(json=lambda:value)
  result={}
  with patch('health.fetch',public_response),patch('health.html',return_value=BeautifulSoup('<article class="reader-content"><p>Loading</p></article>','html.parser')):
   with self.assertRaises(ValueError):health.probe('seanovel.org',result)
  self.assertTrue(result['chapters'])
  self.assertFalse(result['text'])
 def test_health_cannot_request_foreign_domains_or_credentials(self):
  import health
  with patch.object(health.SESSION,'get') as network:
   for url in ['https://evil.test/','http://seanovel.org/','https://user:password@seanovel.org/','https://seanovel.org:8443/']:
    with self.assertRaises(ValueError):health.fetch(url)
   network.assert_not_called()

if __name__=='__main__':unittest.main()
