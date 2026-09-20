# -*- coding: utf-8 -*-
"""Stable identity registry for vehicle-master exports.

The existing human-readable ``id`` remains a compatibility identifier. This
module adds an opaque ``uid`` that is reused across rebuilds. When an
identity-bearing field is intentionally renamed, declare the move in
``data/id-aliases.json`` as ``new_legacy_id -> previous_legacy_id`` so the
same uid is retained.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, Optional

SCHEMA_VERSION = "1.0"
TYPE_PREFIX = {
    "manufacturer": "mf",
    "model": "md",
    "sub_model": "sm",
    "powertrain": "pw",
    "trim": "tr",
}


def _read_json(path: str, default):
    if not path or not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def stable_uid(entity_type: str, first_legacy_id: str) -> str:
    prefix = TYPE_PREFIX.get(entity_type, "xx")
    digest = hashlib.sha256(first_legacy_id.encode("utf-8")).hexdigest()[:20]
    return f"vm_{prefix}_{digest}"


class IdentityRegistry:
    def __init__(self, previous_path: str, alias_path: str, generated: Optional[str] = None):
        previous = _read_json(previous_path, {"schema_version": SCHEMA_VERSION, "entities": {}})
        aliases_doc = _read_json(alias_path, {"schema_version": SCHEMA_VERSION, "aliases": {}})
        if previous.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported identity registry schema_version: %r" % previous.get("schema_version"))
        if aliases_doc.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported id-aliases schema_version: %r" % aliases_doc.get("schema_version"))

        self.generated = generated
        self.entities: Dict[str, dict] = {
            uid: dict(record) for uid, record in previous.get("entities", {}).items()
        }
        self.alias_rules: Dict[str, str] = dict(aliases_doc.get("aliases", {}))
        self.lookup: Dict[str, str] = {}
        self.current_uids = set()

        for uid, record in self.entities.items():
            current_id = record.get("current_id")
            if current_id:
                self._register_lookup(current_id, uid)
            for alias in record.get("aliases", []):
                self._register_lookup(alias, uid)

    def _register_lookup(self, legacy_id: str, uid: str) -> None:
        existing = self.lookup.get(legacy_id)
        if existing and existing != uid:
            raise ValueError("legacy id maps to multiple uids: %s" % legacy_id)
        self.lookup[legacy_id] = uid

    def resolve(self, entity_type: str, legacy_id: str, parent_uid: Optional[str] = None) -> str:
        previous_id = self.alias_rules.get(legacy_id, legacy_id)
        uid = self.lookup.get(legacy_id) or self.lookup.get(previous_id)

        if uid is None:
            uid = stable_uid(entity_type, legacy_id)
            if uid in self.entities:
                raise ValueError("uid collision for %s" % legacy_id)
            self.entities[uid] = {
                "entity_type": entity_type,
                "current_id": legacy_id,
                "aliases": [],
                "parent_uid": parent_uid,
                "first_seen": self.generated,
                "last_seen": self.generated,
            }
        else:
            record = self.entities[uid]
            if record.get("entity_type") != entity_type:
                raise ValueError(
                    "entity type changed for %s: %s -> %s"
                    % (legacy_id, record.get("entity_type"), entity_type)
                )
            old_current = record.get("current_id")
            if old_current and old_current != legacy_id:
                aliases = set(record.get("aliases", []))
                aliases.add(old_current)
                if previous_id != legacy_id:
                    aliases.add(previous_id)
                record["aliases"] = sorted(a for a in aliases if a and a != legacy_id)
            record["current_id"] = legacy_id
            record["parent_uid"] = parent_uid
            record["last_seen"] = self.generated

        if uid in self.current_uids:
            raise ValueError("multiple current entities resolved to the same uid: %s" % uid)
        self.current_uids.add(uid)
        self._register_lookup(legacy_id, uid)
        return uid

    def document(self) -> dict:
        active = {uid: self.entities[uid] for uid in sorted(self.current_uids)}
        retired = sorted(set(self.entities) - self.current_uids)
        return {
            "schema_version": SCHEMA_VERSION,
            "generated": self.generated,
            "entity_count": len(active),
            "retired_uids": retired,
            "entities": active,
        }
