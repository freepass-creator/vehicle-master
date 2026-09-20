# -*- coding: utf-8 -*-
"""Validate vehicle-master identity/provenance export invariants.

Usage:
    python scripts/validate_identity_export.py [dist_dir]

Exits non-zero when any cross-artifact identity reference is inconsistent.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

TYPE_PREFIX = {
    "manufacturer": "vm_mf_",
    "model": "vm_md_",
    "sub_model": "vm_sm_",
    "powertrain": "vm_pw_",
    "trim": "vm_tr_",
}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate(dist_dir):
    required = [
        "manifest.json",
        "vehicle-master.json",
        "vehicle-master.flat.json",
        "codes.json",
        "match-index.json",
        "identity-map.json",
        "provenance.json",
    ]
    errors = []
    for name in required:
        if not os.path.exists(os.path.join(dist_dir, name)):
            errors.append("missing artifact: %s" % name)
    if errors:
        return {"ok": False, "errors": errors}

    manifest = load(os.path.join(dist_dir, "manifest.json"))
    tree = load(os.path.join(dist_dir, "vehicle-master.json"))
    flat_doc = load(os.path.join(dist_dir, "vehicle-master.flat.json"))
    codes_doc = load(os.path.join(dist_dir, "codes.json"))
    match_doc = load(os.path.join(dist_dir, "match-index.json"))
    identity = load(os.path.join(dist_dir, "identity-map.json"))
    provenance = load(os.path.join(dist_dir, "provenance.json"))

    versions = {
        "manifest": manifest.get("version"),
        "tree": tree.get("version"),
        "flat": flat_doc.get("version"),
        "codes": codes_doc.get("version"),
        "match": match_doc.get("version"),
        "provenance": provenance.get("version"),
    }
    if len(set(versions.values())) != 1:
        errors.append("version mismatch: %r" % versions)

    contract = manifest.get("identity_contract") or {}
    if contract.get("schema_version") != "2.0":
        errors.append("manifest identity_contract schema_version must be 2.0")
    if contract.get("durable_id") != "uid" or contract.get("compatibility_id") != "id":
        errors.append("manifest identity_contract is missing uid/id declaration")
    if contract.get("compatibility_id_unique") is not False:
        errors.append("manifest must declare compatibility_id_unique=false")
    if identity.get("schema_version") != "2.0":
        errors.append("identity-map schema_version must be 2.0")
    if provenance.get("schema_version") != "2.0":
        errors.append("provenance schema_version must be 2.0")

    nodes = []
    seen_ids = set()
    seen_uids = set()
    duplicate_ids = []
    duplicate_uids = []

    def add(node, entity_type, parent_uid):
        legacy_id = node.get("id")
        uid = node.get("uid")
        if not legacy_id:
            errors.append("missing id on %s node" % entity_type)
            return None
        if not uid:
            errors.append("missing uid on %s: %s" % (entity_type, legacy_id))
            return None
        if legacy_id in seen_ids:
            duplicate_ids.append(legacy_id)
        seen_ids.add(legacy_id)
        if uid in seen_uids:
            duplicate_uids.append(uid)
        seen_uids.add(uid)
        prefix = TYPE_PREFIX[entity_type]
        if not re.fullmatch(re.escape(prefix) + r"[0-9a-f]{32}", uid):
            errors.append("uid format mismatch: %s %s" % (entity_type, uid))
        nodes.append((entity_type, legacy_id, uid, parent_uid))
        return uid

    counts = Counter()
    trim_pairs = set()
    generation_pairs = set()

    for manufacturer in tree.get("manufacturers", []):
        counts["manufacturers"] += 1
        m_uid = add(manufacturer, "manufacturer", None)
        for model in manufacturer.get("models", []):
            counts["models"] += 1
            model_uid = add(model, "model", m_uid)
            for sub_model in model.get("sub_models", []):
                counts["sub_models"] += 1
                sm_uid = add(sub_model, "sub_model", model_uid)
                if sm_uid:
                    generation_pairs.add((sub_model.get("id"), sm_uid))
                for powertrain in sub_model.get("powertrains", []):
                    counts["powertrains"] += 1
                    pw_uid = add(powertrain, "powertrain", sm_uid)
                    for trim in powertrain.get("trims", []):
                        counts["trims"] += 1
                        trim_uid = add(trim, "trim", pw_uid)
                        if trim_uid:
                            trim_pairs.add((trim.get("id"), trim_uid))

    if duplicate_uids:
        errors.append("duplicate durable uids: %s" % sorted(set(duplicate_uids))[:10])

    manifest_counts = manifest.get("counts") or {}
    for key in ("manufacturers", "models", "sub_models", "powertrains", "trims"):
        if manifest_counts.get(key) != counts.get(key, 0):
            errors.append(
                "count mismatch %s: manifest=%r actual=%r"
                % (key, manifest_counts.get(key), counts.get(key, 0))
            )

    active_registry = {
        uid: record
        for uid, record in (identity.get("entities") or {}).items()
        if record.get("active", True)
    }
    if identity.get("entity_count") != len(nodes):
        errors.append(
            "identity entity_count mismatch: registry=%r tree=%r"
            % (identity.get("entity_count"), len(nodes))
        )
    if set(active_registry) != seen_uids:
        missing = sorted(seen_uids - set(active_registry))[:10]
        extra = sorted(set(active_registry) - seen_uids)[:10]
        errors.append("identity registry/tree uid set mismatch missing=%r extra=%r" % (missing, extra))

    by_uid = {
        uid: (entity_type, legacy_id, parent_uid)
        for entity_type, legacy_id, uid, parent_uid in nodes
    }
    active_identity_keys = {}
    for uid, record in active_registry.items():
        identity_key = record.get("identity_key")
        if not identity_key:
            errors.append("registry identity_key missing for %s" % uid)
        else:
            previous_uid = active_identity_keys.get(identity_key)
            if previous_uid and previous_uid != uid:
                errors.append(
                    "registry identity_key is not unique: %s" % identity_key
                )
            active_identity_keys[identity_key] = uid
        if uid not in by_uid:
            continue
        entity_type, legacy_id, parent_uid = by_uid[uid]
        if record.get("entity_type") != entity_type:
            errors.append("registry entity_type mismatch for %s" % uid)
        if record.get("current_id") != legacy_id:
            errors.append("registry current_id mismatch for %s" % uid)
        if record.get("parent_uid") != parent_uid:
            errors.append("registry parent_uid mismatch for %s" % uid)

    prov_entries = provenance.get("entries") or {}
    if set(prov_entries) != seen_uids:
        missing = sorted(seen_uids - set(prov_entries))[:10]
        extra = sorted(set(prov_entries) - seen_uids)[:10]
        errors.append("provenance/tree uid set mismatch missing=%r extra=%r" % (missing, extra))
    for uid, record in prov_entries.items():
        if uid not in by_uid:
            continue
        entity_type, legacy_id, parent_uid = by_uid[uid]
        if record.get("entity_type") != entity_type:
            errors.append("provenance entity_type mismatch for %s" % uid)
        if record.get("id") != legacy_id:
            errors.append("provenance id mismatch for %s" % uid)
        if record.get("parent_uid") != parent_uid:
            errors.append("provenance parent_uid mismatch for %s" % uid)
        registry_record = active_registry.get(uid) or {}
        if record.get("identity_key") != registry_record.get("identity_key"):
            errors.append("provenance identity_key mismatch for %s" % uid)

    flat_rows = flat_doc.get("rows") or []
    flat_pairs = [(row.get("id"), row.get("uid")) for row in flat_rows]
    if len(flat_pairs) != counts["trims"]:
        errors.append("flat row count mismatch: flat=%d trims=%d" % (len(flat_pairs), counts["trims"]))
    if len(set(flat_pairs)) != len(flat_pairs):
        errors.append("duplicate id/uid pair in flat export")
    invalid_flat = [pair for pair in flat_pairs if pair not in trim_pairs]
    if invalid_flat:
        errors.append("flat rows reference unknown trim identities: %r" % invalid_flat[:10])

    generations_by_uid = codes_doc.get("generations_by_uid") or {}
    generation_id_index = codes_doc.get("generation_id_index") or {}

    expected_generation_by_uid = {
        uid: legacy_id
        for entity_type, legacy_id, uid, parent_uid in nodes
        if entity_type == "sub_model"
    }
    if set(generations_by_uid) != set(expected_generation_by_uid):
        missing = sorted(set(expected_generation_by_uid) - set(generations_by_uid))[:10]
        extra = sorted(set(generations_by_uid) - set(expected_generation_by_uid))[:10]
        errors.append(
            "codes generations_by_uid mismatch missing=%r extra=%r"
            % (missing, extra)
        )
    for uid, legacy_id in expected_generation_by_uid.items():
        record = generations_by_uid.get(uid) or {}
        if record.get("id") != legacy_id:
            errors.append("codes generations_by_uid id mismatch for %s" % uid)

    expected_id_index = {}
    for uid, legacy_id in expected_generation_by_uid.items():
        expected_id_index.setdefault(legacy_id, []).append(uid)
    normalized_actual_index = {
        legacy_id: sorted(values)
        for legacy_id, values in generation_id_index.items()
    }
    normalized_expected_index = {
        legacy_id: sorted(values)
        for legacy_id, values in expected_id_index.items()
    }
    if normalized_actual_index != normalized_expected_index:
        errors.append("codes generation_id_index does not preserve every sub_model uid")

    match_entries = match_doc.get("entries") or []
    match_pairs = [(entry.get("id"), entry.get("uid")) for entry in match_entries]
    if len(match_pairs) != counts["sub_models"]:
        errors.append(
            "match-index count mismatch: match=%d sub_models=%d"
            % (len(match_pairs), counts["sub_models"])
        )
    invalid_match = [pair for pair in match_pairs if pair not in generation_pairs]
    if invalid_match:
        errors.append("match-index references unknown generation identities: %r" % invalid_match[:10])
    if match_doc.get("count") != len(match_entries):
        errors.append("match-index declared count mismatch")

    retired = set(identity.get("retired_uids") or [])
    if retired & seen_uids:
        errors.append("active tree uid incorrectly listed as retired")

    duplicate_id_counts = Counter(duplicate_ids)
    return {
        "ok": not errors,
        "version": manifest.get("version"),
        "counts": dict(counts),
        "tree_identity_count": len(nodes),
        "unique_compatibility_id_count": len(seen_ids),
        "compatibility_id_collision_count": len(duplicate_id_counts),
        "compatibility_id_duplicate_occurrences": len(duplicate_ids),
        "compatibility_id_collision_samples": sorted(duplicate_id_counts)[:10],
        "retired_identity_count": len(retired),
        "errors": errors,
    }


def main():
    dist_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "dist"
    )
    result = validate(os.path.abspath(dist_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
