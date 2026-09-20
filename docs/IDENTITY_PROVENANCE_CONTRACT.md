# Vehicle Master Identity & Provenance Contract

Status: Project 3 implementation candidate  
Scope: `vehicle-master` export contract

## Why this exists

The existing `id` is readable and useful, but parts of it are derived from fields that can legitimately change during normalization:

- powertrain: fuel / displacement or battery / drivetrain
- trim: trim name
- fallback manufacturer/model codes: normalized names

Changing one of those fields can change the current `id`. Downstream ERP systems must not lose entity identity because wording or normalization improved.

## Contract

### 1. `id` stays compatible

The existing hierarchical `id` remains in every export. It is not silently rewritten or removed.

### 2. `uid` is the durable reference

Every exported entity receives an opaque `uid`.

- first appearance: deterministic UID is created from entity type + current compatibility id
- later rebuilds: prior registry is loaded and the same UID is reused
- intentional identity-bearing rename: add an entry to `data/id-aliases.json`
- two current entities may never resolve to the same UID

Downstream systems should migrate foreign keys from `id` to `uid`. During migration they may store both.

### 3. Rename procedure

If a normalization changes an identity-bearing field:

1. calculate the new compatibility `id`
2. add `"new-id": "previous-id"` to `data/id-aliases.json`
3. run export
4. verify the UID did not change
5. ship the export and keep the previous id in the registry alias history

If the renamed entity is a parent, unchanged descendants reuse their prior UID structurally from
`(entity_type, durable parent UID, local id segment)`. You do not need to enumerate every
descendant alias. A descendant whose own identity-bearing segment changes still needs its own alias.

An undeclared rename of the changed identity segment creates a new UID by design; this makes
identity breaks visible instead of silently guessing.

### 4. Provenance

The export produces `provenance.json` keyed by UID. It records:

- entity type
- current compatibility id
- parent UID
- declared source where available
- raw/original naming evidence where available
- pipeline input file and input SHA-256 at dataset level

`manifest.json` points to the identity registry and provenance ledger.

## Compatibility / rollout

This is additive. Existing consumers can keep using `id` unchanged. New consumers should prefer `uid`.

No existing `id` values are rewritten by this change.


## Registry persistence rule

`dist/identity-map.json` is not disposable generated cache. After the first full-dataset baseline is
reviewed, it becomes the persisted identity registry for subsequent exports.

- do not delete or regenerate it from scratch after aliases exist
- review and version it together with identity-bearing master changes
- a fresh clone must receive the previous registry before applying a rename alias
- the exporter fails closed when an alias points to an identity absent from the previous registry

## Release gate

`scripts/export.py` runs `scripts/validate_identity_export.py` after writing the artifacts.
A release fails if the tree, flat export, match index, identity registry, provenance ledger,
manifest counts, or version references disagree.
