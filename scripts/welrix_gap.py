# -*- coding: utf-8 -*-
"""웰릭스 신차 모델 중 우리 트리에 없는 것(신차 갭) 찾기."""
import json, re, os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))
WELRIX = r"C:\dev\welrixtable\src\data\vehicles.json"

def norm(s):
    return re.sub(r"\s+", "", (s or "")).replace("(", "").replace(")", "").lower()

tree = json.load(open(os.path.join(DATA, "vehicle-tree.json"), encoding="utf-8"))
# 트리 모델 인덱스: 제조사norm -> set(모델norm), 그리고 세부모델 norm 집합
tree_models = {}
tree_brands = set()
for m in tree["manufacturers"]:
    bn = norm(m["name"])
    tree_brands.add(bn)
    tree_models.setdefault(bn, set())
    for g in m.get("models", []):
        tree_models[bn].add(norm(g["name"]))

wel = json.load(open(WELRIX, encoding="utf-8"))
# 웰릭스 brand/model 별 트림/연료/배기량 집계
wmodels = {}
for r in wel:
    b, mo = r.get("brand"), r.get("model")
    key = (b, mo)
    d = wmodels.setdefault(key, {"trims": set(), "fuels": set(), "disps": set(), "names": set()})
    d["trims"].add(r.get("trim"))
    d["fuels"].add(r.get("fuel"))
    d["disps"].add(r.get("disp"))
    d["names"].add(r.get("model_name_kr") or r.get("name"))

missing, present, brand_unknown = [], [], []
for (b, mo), d in sorted(wmodels.items()):
    bn = norm(b)
    if bn not in tree_models:
        brand_unknown.append((b, mo))
        continue
    mn = norm(mo)
    # 모델명 정규화 일치 또는 트리 세부모델/모델에 포함관계
    hit = any(mn == tm or mn in tm or tm in mn for tm in tree_models[bn])
    (present if hit else missing).append({
        "brand": b, "model": mo, "names": sorted(x for x in d["names"] if x),
        "trims": sorted(x for x in d["trims"] if x),
        "fuels": sorted(x for x in d["fuels"] if x),
        "disps": sorted(str(x) for x in d["disps"] if x is not None)})

out = {"welrix_models": len(wmodels), "present": len(present),
       "missing": len(missing), "brand_not_in_tree": brand_unknown,
       "missing_models": missing}
json.dump(out, open(os.path.join(DATA, "_welrix_gap.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("welrix models:", len(wmodels), "| 트리에있음:", len(present),
      "| 트리에없음(신차후보):", len(missing), "| 브랜드미존재:", len(brand_unknown))
