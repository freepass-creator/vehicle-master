import json
import os
import tempfile
import unittest

from scripts.identity_contract import IdentityRegistry


class IdentityContractTest(unittest.TestCase):
    def test_uid_is_deterministic_and_128_bit_hex(self):
        from scripts.identity_contract import stable_uid

        first = stable_uid("model", "semantic-key")
        second = stable_uid("model", "semantic-key")
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("vm_md_"))
        self.assertEqual(len(first.split("_")[-1]), 32)

    def test_semantic_alias_preserves_uid(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.path.join(tmp, "identity-map.json")
            aliases = os.path.join(tmp, "id-aliases.json")

            first = IdentityRegistry(previous, aliases, "2026-09-20")
            old_uid = first.resolve(
                "trim", "trim-key-old", "legacy-id-old", "parent"
            )
            with open(previous, "w", encoding="utf-8") as handle:
                json.dump(first.document(), handle)

            with open(aliases, "w", encoding="utf-8") as handle:
                json.dump({
                    "schema_version": "2.0",
                    "aliases": {"trim-key-new": "trim-key-old"},
                }, handle)

            second = IdentityRegistry(previous, aliases, "2026-09-21")
            new_uid = second.resolve(
                "trim", "trim-key-new", "legacy-id-new", "parent"
            )

            self.assertEqual(old_uid, new_uid)
            record = second.document()["entities"][new_uid]
            self.assertIn("trim-key-old", record["key_aliases"])
            self.assertIn("legacy-id-old", record["id_history"])

    def test_parent_alias_preserves_descendant_uid_without_descendant_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.path.join(tmp, "identity-map.json")
            aliases = os.path.join(tmp, "id-aliases.json")

            first = IdentityRegistry(previous, aliases, "2026-09-20")
            parent_uid = first.resolve(
                "model", "model-key-old", "mf-1.md-old", "manufacturer"
            )
            child_key = "sub-model|%s|source:123" % parent_uid
            child_uid = first.resolve(
                "sub_model", child_key, "mf-1.md-old.sm-gn7", parent_uid
            )
            with open(previous, "w", encoding="utf-8") as handle:
                json.dump(first.document(), handle)

            with open(aliases, "w", encoding="utf-8") as handle:
                json.dump({
                    "schema_version": "2.0",
                    "aliases": {"model-key-new": "model-key-old"},
                }, handle)

            second = IdentityRegistry(previous, aliases, "2026-09-21")
            renamed_parent_uid = second.resolve(
                "model", "model-key-new", "mf-1.md-new", "manufacturer"
            )
            renamed_child_key = "sub-model|%s|source:123" % renamed_parent_uid
            renamed_child_uid = second.resolve(
                "sub_model",
                renamed_child_key,
                "mf-1.md-new.sm-gn7",
                renamed_parent_uid,
            )

            self.assertEqual(parent_uid, renamed_parent_uid)
            self.assertEqual(child_uid, renamed_child_uid)

    def test_missing_alias_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            aliases = os.path.join(tmp, "id-aliases.json")
            with open(aliases, "w", encoding="utf-8") as handle:
                json.dump({
                    "schema_version": "2.0",
                    "aliases": {"model-key-new": "model-key-missing"},
                }, handle)

            registry = IdentityRegistry(
                os.path.join(tmp, "identity-map.json"),
                aliases,
                "2026-09-20",
            )
            with self.assertRaises(ValueError):
                registry.resolve(
                    "model", "model-key-new", "mf-1.md-new", "manufacturer"
                )

    def test_same_current_semantic_identity_cannot_be_emitted_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = IdentityRegistry(
                os.path.join(tmp, "identity-map.json"),
                os.path.join(tmp, "id-aliases.json"),
                "2026-09-20",
            )
            registry.resolve(
                "model", "same-key", "mf-1.md-a", "manufacturer"
            )
            with self.assertRaises(ValueError):
                registry.resolve(
                    "model", "same-key", "mf-1.md-b", "manufacturer"
                )

    def test_duplicate_legacy_id_is_allowed_for_distinct_semantic_entities(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = IdentityRegistry(
                os.path.join(tmp, "identity-map.json"),
                os.path.join(tmp, "id-aliases.json"),
                "2026-09-20",
            )
            first = registry.resolve(
                "trim", "trim-key-seat-7", "same-legacy-id", "pw-a"
            )
            second = registry.resolve(
                "trim", "trim-key-seat-9", "same-legacy-id", "pw-b"
            )
            self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
