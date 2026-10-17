# Independent Mknov monitoring

Mknov (`novel.mknov`) uses an anonymous JSON API, not the signed CSS-rule
protocol. This observer is deliberately outside `rules/`, `tools/plan.py`,
`tools/monitor.py`, health history, staging, signing and publication. A PASS is a
scoped observation, never source-wide Android acceptance or publication authority.
No fifth source has been registered in the four-source signed protocol.

## Contracts and scope

Contract reference: Android `MknovSource.kt`, integration commit
`84cb0bd35eeaa9f10866b0bc817c4eb387892fe2`; existing recorded metadata fixtures
were inspected read-only. All requests are POST JSON to the fixed HTTPS base
`https://api.mknov.com/v1/`. No authentication or cookies are used.

| Operation | Request | Required evidence |
| --- | --- | --- |
| Catalog | `getWorks`, `{"works":"views","limit":3,"offset":0}` | Successful envelope, nonempty names, positive unique IDs, correct sampled count |
| Details | `getWorkById`, `{"id":"96"}` | Exact work ID, title and structurally valid author/story/status metadata |
| Search | `searchByKeyword`, keyword from validated details | Complete snapshot, unique IDs, exact independently retrieved work 96 present |
| Index, deep only | `getChaptersByWorkId`, `{"id":96}` | Flatten volume groups, exact declared count, unique IDs, matching work IDs, explicit boolean access state |
| Text | `getChapterBatch`, `{"id":20716}` ordinarily | Exact chapter ID, explicit public access, matching work title, readable nonempty text; output metrics/hash only |

The index request requires a **numeric** ID; details use the established string
ID. Index chapter labels are sorted numerically, with server ID as a stable tie
breaker. Zero and distinct parts sharing a number are valid; duplicate IDs are
not. The maximum chapter label never substitutes for a count.

Ordinary mode uses the historically verified chapter sample and explicitly
reports `chapterMembershipRevalidated:false`; matching title is supplemental,
not fresh proof of work membership. It never downloads the complete index.
Deep mode retrieves one complete index and verifies membership plus number. If
the reference chapter has become restricted/missing, it selects one explicitly
free indexed chapter. It never requests a chapter already known to be restricted.
The reader endpoint does not return `work_id`; deep membership is established
through the index, not inferred from that response. Only the sampled work is
retrieved independently from search, avoiding per-result detail requests.

## Budgets and failure safety

- Serial requests; at least one second between request starts.
- Ordinary: four requests, maximum five with retries. Deep: five, maximum six.
- One retry **total**, only for transport/timeouts (including truncated HTTP reads) or HTTP 5xx, one-second backoff.
- Per-request timeout at most 12 seconds; checked elapsed budget 80/120 seconds.
  A currently blocked socket read can run up to its timeout beyond the budget;
  the workflow also has a four-minute limit. No infinite retries.
- Catalog/search/details bounded at 256 KiB each; text 1 MiB; index 8 MiB.
  Streaming and declared-length limits, truncation detection and strict JSON
  parsing (including rejection of duplicate keys/nonfinite values).
- Fixed official HTTPS endpoints only; redirects, proxies, non-JSON responses
  and non-identity encoding rejected. Default TLS verification remains enabled.
- No chapter bodies, titles, descriptions, headers, cookies, credentials or raw
  exception strings in reports/logs. Text exists only temporarily in process
  memory. Reports contain counters, public opaque IDs, hashes and fixed reasons.
- Reports are atomically replaced with mode 0600, capped below 16 KiB.
- `PASS`: requested scoped operations valid. `FAIL`: observed contract violation.
  `INSUFFICIENT_EVIDENCE`: transport/timeout/5xx, empty or missing sample, internal
  execution failure. `BLOCKED_BY_UPSTREAM`: 401/403/429, redirects or explicit
  access restriction. All non-PASS classifications exit 2; none authorize rules.
- HTTP 403/429 on GitHub is an upstream/runner access observation, not evidence
  that Android is broken. No challenge bypass or alternate bridge is attempted.

## GitHub workflow

`.github/workflows/mknov-health.yml` has only `contents: read`, no signing or
production secrets, no environment, APK build, source publication or feed writes.
Pinned actions checkout without persisted credentials. Offline contracts run
first. Observation reports are uploaded with `always()`, retained seven days;
missing evidence fails rather than manufacturing a PASS. A repository-wide
`mknov-health` concurrency group serializes probes across all refs; pending GitHub
runs may be superseded under GitHub concurrency semantics. Reports include the
run attempt in their artifact name to retain previous attempts without conflicts.

- Daily ordinary sample: 06:17 UTC.
- Weekly deeper sample: Sunday 07:47 UTC.
- Manual dispatch: explicit `monitor` or `deep` mode.
- Pushes on `monitor/mknov-health-*`: **offline tests only**, never live probes.
- Existing health workflow pushes target `main`; source operations require its
  own main-branch gates. This branch's workflow name cannot trigger that chain.
- GitHub schedules run on the default branch. Review/merge is intentionally not
  automatic; schedule/manual availability on the default branch remains pending
  review. A successful branch test is not a scheduled GitHub live observation.

Local commands (no dependencies beyond Python standard library):

```sh
python -m unittest discover -s tests -p test_mknov_health.py -v
python tools/mknov_health.py --mode monitor --output /tmp/mknov-monitor.json
python tools/mknov_health.py --mode deep --output /tmp/mknov-deep.json
```

## Verification recorded 2026-10-17 UTC

Initial repository: branch `docs/reliability-closure-handoff-20261012`, HEAD
`27b887d910e556b92771ac47ad30016c71b8296a`. Seven tracked modifications and
existing untracked Sunovels/SeaNovel work were preserved and excluded from the
Mknov commit. Initial hashes of 111 existing source/configuration files and the
Android HEAD/status/diff were recorded locally before implementation.

**Synthetic offline fixtures**, no copied chapter bodies: 38 tests passed.
Coverage includes identity/count/access checks, genuine empty state, malformed
JSON, timeouts, 403/429/5xx, size bounds, redirects, retry budgets, pacing,
redaction, atomic report permissions and ordinary/deep isolation.

**Live public API**, one work 96: ordinary PASS (4 requests), deep PASS
(5 requests), total 9, no retries. Deep observed 3,218 unique indexed chapters,
all marked public by the index. Chapter 20716 was independently marked public by
the reader response and had 97 paragraphs / 8,812 characters. These observations
are time-specific, not future guarantees or proof every chapter is readable.
Content SHA-256:
`75cd1730ce3f4c3c620ce55757fbb88af1799c457bcaeb8c73c11d2e09f77c87`.
Ordered index identity/access SHA-256:
`cc439c92eb44a22f0cc5adc2cf3cd9bf7e0d00006615a7d82710ef9162e806ed`.
Only metadata reports were retained locally, not chapter content.

**Independent baseline audit (hardening phase)**: clean detached worktrees
at `27b887d910e556b92771ac47ad30016c71b8296a` (pre-Mknov `main`) and
`1a05755f1fcb55e283bda58464023485a9b855a6` (original monitor) passed 150
and 188 tests respectively, each with one optional skip, using the same Python
3.14.7 interpreter and installed dependencies. The earlier 189/227-test reports
were from the owner's **dirty working copy**, including uncommitted Sunovels
changes and extra untracked tests; they were not clean commit acceptance.

The seven bounded-health failures/errors reproduce only with that working
copy's new strict public-metadata parser and old HTML-only fixture. Direct parser
inspection reports `INDEX_OWNERSHIP_MISSING`; the wrapper fails closed with
`REPRESENTATION_INVALID` before pagination/text assertions run. The eighth case
is an untracked Miniflare test depending on a local Worker at 127.0.0.1:8787;
it reports `STAGING_NETWORK_FAILURE` when that service is absent. It does not
exist in either committed baseline. These unrelated files/assertions have not
been modified or excluded. This is not evidence of a Mknov regression.

**Targeted hardening**: deterministic counterexamples demonstrated (1) incomplete
HTTP reads being mislabeled `MONITOR_INTERNAL_ERROR`, (2) per-ref concurrency
allowing simultaneous probes of the same upstream, and (3) artifact names
colliding across run attempts under immutable artifact semantics. Narrow fixes
classify incomplete HTTP reads as transport failures under the existing single
retry budget, serialize all refs, and distinguish artifact attempts. Original
mode selection is unchanged and tested against the actual workflow expression:
manual monitor/deep, daily/weekly cron, push and PR. CLI failure tests verify a
non-PASS JSON artifact plus exit 2; atomic-replace failure preserves old reports.
The focused suite now contains **45 tests**, all passing locally. The independent
review does not claim GitHub deep acceptance from the older local observation;
that separate single deep run is recorded in the owner-review handoff report.
`actionlint` v1.7.12 passes. No scheduled frequency or publisher gate changed.

## Boundaries and remaining acceptance

All original rule files, public manifest/revision, trust keys, publisher,
four-source histories/workflows and SeaNovel authenticated Vercel contracts
remain unchanged from the initial worktree (including pre-existing dirty work).
No Android file was edited, no APK was built/installed and no bridge setup was
run. Mknov cloud publication is **unsupported/unactivated**. It requires a
separate reviewed compatible protocol/client/backend design; this monitor does
not implement that extension. Real Android reader rendering/navigation/offline
acceptance remains a separate outstanding task.
