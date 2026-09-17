# 하네스 가이드 — MCP · 훅 · 설정

스킬 밖 하네스 요소의 단일 출처. 스킬은 [CATALOG.md](CATALOG.md), 유형별 프로필은 [SKILL.md](SKILL.md).

## 도구 선택 기준 — 스킬 vs 훅 vs 서브에이전트 vs CLAUDE.md

무엇으로 만들지부터 정한다 (출처: [공식 가이드](https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more)):

| 원하는 것 | 수단 | 위치 |
|------|------|------|
| 절차형 워크플로 (배포 절차, 리뷰 체크리스트) | 스킬 | `.claude/skills/` |
| **100% 강제**되어야 하는 자동화 (포맷터, 금지 명령 차단) | 훅 | `.claude/settings.json` |
| 컨텍스트를 오염시키는 대형 작업 격리 (감사, 대량 탐색) | 서브에이전트 | `.claude/agents/` |
| 모든 세션에 필요한 지속 문맥 (규칙, 구조, 명령) | CLAUDE.md | 프로젝트 루트 |

안티패턴: 절차 체크리스트를 CLAUDE.md에 넣기(→스킬로), "절대 X 하지 마"를 CLAUDE.md에 쓰기(→훅·permissions로 강제).

## MCP 서버 카탈로그

> 이 문서는 **연결 상태를 주장하지 않는다** — 연결은 저장소 밖에서 변하고, 문서의 상태 주장은 반드시 낡는다.
> 쓰기 전에 세션에서 실제 쓸 수 있는 MCP를 먼저 확인하고, 없으면 필요한 것만 등록한다.

| MCP | 쓰는 시점 | 등록 (필요해질 때만) |
|------|------|------|
| Supabase | DB 스키마·쿼리·로그 직접 조작 | 공식 플러그인, 또는 `claude mcp add supabase -- npx -y @supabase/mcp-server-supabase --access-token <토큰>` |
| Playwright | 화면 확인·E2E·브라우저 자동화 | `claude mcp add playwright -- npx -y @playwright/mcp@latest` |
| context7 | 라이브러리 최신 문서 조회 | 공식 안내(upstash/context7) 참조 |
| GitHub | PR·이슈·리뷰 자동화 | 공식 안내(github/github-mcp-server) 참조 |
| 공식 참조 서버 (filesystem/git/fetch/memory) | — | 등록 불필요 — Claude Code 내장 도구(Read/Bash/WebFetch/메모리)와 중복 |
| mobile (mobile-mcp) | **폰 조작** — Playwright MCP의 안드로이드판. 세션에서 직접 폰 UI 트리 읽고 탭·스와이프·텍스트. 앱 조작 자동화 검증 | `.mcp.json`에 `mobile`로 정의(`npx -y @mobilenext/mobile-mcp@latest`), 프로젝트별 enabledMcpjsonServers로 활성. 실기기/에뮬 ADB 연결 전제 |

새 MCP가 필요하면: [공식 레지스트리](https://github.com/modelcontextprotocol/servers) 또는 PulseMCP에서 찾고, 스킬과 같은 절차(검토→논의→동의)로 등록. 등록 위치는 프로젝트 공유면 `.mcp.json`, 개인용이면 `claude mcp add`(로컬 스코프).

## settings 3계층과 권한

```
~/.claude/settings.json          # 글로벌 — 최소만 (로컬 우선 원칙과 동일)
.claude/settings.json            # 프로젝트 — git 커밋, 팀 공유
.claude/settings.local.json      # 프로젝트 개인 — gitignore
```

- **deny-first**: 민감 파일(.env, 키 파일)은 deny 목록에, 위험 명령은 훅으로 차단
- 반복되는 권한 프롬프트는 `/fewer-permission-prompts`로 allowlist 생성

## 훅 레시피 (프로젝트 로컬 `.claude/settings.json`)

자주 쓰는 패턴 — 형식 상세는 [공식 훅 문서](https://code.claude.com/docs/en/hooks):

1. **.env 읽기 차단** (PreToolUse): Read/Bash가 `.env` 경로를 건드리면 deny 반환
2. **포맷터 자동 실행** (PostToolUse): Edit/Write 후 `ruff format` (Python) 등 실행 — "포맷 지켜라" 지침보다 확실
3. **위험 명령 차단** (PreToolUse): `rm -rf`, `DROP TABLE`, force push 패턴이면 deny
4. **보류 안건 재부상** (SessionStart): `docs/pending.md`에서 재검토 시점이 도래한 안건을 세션 시작 때 컨텍스트로 주입 — llmwiki init이 설치. "나중에 검토하자"가 실제로 되돌아오게 하는 장치

훅은 설정한 만큼 마찰이 생긴다 — 킥오프 때는 1(.env 차단)과 llmwiki 훅(4, init에 포함)만 기본으로 걸고,
나머지는 실제로 문제가 반복될 때 추가. **턴마다 도는 점검 훅(Stop)은 주의** — "매 턴 위키 기록 점검"을
Stop 훅으로 강제해 봤더니 턴의 마지막 사고가 작업 검증이 아니라 기록 점검으로 끝나면서 작업 품질이
떨어져 폐기했다(2026-08-19). 기록 같은 에피소드형 행동은 훅 강제가 아니라 작업 매듭 규칙으로 두는 편이 낫다.

## 썩음 방지 — 값은 스크립트로, 규약은 린트로 (수개월 운영 프로젝트에서 검증)

- **변하는 값은 문서에 적지 않는다** — 계좌·플래그·설정값처럼 바뀌는 값을 문서에 복붙하면 즉시 썩는다.
  문서는 '정체'(무엇이 무엇인지)만 소유하고, 현재 값은 **조회 스크립트**가 코드에서 직접 읽어 출력한다
  ("문서의 값은 신뢰하지 말 것, 코드가 단일 출처").
- **어기면 안 되는 규약은 지침이 아니라 린트 스크립트로 강제한다** — 코드 경계, 디자인 규칙처럼
  검사 가능한 규약은 스크립트로 만들어 PostToolUse 훅이나 CI에 연결한다.
  지침은 잊히지만 린트는 잊지 않는다.
- **문서와 코드가 충돌하면 조용히 한쪽을 정답 처리하지 않는다** — 코드가 현재 구현이라는 이유만으로
  의도된 동작이라 단정하지 말고, ① 낡은 문서 ② 미완성 구현 ③ 진짜 결함 ④ 마이그레이션 진행 중
  넷 중 하나로 **분류한 뒤** 그 사실 종류의 단일 출처와 검증으로 판정한다.

## 직접 제작 — 스킬·훅·서브에이전트

레지스트리에 마땅한 게 없으면 만든다. 위 도구 선택 기준으로 형태를 정한 뒤:

**언제 만드나**
- 같은 절차·지시를 그 프로젝트에서 세 번째 반복하고 있을 때 (두 번까지는 그냥 한다 — 성급한 스킬화는 과잉설계)
- 프로젝트 고유 워크플로라 레지스트리에 있을 리 없을 때 (예: 이 프로젝트의 배포 절차, 데이터 검증 루틴)

**어떻게**
- 스킬: `.claude/skills/<이름>/SKILL.md` — 작성법은 writing-for-agents 스킬(글로벌)이 담당
- 화면 구현 스킬 골격(실전 검증): 프로젝트 디자인 시스템 규칙 + **"이걸 어겨서 매번 깨졌다" 절대규칙 목록** + 자동 린트 스크립트 + 브라우저 검증 절차를 한 스킬로 묶는다
- 서브에이전트: `.claude/agents/<이름>.md` — 컨텍스트 격리가 목적일 때만
- 훅: `.claude/settings.json` — 위 훅 레시피 형식 참고
- 처음부터 완벽하게 만들지 않는다 — 최소로 만들고 실제 사용에서 다듬는다

**재사용 경로 (로컬 → 카탈로그 → 글로벌)**
1. 프로젝트 로컬에서 실사용으로 검증
2. 다른 프로젝트에도 유용하면 CATALOG의 "자작 스킬" 섹션에 기록 (다음 킥오프 때 복사해서 재사용)
3. 거의 모든 프로젝트에서 쓰게 되면 그때 `~/.claude/skills`로 승격 — 글로벌 승격 기준은 CATALOG 설치 원칙과 동일

## CLAUDE.md 작성 원칙 (새 프로젝트 초기화 시)

- 100~400줄. 길어지면 규칙이 무시되기 시작함. **모든 상시 지시는 매 턴 주의력을 지불한다** —
  판단은 검색 가능한 문서에 두고, 반복 실패가 증명될 때만 상시 지시·훅으로 승격한다.
  도구(스킬·위키 등)가 CLAUDE.md에 남기는 블록은 도구당 10줄 예산
- 환경이 답하는 건 적지 않는다 (package.json 스크립트, 디렉토리 구조 등 — 캐시는 낡는다)
- 적을 것: 안 적으면 모르는 관행, 선택의 이유, 함정
- 강제할 것은 CLAUDE.md가 아니라 훅·permissions로
- 운영 환경(서버·실계좌·배포)이 있는 프로젝트는 **위험 작업 규약**을 명시한다 — 배포·운영 반영은 사용자 요청 시에만(임의 실행 금지), 작업 결과 보고에 실행 원라이너 동봉
- **위험 비례 검증 사다리**를 명시한다 — ① 재현/수용 기준 확인 → ② 표적 테스트 → ③ 관련 린트·타입·정적 검사 → ④ 서브시스템 회귀 → ⑤ 풀 게이트. 매번 전체를 돌리는 게 아니라 변경 위험에 비례해 확대
- **완료 보고 규칙**을 명시한다 — 실행하지 않은 검증을 실행했다고 보고하지 않는다. 필수 검증이 안 됐으면 "완료" 대신 **부분 완료/막힘**으로 보고
- 상세 기획·TODO는 `docs/`로 빼고 CLAUDE.md엔 인덱스만 (상위 CLAUDE.md의 문서 관리 원칙과 동일)

출처: [Claude Code 공식 베스트 프랙티스](https://code.claude.com/docs/en/best-practices)
