# Mangaro novel-source updates

Independent declarative rules for **exactly four identities**: `novel.kolnovel` (`kolnovel.com`), `novel.cenele` (`cenele.com`), `novel.sunovels` (`sunovels.com`), and `novel.seanovel` (`seanovel.org`). This repository has no dependency on the manga publisher, APK releases, accounts or website deployment. It contains no story fixtures, chapter HTML, private credentials or downloaded covers. Text rights remain with the respective owners.

## Validation and monitoring

Install `requirements.txt`; run `python tools/validate.py --revision 2` and `python -m unittest discover -s tests -v`. Pull requests run read-only validation/security tests, without environment secrets, persisted Git credentials or live website traffic. Daily monitoring runs at **04:21 UTC**, and can also be manually dispatched. It checks one public sample per source: catalog, search, details, every chapter-index page, and one chapter's readable text. Only counts, hashes and failure categories survive the process. Reports appear in the Actions summary and a seven-day `health.json` artifact. A failing scheduled check never signs or publishes anything. Website redesigns require reviewed fixes; they are not repaired automatically.

## Reviewed publication

Dispatch **Publish validated novel rules** on `main`, select an unused increasing `revision`, and set `reviewed=true` only after reviewing the changes. Only this workflow's main-branch environment `reviewed-novel-rules` has `NOVEL_RULE_SIGNING_KEY`. The key is the existing dedicated novel-rule signing identity, **not** the APK key. Never commit it. The workflow validates the candidate and runs all five live checks against the exact candidate digest before accessing the key. Both the manifest and rules envelope are signed, and both signatures are verified with `keys/rules-public.der`. Incorrect, incompatible or unhealthy candidates cannot advance the feed.

Only `manifest.json` and the explicit `rules-N.json` are uploaded to an immutable `novel-rules-vN` release. The uploaded bytes are downloaded and verified before the published Git ref advances. Older envelopes remain in `published/`; no release or revision is overwritten. A failed/non-fast-forward push leaves the old feed usable. For a verified release whose feed push failed, investigate the branch conflict and recover the already verified assets without replacing its tag; alternatively publish the next unused revision after a fresh review/check.

**Rollback:** dispatch with a *higher new revision* and `rollback_revision` naming a prior published revision. Its pinned-key-verified selectors are revalidated, health-checked and re-signed at the higher revision. Never lower the remote revision or bypass failed health probes.

## Android protocol

Public feed: `https://raw.githubusercontent.com/abderrahimgourram/mangaro-novel-sources/main/published/manifest.json`.

Payload: schema 1, engines 1–2; current emitted rules require engine 2. `source-manifest.schema.json` describes the payload; `update-manifest.schema.json` describes the signed feed. IDs/domains are fixed and selector keys allowlisted. CSS syntax is validated; document-wide/executable selectors are rejected. HTTP endpoints, pagination algorithms and canonical matching stay compiled in Android. Rule updates cannot run Kotlin, JavaScript or alter domains.

Manifest fields: `schemaVersion`, `engineVersion`, `revision`, `envelopePath`, `sha256`, `signature`. The signature is SHA256withECDSA over this exact ASCII protocol (including every final newline):

```
MangaroNovelManifestV1\n
1\n
<engineVersion>\n
<revision>\n
published/rules-<revision>.json\n
<envelope SHA-256>\n
```

The envelope independently signs its base64-decoded payload and includes the payload SHA-256. Android pins the existing DER public key, checks both signatures/hashes and binds manifest engine/revision to the signed payload. It rejects incompatible versions, foreign domains, tampering and older revisions. Atomic current/previous storage and packaged fallback remain independent of manga rules. Corrupt candidates cannot replace them; a newer bundled revision takes precedence over older disk rules.

Compatible selector changes require no new APK **for clients already containing and enabling this updater**. Structural source redesigns/new engine requirements can still require app changes. Enabling this pipeline cannot remotely activate previously shipped APKs whose updater switch was disabled. The local Android client is configured only after the public artifacts have been verified; no Android APK is built or published by these workflows. Checks are scheduled lazily after entering Novels, never on global startup.

Engine 2 supports original-title corroboration, Cenele per-volume `has_more` cursors and complete deduplicated indexes. Transport page size 50 is not a total limit. Public chapter links are counted without fetching their texts; one text sample is not a guarantee that every chapter is accessible. Genuine volume counts use unique URLs; declared counts are advisory. Downloads retain source edition identity and remain outside the manga queue.
