"""Deterministic counterexamples; never publication or live completeness evidence."""
import sys,unittest,threading,time
from unittest.mock import patch
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from bounded_health import probe,Client
from validate import build

DETAIL='https://kolnovel.com/series/dungeon-defense-wn/'
RULES=next(s['selectors'] for s in build(2)['sources'] if s['domain']=='kolnovel.com')
def chapter(i):return 'https://kolnovel.com/fixture-'+str(i)+'/'

class ChainClient:
    def __init__(self,mode='complete'):self.mode=mode;self.metadata=[];self.details=0
    def close(self):pass
    def html(self,url):
        if url==DETAIL:
            self.details+=1
            ids=[3,1] if self.mode=='missing' else [3,2,1]
            if self.mode=='duplicate':ids=[3,2,2]
            changed='Changed' if self.mode=='changed' and self.details>1 else 'Chapter'
            raw='<h1 class="entry-title">Dungeon Defense</h1><div class="sersys" itemprop="description">Meaningful deterministic description of this fixture.</div><section class="epcheck"><div class="lastend"><a href="'+chapter(1)+'"><span class="epcurfirst">First</span></a><a href="'+chapter(3)+'"><span class="epcurlast">Last</span></a></div><div class="eplister">'
            raw+=''.join('<li data-id="'+str(i)+'"><a href="'+chapter(i)+'"><div class="epl-title">'+changed+str(i)+'</div></a></li>' for i in ids)+'</div></section>'
        elif '/fixture-' in url:
            raw='<div id="kol_content">'+''.join('<p>'+'Meaningful text in deterministic regression fixtures. '*30+'</p>' for _ in range(5))+'</div>'
        else:raw='<article class="maindet"><a href="'+DETAIL+'">Dungeon Defense</a></article>'
        return BeautifulSoup(raw,'html.parser')
    def chapter_metadata(self,url):
        self.metadata.append(url);i=int(url.rstrip('/').rsplit('-',1)[1])
        owner=DETAIL if self.mode!='foreign' else 'https://kolnovel.com/series/other/'
        raw='<link rel="canonical" href="'+url+'"><article id="post-'+str(i)+'"><div class="ts-breadcrumb"><a href="'+owner+'">Owner</a></div><div class="kol-chapter-bar">'
        if i<3:raw+='<a rel="next" href="'+chapter(i if self.mode=='cycle' else i+1)+'">Next</a>'
        if i>1:raw+='<a rel="prev" href="'+chapter(i-1)+'">Previous</a>'
        return BeautifulSoup(raw+'</div></article>','html.parser')

class IndexEvidenceTest(unittest.TestCase):
    def test_closed_chain_proves_source_index_without_inventing_official_total(self):
        client=ChainClient();r=probe('kolnovel.com',RULES,deep=True,acceptance=True,client=client)
        self.assertTrue(r['complete']);self.assertIsNone(r['chapterCount'])
        self.assertEqual(r['verifiedChapterCount'],3);self.assertEqual(len(client.metadata),3)
        self.assertEqual(r['completenessBasis'],'VERIFIED_CLOSED_CHAPTER_CHAIN')
    def test_routine_does_not_launch_expensive_chain_verification(self):
        client=ChainClient();r=probe('kolnovel.com',RULES,deep=True,client=client)
        self.assertFalse(r['complete']);self.assertEqual(client.metadata,[])
    def test_missing_middle_cycle_foreign_owner_or_changed_index_cannot_pass(self):
        for mode in ['missing','cycle','foreign','changed','duplicate']:
            with self.subTest(mode=mode):self.assertFalse(probe('kolnovel.com',RULES,deep=True,acceptance=True,client=ChainClient(mode))['complete'])
    def test_acceptance_network_budget_is_separate_and_bounded(self):
        client=Client('kolnovel.com',True,True)
        try:self.assertEqual(client.remaining,600)
        finally:client.close()
        client=Client('kolnovel.com',True)
        try:self.assertEqual(client.remaining,48)
        finally:client.close()
    def test_metadata_requests_are_bounded_and_preserve_index_order(self):
        lock=threading.Lock();active=0;peak=0
        def read(worker,url):
            nonlocal active,peak
            with lock:active+=1;peak=max(peak,active)
            time.sleep(.01)
            with lock:active-=1
            self.assertEqual(worker.remaining,1)
            self.assertEqual(worker.deadline,client.deadline)
            return url
        client=Client('kolnovel.com',True,True)
        try:
            urls=[chapter(i) for i in range(7)]
            with patch.object(Client,'chapter_metadata',read):
                self.assertEqual(list(client.chapter_metadata_batch(urls)),urls)
                self.assertLessEqual(peak,4);self.assertGreaterEqual(peak,1)
                self.assertEqual(client.remaining,593)
                client.remaining=1
                with self.assertRaisesRegex(Exception,'PROBE_BUDGET_EXHAUSTED'):
                    list(client.chapter_metadata_batch(urls))
        finally:client.close()

if __name__=='__main__':unittest.main()
