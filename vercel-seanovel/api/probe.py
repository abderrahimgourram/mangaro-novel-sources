"""Mangaro SeaNovel: bounded, authenticated, scheduled five-stage health check."""
import base64, hashlib, hmac, json, os, re, time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

BASE = "https://seanovel.org"
SLUG = "terra-nova-online-rise-of-the-strongest-player"
URL = BASE + "/novels/" + SLUG
MAX_BODY = 8 * 1024 * 1024

def fetch(session, url, deadline=None):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "seanovel.org" or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise ValueError("Unsafe target")
    remaining = 20 if deadline is None else min(20, deadline-time.monotonic())
    if remaining <= 0:
        raise TimeoutError("Verification budget exhausted")
    with session.get(url, timeout=(8, remaining), allow_redirects=False, stream=True) as r:
        r.raise_for_status()
        content = bytearray()
        for chunk in r.iter_content(8192):
            content.extend(chunk)
            if len(content) > MAX_BODY:
                raise ValueError("Response limit")
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("Verification budget exhausted")
        return bytes(content).decode(r.encoding or "utf-8", "replace")

def run_checks(selectors=None):
    result={"domain":"seanovel.org","checked_at":datetime.now(timezone.utc).isoformat(),
            "catalog":False,"search":False,"details":False,"chapters":False,"text":False}
    stage="catalog"
    try:
        with requests.Session() as session:
            session.headers.update({"User-Agent":"MangaroNovelPrototype/0.1","Accept":"text/html,application/json"})
            entries=json.loads(fetch(session,BASE+"/api/novels?sort=views"))
            if not isinstance(entries,list) or not (0<len(entries)<=1000):
                raise ValueError("Invalid catalog")
            result["catalog"]=True
            result["catalog_count"]=len(entries)
            stage="search"
            if not any("تيرا" in item.get("title_ar","") for item in entries if isinstance(item,dict)):
                raise ValueError("Expected sample missing")
            result["search"]=True
            stage="details"
            item=json.loads(fetch(session,BASE+"/api/novel/"+SLUG))
            if not isinstance(item,dict) or not item.get("description"):
                raise ValueError("Invalid details")
            result["details"]=True
            stage="chapters"
            chapters=item.get("chapters")
            if not isinstance(chapters,list) or not chapters or "id" not in chapters[0]:
                raise ValueError("Invalid chapters")
            result["chapter_count"]=len({str(c["id"]) for c in chapters if "id" in c})
            result["chapters"]=True
            stage="text"
            raw=fetch(session,URL+"/chapters/"+str(chapters[0]["id"]))
            doc=BeautifulSoup(raw,"html5lib")
            style_text=[s.get_text() for s in doc.select("style")]
            container=doc.select_one((selectors or {"text":"article.reader-content"})["text"])
            if container is None:
                raise ValueError("Missing reader content")
            for node in list(container.select("script,style,iframe,form,nav,.d-none,.sr-only,[hidden],[aria-hidden=true]")):
                node.decompose()
            for style in style_text:
                for selectors, declarations in re.findall(r"([^{}]+)\{([^{}]+)\}",style):
                    if re.search(r"opacity\s*:\s*0(?:\.0+)?\s*(?:!important\s*)?(?:;|$)|display\s*:\s*none|visibility\s*:\s*hidden",declarations):
                        for selector in selectors.split(","):
                            selector=selector.strip()
                            if re.fullmatch(r"\.[a-zA-Z_][a-zA-Z0-9_-]*",selector):
                                for node in list(container.select(selector)):
                                    node.decompose()
            paragraphs=[p.get_text(" ",strip=True) for p in container.select("p") if p.get_text(strip=True)]
            if len(paragraphs)<4 or sum(map(len,paragraphs))<=500:
                raise ValueError("Insufficient chapter text")
            result["text"]=True
            result["paragraphs"]=len(paragraphs)
            result["text_characters"]=sum(map(len,paragraphs))
            result["status"]="healthy"
    except Exception as exc:
        result["status"]="failed"
        result["failed_stage"]=stage
        result["error_type"]=type(exc).__name__
        response=getattr(exc,"response",None)
        if response is not None:
            result["upstream_http"]=response.status_code
    return result

def run_deep_checks(selectors):
    """Complete embedded index, official total, stable order and three real texts.

    This API returns one full index, not continuation pages. If it advertises more
    pages or omits its total, fail closed instead of guessing an endpoint/cursor.
    """
    result = {"domain": "seanovel.org", "status": "failed", "completeIndex": False,
              "indexState": "INTERRUPTED", "verificationTier": "ATTESTED_COMPLETE_INDEX",
              **{op: False for op in ("catalog", "search", "details", "chapters", "text")}}
    stage = "catalog"
    deadline = time.monotonic()+90
    try:
        with requests.Session() as session:
            session.headers.update({"User-Agent": "MangaroNovelPrototype/0.1", "Accept": "text/html,application/json"})
            def get(url): return fetch(session, url, deadline)
            entries = json.loads(get(BASE+"/api/novels?sort=views"))
            if not isinstance(entries, list) or not 0 < len(entries) <= 1000:
                raise ValueError("Invalid catalog")
            matches = [item for item in entries if isinstance(item, dict) and item.get("slug") == SLUG]
            if len(matches) != 1 or not matches[0].get("title_ar") or "تيرا" not in matches[0]["title_ar"]:
                raise ValueError("Catalog identity mismatch")
            expected = matches[0]
            result.update(catalog=True, search=True, catalog_count=len(entries))
            stage = "details"
            def index(raw):
                item = json.loads(raw)
                if not isinstance(item, dict) or item.get("slug") != SLUG or item.get("title_ar") != expected["title_ar"] or not item.get("description"):
                    raise ValueError("Novel identity mismatch")
                if expected.get("source_id") is not None and item.get("source_id") != expected["source_id"]:
                    raise ValueError("Source identity mismatch")
                if any(item.get(k) for k in ("has_more", "hasMore", "next", "next_page", "nextPage", "next_cursor")):
                    raise ValueError("Unsupported chapter continuation")
                total, chapters = item.get("chapters_count"), item.get("chapters")
                if type(total) is not int or not 0 < total <= 100000 or not isinstance(chapters, list) or len(chapters) != total:
                    raise ValueError("Official chapter total mismatch or unavailable")
                if any(not isinstance(c, dict) or type(c.get("id")) is not int or c["id"] <= 0 or not isinstance(c.get("title"), str) or not c["title"].strip() for c in chapters):
                    raise ValueError("Invalid chapter identity")
                ids = [c["id"] for c in chapters]
                if len(set(ids)) != len(ids) or ids != sorted(ids):
                    raise ValueError("Duplicate or unordered chapters")
                rows = [(c["id"], c["title"]) for c in chapters]
                return total, rows
            total, rows = index(get(BASE+"/api/novel/"+SLUG))
            result.update(details=True, chapters=True, chapter_count=total, officialTotal=total,
                          chapterPages=1, ordering="SOURCE_ID_ASCENDING")
            stage = "text"
            paragraphs_total = characters_total = 0
            text_hashes = []
            for position in sorted(set((0, len(rows)//2, len(rows)-1))):
                chapter_url = URL+"/chapters/"+str(rows[position][0])
                doc = BeautifulSoup(get(chapter_url), "html5lib")
                canonical = doc.select_one('link[rel=canonical]')
                if canonical is None or canonical.get("href", "").rstrip("/") != chapter_url:
                    raise ValueError("Chapter ownership mismatch")
                if doc.select('#challenge-form,#cf-wrapper,.challenge-running'):
                    raise ValueError("Challenge HTML")
                container = doc.select_one(selectors["text"])
                if container is None: raise ValueError("Missing reader content")
                for node in list(container.select('script,style,iframe,form,nav,.d-none,.sr-only,[hidden],[aria-hidden=true]')):
                    node.decompose()
                for style in doc.select("style"):
                    for css, declarations in re.findall(r"([^{}]+)\{([^{}]+)\}", style.get_text()):
                        if re.search(r"opacity\s*:\s*0(?:\.0+)?\s*(?:!important\s*)?(?:;|$)|display\s*:\s*none|visibility\s*:\s*hidden", declarations):
                            for selector in css.split(','):
                                if re.fullmatch(r"\.[a-zA-Z_][a-zA-Z0-9_-]*", selector.strip()):
                                    for node in list(container.select(selector.strip())): node.decompose()
                paragraphs = [p.get_text(' ', strip=True) for p in container.select('p') if p.get_text(strip=True)]
                joined = '\n'.join(paragraphs)
                if len(paragraphs) < 4 or len(joined) <= 500 or sum(c.isalpha() for c in joined) <= 250 or any(marker in joined.lower() for marker in ('verify you are human', 'cf-browser-verification', 'enable javascript and cookies')):
                    raise ValueError("Invalid chapter text")
                paragraphs_total += len(paragraphs); characters_total += len(joined)
                text_hashes.append(hashlib.sha256(joined.encode()).hexdigest())
            stage = "chapters"
            if index(get(BASE+"/api/novel/"+SLUG)) != (total, rows):
                raise ValueError("Index changed during verification")
            result.update(status="healthy", completeIndex=True, indexState="COMPLETE", text=True,
                          paragraphs=paragraphs_total, text_characters=characters_total, sampledTexts=len(text_hashes),
                          sampleHashes=text_hashes, identityHash=hashlib.sha256(("seanovel.org:"+URL).encode()).hexdigest(),
                          indexHash=hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest())
    except Exception as exc:
        result.update(failed_stage=stage, error_type=type(exc).__name__)
        response = getattr(exc, "response", None)
        if response is not None:
            result["upstream_http"] = response.status_code
            if response.status_code in (403, 429): result["status"] = "blocked"
    return result

def candidate_request(raw):
    data=json.loads(raw)
    if set(data)!={'protocol','candidateSha256','revision','requestedAt','nonce','bundle'}:
        raise ValueError('Request schema')
    if type(data['protocol']) is not int or data['protocol'] not in (1,2) or type(data['requestedAt']) is not int:
        raise ValueError('Protocol')
    if not -5<=int(time.time())-data['requestedAt']<=120 or not isinstance(data['nonce'],str) or not re.fullmatch('[0-9a-f]{64}',data['nonce']):
        raise ValueError('Fresh request required')
    payload=base64.b64decode(data['bundle'],validate=True)
    if len(payload)>64*1024 or hashlib.sha256(payload).hexdigest()!=data['candidateSha256']:
        raise ValueError('Candidate digest')
    bundle=json.loads(payload)
    if set(bundle)!={'schemaVersion','engineVersion','revision','sources'} or type(bundle['schemaVersion']) is not int or bundle['schemaVersion']!=1:
        raise ValueError('Bundle schema')
    if type(bundle['engineVersion']) is not int or bundle['engineVersion'] not in (1,2):
        raise ValueError('Engine')
    if type(bundle['revision']) is not int or not 0<bundle['revision']<=2147483647 or type(data['revision']) is not int or data['revision']!=bundle['revision']:
        raise ValueError('Revision')
    domains={'novel.kolnovel':'kolnovel.com','novel.cenele':'cenele.com','novel.sunovels':'sunovels.com','novel.seanovel':'seanovel.org'}
    keys={'catalogCards','catalogTitle','catalogCover','detailsTitle','detailsCover','description','genres','chapterLinks','chapterTitle','text','originalTitle'}
    sources=bundle['sources']
    if not isinstance(sources,list) or len(sources)!=4:raise ValueError('Four sources required')
    seen=set();sea=None
    for item in sources:
        if not isinstance(item,dict) or set(item)!={'id','domain','selectors'} or item['id'] not in domains or domains[item['id']]!=item['domain'] or item['id'] in seen:
            raise ValueError('Source identity')
        seen.add(item['id']);selectors=item['selectors']
        if not isinstance(selectors,dict) or 'text' not in selectors or not set(selectors)<=keys:raise ValueError('Selector keys')
        for css in selectors.values():
            if not isinstance(css,str) or not 1<=len(css)<=240 or any(c in css for c in '<>:\n\r') or any(x.strip() in ('body','html','*',':root') for x in css.split(',')):
                raise ValueError('Unsafe selector')
            BeautifulSoup('<p></p>','html.parser').select(css)
        if item['id']=='novel.seanovel':
            if set(selectors)!={'text'}:raise ValueError('Unsupported SeaNovel selector')
            sea=selectors
    if seen!=set(domains) or sea is None:raise ValueError('Source set')
    return data,sea

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Independent key; CRON_SECRET still authenticates GET exclusively.
        self.close_connection=True
        key=os.getenv('SEANOVEL_ATTESTATION_SECRET','')
        if len(key)!=64 or not re.fullmatch('[0-9a-f]{64}',key):
            return self.reply(503,{'error':'Attestation unavailable'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=96*1024:raise ValueError('Body limit')
            raw=self.rfile.read(length)
            protocol=json.loads(raw).get('protocol')
            if type(protocol) is not int or protocol not in (1,2): raise ValueError('Protocol')
            expected='HMAC-SHA256 '+hmac.new(key.encode(),('request-v%d\n'%protocol).encode()+raw,hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected,self.headers.get('Authorization','')):
                return self.reply(401,{'error':'Unauthorized'})
            data,selectors=candidate_request(raw)
        except Exception:
            return self.reply(400,{'error':'Invalid request'})
        result=run_checks(selectors) if protocol==1 else run_deep_checks(selectors)
        payload=json.dumps({'protocol':protocol,'candidateSha256':data['candidateSha256'],'revision':data['revision'],
                            'requestedAt':data['requestedAt'],'nonce':data['nonce'],'timestamp':int(time.time()),'result':result},
                           ensure_ascii=True,separators=(',',':')).encode()
        mac=hmac.new(key.encode(),('response-v%d\n'%protocol).encode()+payload,hashlib.sha256).hexdigest()
        self.reply(200 if protocol==2 or result['status']=='healthy' else 503,{'payload':base64.b64encode(payload).decode(),'signature':mac})

    def reply(self,status,data):
        raw=json.dumps(data,separators=(',',':')).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Cache-Control','no-store')
        self.end_headers();self.wfile.write(raw)

    def do_GET(self):
        secret=os.getenv("CRON_SECRET","")
        auth=self.headers.get("Authorization","")
        if not secret or not hmac.compare_digest(auth,"Bearer "+secret):
            body=b'{"error":"Unauthorized"}'
            self.send_response(401)
        else:
            result=run_checks()
            print(json.dumps(result,ensure_ascii=False,sort_keys=True),flush=True)
            body=json.dumps(result,ensure_ascii=False).encode("utf-8")
            self.send_response(200 if result["status"]=="healthy" else 503)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(body)
