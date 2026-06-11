# -*- coding: utf-8 -*-
"""
웰릭스 신차견적기 → 현행 신차 카탈로그(우리 포맷)로 추출.
입력: welrixtable/src/data/vehicles.json (트림/가격/연료/배기량),
      welrixtable/scripts/{hyundai,kia}-models.json (코드명·생산기간·status)
출력: data/welrix_catalog.json = [{brand, name(model_name_kr), gen_code, period, status,
                                   powertrains:[...], trims:[{name, price, fuel, disp}]}]
"""
import json, os, re, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))
WROOT = r"C:\dev\welrixtable"

def load(p):
    return json.load(open(p, encoding="utf-8"))

def gen_code_of(name):
    """model_name_kr 끝의 코드 토큰 (GN7/KA4/MX5/DL3/NQ5...). 없으면 None."""
    if not name:
        return None
    toks = name.split()
    last = toks[-1]
    # 코드 패턴: 영문대문자+숫자 조합 (GN7, KA4, SX2, NX4, DL3, GL3, RJ, JA, TAM, QX1...)
    if re.fullmatch(r"[A-Z]{1,4}\d{0,2}", last) or re.fullmatch(r"[A-Z]{2,4}", last):
        return last
    return None

def main():
    veh = load(os.path.join(WROOT, "src", "data", "vehicles.json"))
    # 모델메타: model_name_kr -> {period,status}
    meta = {}
    for f in ("hyundai-models.json", "kia-models.json"):
        d = load(os.path.join(WROOT, "scripts", f))
        for k, v in d.items():
            if k.startswith("_"):
                continue
            nm = v.get("model_name_kr")
            if nm:
                meta[nm] = {"year_start": v.get("year_start"), "year_end": v.get("year_end"),
                            "status": v.get("status")}

    # vehicles.json 을 model_name_kr 기준 그룹
    groups = {}
    for r in veh:
        nm = r.get("model_name_kr") or r.get("name")
        g = groups.setdefault(nm, {"brand": r.get("brand"), "name": nm,
                                   "pw": {}, "trims": []})
        fuel, disp, eng = r.get("fuel"), r.get("disp"), r.get("engine_label")
        pwkey = (fuel, disp, eng)
        g["pw"].setdefault(pwkey, True)
        g["trims"].append({"name": r.get("trim"), "price": r.get("price"),
                           "fuel": fuel, "disp": disp, "engine": eng,
                           "detail": r.get("trim_detail")})

    catalog = []
    for nm, g in sorted(groups.items()):
        m = meta.get(nm, {})
        ys, ye = m.get("year_start"), m.get("year_end")
        period = None
        if ys:
            period = "%s~%s" % (ys[2:4], "현재" if (ye in ("현재", None)) else ye[2:4])
        catalog.append({
            "brand": g["brand"], "name": nm, "gen_code": gen_code_of(nm),
            "period": period, "status": m.get("status"),
            "powertrains": ["%s %s %s" % (f or "", (str(d) if d else ""), e or "")
                            for (f, d, e) in g["pw"]],
            "trim_count": len(g["trims"]),
            "trims": sorted(g["trims"], key=lambda t: t.get("price") or 0),
        })
    json.dump(catalog, open(os.path.join(DATA, "welrix_catalog.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("welrix 카탈로그:", len(catalog), "모델")
    for c in catalog:
        print("  [%s] %s | code=%s | %s | 트림%d" % (
            c["brand"], c["name"], c["gen_code"], c["period"], c["trim_count"]))

if __name__ == "__main__":
    main()
