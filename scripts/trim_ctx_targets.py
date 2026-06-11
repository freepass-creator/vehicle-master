# -*- coding: utf-8 -*-
"""맥락 포함 트림 분류 대상: 모델별 (세대코드+연료) 맥락마다 트림 목록."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))
MIN = 500

def ctx_of(s, p):
    g = s.get("gen_code") or s.get("period") or s["name"]
    return "%s %s" % (g, p.get("fuel") or "?")

t = json.load(open(os.path.join(DATA, "vehicle-tree.json"), encoding="utf-8"))
targets = []
for m in t["manufacturers"]:
    for g in m.get("models", []):
        if (g.get("count") or 0) < MIN:
            continue
        groups = {}
        for s in g.get("sub_models", []):
            for p in s.get("powertrains", []):
                c = ctx_of(s, p)
                groups.setdefault(c, set()).update(tt["name"] for tt in p.get("trims", []))
        ctxs = [{"ctx": c, "trims": sorted(v)} for c, v in groups.items() if v]
        if sum(len(x["trims"]) for x in ctxs) < 2:
            continue
        targets.append({"manufacturer": m["name"], "model": g["name"], "contexts": ctxs})

json.dump(targets, open(os.path.join(DATA, "trim_ctx_targets.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("대상:", len(targets), "모델 | 맥락:", sum(len(x["contexts"]) for x in targets),
      "| 트림인스턴스:", sum(len(c["trims"]) for x in targets for c in x["contexts"]))
