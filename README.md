# Mangaro novel rules — private local preparation

Four independent identities: KolNovel, Cenele, Sunovels, SeaNovel. No dependency on the manga rule publisher, app releases, website or account system.

Selectors are declarative only. Fixed domains, engine/schema version 1, increasing revisions. Android pins the EC public key, verifies SHA-256 and SHA256withECDSA signatures, rejects invalid/foreign/executable/rollback payloads and retains a previous signed envelope. Structural algorithms and HTTP endpoints remain compiled in the Android engine.

`python tools/validate.py` validates the four namespaced configurations. `python tools/health.py` checks one public sample per source with bounded requests; only counts/hashes/error categories are recorded. A failure keeps the previous published manifest unchanged; the health artifact identifies the failed source for maintenance. Website redesigns require reviewed parser work; they cannot be repaired automatically.

The scheduled workflow detects degradation. Publishing is independently versioned and requires a reviewed environment and successful health checks. No workflow publishes an Android application or chapter text. Signing uses a dedicated novel-rule key, never the APK key. Supply `NOVEL_RULE_SIGNING_KEY` to that repository's reviewed environment only after security/licensing review. Private local key lives outside Git in ~/.config/mangaro/novels/.

**Not pushed, not public, not activated.** Android `PUBLIC_PIPELINE_APPROVED=false` prevents scheduling/networking before review. Once approved and published at the matching namespace, enable that switch; update worker starts only after entering Novels, never during application startup. Routine checks use a 24-hour network-constrained job without idle/backoff conflicts. No arbitrary remotely executable Kotlin or JavaScript.

Text rights remain with the respective owners. This repository contains no story fixtures, chapter HTML, credentials or downloaded covers.
