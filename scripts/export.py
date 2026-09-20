# -*- coding: utf-8 -*-
"""
차종마스터 배포(export): 다른 ERP가 가져가기 쉽게 규격화된 산출물 생성.
출력 dist/:
  manifest.json          버전·생성일·건수·파일목록·스키마요약
  vehicle-master.json    전체 트리 (안정 id 부여, 내부필드 제거)
  vehicle-master.flat.json  트림 1행 denormalized (DB import용)
  vehicle-master.flat.csv   동일 (엑셀/DB)
  codes.json             제조사/모델/세대 코드 → 이름 룩업
  SCHEMA.md              스키마 문서
usage: python export.py [YYYY-MM-DD]   (날짜 생략 시 버전 날짜는 호출자가 stamp)
"""
import json, os, re, csv, sys, hashlib
from identity_contract import IdentityRegistry
from validate_identity_export import validate as validate_identity_export
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))
DIST = os.path.normpath(os.path.join(HERE, "..", "dist"))

INTERNAL = ("name_raw", "_action", "period_raw", "battery_note")  # export 에서 제거

def slug(s):
    s = re.sub(r"[^\w가-힣]+", "-", (s or "").strip())
    return re.sub(r"-+", "-", s).strip("-").lower() or "x"

def clean(node):
    for k in INTERNAL:
        node.pop(k, None)
    return node

def build(date_str):
    input_path = os.path.join(DATA, "vehicle-tree.json")
    input_sha256 = hashlib.sha256(open(input_path, "rb").read()).hexdigest()
    tree = json.load(open(input_path, encoding="utf-8"))
    os.makedirs(DIST, exist_ok=True)

    identity = IdentityRegistry(
        os.path.join(DIST, "identity-map.json"),
        os.path.join(DATA, "id-aliases.json"),
        date_str,
    )
    provenance_entries = {}

    def semantic_key(*parts):
        return json.dumps(parts, ensure_ascii=False, separators=(",", ":"))

    def bind_identity(
        node, entity_type, identity_key, legacy_id, parent_uid=None,
        declared_source=None, raw_name=None, source_code=None,
    ):
        uid = identity.resolve(entity_type, identity_key, legacy_id, parent_uid)
        node["uid"] = uid
        record = {
            "entity_type": entity_type,
            "identity_key": identity_key,
            "id": legacy_id,
            "parent_uid": parent_uid,
        }
        if declared_source:
            record["declared_source"] = declared_source
        if source_code is not None:
            record["source_code"] = source_code
        if raw_name and raw_name != node.get("name"):
            record["raw_name"] = raw_name
        provenance_entries[uid] = record
        return uid

    flat, codes = [], {"manufacturers": {}, "models": {}, "generations": {}}
    for m in tree["manufacturers"]:
        mfc = m.get("code") or slug(m["name"])
        m["id"] = "mf-%s" % mfc
        m_identity_key = semantic_key("manufacturer", mfc)
        m_uid = bind_identity(
            m, "manufacturer", m_identity_key, m["id"],
            raw_name=m.get("name_raw"),
            declared_source=m.get("source"),
            source_code=m.get("code"),
        )
        clean(m)
        codes["manufacturers"][mfc] = {
            "name": m["name"], "eng": m.get("eng"), "car_type": m.get("car_type"), "uid": m_uid
        }
        for g in m.get("models", []):
            mdc = g.get("code") or slug(g["name"])
            g["id"] = "%s.md-%s" % (m["id"], mdc)
            g_identity_key = semantic_key("model", m_uid, mdc)
            g_uid = bind_identity(
                g, "model", g_identity_key, g["id"], m_uid,
                raw_name=g.get("name_raw"),
                declared_source=g.get("source"),
                source_code=g.get("code"),
            )
            clean(g)
            codes["models"]["%s-%s" % (mfc, mdc)] = {
                "manufacturer": m["name"], "name": g["name"], "eng": g.get("eng"), "uid": g_uid
            }
            for s in g.get("sub_models", []):
                gc = s.get("gen_code") or slug(s["name"])
                s["id"] = "%s.sm-%s" % (g["id"], slug(gc))
                if s.get("code") is not None:
                    s_identity_key = semantic_key(
                        "sub_model", g_uid, "source_code", str(s.get("code"))
                    )
                else:
                    s_identity_key = semantic_key(
                        "sub_model", g_uid, "fallback",
                        s.get("gen_code") or "",
                        s.get("start") or "",
                        s.get("name_raw") or s.get("name") or "",
                    )
                s_uid = bind_identity(
                    s, "sub_model", s_identity_key, s["id"], g_uid,
                    raw_name=s.get("name_raw"),
                    declared_source=s.get("source"),
                    source_code=s.get("code"),
                )
                clean(s)
                codes["generations"][s["id"]] = {
                    "model": g["name"], "sub_model": s["name"],
                    "gen_code": s.get("gen_code"), "period": s.get("period"), "uid": s_uid
                }
                for p in s.get("powertrains", []):
                    pid = "%s.pw-%s" % (s["id"], slug("%s-%s-%s" % (p.get("fuel"), p.get("displacement_l") or p.get("battery_kwh") or "", p.get("drivetrain") or "")))
                    p["id"] = pid
                    p_identity_key = semantic_key(
                        "powertrain", s_uid,
                        p.get("fuel"),
                        p.get("displacement_l"),
                        p.get("battery_kwh"),
                        p.get("drivetrain"),
                        p.get("turbo"),
                        p.get("seat"),
                    )
                    p_uid = bind_identity(
                        p, "powertrain", p_identity_key, pid, s_uid,
                        declared_source=s.get("source"),
                    )
                    clean(p)
                    for t in p.get("trims", []):
                        tid = "%s.tr-%s" % (pid, slug(t["name"]))
                        t["id"] = tid
                        t_identity_key = semantic_key(
                            "trim", p_uid, t.get("raw") or t.get("name") or ""
                        )
                        t_uid = bind_identity(
                            t, "trim", t_identity_key, tid, p_uid,
                            declared_source=s.get("source"),
                            raw_name=t.get("raw") or t.get("name_raw"),
                        )
                        clean(t)
                        flat.append({
                            "id": tid, "uid": t_uid,
                            "manufacturer": m["name"], "manufacturer_code": mfc, "car_type": m.get("car_type"),
                            "model": g["name"], "model_code": mdc,
                            "sub_model": s["name"], "gen_code": s.get("gen_code"),
                            "period": s.get("period"), "source": s.get("source", "encar"),
                            "fuel": p.get("fuel"), "displacement_l": p.get("displacement_l"),
                            "turbo": p.get("turbo"), "drivetrain": p.get("drivetrain"), "seat": p.get("seat"),
                            "battery_kwh": p.get("battery_kwh"), "range_km": p.get("range_km"),
                            "trim": t["name"], "msrp_manwon": t.get("msrp"),
                            "fleet": bool(t.get("fleet")), "special": bool(t.get("special")),
                        })

    # 콘텐츠 해시 → 버전 (내용 같으면 같은 버전)
    digest = hashlib.md5(json.dumps(tree, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:8]
    version = "%s+%s" % (date_str or "0000-00-00", digest)

    def w(name, obj):
        json.dump(obj, open(os.path.join(DIST, name), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    tree["version"] = version
    w("vehicle-master.json", tree)
    w("vehicle-master.flat.json", {"version": version, "rows": flat})
    w("codes.json", {"version": version, **codes})
    w("identity-map.json", identity.document())
    w("provenance.json", {
        "schema_version": "2.0",
        "version": version,
        "generated": date_str,
        "input": {"path": "data/vehicle-tree.json", "sha256": input_sha256},
        "entries": provenance_entries,
    })

    # 매칭 전용 슬림 인덱스 — 세부모델당 1엔트리 (외부 ERP 시트→우리 규격 매칭용)
    def norm_maker(name):
        return re.sub(r"\(.*?\)", "", name or "").strip()  # 쉐보레(GM대우)→쉐보레
    match_entries = []
    for m in tree["manufacturers"]:
        mk = norm_maker(m["name"])
        for g in m.get("models", []):
            for s in g.get("sub_models", []):
                variants, ctrims = [], []
                for p in s.get("powertrains", []):
                    e = "%gkWh" % p["battery_kwh"] if p.get("battery_kwh") is not None else (
                        "%g%s" % (p["displacement_l"], "T" if p.get("turbo") else "") if p.get("displacement_l") is not None else "")
                    label = " ".join(x for x in [p.get("fuel"), e, p.get("drivetrain")] if x)
                    ptrims = [t["name"] for t in p.get("trims", []) if not t.get("fleet")]
                    variants.append({"label": label, "fuel": p.get("fuel"),
                                     "displacement_l": p.get("displacement_l"), "turbo": p.get("turbo"),
                                     "drivetrain": p.get("drivetrain"), "seat": p.get("seat"),
                                     "battery_kwh": p.get("battery_kwh"),
                                     "trims": ptrims})   # 파워트레인별 트림 (LPG에 가솔린 트림 안 섞이게)
                    ctrims += ptrims
                ye = s.get("end")
                match_entries.append({
                    "id": s["id"], "uid": s["uid"], "maker": mk, "model": g["name"], "sub_model": s["name"],
                    "gen_code": s.get("gen_code"), "origin": m.get("car_type"),
                    "year_start": (s.get("start") or "")[:4], "year_end": (ye[:4] if ye else "현재"),
                    "title": ("%s %s" % (mk, s["name"])).strip(),
                    "variants": variants, "trims": sorted(set(ctrims)),
                })
    w("match-index.json", {"version": version, "count": len(match_entries), "entries": match_entries})

    # CSV (엑셀 호환 utf-8-sig)
    cols = list(flat[0].keys()) if flat else []
    with open(os.path.join(DIST, "vehicle-master.flat.csv"), "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=cols)
        wr.writeheader(); wr.writerows(flat)

    counts = {"manufacturers": len(tree["manufacturers"]),
              "models": sum(len(m.get("models", [])) for m in tree["manufacturers"]),
              "sub_models": sum(len(g.get("sub_models", [])) for m in tree["manufacturers"] for g in m.get("models", [])),
              "powertrains": sum(len(s.get("powertrains", [])) for m in tree["manufacturers"] for g in m.get("models", []) for s in g.get("sub_models", [])),
              "trims": len(flat)}
    manifest = {
        "name": "vehicle-master", "version": version, "generated": date_str,
        "source": "encar + welrix + namuwiki crosscheck", "levels": tree.get("levels"),
        "counts": counts,
        "files": {
            "tree": "vehicle-master.json", "flat_json": "vehicle-master.flat.json",
            "flat_csv": "vehicle-master.flat.csv", "codes": "codes.json",
            "match_index": "match-index.json", "identity_map": "identity-map.json",
            "provenance": "provenance.json", "schema": "SCHEMA.md"},
        "id_scheme": "mf-{mfCode}.md-{modelCode}.sm-{genCode}.pw-{fuel-disp-drive}.tr-{trim}",
        "identity_contract": {
            "schema_version": "2.0",
            "compatibility_id": "id",
            "compatibility_id_unique": False,
            "durable_id": "uid",
            "durable_identity_basis": "semantic_identity_key",
            "alias_ledger": "../data/id-aliases.json",
        },
        "provenance": {
            "input": "data/vehicle-tree.json",
            "input_sha256": input_sha256,
            "sources": ["encar", "welrix", "namuwiki/wikipedia crosscheck"],
        },
        "notes": "trims[].fleet=true 는 택시/렌트/특장 영업용. 일반 표시 시 제외 권장. msrp_manwon=신차가(만원).",
    }
    w("manifest.json", manifest)

    schema = """# 차종마스터 export 스키마

버전: `%s` / 생성: %s

## 파일
- **manifest.json** — 버전·건수·파일목록 (먼저 읽어 버전 확인)
- **vehicle-master.json** — 전체 트리 (5단계 중첩, 각 노드 `id` 포함)
- **vehicle-master.flat.json** — `{version, rows[]}` 트림 1행 denormalized (DB/매칭용 권장)
- **vehicle-master.flat.csv** — 동일 (엑셀/DB import, utf-8-sig)
- **codes.json** — 제조사/모델/세대 코드 룩업
- **identity-map.json** — 지속 UID 레지스트리와 semantic identity key alias
- **provenance.json** — UID별 semantic key/출처/원본명/부모 관계 추적

## 식별자
- `uid`: 유일한 장기 참조키. 외부 ERP의 신규 foreign key는 uid 사용.
- `id`: 기존 호환 표시키. 현재 데이터에서 중복 가능하므로 foreign key로 사용하지 않음.
- `identity_key`: UID 생성·연속성 판정에 쓰는 내부 semantic key.
- semantic key 변경 시 `data/id-aliases.json`에 새 identity_key → 이전 identity_key를 선언.

## 호환 ID
`%s`
예: `mf-001.md-004.sm-gn7.pw-가솔린-3.5-4wd.tr-캘리그래피`

## 트리 노드
- 제조사: name, eng, code, count, car_type(국산/수입), id
- 모델: name, eng, code, count, id
- 세부모델: name(코드통일 '그랜저 GN7'), gen_code, period('22~26'), start, end, source(encar/welrix), battery_options(EV), id
- 파워트레인: fuel, displacement_l, turbo, drivetrain, seat, battery_kwh, range_km(EV), id
- 트림: name, msrp(신차가/만원), fleet(영업용 bool), special(한정판 bool), id, raw(엔카원본 명칭이 다를 때)

## flat row 컬럼
%s

## 사용 팁
- 일반 소비자용만 필요하면 `fleet==false` 필터.
- 트림 정렬은 `msrp_manwon` 오름차순(기본→상위).
- 모델/세대 매칭 키는 `gen_code`(그랜저 GN7) 권장.
""" % (version, date_str, manifest["id_scheme"], ", ".join(cols))
    open(os.path.join(DIST, "SCHEMA.md"), "w", encoding="utf-8").write(schema)

    validation = validate_identity_export(DIST)
    if not validation["ok"]:
        raise RuntimeError(
            "identity/provenance export validation failed: %s"
            % "; ".join(validation["errors"])
        )

    print(
        "export 완료 + identity 검증 PASS → dist/  version=%s  trims=%d  entities=%d"
        % (version, len(flat), validation["tree_identity_count"])
    )
    return version

if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else None)
