# Project 3 — Vehicle Master Stable ID / Provenance

Date: 2026-09-20  
Branch: `codex/project3-identity-provenance`  
Base: `main@233115fb1daf9f17ba58a4fae2c30eaaf99b2e8c`

## Current decision

The original assumption that the existing `id` was stable and unique was disproved by a
full real-data blob audit.

Current contract:

- `id` = backward-compatible, non-unique display/matching key
- `uid` = unique durable foreign key
- `identity_key` = internal semantic identity basis for uid continuity

## Real-data audit

Current export contains 12,301 total entity nodes:

- manufacturers: 75
- models: 1,121
- sub_models: 1,805
- powertrains: 2,950
- trims: 6,350

Existing compatibility-id debt:

- unique compatibility ids: 11,123
- duplicate occurrences: 1,178
- duplicate distinct ids: 922
- duplicate-id levels:
  - sub_model: 86 distinct duplicated ids
  - powertrain: 392
  - trim: 444

Root causes verified include:

- same chassis/gen code reused across facelift periods
- same fuel/displacement powertrain split by seat count
- normalized trim names collapsing distinct raw variants

Additional lookup-loss finding:

- sub_models: 1,805
- unique compatibility-id keys: 1,695
- existing `codes.json.generations` can therefore overwrite 110 sub-model entries
- v2 adds `generations_by_uid` and `generation_id_index` to preserve all 1,805

## Semantic-key audit

v2 candidate semantic keys were evaluated against the full dataset:

- manufacturer: 75 / 75 unique
- model: 1,121 / 1,121 unique
- sub_model: 1,805 / 1,805 unique
- powertrain: 2,950 / 2,950 unique
- trim: 6,350 / 6,350 unique

Collision count: **0**

## Implemented on branch

- identity contract upgraded to schema v2.0
- semantic-key-based durable UID registry with deterministic 128-bit digest
- shared `identity_semantics.py` to prevent export/audit rule drift
- reproducible `audit_identity_source.py` full-source audit command
- explicit semantic-key alias ledger
- compatibility id history
- parent alias continuity
- duplicate compatibility ids allowed
- duplicate semantic identity / uid rejected
- uid added to tree, flat export, codes, and match index
- lossless `generations_by_uid` + compatibility-id-to-uid[] index
- identity-map generation
- provenance generation
- cross-artifact release validator
- exporter automatically fails closed when validator fails
- persisted-registry lifecycle documented
- regression tests for semantic aliasing, duplicate legacy ids, and validator rejection paths

## Validation completed

- full real-data compatibility-id audit — PASS
- full real-data semantic-key uniqueness audit — PASS, 0 collisions
- semantic alias continuity test — PASS
- parent alias / descendant continuity test — PASS
- missing alias target rejection — PASS
- duplicate active semantic identity rejection — PASS
- duplicate legacy id with distinct semantic entities — PASS
- valid cross-artifact fixture validation — PASS
- corrupted flat uid rejection — PASS
- Python syntax compilation of local validation modules — PASS

GitHub Actions was intentionally not added.

## Remaining HOLD before canonical main

- execute the actual Python exporter once against the full real `vehicle-tree.json`
- inspect and persist the first generated `dist/identity-map.json` baseline
- run the release validator on those generated full artifacts
- then migrate downstream foreign keys from `id` to `uid`

The design collision problem is resolved. The only remaining gate is the first real Python export
and baseline-registry review.
