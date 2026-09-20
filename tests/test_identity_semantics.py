import unittest

from scripts.identity_semantics import (
    sub_model_identity_key,
    powertrain_identity_key,
    trim_identity_key,
)


class IdentitySemanticsTest(unittest.TestCase):
    def test_sub_model_source_code_is_stable_across_display_name_change(self):
        a = {
            "code": "175",
            "gen_code": "KA4",
            "start": "202311",
            "name": "더 뉴 카니발 KA4",
            "name_raw": "더 뉴 카니발 4세대",
        }
        b = dict(a, name="카니발 페이스리프트 KA4")
        self.assertEqual(
            sub_model_identity_key("model-uid", a),
            sub_model_identity_key("model-uid", b),
        )

    def test_sub_model_fallback_uses_start_and_source_name(self):
        a = {
            "code": None,
            "gen_code": "X",
            "start": "202401",
            "name": "모델 X",
            "name_raw": "원본 X",
        }
        b = dict(a, start="202501")
        self.assertNotEqual(
            sub_model_identity_key("model-uid", a),
            sub_model_identity_key("model-uid", b),
        )

    def test_powertrain_seat_count_disambiguates_same_engine(self):
        base = {
            "fuel": "디젤",
            "displacement_l": 2.2,
            "battery_kwh": None,
            "drivetrain": None,
            "turbo": False,
            "seat": 7,
        }
        other = dict(base, seat=9)
        self.assertNotEqual(
            powertrain_identity_key("sub-uid", base),
            powertrain_identity_key("sub-uid", other),
        )

    def test_trim_raw_name_disambiguates_same_normalized_name(self):
        a = {"name": "프레스티지", "raw": "7인승 프레스티지"}
        b = {"name": "프레스티지", "raw": "9인승 프레스티지"}
        self.assertNotEqual(
            trim_identity_key("powertrain-uid", a),
            trim_identity_key("powertrain-uid", b),
        )


if __name__ == "__main__":
    unittest.main()
