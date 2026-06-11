# -*- coding: utf-8 -*-
"""
모델별 트림 가격 수집 (트림 정렬용). 모델당 매물 1회 조회로 BadgeDetail별 중앙값(만원).
출력: data/trim_prices.json = { "제조사|모델": { "BadgeDetail원본": 중앙값만원 } }
가벼운 패스(상세조회 없음). usage: python fetch_trim_prices.py
"""
import json, os, sys, time, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import crawl_encar as ce
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))

def run():
    prices = {}
    for ct in ("Y", "N"):
        mans = ce.find_node(ce.fetch("(And.Hidden.N._.CarType.%s.)" % ct), "Manufacturer") or []
        mans = [f for f in mans if f.get("Value") not in (None, "", "A", "N", "Y")]
        for mi, mf in enumerate(mans):
            mname = mf["Value"]
            mgs = ce.find_node(ce.fetch(mf["Action"]), "ModelGroup") or []
            time.sleep(ce.DELAY)
            mgs = [g for g in mgs if g.get("Value") not in (None, "", "A", "N", "Y")]
            for gf in mgs:
                d = ce.fetch_listings(gf["Action"], 200)
                time.sleep(ce.DELAY)
                pmap = {}
                for r in d.get("SearchResults", []):
                    bd, pr = r.get("BadgeDetail"), r.get("Price")
                    if not bd or pr in (None, 0):
                        continue
                    pmap.setdefault(bd, []).append(pr)
                if pmap:
                    prices["%s|%s" % (mname, gf["Value"])] = {
                        bd: round(statistics.median(v), 1) for bd, v in pmap.items()}
            print("[%s %d/%d] %s" % (ct, mi + 1, len(mans), mname), flush=True)
    ce.save_json(os.path.join(DATA, "trim_prices.json"), prices)
    print("저장: trim_prices.json (모델 %d개)" % len(prices))

if __name__ == "__main__":
    run()
