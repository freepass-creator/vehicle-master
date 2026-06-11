export const meta = {
  name: 'trim-rank-crosscheck',
  description: '모델별 트림 서열(기본→최상위)을 신차가(MSRP) 기준으로 규격화',
  phases: [
    { title: 'Rank', detail: '모델별 트림 서열 교차검증 (나무위키/제조사 가격표)' },
    { title: 'Synthesize', detail: '결과 집계 → trim_rank_results.json' },
  ],
}

// args = [{manufacturer, model, trims:[str]}, ...]
const targets = Array.isArray(args) ? args : []
log(`트림 서열 대상 모델 ${targets.length}개`)

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['model', 'ranked_trims', 'confidence'],
  properties: {
    manufacturer: { type: 'string' },
    model: { type: 'string' },
    ranked_trims: {
      type: 'array',
      description: '우리 트림을 기본(싼)→최상위(비싼) 순으로. rank 1=기본. 우리 트림명 그대로.',
      items: {
        type: 'object', additionalProperties: false, required: ['name', 'rank'],
        properties: {
          name: { type: 'string', description: '우리가 준 트림명 그대로' },
          rank: { type: 'integer', description: '1=기본(최저가), 클수록 상위(고가)' },
          msrp_manwon: { type: 'number', description: '대표 신차가(만원). 알면. 세대 다양하면 최신 기준' },
        },
      },
    },
    sources: { type: 'array', items: { type: 'string' } },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    notes: { type: 'string' },
  },
}

function prompt(t) {
  return [
    `자동차 모델의 **트림(등급) 서열**을 기본(가장 싼)→최상위(가장 비싼) 순으로 매겨줘.`,
    `제조사: ${t.manufacturer} / 모델: ${t.model}`,
    `우리 트림 목록(이 이름들 그대로 rank 매겨서 반환):`,
    t.trims.map(x => `  - ${x}`).join('\n'),
    ``,
    `기준: **신차가(MSRP)**. 나무위키 또는 제조사 가격표로 등급 위계 판단.`,
    `- rank=1 이 기본(최저가), 숫자 클수록 상위(고가). 동급이면 같은 rank 허용.`,
    `- 가능하면 msrp_manwon(대표 신차가, 만원)도. 세대가 여러개면 최신 세대 기준 또는 일반적 위계.`,
    `- 특장/택시/영업용 등 특수트림은 일반 위계 밖이면 rank 를 낮게(기본 근처) 두고 note 에.`,
    `- 우리 트림명을 **그대로** 사용(임의 변경 금지). 못 찾는 트림은 confidence 낮추고 합리적 추정.`,
    `한국시장 일반 위계 예: (스마트/모던/트렌디) < 프리미엄 < 인스퍼레이션/익스클루시브 < 캘리그래피/시그니처/그래비티/N.`,
  ].join('\n')
}

phase('Rank')
const results = await parallel(targets.map((t) => () =>
  agent(prompt(t), { label: `${t.manufacturer}/${t.model}`.slice(0, 40), phase: 'Rank', schema: SCHEMA })
    .then(r => r ? { manufacturer: t.manufacturer, model: t.model, ...r } : null)
))

phase('Synthesize')
const ok = results.filter(Boolean)
log(`완료 ${ok.length}/${targets.length}`)
return { count: ok.length, results: ok }
