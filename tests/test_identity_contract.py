import json
import os
import tempfile
import unittest

from scripts.identity_contract import IdentityRegistry


class IdentityContractTest(unittest.TestCase):
    def test_alias_preserves_uid(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.path.join(tmp, "identity-map.json")
            aliases = os.path.join(tmp, "id-aliases.json")

            first = IdentityRegistry(previous, aliases, "2026-09-20")
            old_uid = first.resolve("trim", "mf-1.md-1.tr-old", "parent")
            with open(previous, "w", encoding="utf-8") as f:
                json.dump(first.document(), f)

            with open(aliases, "w", encoding="utf-8") as f:
                json.dump({
                    "schema_version": "1.0",
                    "aliases": {"mf-1.md-1.tr-new": "mf-1.md-1.tr-old"}
                }, f)

            second = IdentityRegistry(previous, aliases, "2026-09-21")
            new_uid = second.resolve("trim", "mf-1.md-1.tr-new", "parent")

            self.assertEqual(old_uid, new_uid)
            self.assertIn(
                "mf-1.md-1.tr-old",
                second.document()["entities"][new_uid]["aliases"],
            )


    def test_parent_alias_preserves_descendant_uid_without_descendant_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.path.join(tmp, "identity-map.json")
            aliases = os.path.join(tmp, "id-aliases.json")

            first = IdentityRegistry(previous, aliases, "2026-09-20")
            parent_uid = first.resolve("model", "mf-1.md-old", "manufacturer")
            child_uid = first.resolve("sub_model", "mf-1.md-old.sm-gn7", parent_uid)
            with open(previous, "w", encoding="utf-8") as f:
                json.dump(first.document(), f)

            with open(aliases, "w", encoding="utf-8") as f:
                json.dump({
                    "schema_version": "1.0",
                    "aliases": {"mf-1.md-new": "mf-1.md-old"}
                }, f)

            second = IdentityRegistry(previous, aliases, "2026-09-21")
            renamed_parent_uid = second.resolve("model", "mf-1.md-new", "manufacturer")
            renamed_child_uid = second.resolve(
                "sub_model", "mf-1.md-new.sm-gn7", renamed_parent_uid
            )

            self.assertEqual(parent_uid, renamed_parent_uid)
            self.assertEqual(child_uid, renamed_child_uid)

    def test_same_current_identity_cannot_be_emitted_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = IdentityRegistry(
                os.path.join(tmp, "identity-map.json"),
                os.path.join(tmp, "id-aliases.json"),
                "2026-09-20",
            )
            registry.resolve("model", "mf-1.md-a", "manufacturer")
            with self.assertRaises(ValueError):
                registry.resolve("model", "mf-1.md-a", "manufacturer")


if __name__ == "__main__":
    unittest.main()
