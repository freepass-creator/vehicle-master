# 차종마스터 export 스키마

버전: `2026-06-11+0cb40edf` / 생성: 2026-06-11

## 파일
- **manifest.json** — 버전·건수·파일목록 (먼저 읽어 버전 확인)
- **vehicle-master.json** — 전체 트리 (5단계 중첩, 각 노드 `id` 포함)
- **vehicle-master.flat.json** — `{version, rows[]}` 트림 1행 denormalized (DB/매칭용 권장)
- **vehicle-master.flat.csv** — 동일 (엑셀/DB import, utf-8-sig)
- **codes.json** — 제조사/모델/세대 코드 룩업

## 안정 ID
`mf-{mfCode}.md-{modelCode}.sm-{genCode}.pw-{fuel-disp-drive}.tr-{trim}`
예: `mf-001.md-004.sm-gn7.pw-가솔린-3.5-4wd.tr-캘리그래피`
- 같은 차량은 항상 같은 id (재빌드해도 유지). 외부 ERP는 이 id 로 참조.

## 트리 노드
- 제조사: name, eng, code, count, car_type(국산/수입), id
- 모델: name, eng, code, count, id
- 세부모델: name(코드통일 '그랜저 GN7'), gen_code, period('22~26'), start, end, source(encar/welrix), battery_options(EV), id
- 파워트레인: fuel, displacement_l, turbo, drivetrain, seat, battery_kwh, range_km(EV), id
- 트림: name, msrp(신차가/만원), fleet(영업용 bool), special(한정판 bool), id, raw(엔카원본 명칭이 다를 때)

## flat row 컬럼
id, manufacturer, manufacturer_code, car_type, model, model_code, sub_model, gen_code, period, source, fuel, displacement_l, turbo, drivetrain, seat, battery_kwh, range_km, trim, msrp_manwon, fleet, special

## 사용 팁
- 일반 소비자용만 필요하면 `fleet==false` 필터.
- 트림 정렬은 `msrp_manwon` 오름차순(기본→상위).
- 모델/세대 매칭 키는 `gen_code`(그랜저 GN7) 권장.
