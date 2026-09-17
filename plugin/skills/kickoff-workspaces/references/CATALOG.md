# 스킬 카탈로그

검토를 마친 스킬의 단일 출처. 설치 명령·적용 범위·사용 시점은 여기서만 관리한다.
새 스킬을 검토하면 결과를 여기에 추가한다 — **스킵한 것도 사유와 함께** (재검토 방지).

## 설치 원칙

- 원본 저장소에서 `npx skills add <owner/repo@skill>` 로 설치. `--global` 붙이면 글로벌(`~/.claude/skills`)
- 재패키징 설치 도구(weft 등) 금지 — 원본과 내용이 달라질 수 있는 공급망 리스크
- 절차: 검토(SKILL.md 원문 확인) → 사용자와 논의 → 동의 → 설치
- **로컬 우선**: 킥오프의 산출물은 프로젝트별 로컬 하네스(`.claude/skills`) 정의다.
  신규 스킬은 기본적으로 로컬 후보로 분류하고, 글로벌 승격은 보수적으로 —
  대부분의 프로젝트에서 쓰이고, 지침형(스크립트 실행 없음) 위주의 저리스크만
- 같은 영역에 공식 스킬(프레임워크·벤더 자체 제작)이 있으면 개인 큐레이션 모음보다 공식 우선

## 글로벌 권장 — 지침형 저리스크 (대부분 프로젝트에서 사용)

> 이 문서는 **설치 상태를 주장하지 않는다** — 문서의 상태 주장은 반드시 낡는다.
> 설치 여부는 실물로 확인한다: `Get-ChildItem ~/.claude/skills -Directory | Select -Expand Name`

| 스킬 | 설치 명령 (`npx skills add ... --global`) | 언제 쓰나 | 검토 |
|------|------|------|------|
| ponytail | `dietrichgebert/ponytail@ponytail` | 모든 코딩 작업 — 과잉설계 방지 사다리 자동 적용. `/ponytail lite\|full\|ultra` 강도 조절, "stop ponytail"로 해제 | 2026-08-09 ✅ 순수 지침형, 31K 설치 |
| ponytail-review | `dietrichgebert/ponytail@ponytail-review` | "지울 거 찾아줘", 과잉설계 전용 리뷰 | 2026-08-09 ✅ |
| obsidian-markdown | `kepano/obsidian-skills@obsidian-markdown` | Obsidian 볼트(.md) 작업 — wikilink·callout·frontmatter 문법 | 2026-08-09 ✅ 공식(Obsidian CEO), 지침형 |
| obsidian-bases | `kepano/obsidian-skills@obsidian-bases` | Bases(.base) 데이터베이스 뷰 작성 | 2026-08-09 ✅ |
| web-design-guidelines | `vercel-labs/agent-skills@web-design-guidelines` | "UI 리뷰해줘" — 검수 전용, 코드 안 고침. 규칙은 Vercel 저장소에서 실시간 fetch | 2026-08-09 ✅ 프레임워크 무관 |

자작 스킬(grill 계열·screen-plan·llmwiki·킥오프 체인)은 아래 "자작 스킬" 표에 등재.
스킬 검색은 스킬이 아니라 `npx skills find <query>`로 한다 — 설치(`npx skills add`)는 항상 사용자 동의 후.

## 보류 — 필요해지는 시점에 로컬 설치

### 웹 프론트

| 스킬 | 설치 명령 | 쓰는 시점 | 비고 |
|------|------|------|------|
| react-best-practices | `vercel-labs/agent-skills@vercel-react-best-practices` | React/Next 프로젝트 작업 시 | 617K 설치, 품질 최상급 |
| composition-patterns | `vercel-labs/agent-skills@vercel-composition-patterns` | React 컴포넌트 설계 시 | 위와 세트 |
| landing-page | `mengto/skills@landing-page` | 랜딩·홍보 페이지 제작 시 | 전환율 중심 구조+카피 가이드 |
| MengTo web-design 개별 | `mengto/skills@<이름>` | 비주얼 있는 사이트 제작 시 — 스타일·효과 레시피 85종 (gsap, threejs, beautiful-shadows 등) | 127개 통설치 금지, 필요한 것만. 다수가 Tailwind 전제 |
| ui-ux-pro-max | `nextlevelbuilder/ui-ux-pro-max-skill@ui-ux-pro-max` | 디자인 시스템·로고·배너 본격 제작 시 | 무거움(스크립트 59개), 로고 생성은 Gemini API 필요, shadcn/Tailwind 지향 |

### 백엔드 · 데이터

| 스킬 | 설치 명령 | 쓰는 시점 | 비고 |
|------|------|------|------|
| supabase | `supabase/agent-skills@supabase` | Supabase 쓰는 프로젝트 — DB·Auth·Edge Functions·Realtime·Storage 전반 | 2026-08-09 ✅ 공식, 지침형, 207.6K |
| supabase-postgres-best-practices | `supabase/agent-skills@supabase-postgres-best-practices` | Postgres 쿼리·인덱스·RLS 최적화 시 | 2026-08-09 ✅ 공식, 지침형, 336.8K |
| fastapi | `fastapi/fastapi@fastapi` | FastAPI 서버 개발 시 | 2026-08-09 ✅ FastAPI 공식(저장소 101K★), 지침형. uv·Ruff·SQLModel 권장 포함 |
| jupyter-notebook | `openai/skills@jupyter-notebook` | 데이터 분석·실험 노트북 작성 시 | 2026-08-09 ✅ OpenAI 공식, 지침형+템플릿 |

### 모바일

| 스킬 | 설치 명령 | 쓰는 시점 | 비고 |
|------|------|------|------|
| Expo 개별 | `expo/skills@<이름>` | Expo/React Native 앱 — building-native-ui, expo-dev-client, native-data-fetching, expo-deployment 등 필요한 것만 | 2026-08-09 ✅ Expo 공식, 개별 40~59K. 통설치 말고 선별 |
| Flutter 개별 | `flutter/skills@<이름>` | Flutter 앱 — architecture-best-practices, responsive-layout, widget-test 등 필요한 것만 | 2026-08-09 ✅ Flutter(Google) 공식, 개별 20K+. 선별 설치 |
| react-native-best-practices | `callstackincubator/agent-skills@react-native-best-practices` | RN 성능·설계 (Expo 안 쓰는 순수 RN 포함) | 2026-08-09 ✅ Callstack(RN 코어 기여사), 22.1K |

### 안드로이드 온디바이스 에이전트

| 스킬 | 설치 명령 | 쓰는 시점 | 비고 |
|------|------|------|------|
| a11y-bridge | `4ier/agent-skills@a11y-bridge` | 온디바이스 Accessibility 브리지 자체 구현 참고 | 검토 중 보류(2026-08-15) — 네이티브 진입 + 실기기 연결 단계에서 SKILL.md 재검토 후 결정 |
| termux-api | `4ier/agent-skills@termux-api` | Termux에서 폰 능력 접근(온디바이스 LLM 호스팅) | 위와 동일 조건부 보류 |

### 데스크톱 · 브라우저 · 스크래핑

| 스킬 | 설치 명령 | 쓰는 시점 | 비고 |
|------|------|------|------|
| tauri-v2 | `nodnarbnitram/claude-code-extensions@tauri-v2` | Tauri v2 데스크톱 앱 (Electron 경량 대안) | 2026-08-09 ✅ 지침형, 6.7K, 보안감사 통과. 개인 저장소(★15)라 설치 전 원문 재확인 |
| chrome-extensions | `googlechrome/modern-web-guidance@chrome-extensions` | 크롬 확장(Manifest V3) 개발·스토어 배포 | 2026-08-09 ✅ Google Chrome 팀 공식, 지침형 |
| firecrawl 계열 | `firecrawl/cli@firecrawl-scrape` (+interact/browser) | 대량 웹 스크래핑·크롤링 | 2026-08-09 ✅ 78.2K. Firecrawl CLI+API 키 전제(유료 쿼터) — 소규모는 기본 WebFetch로 충분 |
| playwright-test-data-isolation | `stablyai/agent-skills@playwright-test-data-isolation` | Playwright E2E 테스트가 공유 DB·계정을 쓸 때 — 데이터 격리 전략(fixture·네임스페이스·정리) | 2026-08-09 ✅ 지침형, Stably 비의존 명시, 안티패턴·체크리스트 포함 수준급. 단 설치 수 미미(저장소 ★14) |

### 네이버 API 연동

| 스킬/MCP | 설치 명령 | 쓰는 시점 | 비고 |
|------|------|------|------|
| naver-search-mcp (MCP) | `isnow890/naver-search-mcp` (.mcp.json 등록) | 네이버 검색 데이터로 로직을 설계·탐색할 때 (네이버 오픈API 키 확보 후) | 검토 후 조건부 보류(2026-08-16) — 런타임 파이프라인은 API 직접 호출이라 MCP 불필요, 개발 보조로만 가치. ★81, 활성 |

### 문서 · Obsidian

| 스킬 | 설치 명령 | 쓰는 시점 | 비고 |
|------|------|------|------|
| anthropics 문서 스킬 | `anthropics/skills` 저장소의 docx/xlsx/pptx | Word/Excel/PPT 파일 산출물 필요 시 | 공식, source-available |
| obsidian-cli / defuddle / json-canvas | `kepano/obsidian-skills@<이름>` | 해당 도구(Obsidian CLI, defuddle) 쓰게 될 때 | 별도 CLI 설치 필요 |

## 자작 스킬 — 직접 만들어 검증된 것

레지스트리에 없어서 직접 만든 스킬 중, 다른 프로젝트에서도 쓸 만한 것을 기록한다
(제작·재사용 기준은 [HARNESS.md](HARNESS.md) "직접 제작").

| 스킬 | 원본 위치 | 언제 쓰나 | 만든 계기 |
|------|------|------|------|
| grill 계열 3종 (grilling·grill-me·grill-with-docs) | `~/.claude/skills/grill*` | 계획·설계를 질문으로 두드리는 심화 인터뷰 — "그릴해줘"·"검증해줘"·"허점 찾아줘". 킥오프 마무리에서 제안. grill-with-docs는 ADR·용어집 기록 겸함 | 카탈로그 규율 이전 자작 — 2026-08-14 소급 등재 |
| screen-plan | `~/.claude/skills/screen-plan` (글로벌) | 흑백 HTML 와이어프레임 화면 기획 — "화면 기획"·"와이어"·화면 ID(O1/M1). 웹 대시보드 프로필의 기획 단계 | 카탈로그 규율 이전 자작 — 2026-08-14 소급 등재 |
| llmwiki | `kickoff_pack/skills/llmwiki` (팩 동봉, junction 설치) | 킥오프 직후 init(위키+CLAUDE.md 스키마 10줄+SessionStart 훅 설치), 주기 lint. 기록은 작업 매듭에서(CLAUDE.md 규칙), 보류 안건 재부상은 설치된 훅이 담당 | 2026-08-14 카파시 [LLM 위키 gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)를 스킬화, 2026-08-20 팩에 편입. 매 턴 강제(Stop 훅)는 작업 품질 저하로 2026-08-19 폐기 |
| 킥오프 체인 4종 (kickoff-interview·kickoff-refsweep·kickoff-usecases·kickoff-harness) | `kickoff_pack/skills/*` (원본·git 이력) — `~/.claude/skills`에 **junction** 설치: `New-Item -ItemType Junction -Path ~\.claude\skills\<이름> -Target <kickoff_pack>\skills\<이름>` | 새 프로젝트 킥오프 — "킥오프 상담하자"가 interview를 발동, 이후 각 스킬이 다음을 제안. 2부부터 대상 저장소에서 돌므로 글로벌 필수 | 2026-08-19 단일 PLAYBOOK 분할 — 대상 repo에서 절차가 안 읽히고 긴 세션에서 흐려지는 문제. junction이라 npx 설치 절차 비대상, 편집은 kickoff_pack에서만 |

## 스킵 — 재검토 불필요 (2026-08-09 검토)

| 대상 | 스킵 사유 |
|------|------|
| weft (`@weft-ai/weft`) | 트윗 작성자 본인의 재패키징 설치 도구. v0.1.0, 스타 8개. 원본 직접 설치로 대체 |
| planning-with-files | Claude Code 기본 플랜 모드·태스크와 중복, 훅 게이트가 단순 작업에 마찰 |
| gsd-core | grill 계열 + domain-modeling + 플랜 모드와 역할 정면 중복 |
| mattpocock-skills | TypeScript 엔지니어용 ~35개, Python 위주 환경에 과잉 |
| gstack | 슬래시 커맨드 35개로 무겁고 code-review/verify/grill과 중복 |
| andrej-karpathy-skills | Karpathy 본인 아님(이름 차용), 철학이 ponytail과 겹침 |
| vercel deploy 계열 (deploy-to-vercel 등) | Vercel 배포 안 씀 |
| MengTo codex 카테고리 | "Meng처럼 X에 글쓰기" 등 작성자 개인용 위주 |
| 스타터 키트류 (claude-code-mastery-project-starter-kit 등) | 커맨드·훅·스킬 수십 개 통설치 방식 — 선별 설치 원칙과 정면 충돌. 카탈로그로 대체 |
| skill-recommender류 (curate-a-team-library 등) | `npx skills find` 절차로 충분, 나머지는 특정 프레임워크 종속 |
| obra/superpowers | 방법론 통설치 프레임워크("강제 워크플로" 13종) — grill 계열·플랜 모드·ponytail과 역할 중복 |
| wshobson/agents@uv-package-manager | uv 지침은 상위 CLAUDE.md 규칙으로 충분. 보안 감사 혼합(Trust Hub Fail) |
| Telegram 봇 스킬 전반 | 검색 상위가 역할극형(sickn33 3.2K)·n8n 템플릿형(claude-office-skills 4.8K)뿐 — 라이브러리 구체 지침 빈약, 기본 지식으로 충분 |
| pytest 전용 스킬 | 쓸만한 게 없음 — 상위가 Copilot용 모음(github/awesome-copilot). 기본 지식 + fastapi 공식 스킬로 충분 |
| Electron 스킬 | 전부 설치 수 수백 이하 소규모 개인 저장소 — 데스크톱은 tauri-v2로, Electron 필요해지면 재검색 |
| 개인 큐레이션 대형 모음 (sickn33/antigravity, mindrally/skills, wshobson/agents 등) | 각 영역에 공식 스킬 존재 — 공식 우선 원칙. 개별 항목이 꼭 필요하면 그때 SKILL.md 검토 |
| manikosto/claude-code-python-stack | npx 미지원 수동 복사 + 스킬 20개 통설치 방식 — fastapi 공식 스킬로 대체 |
| stablyai/agent-skills 나머지 5종 (sdk-setup/sdk-rules/cli/verify/github-actions-setup) | 전부 Stably 자사 서비스 전용(API 키·CLI 전제) — Stably 미사용. github-actions-setup도 이름과 달리 Stably 테스트 연동 전용. 예외로 playwright-test-data-isolation만 보류 채택 |
| midscene (`web-infra-dev/midscene`) | 클라우드 비전 API 기반 UI 자동화 — "온디바이스 우선" 방침의 프로젝트와 정면 충돌(2026-08-15 검토). 폰 조작은 mobile-mcp/uiautomator2로 충분 |
| droid-tings 계열 (안드로이드 대형 모음) | 500+ 범용 스킬 통설치형 — 선별 설치 원칙과 충돌. 필요 항목 생기면 개별 SKILL.md 검토(2026-08-15 검토) |
