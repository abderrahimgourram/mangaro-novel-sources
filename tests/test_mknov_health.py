"""Offline synthetic contract/transport tests. No upstream chapter bodies recorded."""
import ast
import contextlib
import copy
from http.client import IncompleteRead
from email.message import Message
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from urllib import error
from unittest.mock import patch

from tools import mknov_health as m

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/mknov/sample.json').read_text())


def sample():
    data = copy.deepcopy(FIXTURE)
    data['text']['data']['content'] = '\n'.join(
        'Synthetic monitoring paragraph written exclusively for this offline test. ' * 3
        for _ in range(3))
    return data


class Clock:
    def __init__(self):
        self.now = 0
    def __call__(self):
        return self.now
    def sleep(self, seconds):
        self.now += seconds


class Response(io.BytesIO):
    def __init__(self, raw, status=200, length=None, content_type='application/json'):
        super().__init__(raw)
        self.status = status
        self.headers = Message()
        self.headers['Content-Type'] = content_type
        if length is not None:
            self.headers['Content-Length'] = str(length)


class Opener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
    def open(self, req, timeout):
        self.calls.append((req, timeout))
        item = next(self.responses)
        if isinstance(item, Exception):
            raise item
        return item


def client(responses, deep=False):
    opener, clock = Opener(responses), Clock()
    return m.Client(deep, opener=opener, clock=clock, sleep=clock.sleep), opener


def responses(data, deep=False):
    return [Response(json.dumps(data[key]).encode()) for key in
            (['catalog', 'details', 'search', 'index', 'text'] if deep else ['catalog', 'details', 'search', 'text'])]


class MknovContractTests(unittest.TestCase):
    def setUp(self):
        self.data = sample()

    def rejected(self, code, call):
        with self.assertRaises(m.ObservationError) as exc:
            call()
        self.assertEqual(exc.exception.code, code)
        return exc.exception

    def test_valid_catalog(self):
        self.assertEqual(m.works(self.data['catalog']), ['96'])

    def test_duplicate_work(self):
        self.data['catalog']['data'] *= 2
        self.rejected('DUPLICATE_WORK_ID', lambda: m.works(self.data['catalog']))

    def test_invalid_identity(self):
        for value in (None, True, 0, -1, 'https://other.test', '01', 1.5):
            with self.subTest(value=value):
                self.rejected('INVALID_ID', lambda: m.identity(value))

    def test_search_and_empty(self):
        self.assertEqual(m.works(self.data['search'], True), ['96'])
        self.assertEqual(m.works({'status':'success', 'works':[], 'total_works':0}, True), [])

    def test_search_requires_complete_snapshot(self):
        self.data['search']['total_works'] = 2
        self.rejected('WORK_COUNT_MISMATCH', lambda: m.works(self.data['search'], True))

    def test_details_identity(self):
        self.assertEqual(m.details(self.data['details'], '96')['id'], 96)
        self.rejected('DETAILS_IDENTITY_MISMATCH', lambda: m.details(self.data['details'], '37'))

    def test_details_missing_metadata(self):
        self.data['details']['data'].pop('author')
        self.rejected('INVALID_DETAILS_METADATA', lambda: m.details(self.data['details'], '96'))

    def test_index_and_explicit_access(self):
        rows = m.index(self.data['index'], '96')
        self.assertEqual([r['free'] for r in rows], [True, False])
        self.assertEqual([r['id'] for r in rows], ['20716', '20717'])

    def test_duplicate_chapter_id(self):
        self.data['index']['data'][0]['chapters'][1]['id'] = 20716
        self.rejected('DUPLICATE_CHAPTER_ID', lambda: m.index(self.data['index'], '96'))

    def test_declared_count_mismatch(self):
        self.data['index']['total_chapters'] = 3218
        self.rejected('INDEX_COUNT_MISMATCH', lambda: m.index(self.data['index'], '96'))

    def test_wrong_work_in_index(self):
        self.rejected('CHAPTER_WORK_MISMATCH', lambda: m.index(self.data['index'], '37'))

    def test_unknown_access_not_readable(self):
        del self.data['index']['data'][0]['chapters'][0]['is_free']
        self.rejected('AMBIGUOUS_CHAPTER_ACCESS', lambda: m.index(self.data['index'], '96'))

    def test_volume_order_zero_special_parts(self):
        rows = self.data['index']['data'][0]['chapters']
        rows[0]['chapter_number'] = 0
        rows[1]['chapter_number'] = 0
        rows.reverse()
        self.assertEqual([r['id'] for r in m.index(self.data['index'], '96')], ['20716', '20717'])

    def test_valid_text_metrics_only(self):
        result = m.text(self.data['text'], '20716', 'Synthetic work', 1)
        self.assertEqual(result['paragraphs'], 3)
        self.assertNotIn('content', result)
        self.assertEqual(len(result['sha256']), 64)

    def test_wrong_text_identity(self):
        self.rejected('TEXT_IDENTITY_MISMATCH', lambda: m.text(self.data['text'], '20717', 'Synthetic work'))

    def test_wrong_text_work(self):
        self.rejected('TEXT_WORK_TITLE_MISMATCH', lambda: m.text(self.data['text'], '20716', 'Different work'))

    def test_wrong_text_number(self):
        self.rejected('TEXT_CHAPTER_NUMBER_MISMATCH', lambda: m.text(self.data['text'], '20716', 'Synthetic work', 2))

    def test_restricted_text_never_readable(self):
        self.data['text']['data']['is_free'] = False
        issue = self.rejected('EXPLICIT_ACCESS_RESTRICTION', lambda: m.text(self.data['text'], '20716', 'Synthetic work'))
        self.assertEqual(issue.classification, 'BLOCKED_BY_UPSTREAM')

    def test_missing_malformed_short_html_text(self):
        for content, code in ((None, 'INVALID_TEXT'), ([], 'INVALID_TEXT'), ('tiny', 'INCOMPLETE_TEXT'),
                              ('<html>login</html>', 'INVALID_TEXT_HTML')):
            with self.subTest(code=code):
                self.data['text']['data']['content'] = content
                self.rejected(code, lambda: m.text(self.data['text'], '20716', 'Synthetic work'))

    def test_malformed_duplicate_nonfinite_json(self):
        for raw, code in ((b'{', 'MALFORMED_JSON'), (b'{"status":"success","id":1,"id":2}', 'DUPLICATE_JSON_KEY'),
                          (b'{"status":"success","id":NaN}', 'NONFINITE_JSON')):
            self.rejected(code, lambda: m.decode(raw))

    def test_ordinary_avoids_index_and_reports_scope(self):
        c, opener = client(responses(self.data))
        report = m.observe(client=c)
        self.assertEqual(report['classification'], 'PASS')
        self.assertEqual(c.requests, 4)
        self.assertFalse(report['chapterMembershipRevalidated'])
        self.assertEqual(report['operations']['index']['status'], 'SKIPPED')
        self.assertFalse(report['signedFeedEligible'])
        self.assertNotIn('getChaptersByWorkId', str([r.full_url for r, _ in opener.calls]))

    def test_deep_fetches_exactly_one_index_and_proves_membership(self):
        c, opener = client(responses(self.data, True), True)
        report = m.observe('deep', c)
        self.assertEqual(report['classification'], 'PASS')
        self.assertTrue(report['chapterMembershipRevalidated'])
        self.assertEqual(report['operations']['index']['uniqueChapters'], 2)
        self.assertEqual(sum(r.full_url.endswith('getChaptersByWorkId') for r, _ in opener.calls), 1)
        self.assertEqual(json.loads(opener.calls[3][0].data), {'id':96})

    def test_empty_search_insufficient(self):
        self.data['search'].update(works=[], total_works=0)
        c, _ = client(responses(self.data))
        report = m.observe(client=c)
        self.assertEqual(report['classification'], 'INSUFFICIENT_EVIDENCE')
        self.assertEqual(c.requests, 3)

    def test_verified_empty_is_not_readable_or_sourcewide_outage(self):
        self.data['index'].update(data=[], total_chapters=0)
        c, _ = client(responses(self.data, True), True)
        report = m.observe('deep', c)
        self.assertEqual(report['classification'], 'INSUFFICIENT_EVIDENCE')
        self.assertEqual(report['operations']['index']['state'], 'VERIFIED_EMPTY')
        self.assertEqual(c.requests, 4)

    def test_deep_chooses_only_public_member_if_sample_is_locked(self):
        rows = self.data['index']['data'][0]['chapters']
        rows[0]['is_free'], rows[1]['is_free'] = False, True
        self.data['text']['data'].update(id=20717, chapter_number=2)
        c, opener = client(responses(self.data, True), True)
        report = m.observe('deep', c)
        self.assertEqual(report['classification'], 'PASS')
        self.assertEqual(json.loads(opener.calls[-1][0].data), {'id':20717})

    def test_workflow_isolated_readonly_without_publisher_secrets(self):
        workflow = (Path(__file__).parents[1] / '.github/workflows/mknov-health.yml').read_text()
        self.assertIn('contents: read', workflow)
        self.assertIn('workflow_dispatch:', workflow)
        self.assertIn('if: always()', workflow)
        self.assertIn('persist-credentials: false', workflow)
        self.assertNotIn('secrets.', workflow)
        self.assertNotIn('contents: write', workflow)
        self.assertNotIn('publish.py', workflow)
        self.assertNotIn('PUBLIC_PIPELINE_APPROVED', workflow)
        self.assertNotIn('rules/mknov', workflow)

    def test_all_locked_does_not_fetch_text(self):
        for row in self.data['index']['data'][0]['chapters']:
            row['is_free'] = False
        c, _ = client(responses(self.data, True), True)
        report = m.observe('deep', c)
        self.assertEqual(report['classification'], 'BLOCKED_BY_UPSTREAM')
        self.assertEqual(c.requests, 4)

    def test_report_has_no_body_title_or_private_error(self):
        secret = 'PRIVATE_TOKEN_AND_UPSTREAM_STORY'
        c, _ = client([RuntimeError(secret)])
        report = m.observe(client=c)
        self.assertNotIn(secret, json.dumps(report))
        c, _ = client(responses(self.data))
        report = m.observe(client=c)
        encoded = json.dumps(report)
        self.assertNotIn('Synthetic', encoded)
        self.assertNotIn('content', encoded)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.json'
            m.save_report(path, report)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text()), report)


class MknovTransportTests(unittest.TestCase):
    def test_timeout_bounded_retry_and_spacing(self):
        c, _ = client([TimeoutError(), TimeoutError()])
        with self.assertRaises(m.ObservationError) as exc:
            c.post('getWorks', {})
        self.assertEqual(exc.exception.classification, 'INSUFFICIENT_EVIDENCE')
        self.assertEqual(c.requests, 2)
        self.assertGreaterEqual(c.clock(), 1)

    def test_incomplete_http_read_is_transport_not_monitor_defect(self):
        c, _ = client([IncompleteRead(b'SYNTHETIC_PRIVATE_PARTIAL', 100),
                       IncompleteRead(b'SYNTHETIC_PRIVATE_PARTIAL', 100)])
        report = m.observe(client=c)
        self.assertEqual(report['classification'], 'INSUFFICIENT_EVIDENCE')
        self.assertEqual(report['reason'], 'TRANSPORT_FAILURE')
        self.assertEqual(c.requests, 2)
        self.assertNotIn('SYNTHETIC_PRIVATE_PARTIAL', json.dumps(report))

    def test_deep_retry_shares_single_total_budget(self):
        c, _ = client([TimeoutError()] + responses(sample(), True), True)
        report = m.observe('deep', c)
        self.assertEqual(report['classification'], 'PASS')
        self.assertEqual(c.requests, 6)
        self.assertEqual(sum(x['endpoint'] == 'getChaptersByWorkId' for x in c.audit), 1)

    def test_retry_can_recover(self):
        c, _ = client([TimeoutError(), Response(b'{"status":"success"}')])
        self.assertEqual(c.post('getWorks', {})['status'], 'success')
        self.assertEqual(c.requests, 2)

    def test_403_429_no_retry_no_body_leak(self):
        for status in (403, 429):
            c, _ = client([error.HTTPError('https://api.mknov.com/v1/getWorks', status,
                                          'private upstream error', {}, io.BytesIO(b'private body'))])
            report = m.observe(client=c)
            self.assertEqual(report['classification'], 'BLOCKED_BY_UPSTREAM')
            self.assertEqual(c.requests, 1)
            self.assertNotIn('private', json.dumps(report))

    def test_500_retries_only_once(self):
        c, _ = client([Response(b'', 500), Response(b'', 500)])
        report = m.observe(client=c)
        self.assertEqual(report['classification'], 'INSUFFICIENT_EVIDENCE')
        self.assertEqual(c.requests, 2)

    def test_missing_sample_is_not_sourcewide_failure(self):
        c, _ = client([Response(b'', 404)])
        self.assertEqual(m.observe(client=c)['classification'], 'INSUFFICIENT_EVIDENCE')

    def test_stream_and_declared_size_limits(self):
        for response in (Response(b'x' * (m.LIMITS['getWorks'] + 1)), Response(b'', length=999999999)):
            c, _ = client([response])
            report = m.observe(client=c)
            self.assertEqual(report['reason'], 'OVERSIZED_RESPONSE')

    def test_truncation_and_non_json(self):
        for response, code in ((Response(b'{}', length=10), 'TRUNCATED_RESPONSE'),
                               (Response(b'<html>', content_type='text/html'), 'NON_JSON_RESPONSE')):
            c, _ = client([response])
            self.assertEqual(m.observe(client=c)['reason'], code)

    def test_requests_official_only_no_authorization(self):
        c, opener = client([Response(b'{"status":"success"}')])
        c.post('getWorks', {})
        req, timeout = opener.calls[0]
        self.assertEqual(req.full_url, 'https://api.mknov.com/v1/getWorks')
        self.assertLessEqual(timeout, 12)
        self.assertNotIn('Authorization', req.headers)
        self.assertNotIn('Cookie', req.headers)
        with self.assertRaises(m.ObservationError):
            c.post('https://evil.test/', {})
        self.assertEqual(len(opener.calls), 1)

    def test_redirects_blocked_even_to_other_official_path(self):
        with self.assertRaises(m.ObservationError) as exc:
            m.NoRedirect().redirect_request(None, None, 302, '', {}, 'http://localhost/')
        self.assertEqual(exc.exception.code, 'REDIRECT_REFUSED')

    def test_total_budget_and_deadline(self):
        c, _ = client([Response(b'{"status":"success"}') for _ in range(5)])
        for _ in range(5):
            c.post('getWorks', {})
        with self.assertRaises(m.ObservationError):
            c.post('getWorks', {})
        self.assertEqual(c.requests, 5)
        c, _ = client([])
        c.clock.now = 1000
        with self.assertRaises(m.ObservationError):
            c.post('getWorks', {})
        self.assertEqual(c.requests, 0)


class MknovWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (Path(__file__).parents[1] / '.github/workflows/mknov-health.yml').read_text()

    def expression(self, prefix, values):
        # Interpret the actual workflow's small boolean expression, not a second
        # independent policy. Reject arbitrary AST/code and test every event path.
        line = next(line for line in self.workflow.splitlines() if line.strip().startswith(prefix))
        expression = line.split(prefix, 1)[1].strip().removeprefix('${{').removesuffix('}}').strip()
        for key, value in values.items():
            expression = expression.replace(key, repr(value))
        tree = ast.parse(expression.replace('&&', ' and ').replace('||', ' or '), mode='eval')

        def interpret(node):
            if isinstance(node, ast.Expression):
                return interpret(node.body)
            if isinstance(node, ast.Constant):
                return node.value
            if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
                return interpret(node.left) == interpret(node.comparators[0])
            if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
                result = interpret(node.values[0])
                for value in node.values[1:]:
                    result = (interpret(value) if result else result) if isinstance(node.op, ast.And) else (result if result else interpret(value))
                return result
            self.fail('Unexpected workflow expression; review its semantics explicitly')
        return interpret(tree)

    def test_modes_and_live_gates_for_all_event_paths(self):
        cases = [('workflow_dispatch', 'monitor', '', 'monitor', True),
                 ('workflow_dispatch', 'deep', '', 'deep', True),
                 ('workflow_dispatch', 'monitor', '47 7 * * 0', 'monitor', True),
                 ('schedule', '', '17 6 * * *', 'monitor', True),
                 ('schedule', '', '47 7 * * 0', 'deep', True),
                 ('push', '', '', 'monitor', False),
                 ('pull_request', '', '', 'monitor', False)]
        for event, mode, schedule, expected, live in cases:
            with self.subTest(event=event, mode=mode, schedule=schedule):
                values = {'github.event_name':event, 'inputs.mode':mode, 'github.event.schedule':schedule}
                self.assertEqual(self.expression('MKNOV_MODE:', values), expected)
                self.assertEqual(self.expression('if:', values), live)
        self.assertIn("- cron: '17 6 * * *'", self.workflow)
        self.assertIn("- cron: '47 7 * * 0'", self.workflow)

    def test_all_refs_share_one_upstream_concurrency_group(self):
        group = next(line.strip() for line in self.workflow.splitlines() if line.strip().startswith('group:'))
        self.assertEqual(group, 'group: mknov-health')
        self.assertIn('cancel-in-progress: false', self.workflow)

    def test_artifact_names_preserve_each_run_attempt(self):
        self.assertIn('name: mknov-health-${{ github.run_id }}-${{ github.run_attempt }}', self.workflow)
        self.assertIn('if-no-files-found: error', self.workflow)
        self.assertIn('retention-days: 7', self.workflow)
        self.assertNotIn('continue-on-error:', self.workflow)


class MknovReportTests(unittest.TestCase):
    def test_failure_cli_writes_metadata_artifact_and_fails(self):
        c, _ = client([Response(b'', 403)])
        report = m.observe(client=c)
        with tempfile.TemporaryDirectory() as directory:
            output, summary = Path(directory) / 'failure.json', Path(directory) / 'summary.md'
            with patch.object(m, 'observe', return_value=report), patch('sys.argv', ['monitor', '--output', str(output)]), \
                    patch.dict(os.environ, {'GITHUB_STEP_SUMMARY':str(summary)}), contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(m.main(), 2)
            self.assertEqual(json.loads(output.read_text())['classification'], 'BLOCKED_BY_UPSTREAM')
            self.assertIn('BLOCKED_BY_UPSTREAM', summary.read_text())
            self.assertNotIn('content', stdout.getvalue())

    def test_atomic_replace_failure_preserves_previous_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'report.json'
            output.write_text('previous safe report')
            with patch.object(m.os, 'replace', side_effect=OSError('synthetic disk failure')):
                with self.assertRaises(OSError):
                    m.save_report(output, {'classification':'FAIL'})
            self.assertEqual(output.read_text(), 'previous safe report')
            self.assertEqual([p.name for p in Path(directory).iterdir()], ['report.json'])


if __name__ == '__main__':
    unittest.main()
