"""Only authenticated-current callers may preserve unchanged bundle members."""
import copy,hashlib,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from validate import build,require_health
class ScopedPublicationTest(unittest.TestCase):
 def setUp(self):
  self.current=build(2);self.candidate=copy.deepcopy(self.current);self.candidate['revision']=3
  self.source='cenele.com';self.candidate['sources'][1]['selectors']['text']='article.updated'
  digest=hashlib.sha256(json.dumps(self.candidate,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
  self.report=[dict(domain=self.source,rulesSha256=digest,completeIndex=True,**{op:True for op in ['catalog','search','details','chapters','text']})]
 def test_unchanged_seanovel_does_not_block_independent_source(self):require_health(self.report,self.candidate,current=self.current,source=self.source)
 def test_missing_baseline_cannot_bootstrap_scoped_feed(self):
  with self.assertRaises(ValueError):require_health(self.report,self.candidate,source=self.source)
 def test_unrelated_mapping_cannot_change(self):
  self.candidate['sources'][3]['selectors']['text']='article.other'
  with self.assertRaisesRegex(ValueError,'Unrelated'):require_health(self.report,self.candidate,current=self.current,source=self.source)
 def test_partial_index_fails(self):
  self.report[0]['completeIndex']=False
  with self.assertRaises(ValueError):require_health(self.report,self.candidate,current=self.current,source=self.source)
 def test_other_source_report_or_candidate_digest_fails(self):
  for change in [('domain','seanovel.org'),('rulesSha256','0'*64)]:
   report=copy.deepcopy(self.report);report[0][change[0]]=change[1]
   with self.assertRaises(ValueError):require_health(report,self.candidate,current=self.current,source=self.source)
 def test_genesis_still_requires_all_four_sources(self):
  with self.assertRaises(ValueError):require_health(self.report,self.candidate)
if __name__=='__main__':unittest.main()
