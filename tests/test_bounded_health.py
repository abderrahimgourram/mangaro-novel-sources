"""Deterministic health-client counterexamples; fixtures are never live evidence."""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from bounded_health import probe, text_sample, ProbeError, checked_url
from monitor import check_source
from validate import build

DOMAIN = 'sunovels.com'
DETAIL = 'https://sunovels.com/novel/reverend-insanity'
# Registry order is not used to choose a fixture source.
RULES = next(s['selectors'] for s in build(2)['sources'] if s['domain'] == DOMAIN)
TEXT = '<div class="chapter-content">' + '<p>' + ('Meaningful sample paragraph. ' * 20) + ''.join('<p>' + 'Readable fixture text. '*30 + '</p>' for _ in range(5)) + '</div>'

class FixtureClient:
    def __init__(self, mode='healthy', pages=1):
        self.mode = mode; self.pages = pages; self.requests = []
    def close(self): pass
    def html(self, url):
        self.requests.append(url)
        if 'activeTab=' in url:
            page = int(url.rsplit('=', 1)[1]); number = page if self.mode != 'duplicate' else 0
            html = f'<ul class="chaptersList"><li><a href="/novel/reverend-insanity/chapter-{number}">Chapter {number}</a></li></ul><a aria-label="Page {self.pages}"></a>'
            if self.mode == 'missing': html = f'<ul class="chaptersList"></ul><a aria-label="Page {self.pages}"></a>'
            return BeautifulSoup(html, 'html.parser')
        if '/chapter-' in url:
            return BeautifulSoup('<div class="chapter-content"><p>Loading</p></div>' if self.mode == 'empty' else TEXT, 'html.parser')
        if '/search?' in url:
            target = '/novel/other' if self.mode == 'identity' else '/novel/reverend-insanity'
            return BeautifulSoup(f'<div class="list-item"><a href="{target}">Reverend Insanity</a></div>', 'html.parser')
        if url == DETAIL:
            return BeautifulSoup('<div class="main-head"><h1>Reverend Insanity</h1></div><p class="description">A meaningful fixture description of the book.</p>', 'html.parser')
        return BeautifulSoup('<div class="list-item"><a href="/novel/reverend-insanity">Reverend Insanity</a></div>', 'html.parser')

class BoundedNovelTest(unittest.TestCase):
    def test_partial_long_index_never_claims_full_count(self):
        client = FixtureClient(pages=1000)
        result = probe(DOMAIN, RULES, client=client)
        self.assertTrue(result['ok'])
        self.assertFalse(result['complete'])
        self.assertEqual(result['classification'], 'DEGRADED')
        self.assertEqual(result['chapterPages'], 2)
        self.assertEqual(result['observedChapterCount'], 2)
        self.assertIsNone(result['chapterCount'])
        self.assertEqual(result['indexState'], 'MORE_AVAILABLE')
    def test_unknown_total_remains_unknown_after_termination(self):
        result = probe(DOMAIN, RULES, client=FixtureClient())
        self.assertTrue(result['ok'])
        self.assertEqual(result['indexState'], 'UNKNOWN_TOTAL')
    def test_missing_or_duplicate_page_cannot_pass(self):
        for mode in ['missing', 'duplicate']:
            result = probe(DOMAIN, RULES, client=FixtureClient(mode, 100))
            self.assertFalse(result['ok'])
            self.assertEqual(result['operation'], 'chapters')
    def test_details_dependency_blocks_reader_after_invalid_identity(self):
        client = FixtureClient('identity')
        result = probe(DOMAIN, RULES, client=client)
        self.assertFalse(result['ok'])
        self.assertEqual(result['operation'], 'search')
        self.assertFalse(any('/chapter-' in u for u in client.requests))
    def test_zero_meaningful_text_fails(self):
        result = probe(DOMAIN, RULES, client=FixtureClient('empty'))
        self.assertFalse(result['ok'])
        self.assertEqual(result['operations']['text'], 'FAILED')
    def test_deep_budget_and_three_points(self):
        client = FixtureClient(pages=1000)
        result = probe(DOMAIN, RULES, deep=True, client=client)
        self.assertEqual(result['chapterPages'], 25)
        self.assertEqual(result['sampledTexts'], 3)
        self.assertFalse(result['complete'])
    def test_challenge_text_is_rejected(self):
        doc = BeautifulSoup('<div id="challenge-form">Verify</div>' + TEXT, 'html.parser')
        with self.assertRaises(ProbeError): text_sample(doc, RULES['text'])
    def test_foreign_chapter_or_credentials_are_rejected(self):
        for url in ['https://kolnovel.com/chapter/1', 'https://user:password@sunovels.com/chapter/1', 'http://sunovels.com/']:
            with self.assertRaises(ProbeError): checked_url(url, DOMAIN)
    def test_missing_attestation_secret_makes_no_network_request(self):
        source = next(s for s in build(2)['sources'] if s['domain'] == 'seanovel.org')
        with patch.dict(os.environ, {'SEANOVEL_ATTESTATION_SECRET': ''}):
            with patch('sea_attestation.check') as network:
                result = check_source(source, build(2), False)
                self.assertEqual(result['classification'], 'INSUFFICIENT_EVIDENCE')
                self.assertEqual(result['reason'], 'LOCAL_ATTESTATION_UNAVAILABLE')
                self.assertEqual(set(result['operations'].values()), {'SKIPPED'})
                self.assertEqual(result['sourceObservation'], 'UNVERIFIED')
                network.assert_not_called()
    def test_attested_sample_cannot_prove_official_total(self):
        source = next(s for s in build(2)['sources'] if s['domain'] == 'seanovel.org')
        with patch.dict(os.environ, {'SEANOVEL_ATTESTATION_SECRET': 'a'*64}), patch('sea_attestation.check', return_value={**{k:True for k in ['catalog','search','details','chapters','text']}, 'chapter_count':1000,'attestationVerified':True}):
            result = check_source(source, build(2), True)
        self.assertTrue(result['ok'])
        self.assertFalse(result['complete'])
        self.assertEqual(result['classification'], 'DEGRADED')


    def test_homepage_canonical_does_not_prove_work_identity(self):
        for wrong_title in [False, True]:
            client=FixtureClient(); original=client.html
            def html(url):
                doc=original(url)
                if url==DETAIL:
                    head=BeautifulSoup('<link rel="canonical" href="https://sunovels.com/">','html.parser')
                    doc.append(head.link)
                    if wrong_title:doc.h1.string='Unrelated novel'
                return doc
            client.html=html
            result=probe(DOMAIN,RULES,client=client)
            self.assertEqual(result['ok'],not wrong_title)
            if wrong_title:self.assertEqual(result['operation'],'details')
    def test_bridge_http_error_is_not_a_verified_source_failure(self):
        import requests
        source=next(s for s in build(2)['sources'] if s['domain']=='seanovel.org')
        response=requests.Response();response.status_code=503
        with patch.dict(os.environ,{'SEANOVEL_ATTESTATION_SECRET':'a'*64}),patch('sea_attestation.check',side_effect=requests.HTTPError(response=response)):
            result=check_source(source,build(2),False)
        self.assertTrue(result['unknown'])
        self.assertEqual(result['classification'],'INSUFFICIENT_EVIDENCE')
        self.assertEqual(set(result['operations'].values()),{'SKIPPED'})


    def test_unverified_bridge_result_cannot_pass(self):
        source=next(s for s in build(2)['sources'] if s['domain']=='seanovel.org')
        with patch.dict(os.environ,{'SEANOVEL_ATTESTATION_SECRET':'a'*64}),patch('sea_attestation.check',return_value={'status':'healthy','chapter_count':1000}):
            result=check_source(source,build(2),False)
        self.assertEqual(result['classification'],'INSUFFICIENT_EVIDENCE')
        self.assertTrue(result['unknown'])
        self.assertEqual(result['sourceObservation'],'UNVERIFIED')

if __name__ == '__main__': unittest.main()
