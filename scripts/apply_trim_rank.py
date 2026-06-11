# -*- coding: utf-8 -*-
"""
트림 서열 워크플로우 결과 → 트림 정렬(기본→비싼) + 신차가(MSRP) 부가.
입력: data/trim_rank_targets.json(순서=권위), data/trim_rank_results.json, data/vehicle-tree.json
파워트레인 내 trims 를 rank 오름차순 정렬. rank 없는 트림은 뒤로(이름순).
실행: rebuild 다음(코드명명 뒤). usage: python apply_trim_rank.py
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))

def load(n): return json.load(open(os.path.join(DATA, n), encoding="utf-8"))

def main():
    tp = os.path.join(DATA, "trim_rank_results.json")
    if not os.path.exists(tp):
        print("trim_rank_results.json 없음 — 워크플로우 결과 먼저 저장"); return
    targets = load("trim_rank_targets.json")
    results = load("trim_rank_results.json")
    tree = load("vehicle-tree.json")
    assert len(targets) == len(results), "순서 매칭 불가"

    # (제조사,모델) -> {트림명: (rank, msrp)}
    rankmap = {}
    for t, r in zip(targets, results):
        key = (t["manufacturer"], t["model"])
        d = rankmap.setdefault(key, {})
        for rt in r.get("ranked_trims", []):
            nm = rt.get("name")
            if nm:
                d[nm] = (rt.get("rank", 999), rt.get("msrp_manwon"))

    ordered = 0
    for m in tree["manufacturers"]:
        for g in m.get("models", []):
            d = rankmap.get((m["name"], g["name"]))
            if not d:
                continue
            for s in g.get("sub_models", []):
                for p in s.get("powertrains", []):
                    trims = p.get("trims", [])
                    if len(trims) < 2:
                        # 단일 트림도 msrp 부가
                        for tr in trims:
                            info = d.get(tr.get("name"))
                            if info and info[1] is not None:
                                tr["msrp"] = info[1]
                        continue
                    def keyf(tr):
                        info = d.get(tr.get("name"))
                        rank = info[0] if info else 998
                        return (info is None, rank, tr.get("name") or "")
                    trims.sort(key=keyf)
                    for tr in trims:
                        info = d.get(tr.get("name"))
                        if info and info[1] is not None:
                            tr["msrp"] = info[1]
                    ordered += 1
    json.dump(tree, open(os.path.join(DATA, "vehicle-tree.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("트림 서열 적용: 파워트레인 %d개" % ordered)

if __name__ == "__main__":
    main()
