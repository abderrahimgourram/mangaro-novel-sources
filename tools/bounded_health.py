"""Bounded novel health sampling. Existing rules and SeaNovel protocol remain unchanged."""
import hashlib
import json
import re
import time
import unicodedata
from urllib.parse import urljoin, urlsplit
import requests
from bs4 import BeautifulSoup
from health import SAMPLES

class ProbeError(Exception):
    def __init__(self, code, classification='DEGRADED'):
        super().__init__(code)
        self.code = code
        self.classification = classification


def require(value, code):
    if not value:
        raise ProbeError(code)


def normalized_url(url):
    return url.split('#', 1)[0].split('?', 1)[0].rstrip('/')


def checked_url(url, domain):
    parsed = urlsplit(url)
    require(parsed.scheme == 'https' and parsed.hostname == domain and parsed.port in (None, 443)
            and not parsed.username and not parsed.password, 'SOURCE_ISOLATION_FAILED')
    return url


class Client:
    def __init__(self, domain, deep=False):
        self.domain = domain
        self.remaining = 48 if deep else 12
        self.deadline = time.monotonic() + (180 if deep else 65)
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'MangaroNovelPrototype/0.1'
    def fetch(self, url, data=None):
        checked_url(url, self.domain)
        if self.remaining <= 0 or time.monotonic() >= self.deadline:
            raise ProbeError('PROBE_BUDGET_EXHAUSTED', 'INSUFFICIENT_EVIDENCE')
        self.remaining -= 1
        try:
            with self.session.request('POST' if data else 'GET', url, data=data, timeout=(5, 10),
                                      allow_redirects=False, stream=True) as response:
                if response.status_code in (403, 429):
                    raise ProbeError('PROTECTED_UPSTREAM_RESPONSE', 'BLOCKED_BY_CHALLENGE')
                if response.status_code >= 500:
                    raise ProbeError('UPSTREAM_TEMPORARY_ERROR', 'TRANSIENT_NETWORK_ERROR')
                if response.status_code in (404, 410):
                    raise ProbeError('UPSTREAM_NOT_FOUND', 'UNAVAILABLE')
                require(response.status_code == 200, 'REDIRECT_OR_INVALID_RESPONSE')
                body = bytearray()
                for chunk in response.iter_content(8192):
                    body.extend(chunk)
                    require(len(body) <= 8 * 1024 * 1024, 'BODY_LIMIT_EXCEEDED')
                    if time.monotonic() >= self.deadline:
                        raise ProbeError('PROBE_BUDGET_EXHAUSTED', 'INSUFFICIENT_EVIDENCE')
                raw = bytes(body).decode(response.encoding or 'utf-8', 'strict')
                if re.search(r'(?i)<title[^>]*>\s*(just a moment|attention required|access denied)|id=["\x27](challenge-form|cf-wrapper)|cf-browser-verification', raw):
                    raise ProbeError('CHALLENGE_HTML', 'BLOCKED_BY_CHALLENGE')
                require(bool(raw.strip()), 'EMPTY_RESPONSE')
                return raw
        except (requests.Timeout, requests.ConnectionError):
            raise ProbeError('NETWORK_ERROR', 'TRANSIENT_NETWORK_ERROR') from None
        except requests.RequestException:
            raise ProbeError('TRANSPORT_ERROR', 'TRANSIENT_NETWORK_ERROR') from None
    def html(self, url):
        return BeautifulSoup(self.fetch(url), 'html5lib')
    def close(self):
        self.session.close()


def text_sample(doc, selector):
    require(not doc.select('#challenge-form,.challenge-running,#cf-wrapper'), 'CHALLENGE_HTML')
    container = doc.select_one(selector)
    require(container is not None, 'TEXT_CONTAINER_MISSING')
    styles = [s.decode_contents() for s in doc.select('style')]
    for node in list(container.select('script,style,iframe,form,nav,.d-none,.sr-only,[hidden],[aria-hidden=true]')):
        node.decompose()
    for style in styles:
        for selectors, declarations in re.findall(r'([^{}]+)\{([^{}]+)}', style):
            if re.search(r'opacity\s*:\s*0(?:\.0+)?\s*(?:!important\s*)?(?:;|$)|display\s*:\s*none|visibility\s*:\s*hidden', declarations):
                for selector in selectors.split(','):
                    if re.fullmatch(r'\.[a-zA-Z_][a-zA-Z0-9_-]*', selector.strip()):
                        for node in list(container.select(selector.strip())):
                            node.decompose()
    paragraphs = [unicodedata.normalize('NFC', p.get_text(' ', strip=True)) for p in container.select('p') if p.get_text(strip=True)]
    joined = '\n'.join(paragraphs)
    require(len(paragraphs) > 3 and len(joined) > 500 and sum(c.isalpha() for c in joined) > 250, 'INVALID_CHAPTER_TEXT')
    require(not any(s in joined.lower() for s in ['cf-browser-verification', 'verify you are human', 'enable javascript and cookies']), 'CHALLENGE_TEXT')
    return {'paragraphs': len(paragraphs), 'characters': len(joined), 'textSha256': hashlib.sha256(joined.encode()).hexdigest()}


def chapter_links(doc, selector, detail, domain):
    links = [checked_url(urljoin(detail, a['href']), domain) for a in doc.select(selector) if a.get('href')]
    require(len(set(links)) == len(links), 'DUPLICATE_CHAPTER_IDENTITIES')
    return links


def probe(domain, rules, deep=False, client=None):
    operations = {k: 'SKIPPED' for k in ['catalog', 'search', 'identity', 'details', 'chapters', 'pagination', 'text']}
    result = {'operations': operations, 'ok': False, 'complete': False,
              'classification': 'INSUFFICIENT_EVIDENCE', 'evidence': 'BOUNDED_NOVEL_SAMPLE'}
    stage = 'catalog'
    client = client or Client(domain, deep)
    try:
        if domain not in SAMPLES or domain == 'seanovel.org':
            raise ProbeError('UNSUPPORTED_SOURCE_TRANSPORT', 'INSUFFICIENT_EVIDENCE')
        catalog, search, detail = SAMPLES[domain]
        doc = client.html(catalog)
        cards = doc.select(rules['catalogCards'])
        require(bool(cards), 'EMPTY_CATALOGUE')
        operations[stage] = 'PASS'
        stage = 'search'
        found = client.html(search).select(rules['catalogCards'])
        anchors = [a for card in found for a in ([card] if card.name == 'a' else card.select('a[href]'))]
        matched = [a for a in anchors if normalized_url(urljoin(search, a.get('href', ''))) == normalized_url(detail)]
        require(matched, 'SEARCH_IDENTITY_MISMATCH')
        expected_title = next((a.get('title') or a.get_text(' ', strip=True) or (a.select_one('img').get('alt', '') if a.select_one('img') else '') for a in matched if a.get('title') or a.get_text(strip=True) or a.select_one('img') and a.select_one('img').get('alt')), '')
        operations[stage] = 'PASS'
        stage = 'details'
        doc = client.html(detail)
        canonical = doc.select_one('link[rel=canonical]')
        if canonical:
            canonical_url = normalized_url(canonical.get('href', ''))
            # Sunovels supplies a static homepage canonical; it is not a work identifier.
            if canonical_url != 'https://' + domain:
                require(canonical_url == normalized_url(detail), 'DETAILS_IDENTITY_MISMATCH')
        title = doc.select_one(rules.get('detailsTitle', rules.get('originalTitle', 'h1')))
        require(title is not None and bool(title.get_text(strip=True)), 'DETAILS_TITLE_MISSING')
        if expected_title:
            actual_title = unicodedata.normalize('NFC', title.get_text(' ', strip=True)).casefold()
            expected = unicodedata.normalize('NFC', expected_title).casefold()
            slug_title = urlsplit(detail).path.rsplit('/', 1)[-1].replace('-', ' ').casefold()
            require(expected in actual_title or domain == 'sunovels.com' and actual_title == slug_title, 'DETAILS_TITLE_IDENTITY_MISMATCH')
        description = doc.select_one(rules['description'])
        require(description is not None and len(description.get_text(' ', strip=True)) >= 20, 'DESCRIPTION_MISSING')
        operations[stage] = operations['identity'] = 'PASS'
        stage = 'chapters'
        urls = []
        visited = set()
        more = False
        official_total = None
        terminated = False
        max_pages = 25 if deep else 2
        pages = 0
        def add(links):
            require(bool(links) and not visited.intersection(links), 'REPEATED_OR_MISSING_CHAPTER_PAGE')
            visited.update(links); urls.extend(links)
        if domain == 'kolnovel.com':
            add(chapter_links(doc, '.eplister li[data-id] > a', detail, domain))
            pages = 1; terminated = True
            total_node = doc.select_one('[data-total-chapters]')
            if total_node:
                official_total = int(total_node['data-total-chapters'])
            # No inferred total from the number of HTML rows.
        elif domain == 'sunovels.com':
            declared_pages = None
            for page in range(max_pages):
                page_doc = client.html(detail + '?activeTab=chapters&page=' + str(page))
                add(chapter_links(page_doc, 'ul.chaptersList a', detail, domain)); pages += 1
                totals = [int(re.search(r'\d+', a.get('aria-label', ''))[0]) for a in page_doc.select('a[aria-label^=Page]') if re.search(r'\d+', a.get('aria-label', ''))]
                total_pages = max(totals) if totals else None
                if declared_pages is not None:
                    require(total_pages == declared_pages, 'PAGINATION_TOTAL_CHANGED')
                declared_pages = total_pages
                next_link = page_doc.select_one('a[rel=next], a[aria-label=Next]')
                more = bool(next_link) or total_pages is not None and page + 1 < total_pages
                if not more:
                    terminated = total_pages is not None
                    break
            total_node = page_doc.select_one('[data-total-chapters]')
            if total_node:
                official_total = int(total_node['data-total-chapters'])
        else:
            script = doc.select_one('#nhv-novel-single-v2-js-extra')
            require(script is not None, 'CHAPTER_CONFIGURATION_MISSING')
            match = re.search(r'var nhvNovelV2 = (\{.*?\});', script.decode_contents(), re.S)
            require(match is not None, 'CHAPTER_CONFIGURATION_INVALID')
            config = json.loads(match[1])
            fields = {'action': 'nhv_manga_single_chapters_page', 'nonce': config['chaptersNonce'],
                      'manga_id': config['postId'], 'volume': '-1', 'page': '1', 'per_page': '50', 'order': 'asc', 'meta_only': '1'}
            endpoint = 'https://' + domain + '/wp-admin/admin-ajax.php'
            meta = json.loads(client.fetch(endpoint, fields))
            require(meta.get('success') and isinstance(meta.get('volumes'), list) and meta['volumes'], 'VOLUME_METADATA_INVALID')
            fields.pop('meta_only')
            volumes = meta['volumes']
            counts = [v.get('count') for v in volumes]
            if all(type(count) is int and count >= 0 for count in counts):
                official_total = sum(counts)
            terminated = True
            for volume in volumes:
                before_volume = len(urls)
                fields['volume'] = str(volume['num'])
                for page in range(1, max_pages + 1):
                    if pages >= max_pages:
                        more = True; terminated = False; break
                    fields['page'] = str(page)
                    data = json.loads(client.fetch(endpoint, fields))
                    require(data.get('success') and type(data.get('has_more')) is bool, 'CHAPTER_PAGE_INVALID')
                    links = chapter_links(BeautifulSoup(data['html'], 'html5lib'), '.wp-manga-chapter a', detail, domain)
                    add(links); pages += 1
                    more = data['has_more']
                    if not more:
                        break
                if more:
                    terminated = False; break
                if type(volume.get('count')) is int:
                    require(len(urls)-before_volume == volume['count'], 'TRUNCATED_CHAPTER_INDEX')
            if type(meta.get('total')) is int:
                require(official_total is None or official_total == meta['total'], 'CHAPTER_TOTAL_CONFLICT')
                official_total = meta['total']
        require(urls, 'EMPTY_CHAPTER_INDEX')
        if official_total is not None:
            require(official_total >= len(urls), 'CHAPTER_TOTAL_CONFLICT')
            if terminated:
                require(official_total == len(urls), 'TRUNCATED_CHAPTER_INDEX')
        complete = terminated and official_total is not None and len(urls) == official_total
        operations['chapters'] = 'PASS' if complete else 'PARTIAL'
        operations['pagination'] = 'PASS' if terminated else 'PARTIAL'
        # Check numeric order when the source actually publishes numbers in its chapter paths.
        numbers = [re.search(r'(?:chapter-|chapter/)(\d+(?:\.\d+)?)', urlsplit(u).path) for u in urls]
        if all(numbers):
            values = [float(m[1]) for m in numbers]
            require(len(set(values)) == len(values) and (values == sorted(values) or values == sorted(values, reverse=True)), 'CHAPTER_ORDER_INVALID')
        stage = 'text'
        samples = list(dict.fromkeys([urls[0], urls[len(urls)//2], urls[-1]])) if deep else urls[:1]
        counts = []
        for chapter in samples:
            # Each request is bound to a URL produced by this work's own index.
            checked_url(chapter, domain)
            if domain == 'sunovels.com':
                require(chapter.startswith(detail.rstrip('/') + '/'), 'CHAPTER_OWNERSHIP_MISMATCH')
            chapter_doc = client.html(chapter)
            canonical = chapter_doc.select_one('link[rel=canonical]')
            if canonical:
                canonical_url = normalized_url(canonical.get('href', ''))
                if canonical_url != 'https://' + domain:
                    require(canonical_url == normalized_url(chapter), 'CHAPTER_IDENTITY_MISMATCH')
            counts.append(text_sample(chapter_doc, rules['text']))
        operations[stage] = 'PASS'
        result.update(ok=True, complete=complete, classification='HEALTHY' if complete else 'DEGRADED',
                      reason='VERIFIED_COMPLETE_INDEX' if complete else 'PARTIAL_OR_UNKNOWN_INDEX',
                      indexState='COMPLETE' if complete else 'MORE_AVAILABLE' if more else 'UNKNOWN_TOTAL',
                      observedChapterCount=len(urls), chapterCount=official_total if complete else None,
                      chapterPages=pages, sampledTexts=len(counts), needsDeep=False,
                      identityHash=hashlib.sha256((domain + ':' + normalized_url(detail)).encode()).hexdigest(),
                      indexHash=hashlib.sha256(json.dumps([normalized_url(u) for u in urls],separators=(',',':')).encode()).hexdigest(),
                      sampleHashes=[c['textSha256'] for c in counts])
    except (ProbeError, ValueError, KeyError, TypeError, UnicodeError) as error:
        classification = error.classification if isinstance(error, ProbeError) else 'DEGRADED'
        result.update(classification=classification, reason=error.code if isinstance(error, ProbeError) else 'REPRESENTATION_INVALID',
                      operation=stage, needsDeep=True, unknown=classification == 'INSUFFICIENT_EVIDENCE', indexState='INTERRUPTED')
        operations[stage] = 'FAILED'
    finally:
        client.close()
    return result
