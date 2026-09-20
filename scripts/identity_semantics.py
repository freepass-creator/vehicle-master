# -*- coding: utf-8 -*-
"""Shared vehicle-master semantic identity-key rules.

Keep every identity-bearing rule here so export, audit, and future consumers do
not reimplement identity logic differently.
"""
from __future__ import annotations

import json
import re


def slug(value):
    value = re.sub(r"[^\w가-힣]+", "-", (value or "").strip())
    return re.sub(r"-+", "-", value).strip("-").lower() or "x"


def semantic_key(*parts):
    return json.dumps(parts, ensure_ascii=False, separators=(",", ":"))


def manufacturer_identity_key(manufacturer_code):
    return semantic_key("manufacturer", manufacturer_code)


def model_identity_key(manufacturer_uid, model_code):
    return semantic_key("model", manufacturer_uid, model_code)


def sub_model_identity_key(model_uid, sub_model):
    source_code = sub_model.get("code")
    if source_code is not None:
        return semantic_key(
            "sub_model", model_uid, "source_code", str(source_code)
        )
    return semantic_key(
        "sub_model",
        model_uid,
        "fallback",
        sub_model.get("gen_code") or "",
        sub_model.get("start") or "",
        sub_model.get("name_raw") or sub_model.get("name") or "",
    )


def powertrain_identity_key(sub_model_uid, powertrain):
    return semantic_key(
        "powertrain",
        sub_model_uid,
        powertrain.get("fuel"),
        powertrain.get("displacement_l"),
        powertrain.get("battery_kwh"),
        powertrain.get("drivetrain"),
        powertrain.get("turbo"),
        powertrain.get("seat"),
    )


def trim_identity_key(powertrain_uid, trim):
    return semantic_key(
        "trim",
        powertrain_uid,
        trim.get("raw") or trim.get("name") or "",
    )
