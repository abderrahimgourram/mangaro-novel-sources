# Source reliability monitoring

## Operational closure — 2026-10-12

Authenticated production CURRENT is **revision 4, schema 2 / engine 3 / PARTIAL**:
[public manifest](https://raw.githubusercontent.com/abderrahimgourram/mangaro-novel-sources/main/published/v2/manifest.json),
[immutable release](https://github.com/abderrahimgourram/mangaro-novel-sources/releases/tag/novel-rules-partial-v4).
[Genesis run](https://github.com/abderrahimgourram/mangaro-novel-sources/actions/runs/38185370761)
independently reverified Kolnovel's 507-entry closed published chain (official total
unknown), Cenele 632/632 and SeaNovel 831/831, with representative text. Its signed
receipt explicitly binds owner-attested **local** Android acceptance of exact bytes;
it does not claim Android ran on GitHub. The signed `source-operations-state` journal
records CURRENT, source approval gates false, and no previous LAST-GOOD.

SeaNovel's compatible bridge is deployed on the existing endpoint; legacy and partial
HMAC v2 requests were verified in [CI](https://github.com/abderrahimgourram/mangaro-novel-sources/actions/runs/38183027055).
Sunovels remains bundled and DEGRADED: different fractional labels share integer
addresses in upstream HTML and Flight. Locked bodies provide no equivalence proof.
No speculative URL, chapter key migration, or complete-index claim is authorized.

Manga monitoring is `17 */6 * * *`, retry `47 */3 * * *`; novel monitoring is
`43 */12 * * *`, retry `53 */3 * * *`. Both use conditional deep `29 3 * * *`
and weekly `7 4 * * 0`. Actual schedule events are recorded separately from dispatch
runs. Post-genesis novel cron is not yet observed as of this verification. Routine jobs
never launch Gradle/emulators or access production signing credentials.

**Automatic publication and rollback remain intentionally disabled.** There is no
meaningful accepted second rule change or authentic earlier production LAST-GOOD.
Do not reissue an identical bundle to create history. Activation requires a genuine
required declarative correction, pinned CURRENT/parent lineage, exact source preservation,
fresh independent source/runtime staging, authenticated earlier history, source approval,
and independently exercised source-scoped recovery before enabling the applicable gate.
Manga native BUILT_IN sources are not publishable declarative replacements.

Maintenance: inspect health summaries and trusted history coverage/classification;
use `python tools/verify.py --directory published/v2` for pinned artifact verification
and `python tools/operation_adapter.py` for read-only journal eligibility. Fetch the public
manifest/envelope and compare exact bytes before claiming delivery. Keep signing in
`reviewed-novel-rules` and existing main-only protections. Accepted v2 operations reuse
the exact authenticated staging artifact; re-signing ECDSA bytes would break receipt
bindings. Repair an interrupted signed reservation only with byte-identical evidence.
Never reset monitoring counters, alter immutable revision 4, or treat fixtures as authority.


## Schedule and budgets

Routine: `43 */12 * * *` (novels). Three-hour retry dispatcher: `53 */3 * * *`. Daily targeted deep: `29 3 * * *`.
Weekly comprehensive: `7 4 * * 0` (UTC; GitHub cron timing is approximate).
Planning performs no source requests. A zero-check planning report explicitly says
`PLANNING_ONLY` / `NOT_EXECUTED`, includes eligible/registered counts, and does not claim
source coverage. The checker rejects missing or duplicate results for selected sources.
Retry checks only due sources, after 1h, 2h and 4h, at most three retries per incident. Eligibility stays 1h/2h/4h; execution occurs on the next available three-hour dispatcher, not at the exact eligibility time.
Daily deep checks at most two eligible sources, oldest attempt first, no more than daily
per source. No due sources skips dependencies, source requests and expensive jobs.
Weekly selects every registered source; in-flight leases are explicitly excluded.

## History and credentials

No new health-state secret. Planning uses the existing `GITHUB_TOKEN` (`contents: read`,
`actions: read`) to restore immutable `source-health-state-v1` artifacts from this exact
workflow's completed, trusted default-branch schedule/dispatch runs. PRs cannot restore
or persist history. Artifact retention is 30 days, refreshed on every checking run.
Checksum detects corruption; authenticated GitHub workflow provenance supplies trust,
not the checksum. Scope mismatch, corrupt/expired history, failed API access or deleted
previously persisted history blocks restoration rather than resetting counters.
Local and Actions locks, generation checks, and checkpointed 1h leases prevent races.
Cancelled/unknown checks preserve counters and last verified successes. Partial sample
success can recover observational failures but cannot establish complete/native health.
Monitoring artifacts are observational history, never production rule authority.
SeaNovel HMAC credentials and protocol remain separate and unchanged.

## Verification and reporting

HTTP 200 is not HEALTHY. A 403/challenge is a blocked observation, not parser proof.
Repeated errors do not independently establish a compiled defect. Failed details/identity
block dependent chapters/reader/text. Complete index status requires legitimate totals,
termination and unique identities; counts from sampled rows are observations only.
Reports contain classifications, operation outcomes, verification tier, transitions,
follow-up eligibility, coverage and measured seconds. Private bodies/cookies/tokens are
excluded. Transition notices are deduplicated; correlated network failures suppress
individual defect notices. Every required code-change check runs; in-job path filtering
skips documentation-only expense without skipping the check itself. Changed workflows
run pinned actionlint; source changes run relevant fast tests before native compilation.

## Production and activation

`MANGARO_AUTOPUBLISH_ENABLED=false`. Routine and deep monitoring cannot sign or publish.
No production secrets are available to manga health jobs. Automatic safe-rule operations are isolated in `source-operations.yml`; monitoring cannot publish.
Declarative candidates need a verified baseline, identity/ownership/pagination regression
checks, independent validation and staging; new domains/headers require human review.
Unsupported transformations require a compiled update. Native observation witnesses
cannot become repair rules or establish full HEALTHY semantics.
The user authorized review-branch rollout and monitoring activation. Production activation remains conditional on all gates.
No secrets/variables/environment policies or live deployments were changed locally.
After approval, the first trusted run bootstraps empty observational history; manga
legacy counters are imported only after existing P-256 signature verification. If history
was deleted/expired, restore a trusted checkpoint explicitly; do not bootstrap it silently.
Existing GitHub environment protections and allowed branches still apply.

## Local verification

### Publication initialization and deep attestation

The existing reviewed `publish.yml` dispatch is the one-time genesis path. It must
validate every included source before signing the versioned partial bundle (legacy FULL still requires all four) with the
Android-pinned key, verify uploaded immutable assets, and then advance the feed.
A first signed release is CURRENT only; it is not an invented prior LAST-KNOWN-GOOD.
Automatic operations still require a separately authenticated earlier published
revision, approved source journal, and independent candidate-bound staging receipt.
An existing published bundle permits source-scoped acceptance only when every other
mapping is identical. Shared bundle signatures cover every mapping delivered in that bundle.
Chapter index hashes must match reviewed journal evidence; totals alone cannot prove
chapter identity preservation. New index evidence requires explicit baseline review.

SeaNovel protocol 1 remains bounded sample evidence. Protocol 2 retains the same HMAC
secret, nonce, candidate digest, revision and freshness bindings, with `request-v2`
and `response-v2` separation. It verifies the actual embedded complete index against
the official total, unique ascending source IDs, first/middle/last chapter ownership
and text, and an unchanged index after text checks. It makes six bounded requests
within 90 seconds, and rejects advertised continuations instead of guessing them.
Unknown totals, interrupted traversal or blocked access never produce COMPLETE.
The existing diagnostic workflow verifies both protocols against the authorized
bridge or a staged deployment of that same project. Its signed source evidence does
not establish publication provenance or bypass genesis and rollback requirements.

The Android novel update worker currently has `PUBLIC_PIPELINE_APPROVED=false`.
Feed publication alone does not activate Android consumption; that application change
requires a separate authorized release and is outside publisher maintenance.

`python -m unittest discover -s tests -v`
`actionlint -shellcheck=''`
`git diff --check`

Live local network observations are provisional and are not GitHub schedule verification.
Registry: existing `rules/*.json` / `validate.build`, currently Kolnovel, Cenele,
Sunovels and SeaNovel. Routine checks use at most 12 requests / 65s per direct source,
2 chapter-index pages and 1 text sample. Deep uses at most 48 requests / 180s,
25 index pages and 3 text samples from the observed index. No fabricated totals.
Kolnovel/Cenele/Sunovels stay DEGRADED until official totals and termination are proved.
Sunovels homepage canonical tags are ignored as identity evidence; actual matching
search routes, detail heading evidence and chapter ownership are checked instead.

SeaNovel bridge: https://mangaro-seanovel-check.vercel.app/api/probe.
Unauthenticated HTTP 401 proves only bridge reachability, not source health.
`LOCAL_ATTESTATION_UNAVAILABLE` means source health UNVERIFIED and operations SKIPPED.
Existing authenticated CI uses `SEANOVEL_ATTESTATION_SECRET` in `novel-health` and
`reviewed-novel-rules` environments, with unchanged nonce/digest/revision/timestamp/HMAC
verification. No secret values, names or payload formats changed. Bridge request errors
are unverified observations, not cryptographically confirmed source failures. A verified
sample establishes its attested stages only; the existing bridge does not attest complete
index pagination/official totals. Publication now refuses partial indexes, so a future
reviewed completeness proof is needed before publishing an all-source candidate.
No Vercel redeployment is required for monitoring these existing attested stages.


## Automatic safe-rule operations

`source-operations.yml` is separate from monitoring and shares the publication concurrency
lock. Its default-branch gate uses no signing credential. Production signing is isolated
in the existing credential contract; the existing repository variable must equal `true`
AND an authenticated, approved per-source journal must be eligible. Disabled automatic
operations skip their hosted jobs; no extra pip/install job on a no-op retry.
A manual signing-contract check validates the pinned key without publishing a rule.

The signed source-operation journal belongs to the dedicated `source-operations-state`
Git ref, not `main` or ephemeral runners. Non-force Git CAS checkpoints reserve revisions
before external writes. Signed current and last-good revisions, full witnesses, source
gates, independent staging receipts and audit hashes are mandatory. Missing history never
bootstraps production authority. No public observation artifact authorizes publication.
Safe class/id selector mappings and existing manga inference never emit executable code.
Novel source-scoped rollback preserves the current mappings of all unrelated sources in
its shared bundle. Rollback needs three revision-bound, confirmed semantic failures spaced
at least one hour apart, plus two successful full historical-rule validations and real
independent staging acceptance. Challenges, unknown exceptions and transport errors do
not qualify. Pending operations reconcile only exact authenticated before/after revisions.

Activation blockers currently include absent authenticated published last-good rules and
absent real-source candidate staging receipts. Diagnostic staging fixtures do not satisfy
real-source acceptance. Novel sample attestation/unknown index totals remain insufficient.
Do not enable the production variable merely because signing or monitoring CI succeeds.

Monitoring uses its own history-write concurrency group. Publication and rollback share
a separate publication group; manual signing checks and disabled operation runs have
unique groups, so GitHub's one-pending-run replacement cannot cancel monitoring or
protected publication accidentally. Repair execution reads authenticated observational
history for *eligibility only*: three semantic failures or a pending confirmed regression.
Healthy/unaffected sources do not trigger deep/signing jobs. Observation history never
satisfies the independent production acceptance gates.

## Initial publication and unknown totals

`publish.yml` defaults to `stage_only=true`: source acceptance precedes access to the
existing signing key, and verified manifest/envelope bytes are retained without writing
Releases or the public feed. An absent authenticated CURRENT requires the explicit
`initial_release=true` input. Initialization cannot replace CURRENT or invent a rollback
revision. A first production write still requires final authorization and independent
real-source acceptance of all four mappings. An authenticated first release alone does
not establish a previous last-known-good revision or enable automatic operations.
Subsequent scoped updates preserve every unchanged mapping from authenticated CURRENT;
an unchanged source's temporary failure need not invalidate another source's repair.

Kolnovel acceptance can prove its *published source index* without guessing an official
total: verify every stable post ID, chapter canonical and series owner, the complete
bidirectional reader navigation chain including both terminal boundaries, then refetch
the index and verify unchanged IDs, URLs, titles and boundaries. Displayed numeric labels
are not identities. `chapterCount` remains unknown when no official total is supplied;
`verifiedChapterCount` records the actual distinct chain, with
`completenessBasis=VERIFIED_CLOSED_CHAPTER_CHAIN`. This does not prove availability of
unpublished chapters. Acceptance has a 600-request/300-second ceiling and at most four
concurrent metadata requests, stopping before chapter text; only three representative
chapter bodies are sampled. Routine/deep monitoring retains its original smaller budget
and never traverses this whole chain.

Sunovels' identical chapter URLs with different titles fail explicitly as
`UPSTREAM_CHAPTER_IDENTITY_COLLISION`; fractional parts must not be discarded or assigned
invented URLs. A disabled next-page control is not a continuation. Until the upstream
publishes distinct stable paths or another genuinely verified identity mechanism is
supported, this source and all-source genesis acceptance remain blocked. No selector
change can recover two different chapter bodies from the same ambiguous URL.

## Versioned partial updates (production feed live; automatic operations disabled)

Legacy schema 1/engines 1–2 still mean exactly four sources. Schema 2/engine 3 adds a
mandatory `mode`: `PARTIAL` allows 1–4 unique registered replacements; `FULL` requires
all four. Whole source mappings replace previous mappings; selectors are never merged
field by field. Absent sources remain bundled or previously authenticated in Android.
Signatures still use the pinned ECDSA key, with the versioned manifest domain separator
`MangaroNovelManifestV2`. Both hashes and schema/engine/revision/path bindings are checked.
The new feed is `published/v2/manifest.json` and its immutable envelopes live alongside
it. Legacy files and release tags are independent; old apps keep their original feed.
Android retains at most four complete signed packages needed for current replacements,
with an atomic current/previous cache, global revision floor and shared installation lock.
Neither merged selector maps nor monitoring results become signature authority.

For isolated first staging, pass `initial_release=true`, `stage_only=true` and
`sources=novel.kolnovel,novel.cenele,novel.seanovel`. Initialization creates no historical
revision or rollback claim. Every included mapping must pass actual acceptance. Subsequent
partial preparations retain authenticated, unselected published mappings. For a single
changed domain, `publication_source` allows source-scoped health/signing only against
authenticated CURRENT and exact preservation of every other mapping. Partial production
publication additionally requires a fresh, independently signed `staging/acceptance.json`
bound to candidate hash, revision, repository, included/changed domains and distinct CI
runs. Existing operation journals supply this proof; absence or mismatch blocks writes.

The local SeaNovel candidate validator accepts the explicit new shape; HMAC protocol v2,
request/response bytes, secrets, digest, revision, nonce, expiry and full-index verification
are unchanged. There is no legacy projection or substituted digest. This compatibility
extension was deployed compatibly to the existing bridge and verified for legacy and partial
requests (see operational closure above); existing HMAC keys and protocol bindings remain
intact. No public key, production variable or Android approval flag has been changed.

Disposable signed fixtures test the real consumers but cannot verify against the production
key. Actual pinned-key signing/staging and genesis ran in the existing authorized CI environment
(see operational closure). No CURRENT, LAST-GOOD or receipt is minted from these fixtures. Genesis alone cannot enable rollback or automatic publication.

## Explicit real genesis acceptance

`publish.yml` can restore a successful main staging run through `staging_run`.
It authenticates the run, workflow, actor, pinned signatures and exact reviewed
three-source payload, then independently repeats all included-source acceptance.
`native_evidence` is explicitly **owner-attested local Android emulator evidence**:
it binds the consumer commit, exact manifest/envelope/key hashes, test-log hash,
platform and fresh successful result. It does not claim Android executed on GitHub.
Only the repository owner on main may make this one-time attestation. No private
key is exported to Android or to the local machine. An independently signed receipt
is issued in the existing protected signing environment only after these gates.

With `stage_only=true`, no production state is written. With explicit genesis
publication, a new authenticated journal reservation is created atomically on
`source-operations-state`; existing authenticated state is never overwritten.
Immutable Release assets and their exact public Git path are verified before CURRENT
advances. An interrupted reservation can reuse only byte-identical signed assets.
The final journal records authentic CURRENT, closes source approval gates, and
contains no invented previous revision. Automatic publication and rollback remain
disabled until real earlier publication history and source-specific gates exist.

Kolnovel's full acceptance checks all published chapter metadata with four bounded
requests at a time, preserving the original 600-request/300-second acceptance
budget, canonical identity, owner, complete navigation graph and repeated-index
checks. Routine monitoring does not traverse that graph.
