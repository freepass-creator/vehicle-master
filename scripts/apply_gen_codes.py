# -*- coding: utf-8 -*-
"""
전역 검증 결과 → 세부모델명 코드 통일 + gen_code 필드 + 트림 표준명.
  그랜저 (GN7) → 그랜저 GN7 / 쏘렌토 4세대 → 쏘렌토 MQ4 / 더 뉴 쏘렌토 4세대 → 더 뉴 쏘렌토 MQ4
입력: data/model_targets.json(순서=권위 제조사/모델), data/model_verify_results.json, data/vehicle-tree.json
출력: data/vehicle-tree.json(갱신), data/model_verify_report.json(파워트레인오류·생산기간불일치 검토용)
실행: rebuild 다음. usage: python apply_gen_codes.py
"""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))

def load(n): return json.load(open(os.path.join(DATA, n), encoding="utf-8"))
def save(n, o): json.dump(o, open(os.path.join(DATA, n), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def base_code(gc):
    """gen_code 에서 깨끗한 코드 토큰만 (괄호설명·PE·뒤따르는 말 제거)."""
    if not gc:
        return None
    c = re.sub(r"\(.*?\)", "", gc)                              # 괄호 설명 제거
    c = re.sub(r"\s*(PE|페이스리프트|facelift)\b.*$", "", c, flags=re.I)  # PE 이후 제거
    c = c.strip()
    toks = c.split()
    return toks[0] if toks else None                           # 첫 토큰(코드), KV-II 등 하이픈 유지

def code_name(orig, code):
    """세부모델명을 코드 통일형으로."""
    if not code:
        return orig
    if re.search(r"\([^)]+\)\s*$", orig):                 # (코드) → 코드
        return re.sub(r"\s*\([^)]+\)\s*$", " " + code, orig).strip()
    if re.search(r"\d+세대", orig):                        # N세대 → 코드
        return re.sub(r"\d+세대", code, orig).strip()
    if code in orig.split():                               # 이미 코드 포함
        return orig
    return (orig + " " + code).strip()                     # 코드 없으면 추가

def main():
    targets = load("model_targets.json")
    results = load("model_verify_results.json")
    tree = load("vehicle-tree.json")
    assert len(targets) == len(results), "순서 매칭 불가"

    # 트리 인덱스: (제조사,모델) -> {sub_model명: node}
    midx = {}
    for m in tree["manufacturers"]:
        for g in m.get("models", []):
            midx[(m["name"], g["name"])] = {s["name"]: s for s in g.get("sub_models", [])}

    renamed, coded, trimfix = 0, 0, 0
    report = {"powertrain_findings": [], "period_mismatch": []}
    for t, r in zip(targets, results):
        key = (t["manufacturer"], t["model"])
        subs = midx.get(key, {})
        # 세대코드 + 명명
        for g in r.get("generations", []):
            node = subs.get(g.get("sub_model"))
            if node is None:
                continue
            bc = base_code(g.get("gen_code"))
            if bc:
                node["gen_code"] = bc
                coded += 1
                newname = code_name(node["name"], bc)
                if newname != node["name"]:
                    node.setdefault("name_raw", node["name"])
                    node["name"] = newname
                    renamed += 1
            if g.get("verdict") == "생산기간불일치":
                report["period_mismatch"].append({
                    "model": "%s %s" % key, "sub_model": g.get("sub_model"),
                    "ours": node.get("period"), "verified": g.get("production_period"),
                    "note": g.get("note")})
        # 트림 표준명 (raw→standard), model 범위 적용
        tmap = {ts["raw"]: ts["standard"] for ts in r.get("trim_std", []) if ts.get("raw") and ts.get("standard") and ts["raw"] != ts["standard"]}
        if tmap:
            for node in subs.values():
                for p in node.get("powertrains", []):
                    for tr in p.get("trims", []):
                        cur = tr.get("name")
                        if cur in tmap:
                            tr.setdefault("raw", cur)
                            tr["name"] = tmap[cur]
                            trimfix += 1
        # 파워트레인 오류 리포트
        for pf in r.get("powertrain_findings", []):
            if pf.get("severity") in ("오류", "누락"):
                report["powertrain_findings"].append({"model": "%s %s" % key, **pf})

    # 폴백: 미검증 세부모델도 끝의 (코드)는 안전하게 코드화 (영숫자·하이픈만, 한글설명 제외)
    paren = 0
    for m in tree["manufacturers"]:
        for g in m.get("models", []):
            for s in g.get("sub_models", []):
                if s.get("gen_code"):
                    continue
                mt = re.search(r"\(([A-Za-z0-9][A-Za-z0-9\-]{0,6})\)\s*$", s["name"])
                if mt:
                    s["gen_code"] = mt.group(1)
                    s.setdefault("name_raw", s["name"])
                    s["name"] = re.sub(r"\s*\([^)]+\)\s*$", " " + mt.group(1), s["name"]).strip()
                    paren += 1

    # 코드명 바뀌었으니 세부모델 재정렬(출시순)
    for m in tree["manufacturers"]:
        for g in m.get("models", []):
            g.get("sub_models", []).sort(key=lambda s: (s.get("start") or "000000"), reverse=True)
    print("  (폴백 괄호→코드: %d)" % paren)

    save("vehicle-tree.json", tree)
    save("model_verify_report.json", report)
    print("코드부여 %d · 명칭변경 %d · 트림교정 %d | 리포트: 파워트레인오류 %d, 생산기간불일치 %d" % (
        coded, renamed, trimfix, len(report["powertrain_findings"]), len(report["period_mismatch"])))

if __name__ == "__main__":
    main()
