export const meta = {
  name: 'model-verify-crosscheck',
  description: '모델 단위 전역 교차검증: 세대코드·생산기간·파워트레인·트림을 나무위키/위키백과로 규격화',
  phases: [
    { title: 'Verify', detail: '모델별 전 세대 교차검증 (나무위키+위키백과)' },
    { title: 'Synthesize', detail: '결과 집계 → model_verify_report.json' },
  ],
}

// args = [{manufacturer, model, eng, count, sub_models:[{sub_model, period, powertrains:[str], trims:[str]}]}, ...]
const targets = Array.isArray(args) ? args : []
log(`전역 검증 대상 모델 ${targets.length}개`)

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['model', 'confidence'],
  properties: {
    manufacturer: { type: 'string' },
    model: { type: 'string' },
    generations: {
      type: 'array',
      description: '우리 세부모델별 세대코드·생산기간 검증 (우리 sub_model 명에 1:1 대응)',
      items: {
        type: 'object', additionalProperties: false, required: ['sub_model', 'verdict'],
        properties: {
          sub_model: { type: 'string', description: '우리 데이터의 세부모델명 그대로' },
          gen_code: { type: 'string', description: '세대코드(CN7/GN7/DN8 등). 없으면 빈 문자열' },
          production_period: { type: 'string', description: '실제 생산기간 yy~yy / yy~현재' },
          verdict: { type: 'string', enum: ['일치', '생산기간불일치', '세대코드추가', '명칭의심'] },
          note: { type: 'string' },
        },
      },
    },
    powertrain_findings: {
      type: 'array',
      description: '파워트레인(연료/배기량/구동/터보) 오류·누락만. 정확하면 비움',
      items: {
        type: 'object', additionalProperties: false, required: ['sub_model', 'severity', 'detail'],
        properties: {
          sub_model: { type: 'string' },
          severity: { type: 'string', enum: ['오류', '누락', '경미'] },
          detail: { type: 'string', description: '예: "엔카 가솔린2.0인데 실제 1.6터보", "디젤 2.2 4WD 누락"' },
        },
      },
    },
    trim_std: {
      type: 'array',
      description: '트림 표준명 교정 (바뀌는 것만). 오타·약어·비표준 → 공식 표기',
      items: {
        type: 'object', additionalProperties: false, required: ['raw', 'standard'],
        properties: { raw: { type: 'string' }, standard: { type: 'string' } },
      },
    },
    sources: { type: 'array', items: { type: 'string' } },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    notes: { type: 'string' },
  },
}

function prompt(t) {
  const ours = t.sub_models.map(s =>
    `  - "${s.sub_model}" (생산 ${s.period || '?'}) | 파워트레인: ${(s.powertrains || []).join(' / ') || '미상'} | 트림: ${(s.trims || []).join(', ') || '-'}`
  ).join('\n')
  return [
    `자동차 차종마스터의 한 모델 데이터를 **나무위키와 위키백과(및 공신력 출처)로 교차검증**해줘.`,
    `제조사: ${t.manufacturer} / 모델: ${t.model}${t.eng ? ' (' + t.eng + ')' : ''}`,
    `우리(엔카기반) 세부모델 목록:`,
    ours,
    ``,
    `검증·규격화 항목:`,
    `1) [세대코드·생산기간] 각 세부모델의 세대코드(예: 그랜저=GN7/IG/HG, 쏘렌토=MQ4 등)와 실제 생산기간을 확인. 우리 생산기간이 틀리면 verdict로 표시.`,
    `2) [파워트레인 정확성] 연료/배기량/구동/터보 조합이 실제 시판 사양과 맞는지. **틀리거나 빠진 것만** powertrain_findings 에. 정확하면 비워.`,
    `3) [트림 표준명] 트림 등급명이 오타·약어·비표준이면 공식 표기로 교정해 trim_std 에 (raw→standard). 이미 정확하면 비워.`,
    ``,
    `규칙: 세부모델명(sub_model)은 우리 표기 그대로 써서 매칭. 나무위키+위키백과 **둘 이상** 교차확인. 출처 URL 명시. 불확실하면 confidence 낮춤. 추측 금지, 못 찾으면 note 에 사유.`,
  ].join('\n')
}

phase('Verify')
const results = await parallel(targets.map((t) => () =>
  agent(prompt(t), {
    label: `${t.manufacturer}/${t.model}`.slice(0, 40),
    phase: 'Verify',
    schema: SCHEMA,
  }).then(r => r ? { manufacturer: t.manufacturer, model: t.model, ...r } : null)
))

phase('Synthesize')
const ok = results.filter(Boolean)
const issues = ok.filter(r =>
  (r.powertrain_findings || []).length || (r.trim_std || []).length ||
  (r.generations || []).some(g => g.verdict !== '일치'))
log(`검증 ${ok.length}/${targets.length} · 이슈있는 모델 ${issues.length}`)

return {
  count: ok.length,
  models_with_issues: issues.length,
  results: ok,
}
