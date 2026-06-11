# -*- coding: utf-8 -*-
"""
보충 차종 추가 — 엔카 승용 크롤에서 빠진 차종(상용 1톤 트럭 등)을 트리에 주입.
입력: data/supplemental.json (리서치/수기 큐레이트), data/vehicle-tree.json
출력: data/vehicle-tree.json (갱신)
실행: rebuild 의 export 직전. source='supplemental' 표시.
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))

def yy(yyyy):
    s = str(yyyy or "")
    return s[2:4] if len(s) >= 4 else s

def main():
    sp = os.path.join(DATA, "supplemental.json")
    if not os.path.exists(sp):
        print("supplemental.json 없음 — 스킵"); return
    sup = json.load(open(sp, encoding="utf-8"))
    tree = json.load(open(os.path.join(DATA, "vehicle-tree.json"), encoding="utf-8"))
    man_by_name = {m["name"]: m for m in tree["manufacturers"]}

    added = 0
    for s in sup:
        m = man_by_name.get(s["maker"])
        if not m:
            m = {"name": s["maker"], "car_type": "국산", "models": []}
            tree["manufacturers"].append(m); man_by_name[s["maker"]] = m
        models = m.setdefault("models", [])
        if any(g.get("name") == s["model"] for g in models):
            continue  # 이미 있으면 스킵
        sub_models = []
        for sm in s["sub_models"]:
            pws = []
            for p in sm["powertrains"]:
                pws.append({
                    "fuel": p["fuel"],
                    "displacement": int(p["displacement_l"] * 1000) if p.get("displacement_l") else None,
                    "displacement_l": p.get("displacement_l"),
                    "turbo": False, "drivetrain": p.get("drivetrain"), "seat": p.get("seat"),
                    "trims": [{"name": t} for t in sm.get("trims", [])],
                })
            start = (str(sm["year_start"]) + "01")[:6]
            end = None if sm.get("year_end") in ("현재", None) else (str(sm["year_end"]) + "12")[:6]
            sub_models.append({
                "name": sm["name"], "gen_code": sm.get("gen_code") or None,
                "start": start, "end": end,
                "period": "%s~%s" % (yy(sm["year_start"]), "현재" if not end else yy(sm["year_end"])),
                "source": "supplemental", "powertrains": pws,
            })
        models.append({"name": s["model"], "code": None, "count": 0,
                       "source": "supplemental", "sub_models": sub_models})
        added += 1
    json.dump(tree, open(os.path.join(DATA, "vehicle-tree.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("보충 모델 추가:", added)

if __name__ == "__main__":
    main()
