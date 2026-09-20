import json
import os
import tempfile
import unittest

from scripts.validate_identity_export import validate


class IdentityExportValidatorTest(unittest.TestCase):
    def _write_fixture(self, directory):
        version = "2026-09-20+fixture"
        ids = {
            "manufacturer": ("mf-001", "vm_mf_" + "a" * 32),
            "model": ("mf-001.md-001", "vm_md_" + "b" * 32),
            "sub_model": ("mf-001.md-001.sm-x", "vm_sm_" + "c" * 32),
            "powertrain": ("mf-001.md-001.sm-x.pw-gas", "vm_pw_" + "d" * 32),
            "trim": ("mf-001.md-001.sm-x.pw-gas.tr-base", "vm_tr_" + "e" * 32),
        }
        tree = {
            "version": version,
            "manufacturers": [{
                "id": ids["manufacturer"][0], "uid": ids["manufacturer"][1],
                "models": [{
                    "id": ids["model"][0], "uid": ids["model"][1],
                    "sub_models": [{
                        "id": ids["sub_model"][0], "uid": ids["sub_model"][1],
                        "powertrains": [{
                            "id": ids["powertrain"][0], "uid": ids["powertrain"][1],
                            "trims": [{"id": ids["trim"][0], "uid": ids["trim"][1]}],
                        }],
                    }],
                }],
            }],
        }
        manifest = {
            "version": version,
            "counts": {
                "manufacturers": 1, "models": 1, "sub_models": 1,
                "powertrains": 1, "trims": 1,
            },
            "identity_contract": {
                "schema_version": "2.0",
                "durable_id": "uid",
                "compatibility_id": "id",
                "compatibility_id_unique": False,
            },
        }
        flat = {
            "version": version,
            "rows": [{"id": ids["trim"][0], "uid": ids["trim"][1]}],
        }
        match = {
            "version": version,
            "count": 1,
            "entries": [{"id": ids["sub_model"][0], "uid": ids["sub_model"][1]}],
        }
        codes = {
            "version": version,
            "manufacturers": {},
            "models": {},
            "generations": {
                ids["sub_model"][0]: {
                    "id": ids["sub_model"][0],
                    "uid": ids["sub_model"][1],
                }
            },
            "generations_by_uid": {
                ids["sub_model"][1]: {
                    "id": ids["sub_model"][0],
                    "uid": ids["sub_model"][1],
                }
            },
            "generation_id_index": {
                ids["sub_model"][0]: [ids["sub_model"][1]]
            },
        }
        parents = {
            ids["manufacturer"][1]: None,
            ids["model"][1]: ids["manufacturer"][1],
            ids["sub_model"][1]: ids["model"][1],
            ids["powertrain"][1]: ids["sub_model"][1],
            ids["trim"][1]: ids["powertrain"][1],
        }
        types = {
            ids["manufacturer"][1]: "manufacturer",
            ids["model"][1]: "model",
            ids["sub_model"][1]: "sub_model",
            ids["powertrain"][1]: "powertrain",
            ids["trim"][1]: "trim",
        }
        current_ids = {uid: legacy_id for legacy_id, uid in ids.values()}
        identity = {
            "schema_version": "2.0",
            "entity_count": 5,
            "retired_uids": [],
            "entities": {
                uid: {
                    "entity_type": types[uid],
                    "identity_key": "key:" + uid,
                    "current_id": current_ids[uid],
                    "parent_uid": parents[uid],
                    "active": True,
                }
                for uid in parents
            },
        }
        provenance = {
            "schema_version": "2.0",
            "version": version,
            "entries": {
                uid: {
                    "entity_type": types[uid],
                    "identity_key": "key:" + uid,
                    "id": current_ids[uid],
                    "parent_uid": parents[uid],
                }
                for uid in parents
            },
        }
        payloads = {
            "manifest.json": manifest,
            "vehicle-master.json": tree,
            "vehicle-master.flat.json": flat,
            "codes.json": codes,
            "match-index.json": match,
            "identity-map.json": identity,
            "provenance.json": provenance,
        }
        for name, payload in payloads.items():
            with open(os.path.join(directory, name), "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
        return ids

    def test_valid_cross_artifact_identity_graph_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_fixture(tmp)
            result = validate(tmp)
            self.assertTrue(result["ok"], result["errors"])


    def test_duplicate_compatibility_id_is_allowed_and_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            ids = self._write_fixture(tmp)

            tree_path = os.path.join(tmp, "vehicle-master.json")
            with open(tree_path, encoding="utf-8") as handle:
                tree = json.load(handle)
            trims = tree["manufacturers"][0]["models"][0]["sub_models"][0]["powertrains"][0]["trims"]
            trims.append({"id": ids["trim"][0], "uid": "vm_tr_" + "f" * 32})
            with open(tree_path, "w", encoding="utf-8") as handle:
                json.dump(tree, handle)

            manifest_path = os.path.join(tmp, "manifest.json")
            with open(manifest_path, encoding="utf-8") as handle:
                manifest = json.load(handle)
            manifest["counts"]["trims"] = 2
            with open(manifest_path, "w", encoding="utf-8") as handle:
                json.dump(manifest, handle)

            flat_path = os.path.join(tmp, "vehicle-master.flat.json")
            with open(flat_path, encoding="utf-8") as handle:
                flat = json.load(handle)
            flat["rows"].append({"id": ids["trim"][0], "uid": "vm_tr_" + "f" * 32})
            with open(flat_path, "w", encoding="utf-8") as handle:
                json.dump(flat, handle)

            identity_path = os.path.join(tmp, "identity-map.json")
            with open(identity_path, encoding="utf-8") as handle:
                identity = json.load(handle)
            identity["entity_count"] = 6
            identity["entities"]["vm_tr_" + "f" * 32] = {
                "entity_type": "trim",
                "identity_key": "key:vm_tr_f",
                "current_id": ids["trim"][0],
                "parent_uid": ids["powertrain"][1],
                "active": True,
            }
            with open(identity_path, "w", encoding="utf-8") as handle:
                json.dump(identity, handle)

            provenance_path = os.path.join(tmp, "provenance.json")
            with open(provenance_path, encoding="utf-8") as handle:
                provenance = json.load(handle)
            provenance["entries"]["vm_tr_" + "f" * 32] = {
                "entity_type": "trim",
                "identity_key": "key:vm_tr_f",
                "id": ids["trim"][0],
                "parent_uid": ids["powertrain"][1],
            }
            with open(provenance_path, "w", encoding="utf-8") as handle:
                json.dump(provenance, handle)

            result = validate(tmp)
            self.assertTrue(result["ok"], result["errors"])
            self.assertEqual(result["compatibility_id_collision_count"], 1)
            self.assertEqual(result["compatibility_id_duplicate_occurrences"], 1)

    def test_missing_generation_uid_index_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_fixture(tmp)
            path = os.path.join(tmp, "codes.json")
            with open(path, encoding="utf-8") as handle:
                codes = json.load(handle)
            codes["generation_id_index"] = {}
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(codes, handle)
            result = validate(tmp)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("generation_id_index" in error for error in result["errors"])
            )

    def test_malformed_uid_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_fixture(tmp)
            path = os.path.join(tmp, "vehicle-master.json")
            with open(path, encoding="utf-8") as handle:
                tree = json.load(handle)
            tree["manufacturers"][0]["uid"] = "vm_mf_short"
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(tree, handle)
            result = validate(tmp)
            self.assertFalse(result["ok"])
            self.assertTrue(any("uid format mismatch" in error for error in result["errors"]))

    def test_schema_v1_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_fixture(tmp)
            path = os.path.join(tmp, "identity-map.json")
            with open(path, encoding="utf-8") as handle:
                identity = json.load(handle)
            identity["schema_version"] = "1.0"
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(identity, handle)
            result = validate(tmp)
            self.assertFalse(result["ok"])
            self.assertTrue(any("identity-map schema_version" in error for error in result["errors"]))

    def test_unknown_flat_uid_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_fixture(tmp)
            path = os.path.join(tmp, "vehicle-master.flat.json")
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
            payload["rows"][0]["uid"] = "vm_tr_wrong"
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
            result = validate(tmp)
            self.assertFalse(result["ok"])
            self.assertTrue(any("unknown trim" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
