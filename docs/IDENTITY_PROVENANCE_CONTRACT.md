# Vehicle Master Identity & Provenance Contract

Status: Project 3 implementation candidate  
Schema: identity contract v2.0  
Scope: `vehicle-master` export contract

## Ground truth discovered on 2026-09-20

The existing human-readable `id` is **not unique** in the real export.

- total nodes: 12,301
- unique compatibility ids: 11,123
- duplicate occurrences after the first: 1,178
- duplicate distinct ids: 922
- affected levels: sub_model, powertrain, trim

Examples include the same chassis code being reused across facelift periods and the same
fuel/displacement powertrain being split by seat count.

Therefore `id` is a compatibility/display key only. It must not be used as a unique foreign key.

## Contract

### 1. Compatibility id

The existing `id` format remains available so current consumers are not broken.

```
mf-{manufacturer}.md-{model}.sm-{generation}.pw-{fuel-disp-drive}.tr-{trim}
```

It is explicitly non-unique.

### 2. Durable uid

Every entity receives one unique opaque `uid`.

`uid` is generated from an internal semantic `identity_key`, not from compatibility `id`.

The real 12,301-node dataset was audited against the v2 semantic-key rules and produced
**zero semantic-key collisions** at every level.

### 3. Semantic identity key rules

- manufacturer: manufacturer source code, with normalized name fallback
- model: durable manufacturer uid + model source code, with normalized name fallback
- sub_model:
  - preferred: durable model uid + sub-model source code
  - fallback: durable model uid + generation code + start month + source/raw name
- powertrain: durable sub-model uid + fuel + displacement + battery + drivetrain + turbo + seat
- trim: durable powertrain uid + raw/original trim name, normalized name fallback

Mutable price, range, classification flags, and display ordering are not identity components.

### 4. Alias / rename continuity

If a semantic identity-bearing field must change, add:

```json
{
  "schema_version": "2.0",
  "aliases": {
    "<new identity_key>": "<previous identity_key>"
  }
}
```

The registry reuses the previous uid and records the old key in `key_aliases`.

A compatibility `id` may change without changing uid when the semantic key remains the same.
Past compatibility ids are retained in `id_history`.

If a parent semantic key changes through an alias, unchanged descendants remain stable because
their key uses the durable parent uid.

### 5. Registry persistence

`dist/identity-map.json` becomes persistent state after the first approved full export.

- do not treat it as disposable cache after aliases exist
- version it with identity-bearing master changes
- fresh clones must receive the prior registry before applying aliases
- missing alias targets fail closed

### 6. Provenance

`dist/provenance.json` is keyed by uid and records:

- entity type
- semantic identity key
- compatibility id
- parent uid
- source code where present
- declared source where present
- raw/original naming evidence where present
- dataset input SHA-256

### 7. Release gate

`scripts/export.py` automatically runs `scripts/validate_identity_export.py`.

The release fails for:

- duplicate uid
- duplicate active semantic identity key
- tree / registry uid-set mismatch
- provenance mismatch
- flat / trim reference mismatch
- match-index / sub-model reference mismatch
- manifest count mismatch
- version mismatch
- invalid retired/active identity overlap

Duplicate compatibility `id` is measured and reported, but is not a release failure.

## Consumer migration

Existing consumers may continue reading `id` for display or compatibility matching.
New foreign keys must use `uid`.

During migration, storing both `uid` and `id` is recommended.
