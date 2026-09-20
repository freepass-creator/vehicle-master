import json
import os
import tempfile
import unittest

from scripts.validate_identity_export import validate


class IdentityExportValidatorTest(unittest.TestCase):
    def _write_fixture(self, directory):
        version = "2026-09-20+fixture"
        ids = {
            "manufacturer": ("mf-001", "vm_mf_a"),
            "model": ("mf-001.md-001", "vm_md_b"),
            "sub_model": ("mf-001.md-001.sm-x", "vm_sm_c"),
            "powertrain": ("mf-001.md-001.sm-x.pw-gas", "vm_pw_d"),
            "trim": ("mf-001.md-001.sm-x.pw-gas.tr-base", "vm_tr_e"),
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
                "durable_id": "uid",
                "compatibility_id": "id",
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
            "schema_version": "1.0",
            "entity_count": 5,
            "retired_uids": [],
            "entities": {
                uid: {
                    "entity_type": types[uid],
                    "current_id": current_ids[uid],
                    "parent_uid": parents[uid],
                    "active": True,
                }
                for uid in parents
            },
        }
        provenance = {
            "version": version,
            "entries": {
                uid: {
                    "entity_type": types[uid],
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
