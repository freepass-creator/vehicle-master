# -*- coding: utf-8 -*-
"""교차검증 대상 EV 리스트 추출: 매물>200 제조사의 전기/수소 세부모델."""
import json, urllib.request
t = json.load(urllib.request.urlopen('http://localhost:8777/api/tree', timeout=20))
MIN = 200
targets = []
skipped_small = 0
for m in t['manufacturers']:
    if (m.get('count') or 0) <= MIN:
        skipped_small += 1
        continue
    for g in m.get('models', []):
        for s in g.get('sub_models', []):
            ev_pws = [p for p in s.get('powertrains', []) if (p.get('fuel') in ('전기', '수소'))]
            if not ev_pws:
                continue
            # 현재 엔카 기준 변형들 (구동/인승 조합) + 트림
            variants = sorted({(p.get('drivetrain') or '-', p.get('seat')) for p in ev_pws},
                              key=lambda v: (v[0], v[1] if v[1] is not None else -1))
            trims = sorted({tt['name'] for p in ev_pws for tt in p.get('trims', [])})
            targets.append({
                'manufacturer': m['name'], 'mf_count': m.get('count'),
                'model': g['name'], 'sub_model': s['name'],
                'period': s.get('period'), 'fuel': ev_pws[0].get('fuel'),
                'variants(drive,seat)': [list(v) for v in variants],
                'trims': trims})
out = {'min_listings': MIN, 'manufacturers_skipped(<=200)': skipped_small,
       'ev_target_count': len(targets), 'targets': targets}
json.dump(out, open('data/ev_targets.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('ev targets:', len(targets), '| skipped small mfs:', skipped_small)
