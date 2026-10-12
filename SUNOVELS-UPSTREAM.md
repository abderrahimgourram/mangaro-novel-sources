# Sunovels: fractional chapter links collide — Reverend Insanity

Observed 2026-10-12. This report uses anonymous public HTML and Next.js Flight responses; no authentication or locked-content bypass was attempted.

Reproduce at https://sunovels.com/novel/reverend-insanity?activeTab=chapters&page=23 (displayed page 24; pagination is zero-indexed). There are 50 published rows but only 48 distinct URLs.

| Published label | Published address |
|---|---|
| 1153 | /novel/reverend-insanity/1153 |
| 1153,2 | /novel/reverend-insanity/1153 |
| 1154 | /novel/reverend-insanity/1154 |
| 1154,2 | /novel/reverend-insanity/1154 |

The fractional rows have different titles and publication timestamps. Both rendered HTML and the public `RSC: 1` response preserve these collisions. The four React anchor keys are null; their props contain href, prefetch, title and children, with no independent fractional ID or slug.

Following the actual published addresses returns integer chapter records 21958 (1153) and 21960 (1154), both owned by novel ID 88. Their `isLocked` values are true and `content` values are null. Navigation is 1152 → 1153 → 1154 → 1155, with no independently exposed fractional destination. Integer record slugs are 1153-الفصل-5 and 1154-الفصل-5; these do not supply identities for fractional rows. No alternate URLs or intervening numeric IDs were guessed or requested.

The novel-bound Flight metadata reports 2343 published chapters and 47 pages. Samples: displayed page 24 has 50 rows/48 URLs; page 25 has 50/50; final page 47 has 43/43 and disabled Next. Across these samples, 143 rows map to 141 URLs. Intermediate pages were not re-traversed; the global actual row and distinct-URL counts are unverified. No complete readable index is claimed. Only two reader records were checked for locked state; the global locked-row count remains unknown. No fractional chapter body was verified.

Please clarify whether these are separate chapters or parts of a combined chapter. If separate, expose stable distinct chapter IDs and working officially supported addresses, and correct listing links, chapter ownership, numbering and previous/next navigation consistently. If combined, publish explicit part/content-equivalence semantics. Keep access restrictions explicit; no unlocking request is implied.

This evidence proves an upstream public-address ambiguity, not that the underlying texts are identical or absent. URL deduplication cannot resolve it. Mangaro must retain DEGRADED health and exclude this mapping from independently verified remote publication.

Local consumer caveat: Mangaro's existing URL-keyed chapter parser/cache also deduplicates these colliding addresses. This investigation does not alter persistent keys, reorder progress, or present that deduplication as a verified repair. All four observed rows are retained in the evidence report. Sunovels remains registered through its bundled mapping.

Seven Sunovels requests were made: three chapter-list HTML samples, two public Flight responses and two reader pages. No private endpoints or fractional-route guesses were used. Existing fractional HTTP-400 observations were not repeated. Production signed partial revision 4 remains unchanged and excludes Sunovels.
