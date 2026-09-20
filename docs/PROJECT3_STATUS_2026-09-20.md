# Project 3 — Vehicle Master Stable ID / Provenance

Date: 2026-09-20  
Branch: `codex/project3-identity-provenance`  
Base: `main@233115fb1daf9f17ba58a4fae2c30eaaf99b2e8c`

## Decision

Keep the current readable hierarchical `id` as a compatibility key and add a durable `uid`.
Do not break existing ERP consumers during migration.

## Implemented

- durable UID registry: `scripts/identity_contract.py`
- explicit rename ledger: `data/id-aliases.json`
- UID added to tree, flat export, codes and match index
- `dist/identity-map.json` generation
- `dist/provenance.json` generation
- manifest identity/provenance metadata
- parent rename continuity without descendant alias explosion
- duplicate current identity rejection
- missing alias target rejection (fail-closed)
- unit scenarios for rename continuity and collision protection
- cross-artifact identity/provenance release validator
- exporter now fails closed when the validation gate fails
- persisted registry lifecycle documented
- consumer contract documentation

## Validation performed

Isolated local logic validation:

1. direct rename alias preserves UID — PASS
2. parent rename preserves unchanged descendant UID — PASS
3. duplicate current identity fails closed — PASS
4. alias to missing previous identity fails closed — PASS
5. valid cross-artifact export graph — PASS
6. corrupted flat UID is rejected — PASS

GitHub Actions was intentionally not added.

## Still HOLD before canonical adoption

- run the full real `vehicle-tree.json` export once and inspect generated identity/provenance ledgers
- confirm the release validator passes against the full dataset
- review first generated `identity-map.json` as the persisted baseline registry
- then migrate downstream foreign keys gradually from `id` to `uid`

Until that full-dataset baseline is reviewed, this branch is a candidate implementation, not canonical main.
