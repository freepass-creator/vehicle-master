# 차종마스터 (vehicle-master)

제조사 · 모델 · 세부모델 · 파워트레인 · 세부트림 **5단계 차종 분류 SSOT**.
다른 ERP가 참조해 가는 단일 진실 소스. 엔카 + 웰릭스(신차) + 나무위키/위키백과 교차검증으로 규격화.

## 가져다 쓰기 (다른 시스템)

`dist/` 의 산출물을 그대로 사용:

| 파일 | 용도 |
|---|---|
| `dist/manifest.json` | 버전·건수·파일목록 (먼저 읽기) |
| `dist/vehicle-master.json` | 전체 5단계 트리 (각 노드 안정 `id`) |
| `dist/vehicle-master.flat.json` | 트림 1행 denormalized (DB/매칭 권장) |
| `dist/vehicle-master.flat.csv` | 엑셀/DB import (utf-8-sig) |
| `dist/codes.json` | 제조사/모델/세대 코드 룩업 |
| `dist/identity-map.json` | 지속 UID 레지스트리 + semantic key alias |
| `dist/provenance.json` | UID별 출처·원본명·부모 관계 추적 |
| `dist/SCHEMA.md` | 스키마 문서 |

- **유일 참조키는 `uid`**: 신규 ERP foreign key는 반드시 uid 사용.
- **기존 `id`는 호환 표시키**: 현재 데이터에서도 중복이 존재하므로 유일키로 사용하지 않음.
- **UID 기준은 semantic identity key**: 세부모델 source code, 파워트레인 인승, 트림 raw 원본명까지 포함해 실제 개체를 구분.
- semantic identity key 변경은 `data/id-aliases.json`에 새 key → 이전 key를 선언해 UID 연속성을 보존.
- **트림**: `msrp_manwon`(신차가/만원) 오름차순 = 기본→상위. `fleet:true`(택시/렌트/특장)는 일반 표시 시 제외 권장.
- **세부모델명**: 섀시코드 통일 (`그랜저 GN7`, `카니발 KA4`). 매칭은 `gen_code` 권장.

## 규모 (v2026-06-11)
제조사 75 · 모델 1,119 · 세부모델 1,803 · 파워트레인 2,940 · 트림 6,320

## 로컬 뷰어 / API
```
python app.py        # http://localhost:8777  (5단계 드릴다운 뷰어, /api/tree CORS)
```

## 재빌드 (재크롤 없이 가공만, 멱등)
```
python scripts/rebuild.py   # merge→EV배터리→하이브리드병합→코드명명→트림서열→신차반영→트림분류
python scripts/export.py 2026-06-11   # dist/ 배포물 생성 + identity/provenance 교차검증
# 필요 시 검증만 재실행:
python scripts/validate_identity_export.py
```

## 데이터 출처·정규화
- **엔카**: 5단계 골격 + 매물 기반 변형 (`crawl_encar.py`)
- **웰릭스 신차견적기**: 현행 신차/페이스리프트 + 신차가 (`apply_welrix.py`)
- **나무위키/위키백과 교차검증**: 세대코드·생산기간·배터리(kWh)·트림서열·트림분류 (멀티에이전트 워크플로우)

데이터 자체는 엔카/웰릭스/나무위키 등 공개 출처 기반의 차량 분류 정보입니다.
