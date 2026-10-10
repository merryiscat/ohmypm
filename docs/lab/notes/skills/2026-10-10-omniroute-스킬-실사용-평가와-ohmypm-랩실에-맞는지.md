# OmniRoute 실사용 평가와 ohmyPM 적합성

기준일 2026-10-10 · 핵심 근거: [OmniRoute 저장소](https://github.com/diegosouzapw/OmniRoute), [Claude Code 법무·약관 문서](https://code.claude.com/docs/en/legal-and-compliance)

## 핵심 요약

**OmniRoute는 스킬이 아닙니다. 내 PC에서 계속 돌아가는 "AI 요청 중계소"(게이트웨이)입니다. 맥스 요금제를 쓰는 ohmyPM에는 얻을 것보다 위험이 커서, 지금은 쓰지 않는 쪽이 맞습니다.**

- 하는 일: Claude Code·Codex·Cursor 같은 도구가 보내는 요청을 내 PC의 20128번 포트에서 받아, 등록해 둔 여러 AI 회사(수백 곳이라고 홍보) 중 한 곳으로 보냅니다. 한 곳의 사용 한도가 차면 다른 곳으로 넘깁니다. "스킬"이라 불리는 것은 이 중계소를 조작하는 보조 설명서일 뿐입니다.
- 약관: OmniRoute는 Claude 구독 로그인 정보(토큰)를 받아 저장하고, 그것으로 요청을 대신 보내는 기능이 있습니다. Anthropic 약관은 "Claude.ai 로그인 정보나 세션 토큰을 제3자가 수집·저장·중계하는 것"을 금지합니다.
- 보안: 2026-09-10에 원격 코드 실행 취약점(CVE-2026-88062, 위험도 9.5/10 "치명적")이 공개됐습니다. 이 PC 안의 모든 API 키와 토큰이 털릴 수 있는 종류입니다. 고친 버전이 무엇인지는 출처마다 다릅니다.
- 평판: 별은 매우 많지만(7만 개 이상), 독립적인 사용 후기는 드뭅니다. 독립 평가들은 공통으로 "Claude Code 화면은 공짜 모델로도 돌릴 수 있지만, 공짜 Claude는 아니고 안정적이지도 않다"고 결론 냅니다.

## 대상 확정

'OmniRoute'라는 이름으로 찾은 후보는 다음과 같습니다.

| 후보 | 정체 | 판단 |
|---|---|---|
| diegosouzapw/OmniRoute (GitHub, npm 패키지 `omniroute`) | MIT 라이선스(자유롭게 써도 되는 공개 라이선스)의 AI 게이트웨이. Claude Code 연동을 직접 내세움 | **이 문서의 대상** [출처](https://github.com/diegosouzapw/OmniRoute) |
| 같은 저장소 안의 에이전트 스킬들(omni-auth, cli-plugins-skills 등) | skills.sh·tessl 같은 스킬 목록 사이트에 올라온 SKILL.md 묶음. 게이트웨이 설정·조작용 | 게이트웨이가 없으면 의미 없음 [출처](https://tessl.io/registry/skills/github/diegosouzapw/OmniRoute) [출처](https://skillselion.com/skills/diegosouzapw/OmniRoute/omni-auth) |
| v0l/OmniRoute | 위 저장소를 복사해 온 것(포크). 별 0개 | 별개 도구 아님 [출처](https://github.com/v0l/OmniRoute) |
| nianyi778/omniroute-integration | 제3자가 만든 연동 스킬. 한 감사 결과 보안 문제 4건(외부 주소가 코드에 박혀 있음, 숨김 설정 파일 접근)이 나왔다는 검색 요약이 있음 | 원문 페이지가 404여서 직접 확인 못 함 |
| omniroute.online | 위 프로젝트의 홍보 사이트 | 같은 프로젝트 [출처](https://omniroute.online/pricing) |

## 무엇을 하나

- **구조**: 내 PC에서 계속 돌아가는 중계 프로그램(로컬 프록시)입니다. `npm install -g omniroute`로 설치하면 `http://localhost:20128`에 관리 화면과 요청 창구가 열립니다. Docker(프로그램을 격리된 상자에 담아 돌리는 도구)나 데스크톱 앱으로도 설치할 수 있습니다. [출처](https://github.com/diegosouzapw/OmniRoute)
- **연결 방식**: OpenAI 형식, Anthropic 형식, Gemini 형식의 요청 창구를 모두 엽니다. 그래서 Claude Code가 "Anthropic 서버에 보낸다"고 생각하고 보낸 요청을 받아 다른 회사 모델로 바꿔 보낼 수 있습니다. [출처](https://agentpedia.codes/blog/omniroute-ai-gateway-routing-setup-guide.md)
- **라우팅**: "구독 → API 키 → 저가 → 무료" 순서로 넘어가는 대체 경로(폴백)와, 18가지 분배 방식을 내세웁니다. 토큰 압축 기능(RTK, Caveman)으로 15~95%를 아낀다고 하지만, 이는 만든 사람의 주장이고 독립적으로 검증된 수치는 아닙니다. [출처](https://github.com/diegosouzapw/OmniRoute) [출처](https://agentpedia.codes/blog/omniroute-ai-gateway-routing-setup-guide.md)
- **Claude 구독 연결**: 공식 위키의 제공자 안내에 "Claude Code"가 OAuth(계정으로 로그인해 받는 출입증 방식) 제공자로 올라 있습니다. 절차는 "Claude Code 연결 → OAuth 로그인 → 토큰 자동 갱신 → 5시간·주간 한도 추적"입니다. [출처](https://github.com/diegosouzapw/OmniRoute/wiki/Providers-Guide)
- 관리자의 설명에 따르면, 구독으로 연결하면 요청 하나하나를 구독 한도로 처리할지 추가 결제로 처리할지는 Anthropic이 정합니다. 요청을 보낸 프로그램이 어떤 형태로 요청했는지도 영향을 줍니다. [출처](https://github.com/diegosouzapw/OmniRoute/discussions/7877)
- "공짜 Claude"가 아닙니다. 공식 질의응답에서도 "OmniRoute 자체가 유료 Claude 모델을 무료로 만들지 않는다"고 답했습니다. 비용은 실제로 요청을 처리한 회사의 요금을 따릅니다. [출처](https://github.com/diegosouzapw/OmniRoute/discussions/11127)
- Claude 데스크톱 앱의 대화창은 OmniRoute로 돌릴 수 없다고 관리자가 확인했습니다. [출처](https://github.com/diegosouzapw/OmniRoute/discussions/11127)

## 설치 시 영향

| 항목 | 내용 |
|---|---|
| 계속 돌아가는 프로그램 | Node.js 서버 하나(또는 Docker 컨테이너, 데스크톱 트레이 앱) |
| 열리는 포트 | 20128. 3.8.48 버전은 기본값이 0.0.0.0(같은 네트워크의 다른 기기도 접속 가능)이었다고 한 독립 리뷰가 지적함. 공식 Docker 예시는 127.0.0.1(이 PC만)로 묶음 [출처](https://agentpedia.codes/blog/omniroute-ai-gateway-routing-setup-guide.md) |
| 기본 비밀번호 | `INITIAL_PASSWORD`를 지정하지 않으면 관리 화면 비밀번호가 `CHANGEME`라는 글자 그대로 정해짐 [출처](https://pinggy.io/blog/omniroute_ai_gateway_security/) |
| 만드는 파일 | 설치 과정에서 `.env`(설정·비밀값 파일)를 만들 수 있음. 키 저장소는 SQLite(파일 하나로 된 데이터베이스)이고 AES-256-GCM 방식으로 암호화해 둔다고 함. 로그·백업 폴더도 생김 [출처](https://github.com/diegosouzapw/OmniRoute) |
| 다른 도구 설정 | `omniroute configure <도구>`는 그 도구의 설정 파일을 직접 씀. `omniroute run <도구>`와 `launch`는 파일 대신 실행할 때만 환경 변수로 넣는다고 함. Claude Code에 정확히 어떤 파일·변수를 쓰는지는 확인 못 함 [출처](https://github.com/diegosouzapw/OmniRoute) |
| 보관하는 것 | 등록한 모든 회사의 API 키, OAuth 토큰, 그리고 로그를 켜 두면 프롬프트와 답변 전문 [출처](https://agentpedia.codes/blog/omniroute-ai-gateway-routing-setup-guide.md) |
| 외부로 나가는 것 | 공식 설명으로는 사용 통계 수집이 기본으로 꺼져 있고, 모델 목록 갱신은 받아오기만 함. 클라우드 동기화 기능과 `cloud.omniroute.online` 주소가 있지만, 거기로 무엇이 가는지는 확인 못 함 [출처](https://github.com/diegosouzapw/OmniRoute) |
| 위험한 선택 기능 | TLS 위장(남의 프로그램인 척 접속하기), 암호화된 통신을 중간에서 풀어 보기(MITM, TPROXY). 기본은 꺼져 있음 [출처](https://agentpedia.codes/blog/omniroute-ai-gateway-routing-setup-guide.md) |

## 보안과 약관

### 보안

- **CVE-2026-88062**(CVE: 공개 취약점에 붙는 고유 번호): 에이전트 등록 창구(`/api/acp/agents`)에 원하는 명령을 넣으면 그대로 실행됩니다. 로그인 요구 설정(requireLogin)이 꺼져 있거나 설치 직후 설정 전이면 로그인 없이도 공격할 수 있습니다. 위험도는 9.5/10이고, 공격 예시 코드도 공개돼 있습니다. [출처](https://securityonline.info/omniroute-rce-flaw-cve-2026-88062-poc/) [출처](https://blog.codercops.com/blog/omniroute-ai-gateway-cve-2026-88062-rce)
- 영향 받는 버전은 출처마다 다릅니다. "3.8.49 이하", "3.8.50 이하", "고친 버전 없음"으로 엇갈립니다. 수정 PR #11028은 반영됐지만 이것으로 완전히 막혔는지는 단정되지 않았습니다. [출처](https://vulert.com/vuln-db/CVE-2026-88062) [출처](https://app.opencve.io/cve/CVE-2026-88062)
- 이 PC에는 여러 프로젝트의 `.env` 키가 모여 있습니다. 그래서 중계소 한 곳이 뚫리면 피해가 한꺼번에 커집니다. 독립 리뷰도 "모든 비밀번호와 프롬프트를 한 곳에 모으는 구조"라는 점을 가장 큰 위험으로 꼽았습니다. [출처](https://agentpedia.codes/blog/omniroute-ai-gateway-routing-setup-guide.md)
- 프롬프트 주입(남이 숨겨 둔 지시문) 감지 기능은 기본값이 "경고만"이고, 막지는 않습니다. [출처](https://agentpedia.codes/blog/omniroute-ai-gateway-routing-setup-guide.md)

### 약관 (Anthropic 공식 문서 원문 기준)

- 구독 로그인(OAuth)은 "Claude Code와 다른 Anthropic 자체 앱의 일반적 사용"을 위한 것입니다. 개발자는 "Claude.ai 로그인 정보나 세션 토큰을 수집·저장·중계할 수 없고", 사용자 대신 무료·Pro·맥스 요금제 로그인 정보로 요청을 보내 줄 수 없습니다. Anthropic은 미리 알리지 않고 제재할 수 있다고 적었습니다. [출처](https://code.claude.com/docs/en/legal-and-compliance)
- 같은 문서에 "Pro·맥스 요금제의 사용 한도는 개인의 일반적 사용을 전제로 한다"는 문장도 있습니다. [출처](https://code.claude.com/docs/en/legal-and-compliance)
- 게이트웨이에 관한 공식 문서는 이렇게 설명합니다. Anthropic은 제3자 게이트웨이 제품을 보증하지 않습니다. Claude Code를 Claude가 아닌 모델로 돌리는 것은 지원하지 않습니다. 게이트웨이 전용 열쇠를 쓰면 구독 한도가 아니라 토큰 단위로 따로 과금됩니다. [출처](https://code.claude.com/docs/en/llm-gateway)
- 변경 이력: 2026년 2월 문서 개정, 4월 "제3자 도구는 구독 한도 대신 별도 과금"이라는 고객 메일 보도가 있었습니다. 이후 문구가 다시 고쳐졌다는 보도도 있습니다. 2차 보도들 사이에서 세부 시점과 표현이 엇갈리므로, 위 공식 문서 문구를 기준으로 삼았습니다. [출처](https://alternativeto.net/news/2026/2/anthropic-officially-bans-using-subscription-authentication-for-third-party-claude-use) [출처](https://lilting.ch/en/articles/anthropic-claude-code-openclaw-third-party-paygo)
- OmniRoute도 다른 회사 몇 곳(OpenCode Free, Kiro 등)은 자체 표에서 "약관상 피함"으로 표시해 자동 경로에서 뺍니다. 그런데 독립 리뷰에 따르면 구글 Antigravity를 거친 Claude 경로도 OmniRoute 자체 표에 "제3자 도구 경유 금지"로 표시돼 있습니다. [출처](https://github.com/diegosouzapw/OmniRoute) [출처](https://www.ai.joaoqueiros.com/blog/claude-code-free-omniroute-model-routing-reality-check)

## 사용자 평가

### 저장소 지표 (확인 시점 2026-10-10)

- 별 약 7.48만 개, 열린 이슈 135개, 열린 PR(코드 수정 요청) 214개, 커밋 1만 개 이상, 현재 릴리스 브랜치 v3.8.52, 보안 경고 1건 공개 중입니다. 최근 커밋 날짜는 확인 못 했습니다. [출처](https://github.com/diegosouzapw/OmniRoute)
- 별 수는 출처마다 크게 다릅니다(2.9만, 3.4만, 5.5만, 6.3만, 7.5만). 시점 차이로 보이지만, 몇 달 만에 이만큼 늘었다는 점 자체가 홍보 바람을 탔다는 뜻이기도 합니다.
- 버전 번호가 몇 주 사이에 3.8.48 → 3.8.52로 바뀔 만큼 변경이 매우 잦습니다.

### 독립 평가 (홍보가 아닌 것)

- **joaoqueiros 블로그 (2026-08-04)**: 한 경로에서 13개 모델 중 11개가 응답했습니다. 하지만 OpenCode Free 경유 DeepSeek은 7개 중 2개만 응답했습니다. 결론은 "Claude Code 화면은 공짜 경로로 돌릴 수 있지만 공짜 Claude도 아니고, 업무용으로 믿을 만하지도 않다"입니다. 도중에 다른 모델로 넘어가면 동작이 달라진다는 경고도 있습니다. 단, 이 글이 검토한 원본 영상에는 협찬이 들어 있습니다. [출처](https://www.ai.joaoqueiros.com/blog/claude-code-free-omniroute-model-routing-reality-check)
- **agentpedia (2026-07-21)**: 반드시 이 PC에서만 접속되게 묶고, 버전을 고정하고, 설정 명령은 미리보기(`--dry-run`)부터 돌리라고 권합니다. 내세우는 숫자들은 "목록상 주장이지 검증된 것이 아니다"라고 평했습니다. 위 CVE의 원인이 된 문제를 공개 전에 이미 지적했습니다. [출처](https://agentpedia.codes/blog/omniroute-ai-gateway-routing-setup-guide.md)
- **levelup.gitconnected (Medium)**: 제목부터 "만지지 말아야 할 이유"이고, 코드와 CVE를 읽었다고 합니다. 원문이 403으로 막혀 본문은 확인 못 했습니다. [출처](https://levelup.gitconnected.com/the-ai-tool-that-promises-1-6-billion-free-claude-tokens-and-why-you-shouldnt-touch-it-a63c687f7d91)

### 홍보성이거나 이해관계가 있는 것

- stork.ai "Claude Code를 공짜로 풀어 준다" 시리즈(여러 언어로 같은 글)는 홍보성입니다. [출처](https://www.stork.ai/blog/this-ai-gateway-unlocks-claude-code-for-free)
- Pinggy 블로그는 직접 써 본 글이지만, 자사 터널(외부 접속 통로) 서비스 판매 글입니다. [출처](https://pinggy.io/blog/omniroute_ai_gateway_security/)
- 레딧에서 찾은 글은 관리자 본인이 쓴 소개글이었습니다. "월 16억 토큰 무료" 같은 숫자는 프로젝트 공식 문서가 아니라 퍼진 게시물에서 나온 것입니다. [출처](https://reddit.sentinel-team.org/posts/1uloc3g/snapshots/2026-07-02T21%3A43%3A35.23287Z)

### 사용자들이 겪은 문제 (공식 질의응답 게시판)

- 구독을 연결했는데 추가 결제분만 쓰였다는 문의가 있었습니다. 관리자는 화면 문구가 오해를 부른다고 인정하고 수정 이슈를 열었습니다. [출처](https://github.com/diegosouzapw/OmniRoute/discussions/7877)
- 대체할 연결이 하나뿐이면 400·429 오류(요청 거부·한도 초과)가 그대로 사용자에게 보입니다. 남은 한도를 한 숫자로 보여 주지도 못합니다. [출처](https://github.com/diegosouzapw/OmniRoute/discussions/11127)

## 대안 비교

| 방법 | 하는 일 | 구독(맥스) 사용 | 우리 쪽 부담 |
|---|---|---|---|
| Claude Code 그대로 + `--model` 지정 (지금 방식) | Anthropic에 직접 요청. 작업마다 모델을 고름 | 공식으로 허용 | 없음 |
| Anthropic 공식 게이트웨이(Claude apps gateway) | 조직용 중계소. SSO(회사 계정 한 번 로그인) 로그인, 사용량 기록 | 조직용. 개인에게는 과함 | 설치·운영 [출처](https://code.claude.com/docs/en/llm-gateway) |
| 일반 게이트웨이(LiteLLM 등) + API 키 | 키를 한곳에 모으고, 예산·로그를 관리 | 구독이 아니라 토큰 단위 과금 | 서버 운영, Claude Code 새 기능을 계속 따라가야 함 [출처](https://code.claude.com/docs/en/llm-gateway) |
| OmniRoute | 수백 곳 제공자로 자동 분배·대체 | 구독 토큰을 저장·중계 → 약관과 충돌 | 서버 운영 + 보안 패치 추적 |

공식 문서가 밝힌 게이트웨이 공통 단점이 있습니다. Claude Code가 새 기능을 낼 때마다 게이트웨이가 그것을 그대로 넘겨 주지 못하면 그 기능이 깨집니다. [출처](https://code.claude.com/docs/en/llm-gateway)

## 우리 쪽 적용

이 절은 제안일 뿐 결정이 아닙니다.

**제안: 쓰지 않는다. ohmyPM 본체에도, 다른 프로젝트에도 넣지 않는다.**

이유 (위 사실과 우리 상황을 맞춰 본 판단):

1. **얻을 게 거의 없음.** ohmyPM의 비용 단위는 맥스 요금제 세션(약 5시간)입니다. OmniRoute의 장점은 "여러 회사의 무료·저가 한도를 이어 붙이기"입니다. 우리는 Claude 품질을 전제로 작업을 등급별로 나눠 두었으므로(`src/cc/models.py`의 TASK_TIER), 다른 회사 모델로 자동으로 넘어가면 등급표의 의미가 사라집니다.
2. **등급표 원칙과 충돌.** 2026-09-28 사고 이후 정한 원칙이 "모델은 호출할 때마다 명시하고, 개인 기본값에 맡기지 않는다"입니다(`src/cc/models.py:4-9`). 그런데 OmniRoute의 자동 대체는 중계소가 몰래 모델을 바꾸는 구조라, 같은 종류의 빈틈을 다시 엽니다.
3. **계정 위험.** 헤드리스(사람이 화면을 보지 않고 자동으로 돌리는 방식)로 하루 수십 번 부르는 상황에서 구독 토큰을 OmniRoute에 맡기면, 약관이 금지하는 "토큰 저장·중계"에 해당할 수 있습니다. 공식 문서가 "미리 알리지 않고 제재"한다고 적었으므로, 최악의 경우 ohmyPM 전체가 멈출 수 있습니다.
4. **보안 위험이 한곳에 몰림.** 40개 프로젝트의 키가 있는 PC에서, 치명적 취약점이 공개되고 수정 여부도 불분명한 상주 서버를 돌리는 셈입니다.
5. **폴더 규칙.** OmniRoute는 `configure` 명령으로 다른 도구의 설정 파일을 직접 고칩니다. "다른 프로젝트 파일은 ohmypm/ 폴더와 표식 블록만 건드린다"는 우리 규칙과 맞지 않습니다.

그래도 OmniRoute가 겨냥한 고민(한도가 차면 일이 멈춘다)은 우리에게도 있습니다. 이를 직접 풀 수 있는 작고 안전한 방법을 제안합니다.

- **등급표에 "한도 초과 시 행동"을 한 줄씩 붙이기**: 다른 회사로 넘기지 않습니다. 대신 "light 작업은 다음 세션까지 미룬다 / heavy 작업은 사용자에게 알린다" 정도를 정합니다. 모델은 계속 Claude 안에서만 고릅니다.
- **실험을 꼭 해 보고 싶다면** 조건을 셋 다 지킵니다. (1) 구독 로그인이 아닌 별도 API 키나 무료 모델만 연결한다. (2) 이 PC에서만 접속되게 묶고, 로그인 요구를 켜고, 기본 비밀번호를 바꾼다. (3) ohmyPM 헤드리스 호출과는 완전히 분리된 시험용 폴더에서만 돌린다. 이것도 지금 당장은 권하지 않습니다.
- **재검토 시점**: CVE-2026-88062의 수정 버전이 공식 보안 공지에 명시되고, Anthropic 약관 문서의 "토큰 수집·저장·중계 금지" 문구가 바뀌면 그때 다시 봅니다. 둘 중 하나라도 그대로면 재검토하지 않습니다. 이 조건은 ohmyPM `docs/`의 보류 안건 기록에 함께 적어 두기를 제안합니다.

## 확인 못 한 것

- 저장소의 최근 커밋 날짜(저장소 첫 화면에서 날짜가 보이지 않았음).
- CVE-2026-88062의 정확한 영향 버전과 수정 버전. "3.8.49 이하", "3.8.50 이하", "고친 버전 없음"으로 출처끼리 엇갈림.
- `omniroute configure claude`나 `setup-claude`가 Claude Code의 어떤 설정 파일·환경 변수를 고치는지(예: `~/.claude/settings.json`, `ANTHROPIC_BASE_URL`).
- 클라우드 동기화를 켰을 때 `cloud.omniroute.online`으로 키나 프롬프트가 넘어가는지.
- 최신 버전의 기본 접속 범위(0.0.0.0인지 127.0.0.1인지). 3.8.48 기준 지적만 확인함.
- Medium의 비판 글(levelup.gitconnected) 본문. 접근이 막혔음.
- 제3자 스킬 nianyi778/omniroute-integration의 보안 감사 원문. 페이지가 404였음.
- OmniRoute로 구독을 썼다가 계정이 실제로 제재된 사례. 다른 도구(OpenClaw 등)의 제재 보도는 있지만 OmniRoute 이름이 붙은 사례는 찾지 못함.
- 별 수: 2.9만~7.5만으로 출처마다 다름. 이 문서는 2026-10-10 저장소 화면 기준(약 7.48만)을 썼음.
- Anthropic 약관의 변경 이력: 2월·4월 개정과 그 뒤 문구 수정을 두고 2차 보도끼리 시점과 표현이 엇갈림. 이 문서는 오늘 확인한 공식 문서 문구만 근거로 삼음.
