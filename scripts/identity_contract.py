# -*- coding: utf-8 -*-
"""Durable semantic identity registry for vehicle-master exports.

The readable hierarchical ``id`` is a compatibility label and is NOT unique
in the current dataset. Durable identity is based on an explicit semantic
``identity_key``, persisted in ``dist/identity-map.json``.

When a semantic identity-bearing field must change, declare
``new_identity_key -> previous_identity_key`` in ``data/id-aliases.json``.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, Optional

SCHEMA_VERSION = "2.0"
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


def stable_uid(entity_type: str, identity_key: str) -> str:
    prefix = TYPE_PREFIX.get(entity_type, "xx")
    digest = hashlib.sha256(
        ("%s|%s" % (entity_type, identity_key)).encode("utf-8")
    ).hexdigest()[:20]
    return "vm_%s_%s" % (prefix, digest)


class IdentityRegistry:
    def __init__(self, previous_path: str, alias_path: str, generated: Optional[str] = None):
        previous = _read_json(
            previous_path,
            {"schema_version": SCHEMA_VERSION, "entities": {}},
        )
        aliases_doc = _read_json(
            alias_path,
            {"schema_version": SCHEMA_VERSION, "aliases": {}},
        )
        if previous.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(
                "unsupported identity registry schema_version: %r"
                % previous.get("schema_version")
            )
        if aliases_doc.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(
                "unsupported id-aliases schema_version: %r"
                % aliases_doc.get("schema_version")
            )

        self.generated = generated
        self.entities: Dict[str, dict] = {
            uid: dict(record)
            for uid, record in previous.get("entities", {}).items()
        }
        self.alias_rules: Dict[str, str] = dict(aliases_doc.get("aliases", {}))
        self.key_lookup: Dict[str, str] = {}
        self.current_uids = set()

        for uid, record in self.entities.items():
            identity_key = record.get("identity_key")
            if identity_key:
                self._register_key(identity_key, uid)
            for alias in record.get("key_aliases", []):
                self._register_key(alias, uid)

    def _register_key(self, identity_key: str, uid: str) -> None:
        existing = self.key_lookup.get(identity_key)
        if existing and existing != uid:
            raise ValueError(
                "identity key maps to multiple uids: %s" % identity_key
            )
        self.key_lookup[identity_key] = uid

    def resolve(
        self,
        entity_type: str,
        identity_key: str,
        legacy_id: str,
        parent_uid: Optional[str] = None,
    ) -> str:
        previous_key = self.alias_rules.get(identity_key, identity_key)
        if previous_key != identity_key and previous_key not in self.key_lookup:
            raise ValueError(
                "alias target does not exist in previous identity registry: %s"
                % previous_key
            )

        uid = self.key_lookup.get(identity_key) or self.key_lookup.get(previous_key)

        if uid is None:
            uid = stable_uid(entity_type, identity_key)
            if uid in self.entities:
                raise ValueError("uid collision for identity key: %s" % identity_key)
            self.entities[uid] = {
                "entity_type": entity_type,
                "identity_key": identity_key,
                "key_aliases": [],
                "current_id": legacy_id,
                "id_history": [],
                "parent_uid": parent_uid,
                "first_seen": self.generated,
                "last_seen": self.generated,
            }
        else:
            record = self.entities[uid]
            if record.get("entity_type") != entity_type:
                raise ValueError(
                    "entity type changed for %s: %s -> %s"
                    % (identity_key, record.get("entity_type"), entity_type)
                )

            old_key = record.get("identity_key")
            if old_key and old_key != identity_key:
                aliases = set(record.get("key_aliases", []))
                aliases.add(old_key)
                if previous_key != identity_key:
                    aliases.add(previous_key)
                record["key_aliases"] = sorted(
                    key for key in aliases if key and key != identity_key
                )
                record["identity_key"] = identity_key

            old_id = record.get("current_id")
            if old_id and old_id != legacy_id:
                history = set(record.get("id_history", []))
                history.add(old_id)
                record["id_history"] = sorted(
                    value for value in history if value and value != legacy_id
                )

            record["current_id"] = legacy_id
            record["parent_uid"] = parent_uid
            record["last_seen"] = self.generated

        if uid in self.current_uids:
            raise ValueError(
                "multiple current entities resolved to the same uid: %s" % uid
            )

        self.current_uids.add(uid)
        self._register_key(identity_key, uid)
        return uid

    def document(self) -> dict:
        retired = sorted(set(self.entities) - self.current_uids)
        entities = {}
        for uid in sorted(self.entities):
            record = dict(self.entities[uid])
            record["active"] = uid in self.current_uids
            entities[uid] = record
        return {
            "schema_version": SCHEMA_VERSION,
            "generated": self.generated,
            "entity_count": len(self.current_uids),
            "retired_uids": retired,
            "entities": entities,
        }
