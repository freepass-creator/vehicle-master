# -*- coding: utf-8 -*-
"""Create the first approved vehicle-master identity registry baseline.

Usage:
    python scripts/bootstrap_identity_baseline.py YYYY-MM-DD

This command is intentionally first-baseline-only. Once a non-empty v2
identity-map exists, use the normal export command so identity continuity is
always anchored to the persisted registry.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

from audit_identity_source import audit
from export import DATA, DIST, build
from validate_identity_export import validate


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print(
            "usage: python scripts/bootstrap_identity_baseline.py YYYY-MM-DD",
            file=sys.stderr,
        )
        return 2

    date_str = argv[0]
    identity_path = os.path.join(DIST, "identity-map.json")
    if os.path.exists(identity_path):
        existing = _load(identity_path)
        if (
            existing.get("schema_version") == "2.0"
            and existing.get("entities")
        ):
            print(
                "baseline already exists; use: python scripts/export.py %s"
                % date_str,
                file=sys.stderr,
            )
            return 3
        print(
            "identity-map.json already exists but is not a valid non-empty v2 "
            "baseline; inspect it manually before bootstrap",
            file=sys.stderr,
        )
        return 4

    source_path = os.path.join(DATA, "vehicle-tree.json")
    source_tree = _load(source_path)
    source_audit = audit(source_tree)
    if not source_audit["ok"]:
        print(
            json.dumps(source_audit, ensure_ascii=False, indent=2),
            file=sys.stderr,
        )
        return 5

    version = build(date_str)
    final_validation = validate(DIST)
    if not final_validation["ok"]:
        print(
            json.dumps(final_validation, ensure_ascii=False, indent=2),
            file=sys.stderr,
        )
        return 6

    if final_validation.get("counts") != source_audit.get("counts"):
        print(
            "source/export count mismatch: source=%r export=%r"
            % (source_audit.get("counts"), final_validation.get("counts")),
            file=sys.stderr,
        )
        return 7

    if (
        final_validation.get("compatibility_id_duplicate_occurrences")
        != source_audit["compatibility_id"]["duplicate_occurrences"]
        or final_validation.get("compatibility_id_collision_count")
        != source_audit["compatibility_id"]["duplicate_distinct"]
    ):
        print(
            "source/export compatibility-id collision metrics disagree",
            file=sys.stderr,
        )
        return 8

    identity = _load(identity_path)
    if identity.get("entity_count") != source_audit.get("total_entities"):
        print(
            "baseline entity_count mismatch: identity=%r source=%r"
            % (
                identity.get("entity_count"),
                source_audit.get("total_entities"),
            ),
            file=sys.stderr,
        )
        return 9

    receipt = {
        "ok": True,
        "version": version,
        "entity_count": identity.get("entity_count"),
        "semantic_collision_occurrences": source_audit[
            "semantic_collision_occurrences"
        ],
        "compatibility_id_duplicate_occurrences": source_audit[
            "compatibility_id"
        ]["duplicate_occurrences"],
        "codes_generations_overwrite_risk": source_audit[
            "codes_generations_overwrite_risk"
        ],
        "identity_map_sha256": _sha256(identity_path),
        "provenance_sha256": _sha256(
            os.path.join(DIST, "provenance.json")
        ),
        "manifest_sha256": _sha256(
            os.path.join(DIST, "manifest.json")
        ),
        "release_validation": {
            "tree_identity_count": final_validation["tree_identity_count"],
            "compatibility_id_collision_count": final_validation[
                "compatibility_id_collision_count"
            ],
            "compatibility_id_duplicate_occurrences": final_validation[
                "compatibility_id_duplicate_occurrences"
            ],
        },
    }
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
