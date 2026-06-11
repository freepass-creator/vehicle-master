# -*- coding: utf-8 -*-
"""
규격통일 B: 하이브리드/전기 '세부모델'을 같은 세대 본형의 '파워트레인'으로 병합.
  - 아반떼 하이브리드 (CN7) → 아반떼 (CN7) 의 파워트레인으로
  - 코나 일렉트릭 (SX2)    → (가솔린) 코나 (SX2) 로 (배터리 정보 동반 이동)
  - EV전용(EV6/아이오닉5 등, 가솔린 형제 없음)은 매칭 실패 → 그대로 유지
실행 순서: crawl merge → apply_ev_battery → **unify_variants**
"""
import re, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))

def vkind(n):
    if "하이브리드" in n: return "HEV"
    if "일렉트릭" in n or re.search(r"\bEV\b", n) or n.endswith(" EV"): return "EV"
    return None

def strip_variant(n):
    s = n
    for tok in ("플러그인 하이브리드", "하이브리드", "일렉트릭"):
        s = s.replace(tok, "")
    s = re.sub(r"\bEV\b", "", s)
    return re.sub(r"\s+", " ", s).strip()

def gen_code(n):
    m = re.search(r"\(([^)]+)\)\s*$", n)
    return m.group(1) if m else None

def year(s):
    try: return int((s or "")[:4])
    except: return 0

def merge_pw(base_pws, add_pws):
    """파워트레인 합치고 중복제거 (배터리 등 모든 필드 보존)."""
    seen, out = set(), []
    for p in base_pws + add_pws:
        k = (p.get("fuel"), p.get("displacement_l"), p.get("turbo"),
             p.get("seat"), p.get("drivetrain"), p.get("battery_kwh"))
        if k in seen: continue
        seen.add(k); out.append(p)
    return out

def within_gen(base, v):
    gb, gv = gen_code(base["name"]), gen_code(v["name"])
    if gb is not None and gb == gv:          # 세대코드 일치 (None==None 은 불인정)
        return True
    return abs(year(base.get("start")) - year(v.get("start"))) <= 3

def unify_model(g):
    subs = g.get("sub_models", [])
    bases = [s for s in subs if not vkind(s["name"])]
    by_name = {s["name"]: s for s in bases}
    moved, log = set(), []
    for v in subs:
        if not vkind(v["name"]) or id(v) in moved:
            continue
        sname = strip_variant(v["name"])
        base = by_name.get(sname)
        if base is None:  # 이름 직접매칭 실패 → 세대코드 단일후보
            gc = gen_code(v["name"])
            if gc:
                cands = [b for b in bases if gen_code(b["name"]) == gc]
                if len(cands) == 1:
                    base = cands[0]
        if base is None or not within_gen(base, v):
            continue  # 본형 없음(EV전용 등) → 유지
        base["powertrains"] = merge_pw(base.get("powertrains", []), v.get("powertrains", []))
        # 배터리/FCEV 정보 동반 이동
        for fld in ("battery_options", "battery_sources", "battery_note", "fcev", "fcev_range_km"):
            if v.get(fld) is not None and base.get(fld) is None:
                base[fld] = v[fld]
        moved.add(id(v))
        log.append((v["name"], base["name"]))
    g["sub_models"] = [s for s in subs if id(s) not in moved]
    return log

def main():
    tree = json.load(open(os.path.join(DATA, "vehicle-tree.json"), encoding="utf-8"))
    total, report = 0, []
    for m in tree["manufacturers"]:
        for g in m.get("models", []):
            log = unify_model(g)
            if log:
                total += len(log)
                report.append({"model": "%s %s" % (m["name"], g["name"]),
                               "merged": ["%s → %s" % (a, b) for a, b in log]})
            # 세부모델 재정렬 (출시순 desc)
            g.get("sub_models", []).sort(key=lambda s: (s.get("start") or "000000"), reverse=True)
    json.dump(tree, open(os.path.join(DATA, "vehicle-tree.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump({"merged_count": total, "by_model": report},
              open(os.path.join(DATA, "unify_report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("병합된 변형 세부모델:", total, "개")

if __name__ == "__main__":
    main()
