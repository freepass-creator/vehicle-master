# -*- coding: utf-8 -*-
"""
엔카 차종 트리 크롤러 — 차종마스터 시드
5단계: 제조사 > 모델 > 세부모델 > 파워트레인 > 세부트림

데이터 출처
  제조사(Manufacturer) : nav facet  -- code/eng/ordering/count/국산여부
  모델(ModelGroup)     : nav facet  -- code/eng/ordering/count
  세부모델(Model)      : nav facet  -- code/eng/ordering/count + 생산기간(ModelStartDate/EndDate) + image
  파워트레인           : 세부모델 매물 + 상세조회 -- 연료/배기량/인승 + (터보/구동 = Badge 파싱)
  세부트림             : 국산 BadgeDetail / 수입 category.gradeName

원칙: 한글 쿼리를 셸로 넘기지 않는다. API가 주는 facet['Action'] 를 다음 q 로 재사용.

usage:
  python crawl_encar.py crawl --cartype Y          # 국산 (Y), 수입은 N
  python crawl_encar.py crawl --cartype Y --depth 3  # 세부모델까지만 (파워트레인 생략)
  python crawl_encar.py merge                      # 체크포인트 병합+정렬 -> data/vehicle-tree.json
"""
import sys, os, json, time, argparse, re, urllib.parse, urllib.request

API = "https://api.encar.com/search/car/list/general"
DETAIL = "https://api.encar.com/v1/readside/vehicle/%s"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "http://www.encar.com/",
    "Accept": "application/json",
}
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))
CKPT = os.path.join(DATA, "checkpoints")

NAV_LEVELS = [("Manufacturer", "models"), ("ModelGroup", "sub_models"), ("Model", "powertrains")]
CARTYPE = {"Y": "국산", "N": "수입"}
DELAY = 0.2
LISTING_N = 200    # 세부모델당 표본 매물 수

# ---- HTTP ----
def _get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8")
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1.0 + attempt)

def save_json(path, obj):
    """원자적 저장 (서버가 읽는 중 깨진 파일 보지 않도록)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump(obj, fp, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def fetch(q):
    return json.loads(_get(API + "?count=true&inav=" + urllib.parse.quote("|Metadata|Sort")
                           + "&q=" + urllib.parse.quote(q)))

def fetch_listings(q, n=LISTING_N):
    return json.loads(_get(API + "?count=true&q=" + urllib.parse.quote(q)
                          + "&sr=" + urllib.parse.quote("|ModifiedDate|0|%d" % n)))

def fetch_detail(vid):
    return json.loads(_get(DETAIL % vid))

# ---- facet -> node ----
def find_node(data, node_name):
    def walk(nodes):
        for n in nodes:
            if n.get("Name") == node_name:
                return n.get("Facets", [])
            for f in n.get("Facets", []):
                ref = f.get("Refinements")
                if ref:
                    got = walk(ref.get("Nodes", []))
                    if got is not None:
                        return got
        return None
    return walk(data.get("iNav", {}).get("Nodes", []))

def mfirst(m, k):
    v = (m or {}).get(k)
    return v[0] if isinstance(v, list) and v else None

def period_label(sd, ed):
    """'202308','202307' -> '20~23' / '202308',None -> '23~현재'"""
    yy = lambda s: s[2:4] if s and len(s) >= 6 else None
    s = yy(sd)
    if not s:
        return None
    return "%s~%s" % (s, yy(ed) if ed else "현재")

def node_from_facet(f, level):
    m = f.get("Metadata", {}) or {}
    o = {"name": f.get("Value"), "count": f.get("Count"),
         "code": mfirst(m, "Code"), "eng": mfirst(m, "EngName"),
         "order": mfirst(m, "Ordering"), "_action": f.get("Action")}
    if level == "Model":
        sd, ed = mfirst(m, "ModelStartDate"), mfirst(m, "ModelEndDate")
        o["start"], o["end"] = sd, ed
        o["period"] = period_label(sd, ed)
        img = mfirst(m, "Image")
        if img:
            o["image"] = img
    return o

# ---- 파워트레인 파싱 ----
FUEL_NORM = {"가솔린+전기": "하이브리드", "디젤+전기": "디젤HEV", "LPG+전기": "LPG HEV",
             "LPG(일반인 구입)": "LPG", "LPG(렌터카/장애인용)": "LPG", "전기": "전기"}
DRIVE_PATS = [("xDrive", r"xdrive"), ("4MATIC", r"4matic|4매틱"), ("콰트로", r"콰트로|quattro"),
              ("4모션", r"4모션|4motion"), ("AWD", r"\bawd\b"), ("4WD", r"4wd|사륜"),
              ("2WD", r"2wd"), ("전륜", r"전륜"), ("후륜", r"후륜")]

# 트림(BadgeDetail)에서 파워트레인 토큰 제거 → 순수 등급명만 (우리 정보)
_TRIM_STRIP = re.compile(
    r"\b\d+인승\b"
    r"|\b\d\.\d\b"
    r"|터보|turbo|t-?gdi"
    r"|가솔린|디젤|lpg|전기|하이브리드|hev|phev"
    r"|2wd|4wd|awd|xdrive|4matic|콰트로|quattro|4모션|4motion",
    re.IGNORECASE)

def normalize_trim(raw):
    s = _TRIM_STRIP.sub(" ", raw or "")
    s = re.sub(r"\s+", " ", s).strip(" ·-")
    return s or "기본"

def clean_trims(trims):
    """[{name:raw}] -> 정규화+중복제거, 바뀌면 원본을 raw 로 보관."""
    seen, out = set(), []
    for t in trims:
        raw = t.get("name")
        n = normalize_trim(raw)
        if n in seen:
            continue
        seen.add(n)
        out.append({"name": n, "raw": raw} if n != raw else {"name": n})
    return out

EV_FUELS = ("전기", "수소")  # 배기량 개념 없음 → 엔카 displacement 무시

def finalize_powertrains(pws):
    """세부모델의 파워트레인 마무리: EV는 배기량 제거, 동일 사양 병합, 트림 정규화."""
    groups, order = {}, []
    for p in pws or []:
        fuel = p.get("fuel")
        disp, displ = p.get("displacement"), p.get("displacement_l")
        if fuel in EV_FUELS:
            disp = displ = None  # 전기/수소는 배기량 무의미
        key = (fuel, displ, p.get("turbo"), p.get("seat"), p.get("drivetrain"))
        if key not in groups:
            groups[key] = {"fuel": fuel, "displacement": disp, "displacement_l": displ,
                           "turbo": p.get("turbo"), "seat": p.get("seat"),
                           "drivetrain": p.get("drivetrain"), "trims": []}
            order.append(key)
        groups[key]["trims"].extend(p.get("trims", []))
    out = []
    for key in order:
        g = groups[key]
        g["trims"] = clean_trims(g["trims"])
        out.append(g)
    return out

def norm_fuel(f):
    if not f:
        return None
    return FUEL_NORM.get(f, f)

def to_l(cc):
    return round(cc / 1000.0, 1) if cc else None

def is_turbo(badge):
    s = (badge or "").lower()
    return ("터보" in (badge or "")) or ("turbo" in s) or ("t-gdi" in s) or ("tgdi" in s)

def parse_drive(badge):
    s = (badge or "").lower()
    for label, pat in DRIVE_PATS:
        if re.search(pat, s):
            return label
    return None

def aggregate_powertrains(model_q):
    """세부모델 매물 -> Badge별 상세조회 -> (연료,배기량,인승,구동,터보) 그룹 + 트림."""
    time.sleep(DELAY)
    res = fetch_listings(model_q).get("SearchResults", [])
    by_badge, order = {}, []
    for r in res:
        b = r.get("Badge")
        if not b:
            continue
        if b not in by_badge:
            by_badge[b] = {"id": r.get("Id"), "fuel": r.get("FuelType"), "trims": set()}
            order.append(b)
        bd = r.get("BadgeDetail")
        if bd:
            by_badge[b]["trims"].add(bd)
    pw_map, pw_order = {}, []
    for b in order:
        info = by_badge[b]
        fuel, disp, seat, grade = info["fuel"], None, None, None
        try:
            time.sleep(DELAY)
            det = fetch_detail(info["id"])
            spec, cat = det.get("spec", {}) or {}, det.get("category", {}) or {}
            fuel = spec.get("fuelName") or fuel
            disp, seat = spec.get("displacement"), spec.get("seatCount")
            grade = cat.get("gradeName")
        except Exception:
            pass
        fuel = norm_fuel(fuel)
        drive, turbo = parse_drive(b), is_turbo(b)
        key = (fuel, disp, seat, drive, turbo)
        if key not in pw_map:
            pw_map[key] = {"fuel": fuel, "displacement": disp, "displacement_l": to_l(disp),
                           "turbo": turbo, "seat": seat, "drivetrain": drive, "trims": set()}
            pw_order.append(key)
        tr = info["trims"] if info["trims"] else ([grade] if grade else [])
        pw_map[key]["trims"].update(tr)
    out = []
    for key in pw_order:
        v = pw_map[key]
        out.append({"fuel": v["fuel"], "displacement": v["displacement"],
                    "displacement_l": v["displacement_l"], "turbo": v["turbo"],
                    "seat": v["seat"], "drivetrain": v["drivetrain"],
                    "trims": [{"name": t} for t in sorted(v["trims"])]})
    return out

# ---- crawl ----
def crawl_level(q, level_idx, max_depth):
    node_name, child_key = NAV_LEVELS[level_idx]
    facets = find_node(fetch(q), node_name) or []
    time.sleep(DELAY)
    out = []
    for f in facets:
        if f.get("Value") in (None, "", "A", "N", "Y"):
            continue
        node = node_from_facet(f, node_name)
        action = f.get("Action")
        if level_idx + 1 < len(NAV_LEVELS) and level_idx + 1 < max_depth:
            if action:
                node[child_key] = crawl_level(action, level_idx + 1, max_depth)
        elif node_name == "Model" and max_depth >= 4 and action:
            node["powertrains"] = aggregate_powertrains(action)
        out.append(node)
    return out

def cmd_crawl(cartype, depth):
    os.makedirs(CKPT, exist_ok=True)
    mans = find_node(fetch("(And.Hidden.N._.CarType.%s.)" % cartype), "Manufacturer") or []
    mans = [f for f in mans if f.get("Value") not in (None, "", "A", "N", "Y")]
    print("manufacturers:", len(mans))
    for i, f in enumerate(mans):
        man = node_from_facet(f, "Manufacturer")
        man["car_type"] = CARTYPE.get(cartype, cartype)
        code = man.get("code") or man["name"]
        ckpt = os.path.join(CKPT, "%s_%s.json" % (cartype, code))
        if os.path.exists(ckpt):
            # depth<4 면 존재만으로 스킵. depth>=4 면 파워트레인까지 채워졌을 때만 스킵.
            skip = True
            if depth >= 4:
                try:
                    ex = json.load(open(ckpt, encoding="utf-8"))
                    skip = any("powertrains" in s for g in ex.get("models", [])
                               for s in g.get("sub_models", []))
                except (ValueError, OSError):
                    skip = False
            if skip:
                print("[%d/%d] skip %s" % (i + 1, len(mans), man["name"]))
                continue
        print("[%d/%d] %s ..." % (i + 1, len(mans), man["name"]), flush=True)
        man["models"] = []
        if depth > 1:
            groups = find_node(fetch(f.get("Action")), "ModelGroup") or []
            time.sleep(DELAY)
            groups = [g for g in groups if g.get("Value") not in (None, "", "A", "N", "Y")]
            for gi, gf in enumerate(groups):
                g = node_from_facet(gf, "ModelGroup")
                if depth > 2 and gf.get("Action"):
                    g["sub_models"] = crawl_level(gf.get("Action"), 2, depth)
                man["models"].append(g)
                save_json(ckpt, man)  # 모델그룹 단위 중간 저장 → 라이브 뷰어 점진 채움
                if depth >= 4:
                    print("        %s (%d/%d)" % (g["name"], gi + 1, len(groups)), flush=True)
        save_json(ckpt, man)
        print("        saved", os.path.basename(ckpt), flush=True)
    print("done.")

# ---- merge + sort ----
def strip(node):
    node.pop("_action", None)
    for k in ("models", "sub_models", "powertrains", "trims"):
        if isinstance(node.get(k), list):
            for c in node[k]:
                strip(c)
    return node

def sort_tree(tree):
    # 제조사: 국산 먼저, 각 그룹 매물 많은 순
    tree["manufacturers"].sort(key=lambda m: (0 if m.get("car_type") == "국산" else 1,
                                              -(m.get("count") or 0)))
    for m in tree["manufacturers"]:
        m.get("models", []).sort(key=lambda g: -(g.get("count") or 0))  # 모델 인기순
        for g in m.get("models", []):
            # 세부모델 출시순(최신 위) — start 'YYYYMM' 내림차순
            g.get("sub_models", []).sort(key=lambda s: (s.get("start") or "000000"), reverse=True)
    return tree

def cmd_merge():
    out = {"source": "encar", "levels": ["제조사", "모델", "세부모델", "파워트레인", "세부트림"],
           "manufacturers": []}
    for fn in sorted(os.listdir(CKPT)):
        if fn.endswith(".json"):
            with open(os.path.join(CKPT, fn), encoding="utf-8") as fp:
                out["manufacturers"].append(strip(json.load(fp)))
    # 파워트레인 마무리(EV 배기량 제거·병합) + 트림 정규화
    for m in out["manufacturers"]:
        for g in m.get("models", []):
            for s in g.get("sub_models", []):
                if s.get("powertrains"):
                    s["powertrains"] = finalize_powertrains(s["powertrains"])
    sort_tree(out)
    path = os.path.join(DATA, "vehicle-tree.json")
    save_json(path, out)
    print("merged %d manufacturers -> %s" % (len(out["manufacturers"]), path))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("crawl")
    c.add_argument("--cartype", default="Y")
    c.add_argument("--depth", type=int, default=5)
    sub.add_parser("merge")
    a = ap.parse_args()
    if a.cmd == "crawl":
        cmd_crawl(a.cartype, a.depth)
    elif a.cmd == "merge":
        cmd_merge()
    else:
        ap.print_help()
