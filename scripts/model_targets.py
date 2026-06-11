# -*- coding: utf-8 -*-
"""전역 검증 대상 추출: 모델(ModelGroup) 매물>=MIN 의 모델별 세부모델/파워트레인/트림 요약."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))
MIN = 500

def pw_label(p):
    fuel = p.get("fuel") or ""
    if p.get("battery_kwh") is not None:
        e = "%gkWh" % p["battery_kwh"]
    elif p.get("battery_kwh_options"):
        e = "/".join("%g" % x for x in p["battery_kwh_options"]) + "kWh"
    elif p.get("displacement_l") is not None:
        e = "%g%s" % (p["displacement_l"], "T" if p.get("turbo") else "")
    else:
        e = ""
    parts = [fuel, e]
    if p.get("seat"):
        parts.append("%d인승" % p["seat"])
    if p.get("drivetrain"):
        parts.append(p["drivetrain"])
    return " ".join(x for x in parts if x)

t = json.load(open(os.path.join(DATA, "vehicle-tree.json"), encoding="utf-8"))
targets = []
for m in t["manufacturers"]:
    for g in m.get("models", []):
        if (g.get("count") or 0) < MIN:
            continue
        subs = []
        for s in g.get("sub_models", []):
            trims = sorted({tt["name"] for p in s.get("powertrains", []) for tt in p.get("trims", [])})
            subs.append({
                "sub_model": s["name"], "period": s.get("period"),
                "powertrains": [pw_label(p) for p in s.get("powertrains", [])],
                "trims": trims,
            })
        targets.append({"manufacturer": m["name"], "model": g["name"],
                        "eng": g.get("eng"), "count": g.get("count"), "sub_models": subs})

json.dump(targets, open(os.path.join(DATA, "model_targets.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("model targets:", len(targets), "| sub_models:", sum(len(x["sub_models"]) for x in targets))
