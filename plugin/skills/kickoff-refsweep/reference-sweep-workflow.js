// 레퍼런스 스윕 워크플로 템플릿 — kickoff-refsweep 스킬이 사용 (절차는 같은 폴더 SKILL.md)
// 사용: Workflow({scriptPath: <이 파일>, args: {...}})
// args (필수):
//   projectDef: string — 1부 요약 한 문단 (탐색 에이전트가 관련성을 판단하는 기준)
//   functions:  [{key, name, desc}] — 프로젝트 기능 분해 4~6개
// args (선택):
//   regions:    [{key, name, hint}] — 기본값: 한국/미국/중국/일본 4개
//   known:      [url] — 이미 수집한 노드 (재발견 시 버림)
//   verifyCap:  number — 검증 상한 (기본 30)
//
// 산출: {kept, rejected, unverified, stats} — kept만 대상 프로젝트 docs/references.md에
// 병합하고, 결과 전문은 docs/raw/에 보존한다. rejected는 사유와 함께 남긴다(재검토 방지).

export const meta = {
  name: 'reference-sweep',
  description: '기능×지역 매트릭스 병렬 레퍼런스 탐색 + 검증 (킥오프 레퍼런스 수집 단계)',
  phases: [
    { title: '탐색', detail: '기능×지역 셀별 병렬 검색 — 깊이보다 넓이' },
    { title: '검증', detail: 'URL 중복 제거 후 실재·활성·요약 일치 판정' },
  ],
}

// 하네스가 args를 JSON 문자열로 전달하는 경우 방어 파싱 (실전 킥오프에서 실제 발생)
const A = (typeof args === 'string') ? JSON.parse(args) : args
if (!A || !A.projectDef || !Array.isArray(A.functions) || !A.functions.length) {
  throw new Error('args.projectDef(1부 요약)와 args.functions(기능 분해 배열)는 필수다 — 템플릿 상단 주석 참조')
}

const PROJECT_DEF = A.projectDef
const FUNCTIONS = A.functions
const REGIONS = A.regions || [
  { key: 'KR', name: '한국', hint: '한국어로 검색. 국내 플랫폼 생태계 고유 도구·실전 글. 플랫폼: GitHub, 일반 웹(블로그·브런치), YouTube' },
  { key: 'US', name: '미국/영어권', hint: '영어로 검색. 오픈소스·SaaS·indie hacker 사례·HN 토론. 플랫폼: GitHub, 일반 웹, YouTube' },
  { key: 'CN', name: '중국', hint: '중국어(간체)로 검색. GitHub 중국어 리포, 知乎·juejin·CSDN. bilibili는 웹 검색으로 간접 탐색' },
  { key: 'JP', name: '일본', hint: '일본어로 검색. GitHub, Qiita·note·Zenn, YouTube' },
]
const KNOWN = A.known || []
const VERIFY_CAP = A.verifyCap || 30

const FINDINGS_SCHEMA = {
  type: 'object', required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['name', 'url', 'platform', 'kind', 'summary', 'relevance'],
        properties: {
          name: { type: 'string' },
          url: { type: 'string' },
          platform: { type: 'string', description: 'github|web|youtube|zhihu|qiita|note 등' },
          kind: { type: 'string', enum: ['code', 'tool', 'knowledge', 'video', 'case'] },
          summary: { type: 'string', description: '이것이 무엇인지 1~2문장' },
          relevance: { type: 'string', description: '프로젝트의 어느 기능에 어떻게 참고되는지 1문장' },
          signals: { type: 'string', description: '활성도 신호(스타 수, 최근 업데이트, 조회수 등) 알면 기입' },
        },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object', required: ['exists', 'active', 'keep', 'note'],
  properties: {
    exists: { type: 'boolean', description: 'URL이 실재하고 접근 가능한가' },
    active: { type: 'boolean', description: '살아있는가(최근 업데이트/유지보수/유효한 정보)' },
    keep: { type: 'boolean', description: '레퍼런스로 남길 가치 — 요약이 실물과 다르면 false' },
    note: { type: 'string', description: '판정 근거 + 요약 교정사항 1~2문장' },
  },
}

phase('탐색')
const cells = []
for (const f of FUNCTIONS) for (const r of REGIONS) cells.push({ f, r })

// 전체 결과를 모아 중복 제거해야 하므로 여기만 배리어
const found = await parallel(cells.map(({ f, r }) => () =>
  agent(
    `${PROJECT_DEF}\n\n너는 레퍼런스 탐색 에이전트다. 담당 셀: 기능「${f.name}」× 지역「${r.name}」.\n\n기능 설명: ${f.desc}\n지역 가이드: ${r.hint}\n\n임무: 이 기능에 참고할 수 있는 실존 프로젝트·도구·글·영상·사례를 넓게 수집한다. 아이디어 수집 단계이므로 깊게 읽지 말고 넓게 훑어라.\n\n방법:\n- WebSearch로 해당 지역 언어의 쿼리를 3~6개 변형해 검색 (플랫폼별: "site:github.com ..." 또는 GitHub 키워드, 일반 웹, YouTube/튜토리얼)\n- 필요하면 ToolSearch로 mcp__fetch__fetch, mcp__github__search_repositories, YouTube 검색 도구를 로드해 써도 된다\n- 개별 결과를 깊게 읽지 마라. 검색 결과 스니펫으로 후보를 판단하고 URL만 정확히 확보\n\n수집 기준: 실제 URL이 확인된 것만. 최대 8개, 관련성 높은 순. 광고성 스팸·단순 뉴스 반복은 제외.\n\n최종 출력은 스키마에 맞는 findings 배열이다.`,
    { label: `탐색:${f.key}×${r.key}`, phase: '탐색', schema: FINDINGS_SCHEMA }
  )
))

// 인덱스를 먼저 고정한 뒤 걸러낸다 — filter를 먼저 걸면 셀 하나만 null이어도
// 이후 전 항목의 func/region 라벨이 밀리고, 그 라벨로 도는 기능별 쿼터까지 오염된다
const all = found.flatMap((res, i) => {
  if (!res) return []
  const cell = cells[i]
  return (res.findings || []).map(x => ({ ...x, func: cell.f.key, region: cell.r.key }))
})

const norm = u => String(u || '').toLowerCase().replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/[\/#?]+$/, '')
const seen = new Set(KNOWN.map(norm))
const unique = []
for (const item of all) {
  const k = norm(item.url)
  if (!k || seen.has(k)) continue
  seen.add(k)
  unique.push(item)
}
log(`탐색 완료: 원시 ${all.length}건 → 중복 제거 후 ${unique.length}건`)

phase('검증')
// 코드·도구·사례 우선 검증, 초과분은 미검증으로 보고 (조용한 절단 금지)
// 상한은 기능별 쿼터로 먼저 배분한다 — kind 전역 정렬만으로 자르면 code 후보가 많은
// 기능이 상한을 독식해 다른 기능이 검증 0건이 된다 (실전 실행에서 관측된 기능 기아)
const prio = { code: 0, tool: 1, case: 2, knowledge: 3, video: 4 }
const byKind = (a, b) => (prio[a.kind] ?? 9) - (prio[b.kind] ?? 9)
const quota = Math.max(1, Math.floor(VERIFY_CAP / FUNCTIONS.length))
const groups = {}
for (const item of unique) (groups[item.func] = groups[item.func] || []).push(item)
const toVerify = []
for (const key of Object.keys(groups)) {
  groups[key].sort(byKind)
  toVerify.push(...groups[key].splice(0, quota))   // 기능당 quota건 보장 (splice로 잔여만 groups에 남김)
}
const leftovers = Object.values(groups).flat().sort(byKind)
toVerify.push(...leftovers.slice(0, Math.max(0, VERIFY_CAP - toVerify.length)))
const chosen = new Set(toVerify)
const dropped = unique.filter(x => !chosen.has(x))
if (dropped.length) log(`검증 상한(${VERIFY_CAP}) 초과로 ${dropped.length}건은 미검증 — 결과에 unverified로 포함 (기능별 쿼터 ${quota}건 보장 후 잔여 슬롯 전역 배분)`)

const verified = await parallel(toVerify.map(item => () =>
  agent(
    `너는 레퍼런스 검증 에이전트다. 아래 발견물이 실재하고 쓸만한지 판정하라.\n\n${JSON.stringify(item, null, 2)}\n\n방법: ToolSearch로 mcp__fetch__fetch를 로드해 URL을 직접 열어본다(github.com이면 raw README나 GitHub API도 가능). 접근 불가면 WebSearch로 존재 여부 교차 확인.\n판정: exists(접근 가능한가), active(GitHub이면 최근 1년 내 커밋, 글이면 정보 최신성 — updated_at 메타데이터를 커밋으로 오독하지 말 것), keep(참고 가치 — 요약이 실물과 다르면 false), note(근거 1~2문장 + 스타 수·최종 push 같은 신호).\n깊게 읽지 마라 — 실재·활성·요약 일치만 확인한다.`,
    { label: `검증:${(item.name || '').slice(0, 24)}`, phase: '검증', schema: VERDICT_SCHEMA }
  ).then(v => ({ ...item, verdict: v }))
))

const done = verified.filter(Boolean)
const kept = done.filter(x => x.verdict && x.verdict.keep)
const rejected = done.filter(x => x.verdict && !x.verdict.keep)
// 검증 에이전트가 죽어 verdict가 없는 항목은 keep/drop 어디에도 안 들어간다 —
// 조용히 증발시키지 말고 미검증으로 편입한다 ("조용한 절단 금지" 원칙)
const lost = done.filter(x => !x.verdict)
const unverified = dropped.concat(lost)
if (lost.length) log(`검증 실패로 판정 없음 ${lost.length}건 — 미검증에 편입`)
log(`검증 완료: keep ${kept.length} / drop ${rejected.length} / 미검증 ${unverified.length}`)

return {
  kept,
  rejected: rejected.map(x => ({ name: x.name, url: x.url, note: x.verdict.note })),
  unverified,
  stats: { raw: all.length, unique: unique.length, kept: kept.length, unverified: unverified.length },
}
