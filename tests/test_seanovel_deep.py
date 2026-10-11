"""Protocol-v2 and full-index fixtures; these are NOT live publication evidence."""
import base64,copy,hashlib,hmac,json,os,sys,threading,unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from test_seanovel_attestation import server_module as server,FAKE_KEY
import sea_attestation as client
from validate import build
TEXT='<article class="reader-content">'+''.join('<p>'+('نص رواية حقيقي في الاختبار فقط. '*30)+'</p>' for _ in range(4))+'</article>'
IDENTITY=hashlib.sha256(('seanovel.org:'+server.URL).encode()).hexdigest()
def complete_result(selectors):
 return dict(domain='seanovel.org',status='healthy',completeIndex=True,indexState='COMPLETE',verificationTier='ATTESTED_COMPLETE_INDEX',catalog=True,search=True,details=True,chapters=True,text=True,catalog_count=2,chapter_count=3,officialTotal=3,chapterPages=1,ordering='SOURCE_ID_ASCENDING',paragraphs=12,text_characters=3600,sampledTexts=3,identityHash=IDENTITY,indexHash='a'*64,sampleHashes=['b'*64]*3)
class Handler(server.handler):
 tamper=None
 def log_message(self,*args):pass
 def reply(self,status,data):
  if self.tamper and 'payload' in data:
   p=json.loads(base64.b64decode(data['payload']));self.tamper(p)
   raw=json.dumps(p,separators=(',',':')).encode();data={'payload':base64.b64encode(raw).decode(),'signature':hmac.new(FAKE_KEY.encode(),b'response-v2\n'+raw,hashlib.sha256).hexdigest()}
  super().reply(status,data)
class DeepAttestationTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.httpd=ThreadingHTTPServer(('127.0.0.1',0),Handler);cls.thread=threading.Thread(target=cls.httpd.serve_forever,daemon=True);cls.thread.start()
 @classmethod
 def tearDownClass(cls):cls.httpd.shutdown();cls.httpd.server_close();cls.thread.join()
 def setUp(self):
  Handler.tamper=None;self.env=patch.dict(os.environ,{'SEANOVEL_ATTESTATION_SECRET':FAKE_KEY});self.env.start()
  self.url=patch.object(client,'URL','http://127.0.0.1:%d/api/probe'%self.httpd.server_port);self.url.start()
  self.check=patch.object(server,'run_deep_checks',complete_result);self.check.start()
 def tearDown(self):self.check.stop();self.url.stop();self.env.stop();Handler.tamper=None
 def test_v2_verifies_full_index(self):
  r=client.check(build(2),deep=True);self.assertTrue(r['attestationVerified']);self.assertTrue(r['completeIndex'])
 def test_fresh_signed_missing_completeness_is_rejected(self):
  Handler.tamper=staticmethod(lambda p:p['result'].update(completeIndex=False))
  with self.assertRaises(ValueError):client.check(build(2),deep=True)
 def test_fresh_signed_total_mismatch_is_rejected(self):
  Handler.tamper=staticmethod(lambda p:p['result'].update(officialTotal=4))
  with self.assertRaises(ValueError):client.check(build(2),deep=True)
 def test_wrong_identity_is_rejected(self):
  Handler.tamper=staticmethod(lambda p:p['result'].update(identityHash='0'*64))
  with self.assertRaises(ValueError):client.check(build(2),deep=True)
 def test_wrong_nonce_revision_digest_or_timestamp_is_rejected(self):
  for key,value in [('nonce','0'*64),('revision',999),('candidateSha256','0'*64),('timestamp',0),('protocol',1)]:
   Handler.tamper=staticmethod(lambda p,k=key,v=value:p.update({k:v}))
   with self.subTest(key=key),self.assertRaises(ValueError):client.check(build(2),deep=True)
 def test_signed_blocked_result_is_verified_but_not_complete(self):
  self.check.stop();self.check=patch.object(server,'run_deep_checks',lambda s:dict(domain='seanovel.org',status='blocked',completeIndex=False,indexState='INTERRUPTED',failed_stage='chapters',upstream_http=403));self.check.start()
  r=client.check(build(2),deep=True);self.assertTrue(r['attestationVerified']);self.assertFalse(r['completeIndex']);self.assertEqual(r['status'],'blocked')
 def test_unapproved_deployment_is_rejected_before_post(self):
  with patch('sea_attestation.requests.post') as post:
   with self.assertRaises(ValueError):client.check(build(2),deep=True,endpoint='https://evil.vercel.app/api/probe')
   post.assert_not_called()
class CompleteIndexTest(unittest.TestCase):
 def setUp(self):
  self.book=dict(slug=server.SLUG,title_ar='تيرا نوفا',source_id=1481,description='Description',chapters_count=3,chapters=[dict(id=i,title='Chapter '+str(i)) for i in (1,2,3)])
  self.calls=[];self.mutate=None;self.canonical=True;self.text=TEXT
 def fetch(self,session,url,deadline=None):
  self.calls.append(url)
  if '/api/novels?' in url:return json.dumps([dict(slug=server.SLUG,title_ar='تيرا نوفا',source_id=1481)])
  if '/api/novel/' in url:
   book=copy.deepcopy(self.book)
   if self.mutate and self.calls.count(url)>1:self.mutate(book)
   return json.dumps(book)
  return ('<link rel="canonical" href="'+(url if self.canonical else server.BASE+'/novels/other/chapters/1')+'">')+self.text
 def run_probe(self):
  with patch.object(server,'fetch',self.fetch):return server.run_deep_checks({'text':'article.reader-content'})
 def test_complete_single_response_and_three_texts(self):
  r=self.run_probe();self.assertTrue(r['completeIndex']);self.assertEqual(r['chapter_count'],3);self.assertEqual(r['sampledTexts'],3);self.assertEqual(len(self.calls),6)
 def test_missing_total_duplicate_order_partial_or_foreign_identity_fails(self):
  original=copy.deepcopy(self.book)
  for mutation in [lambda b:b.pop('chapters_count'),lambda b:b.update(chapters_count=4),lambda b:b['chapters'].append(b['chapters'][0]),lambda b:b['chapters'].reverse(),lambda b:b.update(next_page=2),lambda b:b.update(slug='other')]:
   self.book=copy.deepcopy(original);mutation(self.book)
   self.assertFalse(self.run_probe()['completeIndex'])
 def test_changed_index_during_text_checks_fails(self):
  self.mutate=lambda b:b['chapters'][0].update(title='Changed')
  self.assertFalse(self.run_probe()['completeIndex'])
 def test_foreign_chapter_canonical_fails(self):
  self.canonical=False;self.assertFalse(self.run_probe()['completeIndex'])
 def test_challenge_or_empty_text_fails(self):
  for text in ['<div id="challenge-form"></div>'+TEXT,'<article class="reader-content"></article>']:
   self.text=text;self.assertFalse(self.run_probe()['completeIndex'])
if __name__=='__main__':unittest.main()
