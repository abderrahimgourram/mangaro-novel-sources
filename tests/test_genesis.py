"""Counterexamples only: these fixtures are never production authority."""
import base64,copy,json,os,sys,time,unittest
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from genesis import native_gate,compare_health,owner_gate,sha
from operations import GitJournal,OperationBlocked
from validate import ROOT,build

class GenesisTest(unittest.TestCase):
 def evidence(self):
  return dict(method='OWNER_ATTESTED_LOCAL_EMULATOR',consumerCommit='a'*40,manifestSha256=sha(b'manifest'),envelopeSha256=sha(b'envelope'),keySha256=sha((ROOT/'keys/rules-public.der').read_bytes()),resultSha256='b'*64,passed=7,failed=0,emulatorSerial='emulator-5554',androidApi=30,performedAt=int(time.time()))
 def test_native_evidence_is_explicit_operator_attestation_bound_to_exact_bytes(self):
  native_gate(self.evidence(),b'manifest',b'envelope')
  for key,value in [('method','SIMULATED'),('consumerCommit',''),('manifestSha256','0'*64),('envelopeSha256','0'*64),('keySha256','0'*64),('resultSha256',''),('passed',6),('failed',1),('performedAt',0),('emulatorSerial','physical-phone')]:
   with self.subTest(field=key),self.assertRaises((ValueError,TypeError)):native_gate(dict(self.evidence(),**{key:value}),b'manifest',b'envelope')
 def test_missing_native_data_cannot_authorize_genesis(self):
  with self.assertRaises(ValueError):native_gate({},b'manifest',b'envelope')
 def test_owner_review_and_main_are_required_without_enabling_auto(self):
  env=dict(GITHUB_REPOSITORY='abderrahimgourram/mangaro-novel-sources',GITHUB_REF='refs/heads/main',GITHUB_ACTOR='abderrahimgourram',INITIAL_RELEASE='true',PUBLICATION_SOURCE='',MANGARO_AUTOPUBLISH_ENABLED='false')
  with patch.dict(os.environ,env):owner_gate()
  for key,value in [('GITHUB_REF','refs/heads/unreviewed'),('GITHUB_ACTOR','outsider'),('INITIAL_RELEASE','false'),('MANGARO_AUTOPUBLISH_ENABLED','true'),('PUBLICATION_SOURCE','cenele.com')]:
   with self.subTest(field=key),patch.dict(os.environ,dict(env,**{key:value})),self.assertRaises(ValueError):owner_gate()
 def reports(self,candidate):
  import hashlib
  digest=sha(json.dumps(candidate,ensure_ascii=False,separators=(',',':')).encode())
  return [dict(domain=s['domain'],rulesSha256=digest,completeIndex=True,attestationVerified=True,identityHash='a'*64,indexHash='b'*64,verifiedChapterCount=3,**{op:True for op in ['catalog','search','details','chapters','text']}) for s in candidate['sources']]
 def test_independent_acceptance_requires_complete_exact_identity_and_index(self):
  candidate=build(4,['novel.kolnovel','novel.cenele','novel.seanovel']);first=self.reports(candidate)
  compare_health(candidate,first,copy.deepcopy(first))
  for key,value in [('identityHash','c'*64),('indexHash','c'*64),('verifiedChapterCount',2),('completeIndex',False),('text',False)]:
   second=copy.deepcopy(first);second[0][key]=value
   with self.subTest(field=key),self.assertRaises(ValueError):compare_health(candidate,first,second)
 def test_journal_genesis_has_no_fabricated_current_or_previous_revision(self):
  calls=[]
  def api(method,path,data=None):
   calls.append((method,path,data));return {'sha':'tree' if path.endswith('trees') else 'commit' if path.endswith('commits') else 'blob'}
  journal=GitJournal(api,'abderrahimgourram/mangaro-novel-sources',lambda x:x,lambda x:x)
  state=dict(purpose='SOURCE_OPERATIONS_V1',repository='abderrahimgourram/mangaro-novel-sources',sources={},pendingGenesis={'revision':4,'pairHash':'a'*64})
  journal.initialize(state)
  commit=next(data for _,path,data in calls if path.endswith('commits'))
  self.assertEqual(commit['parents'],[]);self.assertNotIn('lastKnownGood',json.dumps(state))
  self.assertEqual(calls[-1][2]['ref'],'refs/heads/source-operations-state')
  with self.assertRaises(OperationBlocked):journal.initialize(state)
 def test_concurrent_journal_initialization_never_overwrites_existing_ref(self):
  def api(method,path,data=None):
   if path.endswith('refs'):raise OperationBlocked('REF_ALREADY_EXISTS')
   return {'sha':'new'}
  journal=GitJournal(api,'abderrahimgourram/mangaro-novel-sources',lambda x:x,lambda x:x)
  with self.assertRaises(OperationBlocked):journal.initialize(dict(purpose='SOURCE_OPERATIONS_V1',repository='abderrahimgourram/mangaro-novel-sources',sources={},pendingGenesis={'revision':4}))
  self.assertIsNone(journal.head)
 def test_journal_cannot_initialize_from_fabricated_healthy_source_history(self):
  api=Mock();journal=GitJournal(api,'abderrahimgourram/mangaro-novel-sources',lambda x:x,lambda x:x)
  with self.assertRaises(OperationBlocked):journal.initialize(dict(purpose='SOURCE_OPERATIONS_V1',repository='abderrahimgourram/mangaro-novel-sources',sources={'cenele.com':{'lastKnownGood':{}}},pendingGenesis={'revision':4}))
  api.assert_not_called()
if __name__=='__main__':unittest.main()

class PublicationOrderingTest(unittest.TestCase):
 def execute_fixture(self,asset_failure=False):
  import runpy,tempfile,subprocess,shutil
  import validate,verify
  candidate=build(4,['novel.kolnovel','novel.cenele','novel.seanovel'])
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);stage=root/'staging';stage.mkdir()
   (stage/'manifest.json').write_text('{}');(stage/'rules-4.json').write_bytes(b'fixture-only');(stage/'acceptance.json').write_text('{}')
   report=GenesisTest().reports(candidate);(root/'health.json').write_text(json.dumps(report));calls=[]
   def run(command,**kwargs):
    calls.append(tuple(command))
    if tuple(command[:3])==('gh','release','view'):return subprocess.CompletedProcess(command,1,b'',b'release not found')
    if tuple(command[:3])==('gh','release','download'):
     target=Path(command[command.index('--dir')+1]);shutil.copy2(stage/'manifest.json',target/'manifest.json');shutil.copy2(stage/'rules-4.json',target/'rules-4.json')
    return subprocess.CompletedProcess(command,0)
   def public_asset(*args):
    calls.append(('VERIFY_PUBLIC_IMMUTABLE',))
    if asset_failure:raise ValueError('fixture network failure')
    return candidate
   env=dict(RULE_REVISION='4',GITHUB_REPOSITORY='abderrahimgourram/mangaro-novel-sources',GITHUB_SHA='a'*40,PUBLICATION_SOURCE='',GENESIS_RESERVATION_HASH='')
   with patch.dict(os.environ,env),patch.object(validate,'ROOT',root),patch.object(validate,'require_staging'),patch.object(verify,'verify_pair',return_value=candidate),patch.object(verify,'verify_public_envelope',side_effect=public_asset),patch.object(verify,'verify_public_feed',return_value=candidate),patch('subprocess.run',side_effect=run),patch('time.sleep'):
    if asset_failure:
     with self.assertRaisesRegex(ValueError,'CURRENT was not advanced'):runpy.run_path(str(ROOT/'tools/publish.py'))
     self.assertFalse((root/'published/v2/manifest.json').exists())
    else:runpy.run_path(str(ROOT/'tools/publish.py'))
   return calls
 def test_public_immutable_is_verified_before_manifest_commit(self):
  calls=self.execute_fixture()
  pushes=[i for i,c in enumerate(calls) if c[:2]==('git','push')]
  verified=calls.index(('VERIFY_PUBLIC_IMMUTABLE',))
  self.assertEqual(len(pushes),2);self.assertLess(pushes[0],verified);self.assertLess(verified,pushes[1])
 def test_failed_public_asset_verification_preserves_current(self):
  calls=self.execute_fixture(True)
  self.assertEqual(sum(c[:2]==('git','push') for c in calls),1)
  self.assertEqual(calls.count(('VERIFY_PUBLIC_IMMUTABLE',)),6)
