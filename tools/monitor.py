#!/usr/bin/env python3
"""Independent monitoring history; no production signing or attestation contract changes."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import time
import requests
from bounded_health import probe
from reliability import load, save, locked, begin, record, report, ReliabilityError
from validate import build


def check_source(source, candidate, deep):
    domain = source['domain']
    if domain != 'seanovel.org':
        return probe(domain, source['selectors'], deep)
    ops = {name: 'SKIPPED' for name in ['catalog', 'search', 'details', 'chapters', 'pagination', 'text']}
    if not os.environ.get('SEANOVEL_ATTESTATION_SECRET'):
        return dict(classification='INSUFFICIENT_EVIDENCE', unknown=True, reason='LOCAL_ATTESTATION_UNAVAILABLE',
                    operations=ops, evidence='ATTESTATION_UNVERIFIED', needsDeep=False,
                    attestationState='LOCAL_ATTESTATION_UNAVAILABLE', sourceObservation='UNVERIFIED', bridgeReachability='NOT_CHECKED')
    try:
        from sea_attestation import check
        result = check(candidate)  # Exact existing HMAC request and response contract.
        if result.get('attestationVerified') is not True:
            raise ValueError('ATTESTATION_NOT_VERIFIED')
        for operation in ['catalog', 'search', 'details', 'chapters', 'text']:
            ops[operation] = 'PASS' if result.get(operation) is True else 'FAILED'
        # Existing attestation authenticates a sample, not an official total or pagination termination.
        ops['chapters'] = ops['pagination'] = 'PARTIAL'
        return dict(classification='DEGRADED', ok=True, complete=False, reason='ATTESTED_SAMPLE_UNKNOWN_INDEX_COMPLETENESS',
                    operations=ops, evidence='SEANOVEL_ATTESTED_SAMPLE', needsDeep=False,
                    observedChapterCount=result['chapter_count'], indexState='UNKNOWN_TOTAL',
                    attestationState='VERIFIED', sourceObservation='ATTESTED_SAMPLE_HEALTHY', bridgeReachability='REACHABLE')
    except requests.RequestException as error:
        code = getattr(getattr(error, 'response', None), 'status_code', None)
        # A bridge HTTP error is not cryptographically verified SeaNovel evidence.
        return dict(classification='INSUFFICIENT_EVIDENCE', unknown=True,
                    reason='BRIDGE_REQUEST_UNVERIFIED', operations=ops, operation='attestation',
                    evidence='ATTESTATION_UNVERIFIED', needsDeep=True, attestationState='UNVERIFIED',
                    sourceObservation='UNVERIFIED', bridgeReachability='REACHABLE' if code else 'UNVERIFIED')
    except (ValueError, KeyError):
        return dict(classification='INSUFFICIENT_EVIDENCE', unknown=True, reason='ATTESTATION_NOT_VERIFIED',
                    operations=ops, operation='attestation', evidence='ATTESTATION_UNAVAILABLE', needsDeep=True,
                    attestationState='UNVERIFIED', sourceObservation='UNVERIFIED', bridgeReachability='UNVERIFIED')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=Path('health-plan.json'))
    parser.add_argument('--state', type=Path, default=Path('.source-health/state.json'))
    parser.add_argument('--report', type=Path, default=Path('monitor-report.json'))
    args = parser.parse_args()
    started = time.monotonic()
    plan = json.loads(args.plan.read_text()); selected = plan['sources']; candidate = build(2)
    registry = {s['domain']: s for s in candidate['sources']}
    if set(registry) != {s['id'] for s in plan['inventory']}:
        raise ReliabilityError('NOVEL_REGISTRY_PLAN_MISMATCH')
    if len(plan['inventory']) != len(registry) or len(selected) != len(set(selected)) or not set(selected) <= set(registry):
        raise ReliabilityError('INVALID_SOURCE_SELECTION')
    with locked(args.state):
        state = load(args.state)
        if state['generation'] != plan['generation']:
            raise ReliabilityError('STALE_PLAN_NO_STATE_WRITE')
        rows = []
        if selected:
            begin(state, selected, plan['mode']); save(args.state, state)
            deep = plan['mode'] in {'deep', 'weekly', 'manual'}
            with ThreadPoolExecutor(max_workers=3) as pool:
                tasks = {pool.submit(check_source, registry[sid], candidate, deep): sid for sid in selected}
                for task in as_completed(tasks):
                    sid = tasks[task]
                    try:
                        observation = task.result()
                    except Exception:
                        observation = dict(classification='INSUFFICIENT_EVIDENCE', unknown=True, reason='ISOLATED_CHECK_ERROR', operations={}, needsDeep=True)
                    rows.append(record(state, sid, observation, plan['mode']))
                    save(args.state, state)
        report(args.report, rows, plan['inventory'], plan['mode'], started, selected, state=state, state_path=args.state)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('MONITOR_EXECUTION_FAILED_NO_PUBLICATION')
        raise SystemExit(1)
