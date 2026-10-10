# Agent-Browser와 Playwright MCP 비교

기준 2026-10-10 · 원본 저장소 [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)

## 핵심 요약

**지금은 Playwright MCP를 그대로 쓰고, agent-browser로 바꾸지 않는 것이 맞다. 이 PC와 같은 Windows 11 Home 환경에서 실행이 막히거나 멈추는 열린 버그가 있고, 화면 점검에 중요한 '페이지 오류 잡기'에서 독립 시험 결과가 Playwright 쪽에 유리했기 때문이다.**

- 원본은 Vercel 회사 계정(vercel-labs)의 저장소가 맞다. 남의 것을 복제한 포크가 아니다. 별은 약 4.4만 개이고, 마지막 반영일은 2026-10-10이다.
- 토큰(AI가 읽고 쓰는 글자 단위) 절약은 실제로 있다. 다만 "Playwright MCP보다 80~90% 적다"는 숫자는 대부분 Vercel이 직접 낸 것이거나 오래된 비교에서 나왔다. 2026년 7~10월에 나온 독립 측정에서는 차이가 작았다(대화 맥락 기준 약 5% 이하).
- Windows 공식 지원은 된다. 하지만 이 PC와 같은 빌드(Windows 11 Home 26200)에서 나온 실행 차단 이슈를 포함해, Windows 관련 열린 이슈가 여럿이고 관리자 답변이 없다.
- 둘 다 설치해 둘 필요는 없다. 바꾸고 싶다면 비교 대상은 agent-browser보다 Microsoft의 Playwright CLI(명령줄 도구)가 먼저다. Playwright MCP 공식 문서도 코딩 에이전트에는 이쪽을 권한다.

## 원본 확정

- 저장소 주인은 조직 계정 vercel-labs다. 포크가 아니고 보관 처리(archived)되지도 않았다. 2026-01-11에 만들어졌고, 2026-10-10 기준 별 43,761개, 포크 2,962개다. [출처](https://api.github.com/repos/vercel-labs/agent-browser)
- npm(Node.js 패키지 저장소)에 올라간 이름은 `agent-browser`다. 최신판은 0.39.0이고, 저장소 주소가 위 원본과 같다. 배포는 GitHub Actions의 신뢰된 발행 설정(사람 손을 거치지 않는 자동 배포)으로 이뤄진다. 관리자 목록에 vercel-release-bot이 있다. [출처](https://registry.npmjs.org/agent-browser/latest)
- 릴리스는 자주 나온다. v0.37.1(9/8) → v0.38.0·0.38.1(9/16) → v0.38.2(10/1) → v0.39.0(10/9). [출처](https://github.com/vercel-labs/agent-browser/releases)
- 저장소 화면에 표시된 수는 열린 이슈 419개, 열린 PR(코드 변경 요청) 428개다. [출처](https://github.com/vercel-labs/agent-browser)
- 라이선스는 Apache-2.0이다.

## 구조와 설치

### 어떻게 돌아가나

- Rust로 만든 명령줄 도구다. 뒤에서 '데몬'(계속 떠 있는 보조 프로그램)이 돌면서 CDP(Chrome DevTools Protocol, 크롬을 바깥에서 조종하는 통로)로 크롬을 움직인다. 데몬은 Playwright도 Node.js도 쓰지 않는다. [출처](https://github.com/vercel-labs/agent-browser)
- `snapshot`을 실행하면 접근성 트리(화면 요소를 글로 나열한 목록)를 돌려준다. 요소마다 `@e2` 같은 번호표(ref)가 붙고, `click @e2`처럼 그 번호로 조작한다. 쓸 만한 옵션이 셋 있다. `-i`는 누를 수 있는 요소만, `-c`는 압축해서, `--delta`는 바뀐 부분만 보여준다. [출처](https://github.com/vercel-labs/agent-browser)
- axe-core(웹 접근성 검사 엔진)가 들어 있다. 그래서 접근성 검사를 인터넷 연결 없이 돌릴 수 있다. [출처](https://github.com/vercel-labs/agent-browser)
- `agent-browser mcp` 명령으로 MCP 서버(AI가 도구를 부르는 표준 연결 방식)로도 띄울 수 있다. [출처](https://github.com/vercel-labs/agent-browser/issues/2047)

### 설치할 때 건드리는 것

- **Node.js 24**: npm 패키지에 `node >=24.0.0`이 명시돼 있다. [출처](https://registry.npmjs.org/agent-browser/latest) 이 PC의 Node는 v24.12.0이라 조건을 만족한다. 저장소 README에는 "Node 24는 소스에서 직접 빌드할 때만 필요하다"고 적혀 있어 두 설명이 조금 다르다.
- **설치 직후 자동 실행 스크립트**(postinstall): 플랫폼에 맞는 실행 파일을 GitHub 릴리스에서 내려받는다. 내려받은 파일의 체크섬(위변조 확인값)이나 서명은 검사하지 않는다. Windows에서 전역 설치하면 npm 전역 폴더의 `agent-browser.cmd`·`agent-browser.ps1`을 덮어쓴다. `~/.claude`, 셸 설정, PATH는 건드리지 않는다. [출처](https://raw.githubusercontent.com/vercel-labs/agent-browser/main/scripts/postinstall.js)
- **`agent-browser install`**: 테스트용 크롬(Chrome for Testing)을 따로 내려받는다. [출처](https://github.com/vercel-labs/agent-browser)
- **Claude Code 스킬**: `npx skills add vercel-labs/agent-browser`로 설치한다. 설치되는 것은 아주 짧은 '안내 쪽지'뿐이고, 실제 사용법은 실행할 때 `agent-browser skills get core`로 받아 온다. 그래서 스킬 내용이 설치된 도구 판과 항상 맞는다. [출처](https://github.com/vercel-labs/agent-browser)
- **훅**(특정 시점에 자동으로 도는 명령): 설치 과정에서 훅을 등록한다는 언급은 찾지 못했다. 저장소에 `.claude-plugin` 폴더가 있지만 무엇이 들었는지는 확인하지 못했다.
- **외부 통신**: 실행 파일과 크롬 다운로드, `upgrade` 명령의 새 판 확인이 있다. 그 밖은 직접 켤 때만 일어난다. API 키를 넣어야 쓰는 AI 대화 기능(Vercel AI Gateway로 통신), 클라우드 브라우저 업체 연결 등이다. README에는 "모든 기능은 직접 켜야 동작한다"고 적혀 있다. [출처](https://github.com/vercel-labs/agent-browser)
- **텔레메트리**(사용 기록 자동 전송): README와 설치 스크립트에서 관련 언급을 찾지 못했다. 소스 코드 전체는 확인하지 못했다.
- **보안 주의**: `--remote-debugging-port`를 켜면 같은 PC의 어떤 프로그램이든 그 브라우저를 조종할 수 있다고 README가 경고한다. [출처](https://github.com/vercel-labs/agent-browser)

## 무엇이 다른가

### 스냅샷 크기

- **Vercel 쪽 숫자**: README 비교표(검색 결과 요약에서 본 것)에 따르면 해커뉴스 첫 화면 스냅샷이 agent-browser 약 1,200토큰, Playwright MCP 약 14,700토큰이다. 제작사가 직접 잰 값이다. [출처](https://www.morphllm.com/agent-browser-vs-playwright-mcp)
- **Pulumi 블로그(2026-01-20)**: 같은 시험 6개를 돌린 응답 글자 수가 Playwright MCP 31,117자, agent-browser 5,455자였다. 페이지 하나의 스냅샷은 4,127자 대 385자였다. 토큰이 아니라 글자 수로 쟀고, 앱 하나로 한 비공식 실험이다. [출처](https://www.pulumi.com/blog/self-verifying-ai-agents-vercels-agent-browser-in-the-ralph-wiggum-loop/)
- **통제된 비교(2026-10-07)**: agent-browser 0.38.2와 Playwright CLI 0.1.22를 비교했다. 작업 12개를 각 5회씩 돌렸고, 대화 맥락 사용량 중앙값은 11.3k 대 12.0k 토큰이었다. agent-browser가 아주 조금 적다. [출처](https://github.com/melodic-software/claude-code-plugins/pull/6477)
- **Checkly(2026-07-30)**: Playwright MCP와 Playwright CLI만 비교했다(agent-browser는 빠짐). 결과는 48~50k 대 45~48k 토큰으로 "차이는 잡음 수준"이었다. 이유로는 두 가지를 들었다. Claude Code가 MCP 도구 설명을 필요할 때만 불러오게 됐고, Playwright MCP가 스냅샷을 파일로 빼낼 수 있게 됐다. [출처](https://www.checklyhq.com/blog/mcp-vs-cli-token-efficiency/)

정리하면 이렇다. 스냅샷 한 장만 놓고 보면 agent-browser가 확실히 작다. 하지만 작업 하나를 끝까지 했을 때의 총량 차이는 최근 측정일수록 작다.

### 도구 설명이 차지하는 몫

- Playwright MCP 도구 설명의 크기는 출처마다 다르다. 약 13,600~14,300토큰이라는 측정과 약 5,900토큰(도구 48개, 2025년 기준)이라는 측정이 엇갈린다. [출처](https://itnext.io/why-does-playwright-mcp-use-so-many-tokens-da56b6dbd2db) [출처](https://www.checklyhq.com/blog/mcp-vs-cli-token-efficiency/)
- 지금의 Claude Code는 MCP 도구의 이름만 먼저 싣고, 자세한 설명은 실제로 쓸 때 불러온다. [출처](https://www.checklyhq.com/blog/mcp-vs-cli-token-efficiency/) 이 조사를 한 세션에서도 MCP 도구가 '지연 로딩'(쓸 때 불러오기) 상태로 떠 있는 것을 직접 봤다. 그러니 "MCP는 도구 설명만으로 1만 토큰을 먹는다"는 주장은 지금 Claude Code에는 대부분 맞지 않는다.
- agent-browser 스킬은 짧은 안내 쪽지 한 장이다. 스킬 설명 한 줄의 비용은 보통 30~50토큰 정도다. [출처](https://www.checklyhq.com/blog/mcp-vs-cli-token-efficiency/)

### 속도

- 위 통제된 비교에서는 AI 없이 스크립트로만 돌렸을 때 agent-browser가 약 3.5배 빨랐다(중앙값 1.8초 대 6.1초). 그런데 AI가 직접 조종하면 이 차이가 사라졌다. [출처](https://github.com/melodic-software/claude-code-plugins/pull/6477)
- DEV 커뮤니티 글은 Vercel의 "3.5배 빠르다"가 자체 선정 질의 5개로 잰 값이라고 지적한다. 이 숫자는 AI가 고민하는 단계가 줄어든 효과이지 브라우저가 빨라진 것이 아니라는 비판이다. 첫 실행 때 크롬이 뜨는 데 2~5초가 걸린다는 지적도 있다. [출처](https://dev.to/stevengonsalvez/browser-tools-for-ai-agents-part-1-playwright-puppeteer-and-why-your-agent-picked-playwright-k71)

### 안정성

- 통제된 비교에서 125회 시행이 모두 통과해 신뢰성 승자는 없었다. 하지만 차이가 셋 있었다. [출처](https://github.com/melodic-software/claude-code-plugins/pull/6477)
  - agent-browser는 명령을 더 많이 썼고(중앙값 15 대 10), 실패한 명령도 더 많았다(22 대 6).
  - 페이지에 일부러 넣은 자바스크립트 오류를 Playwright CLI는 5번 중 5번 찾았다. agent-browser는 한 번도 못 찾았다. `console`·`errors` 출력에도 나오지 않았다.
  - agent-browser는 클릭 뒤 기다리지 않는다. 그래서 다른 요소에 가려졌거나 아직 비활성인 버튼에서 실패했다.
  - 이 비교를 한 쪽은 결국 Playwright를 기본으로 유지하고 agent-browser는 채택하지 않았다.
- Pulumi 글도 비슷한 약점을 적었다. API 호출 뒤 뜨는 창은 직접 기다리게 해야 했고, 문서가 빈약해 소스를 읽어야 했다. 네트워크 가로채기, 여러 탭 다루기, 동기화는 Playwright 쪽이 앞선다고 했다. [출처](https://www.pulumi.com/blog/self-verifying-ai-agents-vercels-agent-browser-in-the-ralph-wiggum-loop/)

## Windows 지원

- 공식 플랫폼 표에 Windows x64가 '네이티브 Rust 실행 파일'로 올라 있다. [출처](https://github.com/vercel-labs/agent-browser) 예전 판 README 사본에는 "Windows는 Node.js 경로로 돈다"는 표가 있었다. 지금 문서와는 다르다. [출처](https://go.waylonwalker.com/vercel-labs-agent-browser.txt)
- 9월 v0.37.1에서 Windows 헤드리스 크롬(화면 없이 도는 크롬) 관련 문제를 고쳤다. [출처](https://github.com/vercel-labs/agent-browser/releases)
- 그래도 제목에 Windows가 들어간 열린 이슈가 최소 8개 있다. [출처](https://github.com/vercel-labs/agent-browser/issues?q=is%3Aissue+is%3Aopen+windows) 우리에게 직접 걸리는 것은 다음과 같다.
  - **#2047 (10/3)**: Windows 11 Home 10.0.26200에서 일어난다. 이 PC와 같은 빌드다. 스마트 앱 컨트롤(서명 없는 프로그램을 막는 Windows 보안 기능)이 서명 없는 실행 파일을 막아서 MCP 서버가 바로 종료된다. 우회하려면 이 보안 기능을 꺼야 한다. 관리자 답변은 없다. [출처](https://github.com/vercel-labs/agent-browser/issues/2047)
  - **#1821 (9/8)**: Windows 10에서 `open`·`connect` 명령이 끝나지 않고 멈춘다. 실패할 때마다 프로세스가 하나씩 남는다. 관리자 답변은 없다. [출처](https://github.com/vercel-labs/agent-browser/issues/1821)
  - **그 밖**: `--init-script`를 쓰면 모든 페이지 이동이 실패하는 문제(#1948), 헤드리스인데 흰 창이 뜨는 문제(#1838), 다운로드가 항상 취소되는 문제(#1659), 크롬 자동 실행 실패(#1710)가 있다.
- Playwright MCP도 Windows에서 주의할 점이 하나 있다. 같은 작업 폴더를 여러 클라이언트가 동시에 쓰면 브라우저 프로필이 충돌한다. 피하려면 `--isolated` 옵션을 쓴다. [출처](https://github.com/microsoft/playwright-mcp)

## 독립 비교 글

| 글 | 날짜 | 성격 | 결론 |
|---|---|---|---|
| melodic-software PR #6477 | 2026-10-07 | 사전 규칙을 정한 통제된 시험(리눅스) | 신뢰성은 무승부, 오류 탐지는 Playwright가 나음 → Playwright 유지 [출처](https://github.com/melodic-software/claude-code-plugins/pull/6477) |
| Checkly | 2026-07-30 | 회사 블로그(agent-browser와 이해관계 없음) | Playwright MCP와 CLI의 토큰 차이는 거의 사라짐 [출처](https://www.checklyhq.com/blog/mcp-vs-cli-token-efficiency/) |
| ytyng 블로그 | 2026-03-27 | 개인 실사용 | 토큰은 agent-browser가 가장 적고, 정확성은 Playwright CLI가 가장 믿을 만함 [출처](https://www.ytyng.com/en/blog/ai-browser-automation-tools-comparison-2026) |
| DEV(Gonsalvez) | 2026-04, 07 수정 | 개인 분석 | 토큰 절약은 진짜, 속도 주장은 증명 안 됨 [출처](https://dev.to/stevengonsalvez/browser-tools-for-ai-agents-part-1-playwright-puppeteer-and-why-your-agent-picked-playwright-k71) |
| Pulumi | 2026-01-20 | 회사 블로그, 비공식 실험 | 글자 수 82% 감소, 깊이는 Playwright가 앞섬 [출처](https://www.pulumi.com/blog/self-verifying-ai-agents-vercels-agent-browser-in-the-ralph-wiggum-loop/) |
| Morphllm | 2026-03 | 도구 회사 블로그 | 오히려 Playwright MCP가 2~3배 적다고 주장. 방법론을 확인하지 못함 [출처](https://www.morphllm.com/agent-browser-vs-playwright-mcp) |

- **홍보와 구분할 것**: "93% 감소", "3.5배 빠름", "5.7배 더 많은 시험" 같은 숫자는 모두 Vercel 측정이거나 그 숫자에서 계산해 낸 값이다.
- **Microsoft 쪽 입장**: Playwright MCP README는 코딩 에이전트에는 Playwright CLI와 스킬 조합을 고려하라고 권한다. 상태를 오래 유지하며 깊게 들여다보는 작업에는 MCP가 낫다고 적었다. [출처](https://github.com/microsoft/playwright-mcp)

## 이 PC의 현재 상태

아래는 이 PC의 설정 파일을 읽고 확인한 사실이다.

- **Playwright MCP 등록 위치**: `~/.claude.json`에는 project_odin 프로젝트 범위에만 등록돼 있다. 패키지는 공식 `@playwright/mcp@latest`다. 사용자 범위(모든 프로젝트 공통)에는 등록돼 있지 않다.
- **ohmyPM 쪽**: ohmyPM 항목에는 MCP 서버가 없다. 저장소의 `.claude/settings.json`에는 서버를 띄우는 SessionStart 훅만 있다. `docs/setup.md`에도 "Playwright MCP는 저장소에 등록돼 있지 않다 — 각 PC에서 따로 등록"이라고 적혀 있다. 다만 `.gitignore`에 `.playwright-mcp/`가 들어 있어서, 실제로 써 온 흔적은 있다.
- **공식 플러그인**: 공식 마켓플레이스의 `playwright` 플러그인은 내려받아져 있지만 켜져 있지 않다. 켜진 플러그인은 supabase 하나다.
- **Node 버전**: v24.12.0이다. agent-browser의 Node 24 조건은 만족한다.

## 우리 쪽 적용

아래는 제안일 뿐 결정이 아니다.

1. **사용자 범위 설치는 하지 않는다.** 사용자 범위에 넣으면 프로젝트 약 40개의 헤드리스 호출에 모두 실린다. 스킬 쪽지 자체는 작지만, 화면이 없는 프로젝트에서 Claude가 엉뚱하게 브라우저를 띄울 여지가 생긴다. 게다가 Windows 버그 #2047(같은 빌드에서 실행 차단)과 #1821(멈춤)이 열려 있다. 헤드리스 호출이 멈추면 맥스 요금제 세션을 헛되이 쓰게 된다.
2. **ohmyPM 화면 점검은 Playwright MCP를 유지한다.** 단일 HTML 화면을 점검할 때 중요한 것은 "자바스크립트 오류가 났는지 잡아내는 것"이다. 독립 시험에서 이 부분은 Playwright 쪽이 확실히 나았다. 등록 위치는 사용자 범위가 아니라 ohmyPM 프로젝트 범위(로컬 설정)로 두는 편이 헤드리스 호출을 깨끗하게 지킨다.
3. **바꿔 볼 후보는 agent-browser보다 Playwright CLI가 먼저다.** 같은 Playwright 엔진이라 지금 쓰는 동작 방식과 같고, Microsoft가 코딩 에이전트용으로 권한다. 다만 Checkly 측정으로는 토큰 이득이 작다. 그래서 지금 바꿀 급한 이유는 없다.
4. **agent-browser에서 아이디어 하나는 빌릴 만하다.** 우리 화면 규칙 가운데 WCAG 대비는 axe-core 접근성 검사로 기계적으로 확인할 수 있다. agent-browser를 깔지 않아도, Playwright로 화면을 연 뒤 axe-core를 돌리는 점검 절차를 ohmyPM 화면 점검 체크에 넣는 방안을 검토할 수 있다.
5. **재검토 시점 고정(안건 보류 규칙)**: agent-browser 도입은 아래 조건 중 하나가 생기면 다시 본다. 기록처는 ohmyPM의 `docs/plan.md` 하네스 줄이 맞아 보인다.
   - #2047과 #1821이 닫히거나 Windows 실행 파일에 서명이 붙을 때
   - 화면 점검 세션에서 `/context`(Claude Code가 대화 맥락 사용량을 보여 주는 명령)로 확인한 브라우저 출력이 맥락의 큰 몫을 차지하는 것이 관찰될 때
   - 위 조건이 생기지 않아도 2027-01-10에 한 번 상태를 확인한다.
6. **시험해 보고 싶다면 이렇게 한다.** ohmyPM 폴더에서만, MCP 모드가 아니라 명령줄 모드로, 한 번만 깐다. 같은 화면 점검 3개를 Playwright MCP와 나란히 돌려 `/context` 숫자와 실패 횟수를 비교한다. 설치 전에 이 PC의 스마트 앱 컨트롤이 켜져 있는지 먼저 확인한다.

## 확인 못 한 것

- **README 비교표 원문**: agent-browser README의 Playwright MCP 비교표(1,200 대 14,700토큰)를 원문에서 직접 보지 못했다. 저장소 페이지를 두 번 읽었지만 표가 잡히지 않았고, 검색 요약으로만 봤다.
- **텔레메트리**: README와 설치 스크립트에는 없었다. Rust 본체 소스 전체는 확인하지 못했다.
- **`.claude-plugin` 폴더**: 안에 무엇이 들었는지(훅 포함 여부) 확인하지 못했다.
- **Node 24 조건**: npm 패키지는 Node 24 이상을 요구하고, README는 "소스 빌드에만 필요"라고 한다. 두 설명이 엇갈린다.
- **Playwright MCP 스냅샷 방식**: 출처끼리 엇갈린다. 공식 README에는 `--snapshot-mode`가 full·none 두 가지이고 기본은 화면 안에 바로 싣는 방식이라고 돼 있다. 0.0.51 릴리스 노트 사본에는 `--snapshot` 옵션의 기본값이 incremental(바뀐 부분만)이라고 돼 있다. Checkly는 스냅샷이 파일로 빠진다고 했다. 지금 판의 기본 동작은 직접 확인하지 못했다.
- **도구 설명 크기**: 5.9k와 13.6~14.3k로 측정이 엇갈린다. 이 PC에서 직접 재지 않았다.
- **ohmyPM에서 Playwright MCP가 어떻게 연결돼 왔는지**: 설정 파일에서 찾지 못했다. 세션마다 임시로 붙였거나 다른 설정 파일에 있을 수 있다.
- **이 PC의 스마트 앱 컨트롤**: 켜져 있는지 확인하지 못했다. 켜져 있으면 #2047 때문에 agent-browser가 아예 실행되지 않을 수 있다.
- **이슈 등록 제한**: 저장소에 "이슈 등록이 제한돼 있다"는 검색 요약이 있었지만 직접 확인하지 못했다.
- **Morphllm 글 본문**: 서버가 요청을 거절해서(429 오류) 읽지 못했다. "Playwright MCP가 2~3배 적다"는 주장의 근거를 확인하지 못했다.
- **목록 밖 오래된 등록**: 우리 프로젝트 목록 밖의 Doit 폴더에 `@anthropic/mcp-server-playwright`, `@anthropic-ai/mcp-server-playwright`라는 이름으로 Playwright MCP가 등록돼 있다. 공식 이름(`@playwright/mcp`)과 다르다. 이 패키지가 실제로 있는지, 누가 올린 것인지는 확인하지 못했다. 안 쓰는 등록이면 지우는 편이 안전해 보인다.
