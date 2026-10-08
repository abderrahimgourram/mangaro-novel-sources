"""One bounded public sample per site. Logs counts/hashes only, never story text or HTML."""
import json, hashlib, re, time
from urllib.parse import urljoin, urlparse
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from validate import ROOT, build, validate, require
SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'MangaroNovelPrototype/0.1'
CONFIG = {x['domain']: x['selectors'] for x in build(2)['sources']}

def fetch(url, data=None):
    parsed = urlparse(url)
    require(parsed.scheme == 'https' and parsed.hostname in CONFIG and (parsed.port in (None, 443)) and (not parsed.username) and (not parsed.password))
    response = SESSION.post(url, data=data, timeout=(10, 25), allow_redirects=False, stream=True) if data else SESSION.get(url, timeout=(10, 25), allow_redirects=False, stream=True)
    try:
        response.raise_for_status()
        chunks = []
        size = 0
        for chunk in response.iter_content(8192):
            size += len(chunk)
            require(size <= 8 * 1024 * 1024)
            chunks.append(chunk)
        response._content = b''.join(chunks)
        response._content_consumed = True
        return response
    finally:
        response.close()

def html(url):
    return BeautifulSoup(fetch(url).text, 'html5lib')
SAMPLES = {'kolnovel.com': ('https://kolnovel.com/series/?order=update&page=1', 'https://kolnovel.com/?s=%D8%AF%D9%81%D8%A7%D8%B9', 'https://kolnovel.com/series/dungeon-defense-wn/'), 'cenele.com': ('https://cenele.com/cont/', 'https://cenele.com/?s=%D8%A7%D9%86%D8%B4%D8%A7%D8%A1&post_type=wp-manga', 'https://cenele.com/cont/create-heaven-riwya/'), 'sunovels.com': ('https://sunovels.com/library?page=0', 'https://sunovels.com/search?title=%D8%A7%D9%84%D9%82%D8%B3&page=0', 'https://sunovels.com/novel/reverend-insanity'), 'seanovel.org': ('https://seanovel.org/api/novels?sort=views', None, 'https://seanovel.org/novels/terra-nova-online-rise-of-the-strongest-player')}

def probe(domain, result):
    catalog, search, detail = SAMPLES[domain]
    rules = CONFIG[domain]
    result.update(domain=domain, catalog=False, search=False, details=False, chapters=False, text=False, checking='catalog')
    if domain == 'seanovel.org':
        entries = fetch(catalog).json()
        require(0 < len(entries) <= 1000)
        result['catalog'] = True
        result['checking'] = 'search'
        result['search'] = any(('تيرا' in x.get('title_ar', '') for x in entries))
        result['checking'] = 'details'
        item = fetch('https://seanovel.org/api/novel/' + detail.rsplit('/', 1)[1]).json()
        result['details'] = bool(item.get('description'))
        result['checking'] = 'chapters'
        chapters = item['chapters']
        result['chapters'] = bool(chapters)
        result.update(chapterCount=len({str(c['id']) for c in chapters}), chapterPages=1, completeIndex=True)
        chapter = detail + '/chapters/' + str(chapters[0]['id'])
    else:
        result['catalog'] = bool(html(catalog).select(rules['catalogCards']))
        result['checking'] = 'search'
        result['search'] = bool(html(search).select(rules['catalogCards']))
        result['checking'] = 'details'
        d = html(detail)
        result['details'] = bool(d.select_one(rules.get('description', '.description')))
        result['checking'] = 'chapters'
        urls = []
        pages = 0
        volume_counts = {}
        if domain == 'kolnovel.com':
            links = list(reversed(d.select('.eplister li[data-id] > a')))
            urls = [urljoin(detail, a['href']) for a in links]
            pages = 1
        elif domain == 'sunovels.com':
            page = 0
            while page < 2000:
                doc = html(detail + '?activeTab=chapters&page=' + str(page))
                links = doc.select('ul.chaptersList a')
                new = [urljoin(detail, a['href']) for a in links if urljoin(detail, a['href']) not in urls]
                require(new, 'Chapter pagination made no progress')
                urls += new
                pages += 1
                total = max([int(re.search('\\d+', a.get('aria-label', ''))[0]) for a in doc.select('a[aria-label^=Page]')] or [page + 1])
                if page + 1 >= total:
                    break
                page += 1
                time.sleep(0.25)
            else:
                raise AssertionError('Incomplete chapter pagination')
        else:
            script = d.select_one('#nhv-novel-single-v2-js-extra').decode_contents()
            config = json.loads(re.search('var nhvNovelV2 = (\\{.*?\\});', script, re.S)[1])
            fields = {'action': 'nhv_manga_single_chapters_page', 'nonce': config['chaptersNonce'], 'manga_id': config['postId'], 'volume': '-1', 'page': '1', 'per_page': '50', 'order': 'asc', 'meta_only': '1'}
            meta = fetch('https://cenele.com/wp-admin/admin-ajax.php', fields).json()
            require(meta.get('success') and meta.get('volumes'))
            fields.pop('meta_only')
            for volume in meta['volumes']:
                fields['volume'] = str(volume['num'])
                seen = 0
                for page in range(1, 2001):
                    fields['page'] = str(page)
                    response = fetch('https://cenele.com/wp-admin/admin-ajax.php', fields).json()
                    require(response.get('success') and isinstance(response.get('has_more'), bool))
                    links = BeautifulSoup(response['html'], 'html5lib').select('.wp-manga-chapter a')
                    new = [urljoin(detail, a['href']) for a in links if urljoin(detail, a['href']) not in urls]
                    if response['has_more']:
                        require(new, 'Chapter pagination made no progress')
                    urls += new
                    seen += len(new)
                    pages += 1
                    if not response['has_more']:
                        break
                    time.sleep(0.25)
                else:
                    raise AssertionError('Incomplete volume pagination')
                label = volume.get('label', '')
                if label not in ('', 'بدون مجلدات', 'بدون مجلد', 'الفصول'):
                    volume_counts[label] = seen
        require(urls)
        result.update(chapters=True, chapterCount=len(set(urls)), chapterPages=pages, completeIndex=True, volumes=volume_counts)
        chapter = urls[0]
    result['checking'] = 'text'
    d = html(chapter)
    styles = [s.decode_contents() for s in d.select('style')]
    container = d.select_one(rules['text'])
    require(container is not None)
    for node in container.select('script,style,iframe,form,nav,.d-none,.sr-only,[hidden],[aria-hidden=true]'):
        node.decompose()
    for style in styles:
        for selectors, declarations in re.findall('([^{}]+)\\{([^{}]+)}', style):
            if re.search('opacity\\s*:\\s*0(?:\\.0+)?\\s*(?:!important\\s*)?(?:;|$)|display\\s*:\\s*none|visibility\\s*:\\s*hidden', declarations):
                for selector in selectors.split(','):
                    if re.fullmatch('\\.[a-zA-Z_][a-zA-Z0-9_-]*', selector.strip()):
                        for node in container.select(selector.strip()):
                            if node.name is not None:
                                node.decompose()
    paragraphs = [p.get_text(' ', strip=True) for p in container.select('p') if p.get_text(strip=True)]
    size = sum(map(len, paragraphs))
    require(len(paragraphs) > 3 and size > 500)
    result.update(text=True, paragraphs=len(paragraphs), characters=size, sha256=hashlib.sha256('\n'.join(paragraphs).encode()).hexdigest())
    result.pop('checking', None)
    return result
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--source', choices=['all', *SAMPLES.keys()], default='all')
    args = parser.parse_args()
    candidate = validate(json.loads(args.bundle.read_text())) if args.bundle else build(2)
    CONFIG = {x['domain']: x['selectors'] for x in candidate['sources']}
    digest = hashlib.sha256(json.dumps(candidate, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    report = []
    for domain in SAMPLES:
        if args.source != 'all' and domain != args.source:
            continue
        result = {'rulesSha256': digest}
        try:
            probe(domain, result)
        except Exception as error:
            result.update(healthy=False, failedStage=result.pop('checking', 'unknown'), error=type(error).__name__)
            response = getattr(error, 'response', None)
            if response is not None:
                result['httpStatus'] = response.status_code
        report.append(result)
        time.sleep(1)
    (ROOT / 'health.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    for item in report:
        print(item)
    raise SystemExit(0 if all((all((item.get(key) for key in ['catalog', 'search', 'details', 'chapters', 'text'])) for item in report)) else 1)
