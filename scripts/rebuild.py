# -*- coding: utf-8 -*-
"""
차종마스터 SSOT 재빌드 파이프라인 (체크포인트 → vehicle-tree.json).
  1) merge            : 제조사 체크포인트 병합 + EV배기량제거/트림정규화 + 정렬
  2) apply_ev_battery : EV 배터리 교차검증 결과 규격화 적용
  3) unify_variants   : 하이브리드/전기 세부모델 → 본형 세대 파워트레인으로 병합
재크롤 없이 가공만 다시 할 때 사용. usage: python rebuild.py
"""
import subprocess, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = ["crawl_encar.py", "apply_ev_battery.py", "unify_variants.py",
         "apply_gen_codes.py", "apply_trim_rank.py", "apply_welrix.py", "apply_trim_class.py", "apply_supplemental.py"]
ARGS = {"crawl_encar.py": ["merge"]}
for s in STEPS:
    cmd = [sys.executable, os.path.join(HERE, s)] + ARGS.get(s, [])
    print(">>>", s, *ARGS.get(s, []))
    if subprocess.run(cmd).returncode != 0:
        print("실패:", s); sys.exit(1)
print("재빌드 완료 → data/vehicle-tree.json")
