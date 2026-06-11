export const meta = {
  name: 'trim-classify-ctx',
  description: '맥락(세대코드+연료)별 트림 분류 — 같은 트림명도 맥락 따라 일반/영업용 구분',
  phases: [
    { title: 'Classify', detail: '모델별 맥락별 트림 분류' },
    { title: 'Synthesize', detail: '결과 집계 → trim_class_results.json' },
  ],
}

// args = [{manufacturer, model, contexts:[{ctx, trims:[str]}]}, ...]
const targets = Array.isArray(args) ? args : []
log(`맥락 트림 분류 대상 모델 ${targets.length}개`)

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['model', 'contexts', 'confidence'],
  properties: {
    manufacturer: { type: 'string' },
    model: { type: 'string' },
    contexts: {
      type: 'array',
      description: '입력 맥락마다, 그 맥락의 트림들을 분류 (ctx 문자열 그대로 반환)',
      items: {
        type: 'object', additionalProperties: false, required: ['ctx', 'trims'],
        properties: {
          ctx: { type: 'string', description: '입력 ctx 그대로' },
          trims: {
            type: 'array',
            items: {
              type: 'object', additionalProperties: false, required: ['name', 'category'],
              properties: {
                name: { type: 'string' },
                category: { type: 'string', enum: ['consumer', 'fleet', 'special', 'error'] },
              },
            },
          },
        },
      },
    },
    sources: { type: 'array', items: { type: 'string' } },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
  },
}

function prompt(t) {
  const body = t.contexts.map(c =>
    `  [${c.ctx}]\n` + c.trims.map(x => `     - ${x}`).join('\n')
  ).join('\n')
  return [
    `자동차 모델의 트림을 **맥락(세대코드+연료)별로** 분류해줘. 같은 트림명도 맥락 따라 성격이 다를 수 있어.`,
    `제조사: ${t.manufacturer} / 모델: ${t.model}`,
    `맥락별 트림 (각 [세대코드 연료] 안의 트림을 분류, ctx 문자열 그대로 반환):`,
    body,
    ``,
    `분류 (제조사 가격표·나무위키 근거):`,
    `- consumer : 그 맥락에서 일반 소비자 정규 판매 트림`,
    `- fleet    : 택시/렌터카/영업용/장애인/특장 전용`,
    `- special  : 한정판·특별 에디션`,
    `- error    : 그 맥락에 실제로 없는, 잘못 섞인 트림`,
    ``,
    `**맥락 판단이 핵심**:`,
    `- 같은 '고급형'도 [GN7 LPG](현행 LPG)면 택시 fleet 이고, [XG 가솔린](구형)이면 consumer 정규등급.`,
    `- LPG 연료 맥락은 영업용(택시/렌트) 트림이 섞이기 쉬움 — 일반 LPG 소비자 트림(프리미엄/익스클루시브 등)과 택시 전용(고급형 등)을 구분.`,
    `- 트림명 그대로 반환. 불확실하면 confidence 낮추고 합리적 추정.`,
  ].join('\n')
}

phase('Classify')
const results = await parallel(targets.map((t) => () =>
  agent(prompt(t), { label: `${t.manufacturer}/${t.model}`.slice(0, 40), phase: 'Classify', schema: SCHEMA })
    .then(r => r ? { manufacturer: t.manufacturer, model: t.model, ...r } : null)
))

phase('Synthesize')
const ok = results.filter(Boolean)
const counts = { consumer: 0, fleet: 0, special: 0, error: 0 }
for (const r of ok) for (const c of (r.contexts || [])) for (const tr of (c.trims || [])) counts[tr.category] = (counts[tr.category] || 0) + 1
log(`완료 ${ok.length}/${targets.length} · ${JSON.stringify(counts)}`)
return { count: ok.length, category_counts: counts, results: ok }
