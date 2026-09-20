import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location(
    "vehicle_master_export", SCRIPTS / "export.py"
)
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class ExportIdentityIntegrationTest(unittest.TestCase):
    def _source_tree(self):
        def sub_model(source_code, display_name, raw_name, start, seat, raw_trim):
            return {
                "name": display_name,
                "name_raw": raw_name,
                "code": source_code,
                "gen_code": "KA4",
                "start": start,
                "end": None,
                "period": "20~현재",
                "powertrains": [{
                    "fuel": "디젤",
                    "displacement_l": 2.2,
                    "turbo": False,
                    "drivetrain": None,
                    "seat": seat,
                    "trims": [{
                        "name": "프레스티지",
                        "raw": raw_trim,
                        "msrp": 3500 + seat,
                    }],
                }],
            }

        return {
            "levels": ["제조사", "모델", "세부모델", "파워트레인", "세부트림"],
            "manufacturers": [{
                "name": "기아",
                "code": "002",
                "car_type": "국산",
                "models": [{
                    "name": "카니발",
                    "code": "036",
                    "sub_models": [
                        sub_model(
                            "175", "카니발 KA4", "카니발 4세대",
                            "202008", 7, "7인승 프레스티지"
                        ),
                        sub_model(
                            "176", "더 뉴 카니발 KA4", "더 뉴 카니발 4세대",
                            "202311", 9, "9인승 프레스티지"
                        ),
                    ],
                }],
            }],
        }

    def test_export_is_lossless_with_duplicate_compatibility_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = os.path.join(tmp, "data")
            dist_dir = os.path.join(tmp, "dist")
            os.makedirs(data_dir)
            os.makedirs(dist_dir)

            with open(
                os.path.join(data_dir, "vehicle-tree.json"),
                "w",
                encoding="utf-8",
            ) as handle:
                json.dump(self._source_tree(), handle, ensure_ascii=False)

            with open(
                os.path.join(data_dir, "id-aliases.json"),
                "w",
                encoding="utf-8",
            ) as handle:
                json.dump(
                    {"schema_version": "2.0", "aliases": {}},
                    handle,
                )

            original_data, original_dist = exporter.DATA, exporter.DIST
            exporter.DATA, exporter.DIST = data_dir, dist_dir
            try:
                version = exporter.build("2026-09-20")
                self.assertTrue(version.startswith("2026-09-20+"))

                with open(
                    os.path.join(dist_dir, "vehicle-master.flat.json"),
                    encoding="utf-8",
                ) as handle:
                    flat = json.load(handle)
                self.assertEqual(len(flat["rows"]), 2)
                self.assertEqual(len({row["uid"] for row in flat["rows"]}), 2)
                self.assertEqual(len({row["id"] for row in flat["rows"]}), 1)

                with open(
                    os.path.join(dist_dir, "codes.json"),
                    encoding="utf-8",
                ) as handle:
                    codes = json.load(handle)
                duplicated_sub_model_id = "mf-002.md-036.sm-ka4"
                self.assertEqual(
                    len(codes["generation_id_index"][duplicated_sub_model_id]),
                    2,
                )
                self.assertEqual(len(codes["generations_by_uid"]), 2)

                with open(
                    os.path.join(dist_dir, "identity-map.json"),
                    encoding="utf-8",
                ) as handle:
                    first_identity = json.load(handle)
                self.assertEqual(first_identity["schema_version"], "2.0")
                self.assertEqual(first_identity["entity_count"], 8)

                first_uids = set(first_identity["entities"])
                exporter.build("2026-09-20")
                with open(
                    os.path.join(dist_dir, "identity-map.json"),
                    encoding="utf-8",
                ) as handle:
                    second_identity = json.load(handle)
                self.assertEqual(first_uids, set(second_identity["entities"]))

                with open(
                    os.path.join(dist_dir, "manifest.json"),
                    encoding="utf-8",
                ) as handle:
                    manifest = json.load(handle)
                self.assertIs(
                    manifest["identity_contract"]["compatibility_id_unique"],
                    False,
                )
                self.assertEqual(
                    manifest["identity_contract"]["durable_id"], "uid"
                )
            finally:
                exporter.DATA, exporter.DIST = original_data, original_dist


if __name__ == "__main__":
    unittest.main()
