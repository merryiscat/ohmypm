# Image to Code(시안 먼저, 코드 나중) 방식 평가

기준일 2026-10-10 · 핵심 근거: [taste-skill의 image-to-code SKILL.md](https://github.com/Leonxlnx/taste-skill/blob/main/skills/image-to-code-skill/SKILL.md)

## 핵심 요약

**ohmyPM에는 설치하지 않는 편이 낫습니다. 쓸 만한 것은 OpenAI 쪽 스킬에 있던 "시안과 실제 화면을 같은 크기로 찍어 비교하고 보고서로 남기는 검사 단계" 아이디어 하나입니다.**

- Claude Code는 이미지를 직접 만들지 못합니다. 이 방식을 쓰려면 별도 이미지 생성 API를 연결해야 하고, 그 비용은 맥스 요금제 밖에서 따로 나갑니다.
- "시안을 먼저 만들면 결과가 낫다"는 주장을 같은 조건에서 비교해 본 독립 연구나 후기는 찾지 못했습니다. 지금 있는 근거는 만든 쪽의 주장뿐입니다.
- 시안과 코드가 어긋나는 문제를 실제로 다루는 쪽은 OpenAI 스킬입니다. taste-skill은 스스로 점검하는 체크리스트만 있습니다. 그런데 OpenAI 스킬은 2026-09-30에 저장소에서 지워졌습니다.
- 이미 있는 screen-plan과 단계가 다릅니다. screen-plan은 흑백 와이어(구조), 이 방식은 색·질감까지 입힌 시각 시안입니다. 겹치기보다는 screen-plan 뒤에 붙는 단계인데, 그 단계를 자동으로 붙일 만큼 이득이 확인되지 않았습니다.

## 두 원본

같은 이름이지만 서로 다른 두 스킬입니다.

### taste-skill 쪽

- 저장소: `Leonxlnx/taste-skill`. 개인 계정 저장소이고, 포크(남의 저장소를 복제한 것)가 아닌 원본입니다. 2026-02-19에 생겼고, MIT 라이선스입니다. [출처](https://api.github.com/repos/Leonxlnx/taste-skill)
- 별 약 9만 4천 개, 포크 6,418개, 열린 이슈 78개. 마지막 푸시는 2026-10-09입니다. [출처](https://api.github.com/repos/Leonxlnx/taste-skill)
- 위치: `skills/image-to-code-skill/`. 설치 이름은 `image-to-code`이고, 설치 명령은 `npx skills add https://github.com/Leonxlnx/taste-skill --skill "image-to-code"`입니다. [출처](https://github.com/Leonxlnx/taste-skill)
- 이 폴더를 마지막으로 고친 커밋은 2026-04-24(이미지 스킬 이름 정리)입니다. 그 뒤로는 바뀌지 않았습니다. [출처](https://api.github.com/repos/Leonxlnx/taste-skill/commits?path=skills/image-to-code-skill)

### OpenAI 쪽

- 저장소: `openai/role-specific-plugins` 안의 Product Design 플러그인에 들어 있던 `image-to-code` 스킬입니다. 이 저장소는 처음에 `role-based-plugins`라는 이름이었고 2026-06-03에 지금 이름으로 바뀌었습니다. [출처](https://api.github.com/repos/openai/role-specific-plugins/commits)
- **2026-09-30 커밋으로 플러그인이 전부 지워졌고, 지금은 안내문(README) 하나만 남은 빈 저장소입니다.** 커밋 메시지는 "앞으로 올 기여를 위해 자리만 남긴다"이며, 다른 곳으로 옮겼다는 말은 없습니다. [출처](https://api.github.com/repos/openai/role-specific-plugins/commits/7a24b798)
- 이 문서에서 OpenAI 스킬 내용은 지워지기 전 마지막 버전(2026-07-13 커밋 `fe5608d2`)을 읽은 것입니다. [출처](https://raw.githubusercontent.com/openai/role-specific-plugins/fe5608d2/plugins/product-design/skills/image-to-code/SKILL.md)
- OpenAI는 이 플러그인을 2026년 6월에 직무별 플러그인 6종 가운데 하나로 발표했습니다. [출처](https://pulse2.com/openai-codex-introduces-role-specific-plugins-sites-and-annotations-to-expand-beyond-software-development/)

## 하는 일 비교

| 항목 | taste-skill | OpenAI(지워짐) |
|---|---|---|
| 출발점 | 스킬이 시안 이미지를 직접 만듦 | 이미 고른 이미지·스크린샷·시안을 받음 |
| 이미지 생성 | 화면 구역마다 큰 이미지 1장 + 세부 이미지, 흐릿하면 다시 생성 | 사진·삽화 같은 화면 속 그림만 생성 |
| 검사 | 21개 항목 자체 점검 | 브라우저로 찍어 시안과 비교, `design-qa.md` 보고서 |
| 끝내는 조건 | 따로 없음 | 보고서에 "통과"가 적혀야 넘겨줌 |
| 전제 환경 | Codex라고 적혀 있음 | ChatGPT 작업 모드, 클라우드 브라우저, `@Sites` 배포 |

출처: [taste-skill](https://raw.githubusercontent.com/Leonxlnx/taste-skill/main/skills/image-to-code-skill/SKILL.md), [OpenAI](https://raw.githubusercontent.com/openai/role-specific-plugins/fe5608d2/plugins/product-design/skills/image-to-code/SKILL.md)

- taste-skill은 스스로를 "Codex용 웹사이트 image-to-code 스킬"이라고 소개합니다. 설정값 가운데 이미지 생성 적극도(`IMAGE_GENERATION_EAGERNESS`)가 10점 만점에 10입니다. 히어로(첫 화면 큰 영역) 규칙처럼 홍보용 웹사이트에 맞춘 규칙이 많습니다. [출처](https://raw.githubusercontent.com/Leonxlnx/taste-skill/main/skills/image-to-code-skill/SKILL.md)
- OpenAI 스킬은 CSS로 그린 그림이나 손으로 짠 인라인 SVG(코드로 직접 그리는 벡터 그림)로 이미지를 대신하는 것을 금지합니다. 또 기본 아이콘 세트를 그대로 쓰지 말고 시안과 가장 비슷한 무료 아이콘 세트를 찾게 합니다. [출처](https://raw.githubusercontent.com/openai/role-specific-plugins/fe5608d2/plugins/product-design/skills/image-to-code/SKILL.md)
- 훅(특정 시점에 자동으로 실행되는 스크립트), 텔레메트리(사용 기록 전송), 설정 변경은 두 스킬 문서 어디에도 없습니다. 둘 다 지시문(SKILL.md) 중심입니다. 다만 taste-skill 저장소 전체에는 스크립트가 들어 있고, 다른 스킬의 이미지 처리 스크립트에 개발자 PC의 윈도우 경로가 그대로 박혀 있다는 열린 이슈가 있습니다(#113, 2026-09-12). [출처](https://api.github.com/search/issues?q=repo:Leonxlnx/taste-skill+image)

## 1. 시안은 무엇으로

### taste-skill

- 스킬 문서에 이미지 모델·API·환경변수 이름이 하나도 없습니다. 그냥 "이미지 생성"이라고만 씁니다. 이미지 생성 도구가 없을 때 어떻게 하라는 대체 경로도 없습니다. [출처](https://raw.githubusercontent.com/Leonxlnx/taste-skill/main/skills/image-to-code-skill/SKILL.md)
- 실제로는 Codex 안에 들어 있는 이미지 생성 도구(`$imagegen`, gpt-image-2 모델)를 가정한 것으로 보입니다. Codex에서 이미지를 만들면 ChatGPT 요금제 사용량에서 차감되고, 한 번에 일반 대화보다 3~5배 빨리 줄어든다는 제3자 설명이 있습니다. 공식 문서로는 확인하지 못했습니다. [출처](https://codex.danielvaughan.com/2026/04/27/codex-cli-image-generation-gpt-image-2-visual-development-workflows/)

### Claude Code만으로는 안 됨

- Claude는 이미지를 보고 이해하는 것만 하고, 만들지는 못합니다. Anthropic 공식 FAQ에 그렇게 적혀 있다는 인용이 있지만, 원문은 직접 열어 보지 못했습니다. [출처](https://www.blockchain-council.org/claude-ai/no-image-with-claude/)
- 그래서 Claude Code에서 이 방식을 쓰려면 외부 이미지 생성 스킬이나 MCP 서버(Claude에 외부 도구를 붙이는 연결 방식)가 필요합니다. 예로 Gemini 이미지 모델(나노 바나나)을 부르는 스킬과 MCP 서버가 있습니다. 둘 다 `GEMINI_API_KEY`가 필요하고, 무료 등급으로는 쓸 수 없습니다. [출처](https://blog.laozhang.ai/en/posts/nano-banana-claude-code)
- 2026년 초에 만들어진 연결 설정은 모델 이름이 퇴역해서 안 돌아가는 경우가 많다고 합니다(미리보기 모델 2026-06-25 종료, `gemini-2.5-flash-image` 2026-10-02 종료). [출처](https://blog.laozhang.ai/en/posts/nano-banana-claude-code)

### 비용(모두 맥스 요금제 밖에서 따로 나감)

- gpt-image-2로 1024×1536 크기를 만들면 품질별로 장당 약 $0.005 / $0.041 / $0.165입니다. 제3자 정리이며, OpenAI 가격 페이지는 직접 확인하지 못했습니다. [출처](https://www.segmind.com/models/gpt-image-2/pricing)
- Gemini 나노 바나나 2는 1K 크기 장당 약 $0.067로 추정됩니다. [출처](https://blog.laozhang.ai/en/posts/nano-banana-claude-code)
- taste-skill은 구역마다 큰 이미지를 만들고 세부 이미지와 재생성까지 요구합니다. 그래서 한 화면에 이미지 10장 안팎은 쉽게 나옵니다. 이 장수는 스킬 지시를 바탕으로 우리가 셈한 것이고, 실제로 재 본 값은 아닙니다.

## 2. 효과의 근거

- **시안을 먼저 만든 경우와 바로 코드를 짠 경우를 같은 조건에서 비교한 독립 실험·후기는 찾지 못했습니다.**
- 검색에 잡힌 소개 페이지는 대부분 README를 옮겨 적은 것입니다. 예를 들어 UiChemy 페이지는 워드프레스 도구 업체가 자기 제품으로 이어지게 만든 디렉터리 글입니다. 설치 수와 별 수 말고는 품질을 잰 수치가 없습니다. 단, 이미지 생성이 없으면 이 스킬과 잘 맞지 않고, 작은 수정에는 과하다는 한계는 그 페이지도 적어 두었습니다. [출처](https://uichemy.com/design-skills/image-to-code/)
- 간접 근거는 있습니다. Apple의 CHI 2026(사람과 컴퓨터 상호작용 분야 학회) 논문은 대부분의 언어 모델이 디자인이 좋은 화면을 꾸준히 만들어 내지 못한다고 봅니다. [출처](https://machinelearning.apple.com/research/designer-feedback) 2026년 벤치마크(성능 비교 시험)도 모델이 컴파일되면서 시각적으로도 맞는 화면 코드를 안정적으로 만들지 못한다고 보고합니다. [출처](https://arxiv.org/pdf/2602.18548) 즉 "코드부터 짜면 밋밋하다"는 문제 제기는 뒷받침되지만, "시안을 먼저 만들면 풀린다"는 해법은 검증되지 않았습니다.
- 연구 쪽 흐름은 "이미지를 보고 코드로 옮긴 뒤, 렌더링한 화면을 다시 보며 고치는" 시각 피드백 반복 쪽입니다. [출처](https://arxiv.org/pdf/2602.18548), [출처](https://arxiv.org/pdf/2506.06251)

## 3. 어긋남 처리

- **taste-skill**: 화면을 캡처해 비교하는 단계가 없습니다. 흐릿한 부분은 새 이미지를 만들고, 코딩을 마친 뒤 21개 항목을 스스로 점검합니다. 시안과 실제 화면이 얼마나 맞는지는 모델의 눈대중에 맡깁니다. [출처](https://raw.githubusercontent.com/Leonxlnx/taste-skill/main/skills/image-to-code-skill/SKILL.md)
- **OpenAI(지워짐)**: 절차가 구체적입니다. [출처](https://raw.githubusercontent.com/openai/role-specific-plugins/fe5608d2/plugins/product-design/skills/image-to-code/SKILL.md)
  - 시안과 실제 화면을 같은 화면 크기, 같은 상태(마우스 올림·빈 화면 등)로 찍은 뒤에만 비교합니다.
  - 발견한 문제는 `design-qa.md`에 적습니다. 심각한 것부터 중간 것까지는 고치고 다시 찍기를 "통과"가 나올 때까지 반복합니다. 사소한 다듬기는 메모로만 남깁니다.
  - "빌드 성공이나 서버 정상 응답을 브라우저 확인으로 치지 말라", "브라우저를 못 쓰면 '막힘'으로 보고하라"고 못박아 둡니다.
- **OpenAI 공식 사용 안내서**: Playwright(브라우저 자동 조작 도구)로 여러 화면 폭에서 열어 시안과 비교합니다. 기존 디자인 시스템(색·간격·부품 규칙)과 시안이 부딪히면 **디자인 시스템을 우선하고**, 간격·크기만 조금 조정하라고 합니다. [출처](https://learn.chatgpt.com/use-cases/frontend-designs)

## 4. ohmyPM과의 궁합

### screen-plan과의 관계

- screen-plan은 흑백 회색 6단계만 쓰고, 그림자·그라데이션·색을 금지하며, 서로 다른 4개 안을 내고, Playwright로 띄워 사람이 확인하게 합니다(`C:\Users\minhy\.claude\skills\screen-plan\SKILL.md:90-163`).
- 정리하면 screen-plan은 "무엇을 어디에 둘지(구조)", image-to-code는 "어떻게 보일지(시각)"를 다룹니다. 단계가 달라서 정면으로 겹치지는 않습니다. 다만 둘 다 "화면 만들어줘"류 요청에 반응하므로, 둘 다 사용자 범위에 깔면 어느 스킬이 발동할지 엇갈릴 수 있습니다.

### 우리 규칙과 부딪히는 점

- OpenAI 스킬의 "인라인 SVG로 그림 대신 금지"는 우리 글로벌 지침(아이콘은 인라인 SVG 등으로)과 반대 방향입니다.
- taste-skill의 이미지 생성 적극도 10과 히어로·홍보 페이지 중심 규칙은 ohmyPM 같은 관리 화면(대시보드)과 성격이 다릅니다.
- 생성된 시안은 대비(WCAG, 웹 접근성 기준의 글자·배경 명암 차이)를 보장하지 않습니다. 시안을 "정답"으로 삼으면 대비 규칙과 충돌할 수 있습니다. 이 점은 우리 쪽 판단이며, 실제로 재 보지는 않았습니다.

### 헤드리스·비용 측면

- 사용자 범위에 설치하면 40개 프로젝트의 헤드리스 호출 모두에 스킬 설명이 실립니다. 화면 관련 요청마다 외부 이미지 API 호출을 시도할 수 있습니다.
- 그 비용은 세션 단위로 따지는 맥스 요금제 밖에서 API 키로 따로 청구됩니다.
- 화면 내용(프로젝트 이름·상태)이 외부 이미지 API로 나갑니다.

## 우리 쪽 적용

아래는 제안일 뿐 결정이 아닙니다.

- **형태 제안: 아이디어만 참고.** 두 스킬 모두 사용자 범위 설치는 권하지 않습니다. 이유는 세 가지입니다. 이미지 생성 수단이 없어 Claude Code에서는 핵심 단계가 비고, 외부 API 비용과 데이터 반출이 생기며, 효과 근거가 없습니다. OpenAI 쪽은 원본이 이미 지워져 설치할 대상 자체가 없습니다.
- **가져올 아이디어 1 — 비교 검사 단계.** OpenAI의 `design-qa` 방식(같은 크기·같은 상태로 찍어 비교 → 보고서에 통과/막힘 기록 → 심각한 것만 반복 수정)을 screen-plan의 8절 "화면 확인"이나 ohmyPM 화면 개편 절차에 몇 줄로 옮겨 적는 방안입니다. 이미지 생성이 필요 없고, Playwright는 screen-plan이 이미 씁니다.
- **가져올 아이디어 2 — 디자인 시스템 우선.** 시안과 기존 규칙(이모지 금지, 대비, 공용 CSS)이 부딪히면 규칙이 이긴다는 원칙을 그대로 적어 두는 방안입니다.
- **꼭 시각 시안을 써 보고 싶다면: 한 번만 손으로 시험.** ohmyPM 새 화면 하나를 정해 screen-plan으로 구조를 확정합니다. 그 다음 사용자가 이미 쓰는 이미지 도구(예: ChatGPT)로 시안 한 장을 만들어 Claude Code에 넘깁니다. Claude Code는 이미지를 읽을 수 있습니다. 그렇게 만든 결과를 바로 코드를 짠 결과와 나란히 놓고 봅니다. 자동화는 이 비교에서 차이가 보일 때만 검토합니다.
- **보류하는 안의 재검토 조건.** 조건 ① Anthropic이 Claude Code에 이미지 생성 기능을 공식으로 넣을 때, 또는 조건 ② OpenAI가 image-to-code를 다른 저장소에 다시 공개할 때 다시 봅니다. 기록처는 ohmyPM `docs/`의 보류 문서입니다(파일 이름은 확인 못 함).

## 확인 못 한 것

- OpenAI가 2026-09-30에 플러그인을 지운 이유, 그리고 다른 곳(Codex 내장 기능 등)으로 옮겼는지 여부. 커밋 메시지에는 아무 설명이 없습니다.
- 사용자 요청에는 "OpenAI가 자사 저장소에 공개했다"고 되어 있는데, 지금 기준으로는 그 저장소가 비어 있습니다. 공개된 적은 있으나 현재는 없습니다.
- gpt-image-2와 Gemini 이미지 모델 가격은 제3자 정리만 봤습니다. OpenAI·Google 공식 가격 페이지는 직접 열지 못했습니다. Codex에서 이미지를 만들 때 ChatGPT 요금제가 얼마나 차감되는지도 출처끼리 엇갈립니다.
- "Claude는 이미지를 만들지 않는다"는 Anthropic 공식 FAQ 원문은 직접 확인하지 못했습니다. 2026년 초 이후 바뀌었는지도 확인하지 못했습니다.
- taste-skill image-to-code를 실제로 써 본 독립 사용자 후기. 찾은 것은 README를 옮긴 디렉터리 글뿐입니다.
- taste-skill에서 이미지 생성 도구가 없는 Claude Code에 설치했을 때 실제로 어떻게 움직이는지(단계를 건너뛰는지, 멈추는지). 문서에 대체 경로가 없고, 직접 실행해 보지는 않았습니다.
- 열린 이슈 31건 가운데 일부만 읽었습니다(검색 결과가 잘림). 이 스킬에 직접 걸린 심각한 이슈는 보이지 않았지만, 전부 확인한 것은 아닙니다.
