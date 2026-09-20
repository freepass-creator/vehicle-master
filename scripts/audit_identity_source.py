# -*- coding: utf-8 -*-
"""Audit source master identity uniqueness before export.

Usage:
    python scripts/audit_identity_source.py [data/vehicle-tree.json]

The audit intentionally allows duplicate compatibility ids but fails when the
semantic identity-key contract produces any collision.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

from identity_contract import stable_uid
from identity_semantics import (
    slug,
    manufacturer_identity_key,
    model_identity_key,
    sub_model_identity_key,
    powertrain_identity_key,
    trim_identity_key,
)


HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SOURCE = os.path.normpath(os.path.join(HERE, "..", "data", "vehicle-tree.json"))


def _collision_summary(values):
    counts = Counter(values)
    duplicated = {key: count for key, count in counts.items() if count > 1}
    return {
        "total": len(values),
        "unique": len(counts),
        "duplicate_distinct": len(duplicated),
        "duplicate_occurrences": sum(count - 1 for count in duplicated.values()),
        "samples": [
            {"value": key, "occurrences": count}
            for key, count in list(sorted(duplicated.items()))[:10]
        ],
    }


def audit(tree):
    compatibility_ids = []
    compatibility_by_type = defaultdict(list)
    semantic_keys_by_type = defaultdict(list)
    counts = Counter()
    sub_model_ids = []

    for manufacturer in tree.get("manufacturers", []):
        counts["manufacturers"] += 1
        mfc = manufacturer.get("code") or slug(manufacturer["name"])
        m_id = "mf-%s" % mfc
        m_key = manufacturer_identity_key(mfc)
        m_uid = stable_uid("manufacturer", m_key)
        compatibility_ids.append(m_id)
        compatibility_by_type["manufacturer"].append(m_id)
        semantic_keys_by_type["manufacturer"].append(m_key)

        for model in manufacturer.get("models", []):
            counts["models"] += 1
            mdc = model.get("code") or slug(model["name"])
            model_id = "%s.md-%s" % (m_id, mdc)
            model_key = model_identity_key(m_uid, mdc)
            model_uid = stable_uid("model", model_key)
            compatibility_ids.append(model_id)
            compatibility_by_type["model"].append(model_id)
            semantic_keys_by_type["model"].append(model_key)

            for sub_model in model.get("sub_models", []):
                counts["sub_models"] += 1
                gc = sub_model.get("gen_code") or slug(sub_model["name"])
                sub_model_id = "%s.sm-%s" % (model_id, slug(gc))
                sub_model_key = sub_model_identity_key(model_uid, sub_model)
                sub_model_uid = stable_uid("sub_model", sub_model_key)
                compatibility_ids.append(sub_model_id)
                compatibility_by_type["sub_model"].append(sub_model_id)
                semantic_keys_by_type["sub_model"].append(sub_model_key)
                sub_model_ids.append(sub_model_id)

                for powertrain in sub_model.get("powertrains", []):
                    counts["powertrains"] += 1
                    powertrain_id = "%s.pw-%s" % (
                        sub_model_id,
                        slug(
                            "%s-%s-%s"
                            % (
                                powertrain.get("fuel"),
                                powertrain.get("displacement_l")
                                or powertrain.get("battery_kwh")
                                or "",
                                powertrain.get("drivetrain") or "",
                            )
                        ),
                    )
                    powertrain_key = powertrain_identity_key(
                        sub_model_uid, powertrain
                    )
                    powertrain_uid = stable_uid("powertrain", powertrain_key)
                    compatibility_ids.append(powertrain_id)
                    compatibility_by_type["powertrain"].append(powertrain_id)
                    semantic_keys_by_type["powertrain"].append(powertrain_key)

                    for trim in powertrain.get("trims", []):
                        counts["trims"] += 1
                        trim_id = "%s.tr-%s" % (
                            powertrain_id, slug(trim["name"])
                        )
                        trim_key = trim_identity_key(powertrain_uid, trim)
                        compatibility_ids.append(trim_id)
                        compatibility_by_type["trim"].append(trim_id)
                        semantic_keys_by_type["trim"].append(trim_key)

    compatibility = _collision_summary(compatibility_ids)
    compatibility["by_type"] = {
        entity_type: _collision_summary(values)
        for entity_type, values in compatibility_by_type.items()
    }

    semantic = {
        entity_type: _collision_summary(values)
        for entity_type, values in semantic_keys_by_type.items()
    }
    semantic_collision_count = sum(
        item["duplicate_occurrences"] for item in semantic.values()
    )

    unique_sub_model_ids = len(set(sub_model_ids))
    codes_overwrite_risk = len(sub_model_ids) - unique_sub_model_ids

    return {
        "ok": semantic_collision_count == 0,
        "counts": dict(counts),
        "total_entities": sum(counts.values()),
        "compatibility_id": compatibility,
        "semantic_identity": semantic,
        "semantic_collision_occurrences": semantic_collision_count,
        "codes_generations_overwrite_risk": codes_overwrite_risk,
    }


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SOURCE
    with open(path, encoding="utf-8") as handle:
        tree = json.load(handle)
    result = audit(tree)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
