# -*- coding: utf-8 -*-
"""
맥락별 트림 분류 결과 적용: error 제거 / fleet·special 플래그.
입력: data/trim_ctx_targets.json(순서=권위), data/trim_class_results.json, data/vehicle-tree.json
맥락 = "세대코드 연료" (apply 시 동일 규칙으로 재구성해 매칭).
실행: rebuild 마지막. usage: python apply_trim_class.py
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))

def load(n): return json.load(open(os.path.join(DATA, n), encoding="utf-8"))

def ctx_of(s, p):
    g = s.get("gen_code") or s.get("period") or s["name"]
    return "%s %s" % (g, p.get("fuel") or "?")

def main():
    rp = os.path.join(DATA, "trim_class_results.json")
    if not os.path.exists(rp):
        print("trim_class_results.json 없음"); return
    targets = load("trim_ctx_targets.json")
    results = load("trim_class_results.json")
    tree = load("vehicle-tree.json")
    assert len(targets) == len(results), "순서 매칭 불가"

    # (제조사,모델,ctx,트림) -> category
    cmap = {}
    for t, r in zip(targets, results):
        for c in r.get("contexts", []):
            for tr in c.get("trims", []):
                if tr.get("name"):
                    cmap[(t["manufacturer"], t["model"], c.get("ctx"), tr["name"])] = tr.get("category")

    stat = {"fleet": 0, "special": 0, "error_removed": 0, "consumer": 0, "unmapped": 0}
    for m in tree["manufacturers"]:
        for g in m.get("models", []):
            for s in g.get("sub_models", []):
                for p in s.get("powertrains", []):
                    ctx = ctx_of(s, p)
                    kept = []
                    for tr in p.get("trims", []):
                        cat = cmap.get((m["name"], g["name"], ctx, tr.get("name")))
                        if cat == "error":
                            stat["error_removed"] += 1; continue
                        elif cat == "fleet":
                            tr["fleet"] = True; stat["fleet"] += 1
                        elif cat == "special":
                            tr["special"] = True; stat["special"] += 1
                        elif cat == "consumer":
                            tr.pop("fleet", None); tr.pop("special", None); stat["consumer"] += 1
                        else:
                            stat["unmapped"] += 1
                        kept.append(tr)
                    p["trims"] = kept
    json.dump(tree, open(os.path.join(DATA, "vehicle-tree.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("트림 분류 적용:", stat)

if __name__ == "__main__":
    main()
