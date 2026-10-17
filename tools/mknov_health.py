#!/usr/bin/env python3
"""Independent anonymous Mknov observations. Never feeds the signed-rule publisher.

Ordinary mode deliberately does NOT re-fetch the full index: membership of its
historically recorded chapter sample is not freshly established. Deep mode does.
No upstream strings (including error bodies or story text) enter reports.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import tempfile
import time
from datetime import datetime, timezone
from decimal import Decimal
from urllib import error, request

BASE = 'https://api.mknov.com/v1/'
LIMITS = {'getWorks': 262144, 'searchByKeyword': 262144,
          'getWorkById': 262144, 'getChaptersByWorkId': 8388608,
          'getChapterBatch': 1048576}
WORK = '96'
CHAPTER = '20716'


class ObservationError(Exception):
    def __init__(self, code, classification='FAIL', status=None):
        super().__init__(code)
        self.code, self.classification, self.status = code, classification, status


def require(condition, code):
    if not condition:
        raise ObservationError(code)


def identity(value):
    require(not isinstance(value, bool) and isinstance(value, (str, int, Decimal)), 'INVALID_ID')
    raw = str(value)
    require(bool(re.fullmatch(r'[1-9][0-9]{0,17}', raw)), 'INVALID_ID')
    return raw


def count(value):
    require(type(value) is int and 0 <= value <= 1000000, 'INVALID_COUNT')
    return value


def obj(value):
    require(isinstance(value, dict), 'INVALID_OBJECT')
    return value


def nonblank(value):
    require(isinstance(value, str) and bool(value.strip()), 'MISSING_METADATA')
    return value


def root(value):
    obj(value)
    require(value.get('status') == 'success', 'API_STATUS_NOT_SUCCESS')
    return value


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def decode(raw):
    try:
        return root(json.loads(raw, parse_float=Decimal, object_pairs_hook=unique_pairs,
                               parse_constant=lambda _: (_ for _ in ()).throw(ObservationError('NONFINITE_JSON'))))
    except (ValueError, UnicodeError, RecursionError):
        raise ObservationError('MALFORMED_JSON') from None


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ObservationError('REDIRECT_REFUSED', 'BLOCKED_BY_UPSTREAM', code)


class Client:
    """Serial requests, no cookies/auth/proxy credentials, one total transport retry."""
    def __init__(self, deep=False, opener=None, clock=time.monotonic, sleep=time.sleep):
        self.opener = opener or request.build_opener(request.ProxyHandler({}), NoRedirect())
        self.clock, self.sleep = clock, sleep
        self.started = clock()
        self.deadline = self.started + (120 if deep else 80)
        self.budget = 6 if deep else 5
        self.requests = 0
        self.retry_used = False
        self.last_start = None
        self.audit = []

    def post(self, endpoint, body):
        require(endpoint in LIMITS, 'ENDPOINT_NOT_ALLOWED')
        while True:
            if self.requests >= self.budget or self.clock() >= self.deadline:
                raise ObservationError('REQUEST_BUDGET_EXHAUSTED', 'INSUFFICIENT_EVIDENCE')
            if self.last_start is not None:
                self.sleep(max(0, 1.0 - (self.clock() - self.last_start)))
            remaining = self.deadline - self.clock()
            if remaining <= 0:
                raise ObservationError('DEADLINE_EXHAUSTED', 'INSUFFICIENT_EVIDENCE')
            self.requests += 1
            self.last_start = self.clock()
            attempt = {'endpoint': endpoint, 'attempt': self.requests}
            self.audit.append(attempt)
            req = request.Request(BASE + endpoint, data=json.dumps(body).encode(), method='POST', headers={
                'User-Agent': 'MangaroNovelMonitor/1.0', 'Content-Type': 'application/json',
                'Accept': 'application/json', 'Accept-Encoding': 'identity'})
            try:
                with self.opener.open(req, timeout=min(12, remaining)) as response:
                    status = response.status
                    attempt['httpStatus'] = status
                    self.check_status(status)
                    require(response.headers.get_content_type() == 'application/json', 'NON_JSON_RESPONSE')
                    require(response.headers.get('Content-Encoding', 'identity').lower() == 'identity', 'UNSUPPORTED_ENCODING')
                    length = response.headers.get('Content-Length')
                    if length is not None:
                        require(length.isdigit(), 'INVALID_LENGTH')
                        require(int(length) <= LIMITS[endpoint], 'OVERSIZED_RESPONSE')
                    raw = bytearray()
                    while True:
                        if self.clock() >= self.deadline:
                            raise ObservationError('DEADLINE_EXHAUSTED', 'INSUFFICIENT_EVIDENCE')
                        chunk = response.read(min(16384, LIMITS[endpoint] + 1 - len(raw)))
                        if not chunk:
                            break
                        raw.extend(chunk)
                        require(len(raw) <= LIMITS[endpoint], 'OVERSIZED_RESPONSE')
                    if length is not None:
                        require(len(raw) == int(length), 'TRUNCATED_RESPONSE')
                    attempt['bytes'] = len(raw)
                    return decode(raw)
            except error.HTTPError as exc:
                attempt['httpStatus'] = exc.code
                exc.close()
                try:
                    self.check_status(exc.code)
                except ObservationError as failure:
                    issue = failure
            except (error.URLError, TimeoutError, socket.timeout, ConnectionError, OSError):
                issue = ObservationError('TRANSPORT_FAILURE', 'INSUFFICIENT_EVIDENCE')
            except ObservationError as exc:
                issue = exc
            attempt['error'] = issue.code
            if issue.code in {'TRANSPORT_FAILURE', 'HTTP_SERVER_ERROR'} and not self.retry_used:
                self.retry_used = True
                self.sleep(1.0)
                continue
            raise issue

    @staticmethod
    def check_status(status):
        if status in (401, 403, 429):
            raise ObservationError('HTTP_ACCESS_OR_RATE_LIMIT', 'BLOCKED_BY_UPSTREAM', status)
        if status in (404, 410):
            raise ObservationError('SAMPLE_UNAVAILABLE', 'INSUFFICIENT_EVIDENCE', status)
        if 500 <= status <= 599:
            raise ObservationError('HTTP_SERVER_ERROR', 'INSUFFICIENT_EVIDENCE', status)
        require(status == 200, 'UNEXPECTED_HTTP_STATUS')


def works(payload, search=False, limit=3):
    payload = root(payload)
    rows = payload.get('works' if search else 'data')
    require(isinstance(rows, list) and len(rows) <= 10000, 'INVALID_WORK_LIST')
    ids = []
    for row in rows:
        row = obj(row)
        ids.append(identity(row.get('id')))
        nonblank(row.get('name'))
    require(len(set(ids)) == len(ids), 'DUPLICATE_WORK_ID')
    total = count(payload.get('total_works' if search else 'total'))
    require(len(rows) == (total if search else min(total, limit)), 'WORK_COUNT_MISMATCH')
    return ids


def details(payload, expected):
    row = obj(root(payload).get('data'))
    require(identity(row.get('id')) == expected, 'DETAILS_IDENTITY_MISMATCH')
    nonblank(row.get('name'))
    for key in ('author', 'story', 'status'):
        require(isinstance(row.get(key), str), 'INVALID_DETAILS_METADATA')
    return row


def chapter_number(value):
    require(not isinstance(value, bool) and isinstance(value, (int, Decimal)), 'INVALID_CHAPTER_NUMBER')
    value = Decimal(value)
    require(value.is_finite() and value >= 0, 'INVALID_CHAPTER_NUMBER')
    return value


def index(payload, expected):
    payload = root(payload)
    total = count(payload.get('total_chapters'))
    require(total <= 100000, 'INDEX_TOO_LARGE')
    volumes = payload.get('data')
    require(isinstance(volumes, list) and len(volumes) <= 10000, 'INVALID_VOLUME_LIST')
    rows = []
    seen = set()
    for volume in volumes:
        chapters = obj(volume).get('chapters')
        require(isinstance(chapters, list) and len(chapters) <= 100000, 'INVALID_CHAPTER_LIST')
        for raw in chapters:
            row = obj(raw)
            cid = identity(row.get('id'))
            require(cid not in seen, 'DUPLICATE_CHAPTER_ID')
            seen.add(cid)
            require(identity(row.get('work_id')) == expected, 'CHAPTER_WORK_MISMATCH')
            number = chapter_number(row.get('chapter_number'))
            require(type(row.get('is_free')) is bool, 'AMBIGUOUS_CHAPTER_ACCESS')
            rows.append({'id': cid, 'number': number, 'free': row['is_free']})
            require(len(rows) <= 100000, 'INDEX_TOO_LARGE')
    require(total == len(rows), 'INDEX_COUNT_MISMATCH')
    # Official index groups volumes; normalize numeric order without inventing entries.
    return sorted(rows, key=lambda r: (r['number'], int(r['id'])))


def text(payload, expected, work_title, number=None):
    row = obj(root(payload).get('data'))
    require(identity(row.get('id')) == expected, 'TEXT_IDENTITY_MISMATCH')
    require(type(row.get('is_free')) is bool, 'AMBIGUOUS_CHAPTER_ACCESS')
    if not row['is_free']:
        raise ObservationError('EXPLICIT_ACCESS_RESTRICTION', 'BLOCKED_BY_UPSTREAM')
    require(row.get('novel_title') == work_title, 'TEXT_WORK_TITLE_MISMATCH')
    actual_number = chapter_number(row.get('chapter_number'))
    if number is not None:
        require(actual_number == number, 'TEXT_CHAPTER_NUMBER_MISMATCH')
    content = row.get('content')
    require(isinstance(content, str) and len(content) <= 1000000, 'INVALID_TEXT')
    require(not re.search(r'<(?:html|script|form|body)\b', content, re.I), 'INVALID_TEXT_HTML')
    paragraphs = [p.strip() for p in content.replace('\r\n', '\n').split('\n') if p.strip()]
    characters = sum(map(len, paragraphs))
    require(len(paragraphs) >= 3 and characters >= 200 and sum(c.isalpha() for c in content) >= 100,
            'INCOMPLETE_TEXT')
    return {'paragraphs': len(paragraphs), 'characters': characters,
            'sha256': hashlib.sha256(content.encode()).hexdigest(), 'chapterId': expected,
            'explicitlyFree': True}


def observe(mode='monitor', client=None):
    deep = mode == 'deep'
    client = client or Client(deep)
    report = {'schemaVersion': 1, 'sourceId': 'novel.mknov', 'mode': mode,
              'timestamp': datetime.now(timezone.utc).isoformat(), 'classification': 'INSUFFICIENT_EVIDENCE',
              'scope': 'COMPLETE_INDEX_SAMPLE' if deep else 'PUBLIC_SAMPLE_NO_FRESH_INDEX',
              'productionAuthorization': False, 'signedFeedEligible': False,
              'androidReaderAcceptance': 'NOT_TESTED', 'sourceWideHealthEstablished': False,
              'chapterMembershipRevalidated': False, 'operations': {}}
    operations = report['operations']
    stage = 'catalog'
    try:
        ids = works(client.post('getWorks', {'works': 'views', 'limit': 3, 'offset': 0}))
        require(bool(ids), 'EMPTY_CATALOG')
        operations[stage] = {'status': 'PASS', 'sampledWorks': len(ids)}
        stage = 'details'
        work = details(client.post('getWorkById', {'id': WORK}), WORK)
        operations[stage] = {'status': 'PASS', 'workId': WORK}
        stage = 'search'
        ids = works(client.post('searchByKeyword', {'keyword': work['name']}), search=True)
        if not ids:
            raise ObservationError('EMPTY_SEARCH_SAMPLE', 'INSUFFICIENT_EVIDENCE')
        require(WORK in ids, 'SEARCH_WORK_NOT_FOUND')
        operations[stage] = {'status': 'PASS', 'matches': len(ids), 'exactWorkFound': True}
        stage = 'index'
        chapter, number = CHAPTER, None
        if deep:
            rows = index(client.post('getChaptersByWorkId', {'id': int(WORK)}), WORK)
            free = [r for r in rows if r['free']]
            operations[stage] = {'status': 'PASS', 'state': 'COMPLETE' if rows else 'VERIFIED_EMPTY',
                                 'uniqueChapters': len(rows), 'freeChapters': len(free),
                                 'lockedChapters': len(rows) - len(free),
                                 'orderedIdentitySha256': hashlib.sha256(json.dumps(
                                     [(r['id'], str(r['number']), r['free']) for r in rows]).encode()).hexdigest()}
            if not rows:
                raise ObservationError('VERIFIED_EMPTY_SAMPLE', 'INSUFFICIENT_EVIDENCE')
            if not free:
                raise ObservationError('NO_PUBLIC_CHAPTER_SAMPLE', 'BLOCKED_BY_UPSTREAM')
            chosen = next((r for r in free if r['id'] == CHAPTER), free[0])
            chapter, number = chosen['id'], chosen['number']
            report['chapterMembershipRevalidated'] = True
        else:
            operations[stage] = {'status': 'SKIPPED', 'reason': 'FULL_INDEX_RESERVED_FOR_DEEP_MODE'}
        stage = 'text'
        result = text(client.post('getChapterBatch', {'id': int(chapter)}), chapter, work['name'], number)
        operations[stage] = {'status': 'PASS', **result}
        report.update(classification='PASS', reason='SCOPED_SAMPLE_VALID')
    except ObservationError as exc:
        operations[stage] = {**operations.get(stage, {}), 'status': exc.classification, 'reason': exc.code}
        if exc.status is not None:
            operations[stage]['httpStatus'] = exc.status
        report.update(classification=exc.classification, reason=exc.code)
    except Exception:
        # Never serialize unexpected exception messages: they may contain payloads.
        operations[stage] = {'status': 'INSUFFICIENT_EVIDENCE', 'reason': 'MONITOR_INTERNAL_ERROR'}
        report.update(classification='INSUFFICIENT_EVIDENCE', reason='MONITOR_INTERNAL_ERROR')
    for name in ('catalog', 'details', 'search', 'index', 'text'):
        operations.setdefault(name, {'status': 'SKIPPED', 'reason': 'PREREQUISITE_NOT_VERIFIED'})
    report['requests'] = client.requests
    report['transport'] = client.audit
    report['elapsedSeconds'] = round(client.clock() - client.started, 3)
    return report


def save_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(report, ensure_ascii=True, indent=2) + '\n'
    require(len(encoded) < 16384, 'REPORT_TOO_LARGE')
    fd, temporary = tempfile.mkstemp(prefix='.mknov-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('monitor', 'deep'), default='monitor')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = observe(args.mode)
    save_report(args.output, report)
    # Only internally controlled classifications/reasons; no response content.
    summary = f"Mknov: {report['classification']} ({report['reason']}); {report['requests']} requests."
    print(summary)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write('## Independent Mknov observation\n\n' + summary + '\n\nScope: ' + report['scope'] +
                         '. This is not Android acceptance or signed-feed publication approval.\n')
    return 0 if report['classification'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
