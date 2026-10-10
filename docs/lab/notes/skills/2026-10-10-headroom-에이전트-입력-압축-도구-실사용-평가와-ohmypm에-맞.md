# Headroom 실사용 평가와 ohmyPM 적합성

기준 2026-10-10 · 근거: [저장소](https://github.com/headroomlabs-ai/headroom) · [Claude Code 약관 안내](https://code.claude.com/docs/en/legal-and-compliance)

## 핵심 요약

**지금 ohmyPM에는 쓰지 않는 게 맞다. 아이디어만 참고하자. 맥스 구독 로그인 토큰이 로컬 프록시를 거쳐 나가는 구조라 약관상 애매하다. 절감 수치는 거의 다 만든 쪽이 잰 것이다. Claude Code 자체 자동 요약과 부딪힌 사례도 이번 주에야 고쳐졌다.**

- 정체: 원본 저장소가 맞다. 포크나 사칭이 아니다. 별 7.49만 개, Apache-2.0(누구나 고쳐 쓰고 배포할 수 있는 공개 라이선스)이다. 10월 6일 v0.40.0이 나올 만큼 활발하다.
- 끼어드는 방식: 기본은 **로컬 프록시**(내 컴퓨터 안의 중계 서버)다. Claude Code의 요청 주소를 바꿔 프록시를 거치게 한다. 그 과정에서 각 프로젝트 설정 파일과 세션 시작 훅을 건드린다. MCP(에이전트에 도구를 붙이는 표준 방식) 서버로만 쓰는 방법도 있다.
- 텔레메트리(사용 통계 전송)는 기본으로 켜져 있다. 문서는 내용은 보내지 않고 숫자만 보낸다고 한다. `HEADROOM_BEACON=off`나 `DO_NOT_TRACK=1`로 끈다.
- "코딩 에이전트 20% 절감"은 제작사 자체 측정이다. 독립 측정은 찾지 못했다. 압축 때문에 세션이 망가진 사례는 실제로 보고됐다.

## 정체 확인

- `github.com/headroomlabs-ai/headroom`이 원본이다. 페이지에 "포크해 온 저장소" 표시가 없다. 예전 주소 `chopratejas/headroom`으로 들어가도 같은 저장소가 열린다. 개인 계정에서 회사 조직으로 옮긴 것으로 보인다. [출처](https://github.com/chopratejas/headroom)
- 만든 사람은 넷플릭스 출신 Tejas Chopra다. 회사 이름은 Headroom Labs다. 소규모 초기 투자를 받았다고 인터뷰에서 밝혔다. [출처](https://www.aiacceleratorinstitute.com/q-a-how-headroom-went-from-side-project-to-enterprise-infrastructure/)
- 헷갈리기 쉬운 곳이 하나 있다. `extraheadroom.com`은 Garm Tech라는 다른 업체가 판다. 이 오픈소스 위에 만든 **유료 데스크톱 앱**이다(7일 체험 후 유료). 원작자의 "지지"를 받았다고만 적혀 있다. 공식 제품은 아니다. [출처](https://extraheadroom.com/faq)

## 끼어드는 방식

세 가지 길이 있다. [출처](https://github.com/headroomlabs-ai/headroom)

| 방식 | 하는 일 | 건드리는 것 |
|---|---|---|
| `headroom wrap claude` | 로컬 프록시를 띄운다. 그다음 Claude Code를 프록시 경유로 실행한다 | 아래 목록 |
| `headroom proxy --port 8787` | 프록시만 띄운다. 요청 주소는 사람이 직접 프록시로 바꾼다 | 사용자가 바꾸는 환경 변수 |
| `headroom mcp install` | 압축·원본 꺼내기·통계 도구 3개를 MCP로 붙인다. 모델이 필요할 때 부른다 | MCP 설정 파일 |

`wrap claude`가 건드리는 것(코드 확인)은 다음과 같다. [출처](https://raw.githubusercontent.com/headroomlabs-ai/headroom/main/headroom/cli/wrap.py)
- `ANTHROPIC_BASE_URL`(Claude Code가 요청을 보낼 주소)을 프록시로 바꾼다. 이 값을 파일에 남기는 것은 선택이다. 남기면 **프로젝트의 `.claude/settings.local.json`**에 적는다.
- `ENABLE_TOOL_SEARCH=true` 같은 환경 변수를 넣는다.
- **SessionStart 훅**(세션이 시작될 때 도는 스크립트)을 설치한다. 프록시가 죽어 있으면 되살리는 용도다.
- 프로젝트 폴더에 `.headroom_wrap_marker.json`, `.headroom_wrap_owners.json`, 잠금 파일을 만든다.
- 코드 탐색 도구 Serena를 함께 설치한다. `~/.claude.json`에 MCP 서버로 등록한다.
- 따로 `headroom learn`을 돌리면 `CLAUDE.local.md`나 `CLAUDE.md`에 글을 쓴다.
- 되돌리기는 `headroom unwrap`이다. 다만 "한 번에 깨끗이 지우는 명령과 문서가 없다"는 이슈가 열려 있다. [출처](https://github.com/headroomlabs-ai/headroom/issues/748)

원본 복구 방식(CCR)은 이렇다. 압축 전 원본을 내 컴퓨터에 보관하고, 모델이 `headroom_retrieve`를 부르면 원본을 돌려준다. 보관은 설정한 기한까지만 한다. [출처](https://github.com/headroomlabs-ai/headroom)

## 약관 쟁점

### 사실

- Anthropic 약관 안내는 구독(Free·Pro·Max) 로그인을 "Claude Code와 Anthropic 자체 앱의 일반적 사용"용이라고 적는다. 그리고 "개발자는 Claude.ai 자격 증명이나 세션 토큰을 수집·저장·중계(intermediate)해서는 안 된다"고 적는다. 또 "사용자를 대신해 구독 자격 증명으로 요청을 보내는 것"도 금지한다. 위반하면 예고 없이 제재할 수 있다고 한다. [출처](https://code.claude.com/docs/en/legal-and-compliance)
- 같은 문서는 반대 방향의 예외도 적는다. 사용자 본인이 **수정하지 않은 Claude Code**에 자기 구독으로 로그인하는 것은 막지 않는다. [출처](https://code.claude.com/docs/en/legal-and-compliance)
- Headroom 프록시는 Claude Code가 보낸 요청을 받아 Anthropic에 다시 보낸다. 그러니 구독 토큰(`sk-ant-oat…`)이 실린 요청이 Headroom 프로세스를 **지나간다**.
- Headroom 코드는 Claude Code 요청을 User-Agent(요청에 붙는 프로그램 이름표)로 알아본다. 그런 요청은 "구독 클라이언트"로 따로 분류한다. 분류 단계는 "헤더 값을 기록하지 않는다"고 주석에 적혀 있다. [출처](https://raw.githubusercontent.com/headroomlabs-ai/headroom/main/headroom/proxy/auth_mode.py)
- 이슈 #3017 로그에는 구독 로그인(oauth) 헤더가 보인다. 실제로 맥스 구독으로 wrap을 쓰는 사람이 있다는 뜻이다. [출처](https://github.com/headroomlabs-ai/headroom/issues/3017)
- 같은 회사 문서에는 다른 도구(OpenCode)에 대한 설명도 있다. Anthropic이 막아서 Claude 구독은 쓸 수 없고 API 키만 된다는 내용이다. [출처](https://github.com/headroomlabs-ai/headroom/issues/78)

### 판단이 갈리는 지점

토큰을 **저장**한다는 근거는 찾지 못했다. 그러나 **중계**는 구조상 일어난다. 내 컴퓨터 안에서 본인 토큰을 그대로 흘려보내는 것을 금지된 "중계"로 볼지, Anthropic이 명확히 밝힌 글은 찾지 못했다. 또 Headroom은 요청 **내용을 고쳐서** 보낸다. "수정하지 않은 Claude Code"를 그대로 쓰는 경우와는 결이 다르다. 결론적으로 약관 위반이라고 단정할 근거도, 안전하다고 할 근거도 없다. 회색 지대다.

## 텔레메트리

- **익명 비콘**(제작사로 보내는 사용 통계): 기본으로 켜져 있다. 코드에 `BEACON_DEFAULT_ON = True`가 있다. 세션이 쉬는 상태가 되면 요약 하나를 Headroom Labs 수집 서버로 보낸다. [출처](https://docs.headroomlabs.ai/docs/proxy)
  - 보내는 것(문서 기준): 압축률, 각종 횟수, 제공사·모델 이름, 운영체제·CPU 종류, 캐시 동작, 세션 형태, 사용 중인 도구와 설정. 설치할 때 무작위로 만든 식별 번호(하드웨어나 컴퓨터 이름과는 무관)도 함께 간다.
  - 보내지 않는 것(문서 기준): 프롬프트, 답변, 코드, 파일 경로, 환경 변수.
  - 정확히 무엇이 나가는지는 `headroom telemetry --show`로 볼 수 있다고 코드 주석에 적혀 있다. [출처](https://raw.githubusercontent.com/headroomlabs-ai/headroom/main/headroom/telemetry/beacon.py)
- **끄는 법**: `HEADROOM_BEACON=off`, `DO_NOT_TRACK=1`, `HEADROOM_OFFLINE=1` 중 하나를 쓴다. 마지막 것은 업데이트 확인과 "라이선스 보고"까지 끈다. `HEADROOM_TELEMETRY_WARN=off`는 안내 문구만 숨긴다. **전송은 멈추지 않는다**. [출처](https://docs.headroomlabs.ai/docs/proxy)
- **그 밖의 외부 통신**: 하루 한 번 이하로 PyPI(파이썬 패키지 저장소)에 업데이트를 확인한다(`HEADROOM_UPDATE_CHECK=off`로 끔). `HEADROOM_USAGE_REPORTING`은 기본으로 꺼져 있다. 켜면 사용량 합계를 Headroom 클라우드로 보낸다. [출처](https://docs.headroomlabs.ai/docs/proxy)
- **엇갈리는 점**: 창업자는 인터뷰에서 "오픈소스 제품은 사용 데이터를 모으지 않는다"고 말했다. 그러나 현재 코드와 문서는 비콘이 기본으로 켜져 있다고 한다. 인터뷰 시점이 비콘 도입 전이었을 수도 있다. 확인은 못 했다. [출처](https://www.aiacceleratorinstitute.com/q-a-how-headroom-went-from-side-project-to-enterprise-infrastructure/)
- 참고로 `wrap`은 띄우는 Claude Code 쪽에 `DO_NOT_TRACK`을 기본으로 넣는다. 다만 이것이 프록시 자신의 비콘까지 끄는지는 확인하지 못했다. [출처](https://raw.githubusercontent.com/headroomlabs-ai/headroom/main/headroom/cli/wrap.py)

## 절감 수치

| 주장 | 누가 쟀나 | 메모 |
|---|---|---|
| 코딩 에이전트 20%, JSON 60~95% | 제작사 README | "내용이 반복될수록 절감이 커진다"고 스스로 적음 |
| 코드 검색 21%, 장애 디버깅 57%, 코드베이스 탐색 42%, 이슈 분류 30% | 제작사 벤치마크 스크립트 | "고정 시드, 오프라인" 조건 |
| 정확도: GSM8K(수학 문제 시험) 0.870→0.870, TruthfulQA(사실성 시험) 0.530→0.560 | 제작사 | 제작사 스스로 "차이 없음"으로 해석 |
| 출력 토큰 31.7% 감소 | 제작사 | "추정치"로 표기 |
| Snowflake 내부 시험 65~70% | 인터뷰 속 전언 | 정식 측정인지 불명 |
| 한 달 1.5억 개가 아니라 15억 토큰 절감 중 Headroom 몫 1.89억 | 개인 블로그 | 도구 자체 계기판 숫자. 비교 실험 없음. 요금제 언급 없음 |

출처: [README](https://github.com/headroomlabs-ai/headroom) · [인터뷰](https://www.aiacceleratorinstitute.com/q-a-how-headroom-went-from-side-project-to-enterprise-infrastructure/) · [블로그](https://andrewpatterson.dev/posts/token-savings-rtk-headroom/)

정리하면 독립된 제3자가 같은 조건에서 비교 측정한 자료는 찾지 못했다. 위 블로그 저자는 이 도구들의 설치 스킬을 직접 만들어 배포한다. 완전히 중립적인 후기로 보기는 어렵다. 소개 글 대부분은 README 숫자를 옮겨 적은 수준이다. 한 리뷰도 "최대치 숫자가 홍보의 전부이자 함정"이라고 경고했다. [출처](https://mer.vin/2026/06/headroom-explained-open-source-context-compression-for-ai-agents-60-95-fewer-tokens/)

## 망가진 사례

- **#3998 (10/6 접수, 같은 날 닫힘)**: 프록시가 Claude Code에 "압축 **후**" 토큰 수를 알려줬다. 그래서 Claude Code는 대화가 아직 짧다고 착각해 자동 요약을 미뤘다. 그사이 실제 원본 대화는 계속 길어져 한계를 넘었다. 그 뒤로는 매 턴 "프롬프트가 너무 길다" 오류가 나고 강제 요약이 반복됐다. 100만 토큰 세션을 20만 기준으로 압축하는 문제도 함께 있었다. 한 사용자는 "맥락을 잘라먹고 두 번 물을 때마다 요약했다"며 사용을 그만뒀다. [출처](https://github.com/headroomlabs-ai/headroom/issues/3998)
- **#709 (열림)**: 빠르게 돌아가는 세션에서 예전 원본(CCR)을 엉뚱하게 다시 끼워 넣는다. [출처](https://github.com/headroomlabs-ai/headroom/issues?q=is%3Aissue+is%3Aopen+sort%3Acomments-desc)
- **#2825 (열림)**: 특정 설정에서 스트리밍 답이 빈 내용으로 온다.
- **#2363 (열림)**: 다른 경로(litellm-vertex)로 연결하면 Claude Code 요청이 말없이 옛 모델로 간다.
- **#3017 (8월, 열림)**: 프록시를 거친 Claude Code가 "빈 응답 또는 형식이 잘못된 응답" 오류를 낸다. 원인은 원본 복구 경로가 요청 형식을 바꾼 것이었다. v0.36.0에서 고쳐졌다. 우회책은 `--no-ccr`(원본 복구 기능 끄기)이다. [출처](https://github.com/headroomlabs-ai/headroom/issues/3017)
- **윈도우 관련 (열림)**: 큰 JSON을 압축하다 멈춘다(#600). 내용 종류를 판별하다 멈춘다(#845).
- 블로그 후기: 프록시가 죽으면 **알리지 않고** 직접 연결로 넘어간다. 그대로 넘긴 일부 요청은 오히려 200~500토큰 늘었다. [출처](https://andrewpatterson.dev/posts/token-savings-rtk-headroom/)

"압축이 정보를 빼먹어서 모델이 틀린 답을 냈다"고 콕 집은 사례는 찾지 못했다. 그러나 맥락 손실과 엉뚱한 맥락 주입은 위처럼 보고돼 있다.

## 기본 기능과 겹침

Claude Code에는 이미 다음 기능이 있다. [출처](https://code.claude.com/docs/en/costs)
- **자동 요약**: 한계에 가까워지면 오래된 대화를 요약한다. 요약 때 무엇을 남길지 지시할 수도 있다.
- **오래된 도구 결과 지우기**와 **프롬프트 캐시**(같은 앞부분을 다시 보낼 때 싸게 처리). 구독은 캐시 수명이 1시간이다.
- **MCP 도구 설명 지연 로딩**: 기본으로 켜져 있다.
- **PreToolUse 훅**: 도구 출력을 미리 걸러낸다. 예를 들어 테스트 결과에서 실패만 남긴다. 공식 문서가 직접 권하는 방법이다.
- **서브에이전트 위임**: 긴 로그는 서브에이전트가 읽고 요약만 돌려준다.

겹치는 정도와 충돌 지점은 이렇다.
- 자동 요약과는 **직접 부딪힌다**(#3998). 두 장치가 각자 대화 길이를 다르게 세기 때문이다.
- 프롬프트 캐시는 Headroom도 의식한다. 기본 모드가 `cache`다. 이 모드는 새로 들어온 부분만 압축하고 앞부분은 건드리지 않는다. 캐시 적중 96~97%라는 숫자는 모두 자체 보고다. [출처](https://docs.headroomlabs.ai/docs/proxy)
- 공식 기능(훅·서브에이전트·지연 로딩)은 출력을 "안 들이거나 줄여서 들이는" 방식이다. Headroom은 이미 들어온 내용을 "보내기 직전에 줄이는" 방식이다. 서로 겹치는 부분이 크다.

## 저장소 상태

- 별 7.49만 개, 포크 5.8천 개, 커밋 3,209개. [출처](https://github.com/headroomlabs-ai/headroom)
- 최근 릴리스: v0.40.0(10/6), v0.39.1(9/26), v0.38.0(9/21). [출처](https://github.com/headroomlabs-ai/headroom/releases)
- 열린 이슈 197개, 열린 PR(코드 수정 제안) 253개.
- 눈여겨볼 열린 이슈:
  - 도커 이미지가 관리자(root) 권한으로 돈다(#3569).
  - 프록시가 3~4분 멈췄다가 502 오류를 낸다(#3259).
  - Bedrock 경로의 404 오류가 Claude Code 자동 모드를 깬다(#1589).
  - [출처](https://github.com/headroomlabs-ai/headroom/issues?q=is%3Aissue+is%3Aopen+sort%3Acomments-desc)
- 해커뉴스나 레딧의 독립 토론은 검색으로 찾지 못했다.

## 대안 비교

| 방법 | 성격 | 구독 토큰 경유 | 비고 |
|---|---|---|---|
| Headroom 프록시·wrap | 보내기 직전 압축 | 거침 | 위 쟁점 전부 |
| Headroom MCP만 | 모델이 원할 때 압축 도구를 부름 | 안 거침 | 모델이 부르지 않으면 효과 없음 |
| RTK | 명령 출력 거르기(훅) | 안 거침 | 블로그에서 절감 대부분(13.3억)이 이쪽. 자동 허용 관련 보안 우려가 언급됨 [출처](https://andrewpatterson.dev/posts/token-savings-rtk-headroom/) |
| Claude Code 공식 훅·서브에이전트 | 출력을 줄여 들이기 | 안 거침 | 추가 설치 없음 |

기존 "OmniRoute" 문서에서 다룬 로컬 프록시 경유 문제가 Headroom 프록시에도 그대로 적용된다.

## 우리 쪽 적용

이 절은 **제안일 뿐 결정이 아니다**.

**추천: 쓰지 않는다. 아이디어만 참고한다.** 이유는 넷이다.
1. **표식 규칙과 충돌한다.** `wrap`은 각 프로젝트에 `.claude/settings.local.json`, 세션 시작 훅, `.headroom_wrap_*.json` 파일을 만든다. ohmyPM은 다른 프로젝트에서 `ohmypm/` 폴더와 표식 블록만 건드린다는 규칙이 있다. 프로젝트 40개에 이 파일들이 퍼지면 규칙이 깨진다.
2. **헤드리스와 맥스 구독 조합이 가장 애매한 영역이다.** 헤드리스 호출을 대량으로 프록시에 태우면 약관 회색 지대에 정면으로 들어간다. 계정 제재의 대가가 절감 효과보다 크다.
3. **비용 계산이 맞지 않을 수 있다.** 우리는 토큰 단가가 아니라 맥스 세션 한도로 비용을 따진다. 구독 요청은 캐시를 우선하는 모드로 돈다. 그래서 20% 절감이 세션 한도 절약으로 그대로 이어질지 근거가 없다.
4. **윈도우 환경 이슈와 조용한 실패가 있다.** 프록시가 죽으면 알리지 않고 직접 연결로 넘어간다. 무인으로 도는 헤드리스 호출에는 나쁜 성질이다.

**대신 해 볼 만한 것(우리 스스로 만드는 범위)**
- 공식 PreToolUse 훅으로 긴 로그나 테스트 출력을 미리 거르는 작은 훅을 둔다. 우선은 ohmyPM 자기 프로젝트 범위에서만 시험한다.
- ohmyPM이 헤드리스로 넘기는 입력을 정리한다. 특히 JSON 덩어리, 검색 결과, 로그는 보내기 전에 ohmyPM 코드에서 직접 줄인다. "JSON은 많이 줄어든다"는 Headroom의 관찰 자체는 참고할 만하다.
- 시험할 거라면 범위를 좁힌다. API 키를 쓰는 별도 시험 환경에서 MCP 방식(`headroom mcp install`)만 한 프로젝트에 붙인다. 텔레메트리는 `HEADROOM_OFFLINE=1`로 끈다. 같은 작업을 압축 있이/없이 돌려 결과를 비교한다. 사용자 범위(~/.claude) 설치는 하지 않는다. 헤드리스 호출 전체에 실리기 때문이다.

**보류 안건의 재검토 조건(제안)**: 아래 둘 중 하나가 생기면 다시 본다.
- Anthropic이 "로컬 프록시 경유 구독 사용"이 허용되는지 명시한다.
- 독립된 제3자가 압축 있이/없이 비교한 측정을 공개한다.

이 조건을 그대로 쓸지는 사용자와 정해 `docs/`에 적어야 한다.

## 확인 못 한 것

- 내 컴퓨터 안에서 본인 구독 토큰을 프록시로 흘려보내는 것이 약관의 "중계"에 해당하는지. Anthropic의 명시적 설명을 찾지 못했다.
- 구독 요청에 실제로 어떤 압축이 걸리는지. 압축 정책 파일(`auth_policy.py`)에는 분류 코드만 있었다. 제3자 요약은 "OAuth 요청은 원본 그대로 복원 가능한 압축만 한다"고 했다. 그러나 코드상 Claude Code 요청은 "OAuth"가 아니라 "구독"으로 분류된다. 그래서 그 설명이 Claude Code에 적용되는지 알 수 없다. [출처](https://instagit.com/chopratejas/headroom/what-authentication-modes-headroom-supports-llm-providers.md)
- 맥스 구독에서 세션 한도가 실제로 얼마나 덜 닳는지. 측정 자료가 없다.
- 비콘이 보내는 정확한 필드 목록과 수집 서버 주소.
- `wrap`이 Claude Code에 넣는 `DO_NOT_TRACK`이 프록시 자신의 비콘도 끄는지.
- #3998 수정이 10/6에 나온 v0.40.0에 들어갔는지, 그 뒤 버전에 들어가는지.
- 원본 복구용 보관소의 위치와 보관 기한 기본값.
- 별 7.49만 개가 자연스럽게 늘어난 것인지. 증가 속도는 확인하지 못했다.
- 창업자의 "사용 데이터를 모으지 않는다" 발언과 현재 기본으로 켜진 비콘이 엇갈린다. 시점 차이인지는 확인하지 못했다.
- 압축 탓에 모델이 틀린 답을 냈다고 특정한 독립 사례는 찾지 못했다. 위 사례들은 맥락 손실과 연결 오류 쪽이다.
