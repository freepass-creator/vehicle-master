# -*- coding: utf-8 -*-
"""
EV 배터리 교차검증 결과를 vehicle-tree 에 규격화 적용.
  입력: data/vehicle-tree.json (병합본), data/ev_targets.json (권위 키, 순서),
        data/ev_battery_specs.json (워크플로우 결과, 같은 순서)
  처리: 표준화(kwh 기준) + 중복제거 + 오류검증 + 트리 머지
  출력: data/vehicle-tree.json (갱신), data/ev_validation_report.json

원칙(요청): 중복제거 / 오류검증 / 규격통일 / 효율화(O(N), 인덱스 정렬 매칭)
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))

def load(n): return json.load(open(os.path.join(DATA, n), encoding="utf-8"))
def save(n, o): json.dump(o, open(os.path.join(DATA, n), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

EV_FUELS = ("전기", "수소")

def std_drive(d):
    """배터리 spec 의 자유서술 구동 → 엔카 표기로 정규화."""
    s = (d or "").lower()
    if "xdrive" in s: return "xDrive"
    if "4matic" in s or "4매틱" in s: return "4MATIC"
    if "콰트로" in s or "quattro" in s: return "콰트로"
    if "awd" in s: return "AWD"
    if "4wd" in s or "사륜" in s: return "4WD"
    if "rwd" in s or "후륜" in s or "2wd" in s or "ff" in s or "전륜" in s: return "2WD"
    return None

def standardize(batteries):
    """kwh 기준 표준화 + (kwh,구동) 중복제거 + kwh 오름차순."""
    seen, out = set(), []
    for b in batteries or []:
        kwh = b.get("kwh")
        if kwh is None:
            continue
        kwh = round(float(kwh), 1)
        dr = std_drive(b.get("drivetrain"))
        key = (kwh, dr)
        if key in seen:
            continue
        seen.add(key)
        out.append({"kwh": kwh, "usable_kwh": b.get("usable_kwh"),
                    "range_km": b.get("range_km"), "drivetrain": dr})
    out.sort(key=lambda x: (x["kwh"], x["drivetrain"] or ""))
    return out

def main():
    tree = load("vehicle-tree.json")
    targets = load("ev_targets.json")["targets"]
    specs = load("ev_battery_specs.json")
    assert len(targets) == len(specs), "타깃/스펙 길이 불일치 (순서 매칭 불가)"

    # 트리 EV 세부모델 인덱스 (제조사,모델,세부모델) -> node  : O(N)
    idx = {}
    for m in tree["manufacturers"]:
        for g in m.get("models", []):
            for s in g.get("sub_models", []):
                idx[(m["name"], g["name"], s["name"])] = s

    report = {"checked": 0, "applied_bev": 0, "fcev": [], "errors": [], "review_medium": []}
    for t, sp in zip(targets, specs):
        report["checked"] += 1
        key = (t["manufacturer"], t["model"], t["sub_model"])
        label = "%s %s / %s" % key
        node = idx.get(key)
        if node is None:
            report["errors"].append({"model": label, "flag": "트리매칭실패"})
            continue

        # 수소차(FCEV): 배터리 개념 아님 → H2/주행거리만, 배터리 스탬핑 안 함
        if t.get("fuel") == "수소":
            rng = next((b.get("range_km") for b in sp.get("batteries", []) if b.get("range_km")), None)
            node["fcev"] = True
            if rng:
                node["fcev_range_km"] = rng
            node["battery_sources"] = sp.get("sources", [])[:4]
            for p in node.get("powertrains", []):
                p["displacement"] = p["displacement_l"] = None
            report["fcev"].append(label)
            continue

        bats = standardize(sp.get("batteries", []))
        if not bats:
            report["errors"].append({"model": label, "flag": "배터리없음"})
            continue
        outliers = [b["kwh"] for b in bats if not (5 <= b["kwh"] <= 160)]
        if outliers:
            report["errors"].append({"model": label, "flag": "kwh이상치", "values": outliers})

        node["battery_options"] = bats
        node["battery_sources"] = sp.get("sources", [])[:4]
        if sp.get("notes"):
            node["battery_note"] = sp["notes"]
        # EV 파워트레인에 배터리 스탬핑 (구동 매칭, 배터리는 구동무관 공유 가능)
        for p in node.get("powertrains", []):
            if p.get("fuel") not in EV_FUELS:
                continue
            p["displacement"] = p["displacement_l"] = None
            matched = [b for b in bats if b["drivetrain"] == p.get("drivetrain")]
            if not matched:  # 구동별 배터리 구분이 없으면(공유) 전체 후보
                matched = bats
            if len(matched) == 1:
                p["battery_kwh"] = matched[0]["kwh"]
                p["usable_kwh"] = matched[0]["usable_kwh"]
                p["range_km"] = matched[0]["range_km"]
            else:
                p["battery_kwh_options"] = sorted({b["kwh"] for b in matched})
        report["applied_bev"] += 1

        if sp.get("confidence") != "high":
            report["review_medium"].append({"model": label, "batteries": [b["kwh"] for b in bats]})

    save("vehicle-tree.json", tree)
    save("ev_validation_report.json", report)
    print("checked=%d  BEV적용=%d  FCEV=%d  오류=%d  검토(medium)=%d" % (
        report["checked"], report["applied_bev"], len(report["fcev"]),
        len(report["errors"]), len(report["review_medium"])))

if __name__ == "__main__":
    main()
