# ECC(Everything Claude Code) 실사용 평가와 ohmyPM 적합성

기준일 2026-10-10 · 핵심 근거: [원본 저장소 affaan-m/ECC](https://github.com/affaan-m/everything-claude-code)

## 핵심 요약

**ECC는 악성 코드는 아니지만, 사용자 범위(~/.claude)에 통째로 깔면 ohmyPM의 헤드리스 호출 40여 곳 전부에 훅 27개와 큰 스킬 목록이 함께 실립니다. 우리가 이미 버린 '미리 짜 둔 구조'와 성격이 같아서, 전체 설치는 맞지 않습니다.**

- 원본은 `affaan-m/ECC`입니다(옛 이름 everything-claude-code, 포크 아님). 2026-10-10 기준 별 276,261개, 에이전트 71개, 스킬 폴더 302개입니다. 요청서의 "68개·292개"는 예전 숫자입니다.
- 전체 설치가 기본은 아닙니다. 설치 묶음(minimal·core·full)을 고르거나 파일을 하나씩 복사할 수 있습니다. 다만 플러그인 마켓플레이스로 설치하면 스킬을 하나씩 끌 방법이 없습니다.
- 컨텍스트 비용은 사용자가 직접 잰 값이 있습니다. 스킬 182개와 에이전트 48개일 때 매 턴 약 12,800토큰이 실렸습니다. 스킬이 많으면 Claude Code가 설명문을 잘라내고, 우리가 직접 만든 스킬까지 밀려날 수 있습니다.
- 독립된 실사용 후기는 거의 찾지 못했습니다. 확인된 것은 보안 감사 글 1편(작성자가 자기 제품을 홍보함)과 원본 저장소 이슈뿐입니다. 이름을 사칭한 악성 복제 저장소는 실제로 확인됐습니다.

## 원본 확정

- 원본 주소는 `github.com/affaan-m/ECC`입니다. 예전 주소 `affaan-m/everything-claude-code`로 들어가도 이 저장소로 연결됩니다. GitHub API 기준 `fork: false`, 생성 2026-01-18, 마지막 반영 2026-10-10, MIT 라이선스입니다. 별 276,261개, 포크 41,213개, 열린 이슈 229개입니다. [출처](https://api.github.com/repos/affaan-m/ECC)
- 최신 배포판은 2.2.3(2026-10-01)입니다. [출처](https://github.com/affaan-m/everything-claude-code)
- 공식 경로는 README에 적힌 다섯 가지입니다. affaan-m/ECC 저장소, 플러그인 `ecc@ecc`, npm(자바스크립트 패키지 저장소) 패키지 `ecc-universal`과 `ecc-agentshield`, 그리고 ecc-tools GitHub 앱입니다. README에는 "제3자가 다시 올린 것에는 악성 코드가 있을 수 있다"는 경고가 붙어 있습니다. [출처](https://github.com/affaan-m/everything-claude-code)

### 숫자를 다시 센 결과

| 항목 | README 표기 | 직접 센 값(2026-10-10) |
|---|---|---|
| 에이전트 | 71 | `agents/` 폴더의 .md 파일 71개 [출처](https://api.github.com/repos/affaan-m/ECC/contents/agents) |
| 스킬 | 요약표 302, 본문 목록 293 | `skills/` 하위 폴더 302개 [출처](https://api.github.com/repos/affaan-m/ECC/contents/skills) |
| 명령어 | 요약표 95, 본문 목록 94 | 세지 않음 |
| 훅 | 개수 표기 없음 | `hooks/hooks.json`에 27개 [출처](https://raw.githubusercontent.com/affaan-m/ECC/main/hooks/hooks.json) |

같은 README 안에서도 숫자가 서로 다릅니다. 한 이슈(#2694)는 SKILL.md 파일이 773개라고 셌습니다. 이 수는 여러 도구용 사본까지 합친 것으로 보이지만, 확인하지는 못했습니다. [출처](https://github.com/affaan-m/ECC/issues/2694)

## 구성 한눈에

| 구성 | 하는 일 | 근거 |
|---|---|---|
| 에이전트(71개) | 역할별 하위 작업자(리뷰어·설계자 등). 6월 감사 시점에는 64개 중 49개가 셸 명령을 실행할 수 있었음 | [출처](https://dev.to/joergmichno/we-audited-the-viral-213k-star-everything-claude-code-repo-and-found-a-malware-clone-in-the-wild-14hb) |
| 스킬(302개) | 언어·프레임워크 패턴, 테스트 우선 개발, 영상 편집, 비자 서류 번역까지 범위가 매우 넓음 | [출처](https://api.github.com/repos/affaan-m/ECC/contents/skills) |
| 훅(27개) | 도구를 쓰기 전과 후, 응답이 끝날 때, 세션 시작과 끝에 자동 실행. 설정 파일 보호, 포맷·타입 검사, console.log 감시, 비용 기록, 데스크톱 알림 | [출처](https://raw.githubusercontent.com/affaan-m/ECC/main/hooks/hooks.json) |
| 규칙(rules) | 언어별 지침. "항상 실리는 컨텍스트"라서 README도 공통 규칙에 언어 하나만 더하라고 권함 | [출처](https://github.com/affaan-m/everything-claude-code) |
| 메모리 | 세션 요약, '본능(instinct)'(확신도 점수가 붙은 행동 패턴), 학습된 스킬. `ecc memory` 명령은 `.ecc/memory/`와 `~/.ecc/memory/`에 저장 | [출처](https://github.com/affaan-m/everything-claude-code) |
| 보안 스캔(AgentShield) | 프롬프트·훅·MCP(Claude에 외부 도구를 붙이는 연결 규격) 설정·권한·비밀값을 검사하는 별도 npm 패키지. `--opus` 모드는 Opus 에이전트 3개를 띄움 | [출처](https://github.com/affaan-m/everything-claude-code) |

### 설치 방식

- **마켓플레이스 설치**(`/plugin install ecc@ecc`): 스킬·에이전트·훅이 플러그인째로 켜집니다. Claude Code 공식 문서에 따르면 플러그인에 든 스킬은 `skillOverrides` 설정으로 하나씩 끌 수 없습니다. 플러그인 전체를 켜거나 끄는 것만 가능합니다. [출처](https://code.claude.com/docs/en/skills)
- **설치 스크립트**(`install.sh` / `install.ps1`): `--profile minimal|core|full`, `--modules`, `--no-hooks`로 골라서 설치할 수 있습니다. 스킬이 많은 모듈은 `full`에만 들어 있습니다. `core`는 훅을 포함하는 가장 가벼운 묶음이고, `minimal`에는 훅 실행 장치가 없습니다. [출처](https://github.com/affaan-m/ECC/issues/2482)
- **수동 복사**: 에이전트·규칙·스킬을 파일 하나씩 복사합니다. [출처](https://github.com/affaan-m/everything-claude-code)
- 두 방식을 섞으면 훅이 두 번씩 실행됩니다. README에 알려진 문제로 적혀 있습니다. [출처](https://github.com/affaan-m/everything-claude-code)

## 설치가 건드리는 것

### ~/.claude와 설정

- 기본 설치 스크립트는 훅을 `~/.claude/`에 전역으로 씁니다. 그러면 이 PC의 모든 Claude Code 세션에서 훅이 돕니다. [출처](https://dev.to/joergmichno/we-audited-the-viral-213k-star-everything-claude-code-repo-and-found-a-malware-clone-in-the-wild-14hb)
- 훅이 실행될 때마다 새 `node` 프로세스가 뜹니다. 이 프로세스는 `~/.claude/plugins` 아래를 뒤져 처음 찾은 폴더의 코드를 실행합니다. 서명을 확인하는 단계는 없습니다. [출처](https://raw.githubusercontent.com/affaan-m/ECC/main/hooks/hooks.json)
- 관찰 데이터는 `~/.local/share/ecc-homunculus`(`~/.claude` 밖)에 쌓입니다. 프롬프트와 도구 사용 내역을 기록합니다. [출처](https://raw.githubusercontent.com/affaan-m/ECC/main/skills/continuous-learning-v2/SKILL.md)
- 세션 시작 훅은 30일이 지난 세션 요약 파일을 지웁니다(`ECC_SESSION_RETENTION_DAYS`로 바꿀 수 있음). [출처](https://raw.githubusercontent.com/affaan-m/ECC/main/scripts/hooks/session-start.js)

### 매 턴·매 도구 호출에 붙는 것

- **도구를 쓰기 전 훅 10개**: 그중 `.*`(모든 도구)에 걸리는 것이 2개입니다(관찰 기록, hookify 실행기). 셸 명령 하나를 실행하면 내부에서 하위 훅이 최대 10개까지 더 돕니다. [출처](https://raw.githubusercontent.com/affaan-m/ECC/main/hooks/hooks.json) [출처](https://dev.to/joergmichno/we-audited-the-viral-213k-star-everything-claude-code-repo-and-found-a-malware-clone-in-the-wild-14hb)
- **프롬프트 제출 훅 1개**: 사용자가 메시지를 보낼 때마다 실행됩니다.
- **응답 종료 훅 8개**: 그중 포맷·타입 검사는 제한 시간이 300초입니다. 비용 기록과 데스크톱 알림은 뒤에서 따로 돕니다(비동기). [출처](https://raw.githubusercontent.com/affaan-m/ECC/main/hooks/hooks.json)
- **세션 시작 훅**: 새 세션의 컨텍스트에 아래 내용을 끼워 넣습니다. 확신도 0.7 이상인 본능 최대 6개, 7일 안의 이전 세션 요약 1건("과거 참고용, 현재 지시 아님"이라는 꼬리표 포함), 학습된 스킬 최대 6개, 감지한 프로젝트 유형. 상한은 기본 8,000자이고 `ECC_SESSION_START_CONTEXT=off`로 끌 수 있습니다. [출처](https://raw.githubusercontent.com/affaan-m/ECC/main/scripts/hooks/session-start.js)
- 8,000자는 대략 2,000토큰 안팎입니다(영문 기준 글자 수 ÷ 4로 어림). 매 턴 붙는 것이 아니라 세션을 시작할 때 한 번 붙습니다.

### 상주 프로세스와 외부 통신

- 백그라운드 관찰자(Haiku 모델로 5분마다 관찰 내용을 분석)는 기본값이 **꺼짐**(`"enabled": false`)입니다. [출처](https://raw.githubusercontent.com/affaan-m/ECC/main/skills/continuous-learning-v2/SKILL.md) 6월 감사 글은 이 관찰자가 확인 절차를 끈 채 Claude 하위 프로세스를 띄워 '본능' 파일을 쓰는 구조를 위험한 설계로 지적했습니다. [출처](https://dev.to/joergmichno/we-audited-the-viral-213k-star-everything-claude-code-repo-and-found-a-malware-clone-in-the-wild-14hb)
- 같은 감사 글은 기본 설치 경로에서 몰래 외부로 데이터를 보내는 코드를 찾지 못했다고 했습니다. 다만 두 가지를 지적했습니다. 자동 업데이트 스크립트가 서명 확인 없이 `git pull`을 한다는 점, 그리고 `.mcp.json`이 `npx -y chrome-devtools-mcp@latest`로 버전을 고정하지 않고 최신판을 받는다는 점입니다. [출처](https://dev.to/joergmichno/we-audited-the-viral-213k-star-everything-claude-code-repo-and-found-a-malware-clone-in-the-wild-14hb)
- README에 따르면 마켓플레이스로 설치할 때는 묶여 있는 MCP 서버가 자동으로 켜지지 않습니다. [출처](https://github.com/affaan-m/everything-claude-code)

## 컨텍스트 비용

- 공식 문서 기준으로 스킬 본문은 쓸 때만 읽힙니다. 하지만 스킬 설명문은 "매 턴 컨텍스트에 더해진다"고 되어 있고, 스킬 하나당 설명은 1,536자에서 잘립니다. [출처](https://code.claude.com/docs/en/skills)
- 실측 사례가 있습니다. ECC 2.0.0-rc.1 플러그인을 켜자 매 턴 약 12,800토큰이 늘었습니다. 스킬 182개분 설명이 약 10,300토큰, 에이전트 48개분이 약 2,500토큰이었습니다. 작성자는 이 중 15~20개만 썼다고 했습니다. 해결 방법은 가벼운 설치 묶음으로 바꾸는 것이었고, 이슈는 '계획 없음'으로 닫혔습니다. [출처](https://github.com/affaan-m/ECC/issues/2482)
- 3월에는 "에이전트 설명이 너무 길다(약 26,000토큰)"는 이슈가 있었고, 이후 닫혔습니다. [출처](https://github.com/affaan-m/ECC/issues?q=is%3Aissue+context+tokens)
- 스킬 목록 전체에 쓸 수 있는 몫은 컨텍스트 창의 약 1%입니다. 이를 넘으면 덜 쓰는 스킬부터 설명이 빠지고, 설명이 빠진 스킬은 모델이 스스로 고르지 못합니다. 이 내용은 제3자 글 기준이며 공식 문서에서 전체 예산 부분은 읽지 못했습니다. [출처](https://dev.to/rulestack/too-many-claude-code-skills-how-the-listing-budget-decides-which-descriptions-claude-sees-4a6m)
- 이슈 #2694(2026-08-06에 열림, 아직 열려 있음, 관리자 답 없음)의 보고 내용은 이렇습니다. 스킬 773개, 약 42,500토큰 분량이 예산(100만 토큰 창 기준 약 10,000토큰)의 4배를 넘었습니다. 잘린 스킬은 아예 고를 수 없게 됐고, 예산을 다른 플러그인과 같이 쓰기 때문에 **사용자 자신의 스킬과 명령까지 밀려났습니다.** [출처](https://github.com/affaan-m/ECC/issues/2694)
- "엉뚱한 스킬을 고른다"는 직접 사례는 찾지 못했습니다. 확인된 것은 "필요한 스킬이 목록에서 사라진다"는 보고까지입니다.

## 사용자 평가

### 홍보성 글과 독립 평가 구분

| 글 | 성격 | 내용 |
|---|---|---|
| Augment Code 소개글 | 경쟁 제품을 파는 회사가 씀 | 별 수와 구성을 소개. 실사용 평가 없음 [출처](https://www.augmentcode.com/learn/everything-claude-code-github) |
| DEV 보안 감사(2026-06) | 작성자가 자사 스캐너(ClawGuard)를 홍보함 | 원본은 악성 아님. 다만 전역에서 자동 실행되는 범위가 넓다고 지적. 악성 복제본 발견 [출처](https://dev.to/joergmichno/we-audited-the-viral-213k-star-everything-claude-code-repo-and-found-a-malware-clone-in-the-wild-14hb) |
| note.com 일본어 입문기 | 개인 블로그 | "전부 넣으면 위험하다는 데 제작자와 해설 글들이 모두 동의"한다고 정리 [출처](https://note.com/ai_eng_tech/n/n6f171f424e02?hl=en) |
| 원본 이슈 #2482, #2694 | 실제 사용자 보고 | 위 컨텍스트 비용 절 참고 |

### 좋았다 / 별로였다

- **좋았다는 쪽**: 별 수와 포크 수가 압도적입니다. 하지만 별 수는 쓸모를 보여 주는 지표가 아닙니다. 기능이 좋았다는 구체적인 1인칭 후기는 찾지 못했습니다.
- **별로였다는 쪽**: 기록으로 남은 불만은 모두 "너무 많이 실린다"는 내용입니다(#2482, #2694, #453). 훅 중복 실행 오류도 반복해서 보고됐습니다(#29, #52, #103). [출처](https://github.com/affaan-m/everything-claude-code)
- **설치 후 지운 사례**: #2482 작성자는 플러그인을 통째로 끄는 대신 가벼운 설치 묶음으로 갈아탔습니다. 완전히 지웠다는 1인칭 사례는 찾지 못했습니다. 레딧과 해커뉴스에서 ECC를 직접 다룬 글도 찾지 못했습니다.

## 보안

- **훅 구조 자체의 위험**: 훅은 사용자 권한으로 셸 명령(여기서는 node)을 자동 실행합니다. 플러그인 폴더에 무언가를 쓸 수 있는 공격자라면 서명 확인이 없으니 그 코드를 실행시킬 수 있습니다. [출처](https://dev.to/joergmichno/we-audited-the-viral-213k-star-everything-claude-code-repo-and-found-a-malware-clone-in-the-wild-14hb)
- **간접 주입으로 오래 남는 위험**: 세션 시작 때 지난 세션 요약과 '본능'을 자동으로 끼워 넣습니다. 오염된 내용이 한 번 저장되면 이후 세션에 계속 실릴 수 있는 구조입니다. ECC도 이를 의식해 "과거 참고용" 꼬리표를 붙이고, README에 "메모리는 검토되지 않은 컨텍스트"라고 적어 두었습니다. [출처](https://raw.githubusercontent.com/affaan-m/ECC/main/scripts/hooks/session-start.js) [출처](https://github.com/affaan-m/everything-claude-code)
- **사칭 저장소(실제 확인됨)**: `arabicapp/everything-claude-code`는 포크가 아니라 내용을 복사한 별도 저장소입니다. ZIP 파일을 받아 "관리자 권한으로 실행"하라고 유도하며, 유튜브로 홍보됐습니다. 관리자가 2026-06-15에 README 경고문을 추가했습니다. 2026-09-23 댓글에 따르면 관련 복제본 `worldflowai/everything-claude-code`와 `Drstone0007/everything-claude-cody`는 그때까지도 살아 있었습니다. [출처](https://github.com/affaan-m/ECC/issues/2255)
- **같은 계열의 위협**: 마켓플레이스 플러그인 주입으로 Claude Code를 장악하는 연구 사례가 있고, Claude Code를 사칭한 정보 탈취 악성 코드도 보도됐습니다. [출처](https://promptarmor.substack.com/p/hijacking-claude-code-via-injected) [출처](https://www.techradar.com/pro/security/infostealers-are-being-disguised-as-claude-code-openclaw-and-other-ai-developer-tools)
- **이 PC 현황**: `~/.claude/plugins`에서 ECC가 설치된 흔적은 찾지 못했습니다. 공식 마켓플레이스(claude-plugins-official) 목록에도 없습니다.

## 우리와 겹침

- ohmyPM은 2026-10-07에 main/pl/work 작업 구조와 그 플러그인을 폐기했습니다. 이유는 "역할 분리·스펙·교차 검토 배관이 작업에 도움이 되지 않는다"는 것이었습니다. 2026-10-09에는 24개 저장소에서 llmwiki 훅과 docs 위키를 걷어냈습니다. (`ohmypm/docs/plan.md:39-44`, `ohmypm/docs/archive-wiki-2026-10-09.md:279-283`)
- ECC의 핵심 부품은 그때 버린 것과 성격이 같습니다.
  - 역할별 에이전트 71개 ≈ pl 구조의 역할 분리
  - 세션 요약·본능·메모리 ≈ llmwiki의 연속성 뼈대
  - 매 턴 도는 훅 ≈ llmwiki 훅
- 규모는 우리 것보다 몇 배 큽니다.
- 이미 쓰고 있는 스킬과도 겹칩니다. 전역 스킬로 screen-plan, ponytail, grill, web-design-guidelines가 있고, ECC에는 `tdd-workflow`, `verification-loop`, `token-budget-advisor`, `unified-memory`처럼 같은 영역의 스킬이 있습니다. [출처](https://api.github.com/repos/affaan-m/ECC/contents/skills)
- 겹치지 않고 새로운 쪽은 '안전장치형 훅'입니다. 설정 파일 보호, 비밀값 패턴 감지, .env 읽기 차단, git 훅 우회 차단이 여기에 해당합니다. 이것들은 '구조'가 아니라 '방어'라서, 폐기 사유에 걸리지 않습니다. [출처](https://github.com/affaan-m/everything-claude-code)

## 우리 쪽 적용

제안일 뿐 결정이 아닙니다.

### 형태별 판단

| 형태 | 판단 | 이유 |
|---|---|---|
| 전체 설치(마켓플레이스·사용자 범위) | 하지 않는 것을 권함 | ohmyPM이 헤드리스로 부르는 모든 호출에 훅 27개와 스킬 목록이 실립니다. 응답 종료 훅의 포맷·타입 검사(최대 300초)는 헤드리스 작업을 느리게 만들 수 있습니다. 우리 스킬이 목록 예산에서 밀려날 위험도 있습니다. "다른 프로젝트는 ohmypm/ 폴더와 표식 블록만 건드린다"는 규칙과도 맞지 않습니다(설치 스크립트가 `~/.claude`에 전역으로 씀). |
| 일부만 골라 복사 | 꼭 필요하면 1~3개까지만 | 훅 스크립트 가운데 의존성이 적은 것 1~2개(예: 비밀값 감지, 설정 파일 보호)만 읽어 보고 우리 식으로 다시 쓰는 정도가 적당합니다. 원본 파일을 그대로 가져오면 `lib/` 의존성과 자동 업데이트까지 딸려 옵니다. |
| 아이디어만 참고 | 가장 맞음 | 세 가지가 쓸 만합니다. (1) 세션 시작 때 끼워 넣는 내용에 글자 상한(8,000자)과 끄는 스위치를 둔 설계. (2) 과거 요약에 "현재 지시 아님" 꼬리표를 붙이는 방식. (3) 훅마다 엄격도(minimal/standard/strict)와 개별 끄기 환경변수를 두는 방식. |
| 쓰지 않음 | 전체 설치에 대해서는 이쪽 | 폐기 사유("미리 짜 둔 구조가 실작업에 도움이 안 됨")가 그대로 해당합니다. |

### 해 볼 만한 것

1. 지금 우리 스킬 목록이 예산 안에 들어가는지 `/doctor`로 한 번 확인해 봅니다. ECC와 상관없이 플러그인(supabase 등)이 늘어날 때 생기는 문제라서입니다.
2. 앞으로 외부 묶음을 시험할 일이 있으면 사용자 범위가 아니라 **시험용 폴더 하나의 프로젝트 범위**에만 설치합니다. 그리고 ohmyPM 헤드리스 호출에 섞이지 않는지 먼저 봅니다.
3. 안전장치 훅(비밀값 감지 등)이 필요하다고 판단되면, ECC를 들이지 말고 우리 쪽 훅으로 짧게 새로 씁니다.

### 버려지는 안건의 재검토 시점(사용자와 고정 필요)

- **"ECC 전체 설치"**: 재검토 조건 후보는 이슈 #2694(스킬 묶음 선택 기능)가 해결되고, 플러그인 설치에서도 스킬 일부만 켤 수 있게 되는 때입니다. 아니면 "재검토 없음"(이유: 폐기한 구조와 같은 성격)으로 둘 수도 있습니다. 둘 중 무엇으로 할지 정해서 `ohmypm/docs/`에 기록해야 합니다.

## 확인 못 한 것

- **스킬 개수가 출처마다 다릅니다.** README 302와 293, 직접 센 폴더 302개, 이슈 #2694의 SKILL.md 773개. 773개가 무엇을 센 것인지는 확인하지 못했습니다.
- **ECC 2.2.3 `core` 묶음의 실제 매 턴 토큰 비용**: 실측값은 rc.1 플러그인 기준(12,800토큰) 하나뿐입니다.
- **훅 스크립트 전부의 외부 통신 여부**: `session-start.js`와 `evaluate-session.js`에는 통신이 없음을 확인했습니다. `cost-tracker.js`, `mcp-health-check.js`, `desktop-notify.js`, `lib/` 아래 파일은 읽지 않았습니다.
- **스킬 목록 예산의 정확한 규칙**: 제3자 글은 "컨텍스트 창의 1%"라고 하고, 다른 글은 "약 4,000토큰(2%)"이라고 해 서로 다릅니다. 공식 문서의 해당 부분은 읽지 못했습니다. `skillListingBudgetFraction` 설정은 공식 문서에서 확인하지 못했습니다.
- **헤드리스 호출에서 플러그인과 훅을 빼는 방법**: Claude Code의 실행 옵션으로 사용자 범위 설정을 빼고 부를 수 있는지는 이번에 확인하지 않았습니다.
- **좋은 쪽 독립 후기**: 레딧과 해커뉴스에서 ECC를 직접 다룬 1인칭 후기를 찾지 못했습니다. 실제 사용 만족도는 알 수 없습니다.
- **관찰자(observer)가 프롬프트와 도구 입출력을 원문 그대로 저장하는지**: 문서에는 "프롬프트와 도구 사용을 기록"한다고만 되어 있습니다.
