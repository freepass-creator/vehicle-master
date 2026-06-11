# -*- coding: utf-8 -*-
"""
웰릭스 신차견적기 → 트리 신차 반영.
  - 웰릭스 현행세대가 트리 동일코드보다 충분히 최신(>=2년) → 신차 세부모델 추가 (더 뉴 그랜저 GN7 등)
  - 같은 세대 → 트리 세부모델명을 웰릭스 권위명으로 改名
입력: welrixtable/scripts/{hyundai,kia}-models.json (코드명·기간), welrixtable/src/data/vehicles.json (트림/가격)
출력: data/vehicle-tree.json(갱신), data/welrix_sync_report.json
실행: rebuild 뒤(코드명명·트림서열 후). 신차 트림은 이미 MSRP 보유.
"""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))
WROOT = r"C:\dev\welrixtable"

TRIM_KR = {"premium": "프리미엄", "exclusive": "익스클루시브", "calligraphy": "캘리그래피",
           "honors": "아너스", "trendy": "트렌디", "signature": "시그니처", "noblesse": "노블레스",
           "prestige": "프레스티지", "gravity": "그래비티", "smart": "스마트", "modern": "모던",
           "inspiration": "인스퍼레이션", "earth": "어스", "air": "에어", "light": "라이트"}
PREFIX = ["디 올 뉴", "디 올뉴", "올 뉴", "더 뉴", "더 2026", "더 2025", "디 엣지", "뉴"]

def load(p): return json.load(open(p, encoding="utf-8"))

def base_model(name, code):
    s = name
    if code:
        s = re.sub(r"\s*" + re.escape(code) + r"\s*$", "", s)
    for p in PREFIX:
        if s.startswith(p + " "):
            s = s[len(p) + 1:]
    return s.strip()

def parse_pw(engine_label):
    s = engine_label or ""
    fuel = next((f for f in ("하이브리드", "가솔린", "디젤", "LPG", "전기") if f in s), None)
    dm = re.search(r"(\d\.\d)", s)
    disp_l = float(dm.group(1)) if dm else None
    dr = next((d for d in ("4WD", "AWD", "2WD") if d in s), None)
    turbo = "터보" in s or bool(re.search(r"\bT\b", s))
    return {"fuel": fuel, "displacement_l": disp_l, "turbo": turbo,
            "seat": None, "drivetrain": dr, "trims": []}

def trim_kr(detail):
    return TRIM_KR.get((detail or "").strip().lower(), (detail or "").strip())

def year(s):
    try: return int((s or "")[:4])
    except: return 0

def main():
    veh = load(os.path.join(WROOT, "src", "data", "vehicles.json"))
    meta = {}                 # base_model -> 최신 current 엔트리
    meta_codes = {}           # base_model -> 웰릭스 현행 코드 집합 (병행생산 판단용)
    for f in ("hyundai-models.json", "kia-models.json"):
        for k, v in load(os.path.join(WROOT, "scripts", f)).items():
            if k.startswith("_") or v.get("status") != "current":
                continue
            nm = v.get("model_name_kr")
            code = nm.split()[-1] if nm and re.fullmatch(r"[A-Z0-9\-]{2,6}", nm.split()[-1]) else None
            bm = base_model(nm, code)
            e = {"name": nm, "code": code, "ys": v.get("year_start"), "ye": v.get("year_end")}
            if code:
                meta_codes.setdefault(bm, set()).add(code)
            if bm not in meta or year(e["ys"]) > year(meta[bm]["ys"]):
                meta[bm] = e

    # vehicles.json 을 (brand, model) 그룹 → 파워트레인/트림
    groups = {}
    for r in veh:
        groups.setdefault((r.get("brand"), r.get("model")), []).append(r)

    tree = load(os.path.join(DATA, "vehicle-tree.json"))
    # 트리 (제조사,모델) -> model node
    tmodel = {}
    for m in tree["manufacturers"]:
        for g in m.get("models", []):
            tmodel[(m["name"], g["name"])] = g

    report = {"added": [], "renamed": [], "skipped": []}
    for (brand, model), rows in groups.items():
        m = meta.get(model)
        if not m or not m["code"]:
            report["skipped"].append("%s %s (메타/코드 없음)" % (brand, model))
            continue
        g = tmodel.get((brand, model))
        if g is None:
            report["skipped"].append("%s %s (트리 모델 없음)" % (brand, model))
            continue
        code, ys = m["code"], year(m["ys"])
        same_code = [s for s in g.get("sub_models", []) if s.get("gen_code") == code]
        latest = max((year(s.get("start")) for s in same_code), default=0)

        if same_code and ys - latest < 2:
            # 같은 세대 → 권위명으로 改名
            tgt = max(same_code, key=lambda s: s.get("start") or "")
            if tgt["name"] != m["name"]:
                tgt.setdefault("name_raw", tgt["name"])
                tgt["name"] = m["name"]
                report["renamed"].append("%s → %s" % (tgt.get("name_raw"), m["name"]))
            continue

        # 신차 추가 (트리에 동일코드 없거나, 웰릭스가 2년+ 최신)
        pw = {}
        for r in rows:
            key = r.get("engine_label")
            node = pw.get(key)
            if node is None:
                node = parse_pw(key); pw[key] = node
            node["trims"].append({"name": trim_kr(r.get("trim_detail")),
                                  "msrp": round((r.get("price") or 0) / 10000)})
        # 트림 MSRP 오름차순
        for node in pw.values():
            seen = {}
            for t in node["trims"]:
                seen[t["name"]] = t
            node["trims"] = sorted(seen.values(), key=lambda t: t.get("msrp") or 0)
        ys_str = (m["ys"] or "").replace("-", "")[:6]
        new_sub = {"name": m["name"], "gen_code": code, "start": ys_str,
                   "period": "%s~%s" % ((m["ys"] or "")[2:4], "현재" if m.get("ye") in ("현재", None) else (m["ye"] or "")[2:4]),
                   "source": "welrix", "powertrains": list(pw.values())}
        # 단종 판단(보수적): 신차와 '같은 코드'인 현재형 = 페이스리프트 이전형 → 신형이 대체 → 닫기.
        #  다른 코드의 현재형(병행 라인·별도 세대, 예: 니로 플러스 DE)은 생산여부 불확실 → 건드리지 않음.
        for s in g.get("sub_models", []):
            if s.get("gen_code") != code:
                continue
            if (s.get("start") or "") >= ys_str or not (s.get("period") or "").endswith("현재"):
                continue
            s.setdefault("period_raw", s.get("period"))
            s["end"] = ys_str
            s["period"] = "%s~%s" % ((s.get("start") or "000000")[2:4], ys_str[2:4])
            report.setdefault("closed", []).append("%s → 생산중단 %s (페리 이전형)" % (s["name"], s["period"]))
        g.setdefault("sub_models", []).insert(0, new_sub)
        report["added"].append("%s (%s, 트림 %d)" % (m["name"], new_sub["period"],
                               sum(len(n["trims"]) for n in pw.values())))

    # 재정렬
    for m in tree["manufacturers"]:
        for g in m.get("models", []):
            g.get("sub_models", []).sort(key=lambda s: (s.get("start") or "000000"), reverse=True)

    json.dump(tree, open(os.path.join(DATA, "vehicle-tree.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(report, open(os.path.join(DATA, "welrix_sync_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("신차 추가 %d · 改名 %d · 스킵 %d" % (len(report["added"]), len(report["renamed"]), len(report["skipped"])))
    for a in report["added"]:
        print("  + ", a)

if __name__ == "__main__":
    main()
