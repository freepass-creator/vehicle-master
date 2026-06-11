export const meta = {
  name: 'ev-battery-crosscheck',
  description: 'EV 세부모델별 배터리 용량(kWh)을 나무위키/위키백과로 교차검증해 규격화',
  phases: [
    { title: 'Research', detail: 'EV별 배터리 kWh 교차검증 (나무위키+위키백과)' },
    { title: 'Synthesize', detail: '결과 집계 → ev_battery_specs.json' },
  ],
}

// args = [{manufacturer, model, sub_model, period, fuel, variants, trims}, ...]
const targets = Array.isArray(args) ? args : []
log(`EV 교차검증 대상 ${targets.length}건`)

const BATTERY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['sub_model', 'batteries', 'sources', 'confidence'],
  properties: {
    manufacturer: { type: 'string' },
    model: { type: 'string' },
    sub_model: { type: 'string' },
    batteries: {
      type: 'array',
      description: '이 세부모델이 제공한 배터리 옵션들 (스탠다드/롱레인지 등 각각)',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['kwh'],
        properties: {
          kwh: { type: 'number', description: '총 배터리 용량 kWh (공칭). 모르면 생략 말고 usable 만이라도' },
          usable_kwh: { type: 'number', description: '사용가능 용량 kWh (알면)' },
          label: { type: 'string', description: '스탠다드/롱레인지/숏레인지 등 구분 명칭' },
          drivetrain: { type: 'string', description: '2WD/4WD/AWD 등 해당 구동 (특정되면)' },
          range_km: { type: 'number', description: '공인 1회충전 주행거리 km (알면)' },
          applies_to_trims: { type: 'array', items: { type: 'string' }, description: '해당 트림 힌트 (알면)' },
        },
      },
    },
    sources: { type: 'array', items: { type: 'string' }, description: '출처 URL (나무위키/위키백과/제조사 등)' },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    notes: { type: 'string', description: '불확실성·주의사항 (택시형, 특장, 단종 등)' },
  },
}

function prompt(t) {
  const vars = (t['variants(drive,seat)'] || t.variants || []).map(v => `${v[0]}/${v[1]}인승`).join(', ')
  return [
    `한국에 시판된 전기차의 **배터리 용량(kWh)** 을 교차검증해줘.`,
    `차량: ${t.manufacturer} ${t.model} — 세부모델 "${t.sub_model}" (생산 ${t.period || '?'})`,
    `엔카 기준 변형: ${vars || '단일'} / 트림: ${(t.trims || []).join(', ')}`,
    ``,
    `요구사항:`,
    `1) 나무위키와 위키백과(가능하면 제조사/환경부 공인 출처)를 **둘 이상** 찾아 교차검증.`,
    `2) 배터리 옵션이 여러 개면(예: 스탠다드/롱레인지, 58 vs 77.4kWh) **각각** kWh 와 어떤 구동/트림에 해당하는지.`,
    `3) 알면 사용가능 용량(usable kWh), 공인 1회충전 주행거리(km)도.`,
    `4) 출처 URL 명시. 자료가 상충하거나 못 찾으면 confidence=low 로 솔직히.`,
    `세대/연식이 헷갈리면 생산기간(${t.period})으로 구분. 페이스리프트 배터리 증설(예: 아이오닉5 58/72.6 → 63/84) 주의.`,
  ].join('\n')
}

phase('Research')
const results = await parallel(targets.map((t, i) => () =>
  agent(prompt(t), {
    label: `${t.manufacturer}/${t.model}/${t.sub_model}`.slice(0, 48),
    phase: 'Research',
    schema: BATTERY_SCHEMA,
  }).then(r => r ? { ...t, result: r } : null)
))

phase('Synthesize')
const ok = results.filter(Boolean)
const low = ok.filter(r => r.result.confidence === 'low')
log(`완료 ${ok.length}/${targets.length} · 저신뢰 ${low.length}건`)

return {
  count: ok.length,
  low_confidence: low.map(r => `${r.manufacturer} ${r.sub_model}`),
  specs: ok.map(r => ({
    manufacturer: r.manufacturer, model: r.model, sub_model: r.sub_model,
    period: r.period, ...r.result,
  })),
}
