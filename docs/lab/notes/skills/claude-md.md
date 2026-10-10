# CLAUDE.md 잘 쓰는 법

2026-10-10 조사 기준 · Claude Code 2.1.295 · [공식 문서: 메모리](https://code.claude.com/docs/en/memory) · [공식 문서: 모범 사례](https://code.claude.com/docs/en/best-practices)

## 핵심 요약
**CLAUDE.md는 "매번 다시 설명하게 되는 것"만 짧고 구체적으로 적는 파일이다. 길어지거나 가끔만 필요하면 스킬로, 반드시 지켜야 하면 훅으로 옮긴다.**

- **분량:** 파일 하나당 200줄 아래가 공식 권장이다. 길수록 문맥을 먹고 지시를 덜 따른다.
- **쓰는 법:** 확인 가능한 구체적 문장으로, 이유를 붙여서, 강조는 정말 안 지켜지는 한 줄에만.
- **최신 모델:** 지시를 문자 그대로 잘 따르므로, 예전 모델용 "절대·반드시·MUST" 남발은 과하게 적용된다.
- **우리 파일:** 상위 폴더 `project/CLAUDE.md`에 Odin 전용 내용과 OpenAI 단가표가 섞여 모든 프로젝트에 매번 실린다. 먼저 정리할 곳이다.

## 용어 몇 가지
- **문맥(context):** 모델이 한 번에 보는 글 전체. CLAUDE.md는 세션마다 통째로 들어가므로 한 줄 한 줄이 매 요청의 비용이다.
- **스킬(skill):** 필요할 때만 꺼내 읽는 지시서. 평소엔 이름과 한 줄 설명만 문맥에 있다.
- **훅(hook):** 정해진 시점(파일 수정 뒤, 명령 실행 전 등)에 Claude Code가 자동으로 실행하는 스크립트. 모델의 판단과 무관하게 항상 돈다.
- **import:** CLAUDE.md 안에 `@경로`를 쓰면 그 파일 내용을 함께 불러오는 기능.

## 어디서 읽히나
Claude Code는 아래 파일을 모두 이어 붙여 읽는다. 서로 덮어쓰지 않고 **합쳐진다** [출처](https://code.claude.com/docs/en/memory).

- **조직 관리 파일:** Windows는 `C:\Program Files\ClaudeCode\CLAUDE.md`. 개인 설정으로 뺄 수 없다.
- **사용자 전역:** `~/.claude/CLAUDE.md`. 내 모든 프로젝트에 적용된다.
- **상위 폴더들:** 작업 폴더에서 루트까지 올라가며 있는 `CLAUDE.md`·`CLAUDE.local.md`를 시작할 때 전부 읽는다. 루트 쪽이 먼저, 작업 폴더 쪽이 나중에 들어간다.
- **프로젝트:** `./CLAUDE.md` 또는 `./.claude/CLAUDE.md`. 저장소에 올려 팀과 공유한다.
- **개인 프로젝트 메모:** `./CLAUDE.local.md`. 같은 폴더의 CLAUDE.md 뒤에 붙는다. `.gitignore`에 넣는다.
- **하위 폴더:** 하위 폴더의 CLAUDE.md는 시작 때가 아니라, Claude가 그 폴더의 파일을 읽거나 고칠 때 불러온다.

알아둘 동작 [출처](https://code.claude.com/docs/en/memory):

- 두 지시가 충돌하면 Claude가 **아무 쪽이나** 고를 수 있다. 우선순위 규칙이 없다.
- 줄 단위 HTML 주석(`<!-- ... -->`)은 문맥에 넣기 전에 지워진다. 사람용 메모를 토큰 없이 남길 수 있다.
- 4MiB를 넘는 파일은 건너뛴다. 200줄을 넘으면 시작 화면과 `/status`에 경고가 뜬다.
- `/compact`(대화 압축) 뒤에도 프로젝트 루트 CLAUDE.md는 디스크에서 다시 읽어 넣는다.
- 지금 무엇이 실렸는지는 `/context`의 Memory files 목록으로 확인한다.

## 관련 기능
### import(`@경로`)
- 상대 경로는 **그 CLAUDE.md 파일 기준**이다. 최대 4단계까지 연쇄로 불러온다 [출처](https://code.claude.com/docs/en/memory).
- 정리에는 좋지만 **문맥은 줄지 않는다.** import한 파일도 시작할 때 전부 실린다.
- 백틱으로 감싼 `` `@README` ``는 불러오지 않고 글자로만 남는다.
- 프로젝트 밖 파일을 import하면 처음 한 번 승인 창이 뜬다. 사용자 전역 파일의 import는 승인 없이 읽는다.

### `.claude/rules/` 폴더
- 주제별 파일로 지시를 나눈다. `paths:` 머리말이 없으면 CLAUDE.md처럼 항상 실린다 [출처](https://code.claude.com/docs/en/memory).
- `paths: ["src/api/**"]`처럼 경로를 지정하면 그 파일을 만질 때만 실린다. 일부 폴더에만 해당하는 규칙에 맞다.
- 사용자 전역 `~/.claude/rules/`도 있다. 모든 프로젝트에 적용된다.

### 자동 메모리(auto memory)
- 사용자가 아니라 **Claude가 직접 쓰는** 노트다. 위치는 `~/.claude/projects/<프로젝트>/memory/` [출처](https://code.claude.com/docs/en/memory).
- 목차 파일 `MEMORY.md`의 앞 200줄 또는 25KB까지만 매 세션 실린다. 세부 노트 파일은 필요할 때 읽는다.
- CLAUDE.md에 이미 적힌 내용과 코드에서 알 수 있는 내용은 저장하지 않는다.
- "기억해 둬"라고 하면 자동 메모리로, "CLAUDE.md에 추가해"라고 하면 CLAUDE.md로 간다.

### AGENTS.md와의 관계
AGENTS.md는 Codex 등 다른 코딩 도구가 쓰는 지시 파일이다. Claude Code 2.1.277부터 직접 읽는다 [출처](https://code.claude.com/docs/en/memory).

- **기본값:** 작업 폴더나 그 위에 `CLAUDE.md`(또는 `CLAUDE.local.md`)가 하나라도 있으면 **AGENTS.md는 읽지 않는다.** CLAUDE.md가 없을 때만 AGENTS.md를 읽는다.
- 사용자 전역 `~/.claude/CLAUDE.md`는 이 판단에 들어가지 않는다.
- 둘 다 쓰려면 CLAUDE.md 첫 줄에 `@AGENTS.md`를 import하거나, `/config`의 Project instructions를 `claude-md-and-agents-md`로 바꾼다.
- Windows에서는 심볼릭 링크 대신 `@AGENTS.md` import가 권장된다.

## 넣을 것과 뺄 것
공식 문서의 기준 질문은 하나다. **"이 줄을 지우면 Claude가 실수할까?" 아니면 지운다** [출처](https://code.claude.com/docs/en/best-practices).

### 넣을 것
- Claude가 추측할 수 없는 명령어(빌드·테스트·서버 재기동)
- 기본값과 다른 코드 스타일 규칙
- 저장소 관례(브랜치 이름, 커밋 메시지 형식)
- 이 프로젝트만의 구조 결정
- 개발 환경의 특이점(필요한 환경 변수, 셸 차이)
- 자주 걸려 넘어지는 함정

### 뺄 것
- 코드를 읽으면 알 수 있는 것(폴더 구조 설명, 파일별 설명)
- 언어의 표준 관례, "깔끔하게 짜라" 같은 당연한 말
- 상세한 API 문서(링크만 남긴다)
- 자주 바뀌는 정보
- 긴 설명이나 튜토리얼

### 언제 추가하나
공식 문서는 이런 때 추가하라고 한다 [출처](https://code.claude.com/docs/en/memory).

- Claude가 같은 실수를 두 번째 할 때
- 같은 정정을 지난 세션에 이어 또 입력할 때
- 새로 온 사람에게도 똑같이 설명해야 할 내용일 때

## 잘 쓰는 문장
- **확인 가능하게:** "코드를 잘 정리해" 대신 "API 처리 코드는 `src/api/handlers/`에 둔다" [출처](https://code.claude.com/docs/en/memory).
- **이유를 붙여서:** "말줄임표 금지"보다 "음성 합성기가 읽으므로 말줄임표를 쓰지 않는다"가 더 잘 통한다 [출처](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices).
- **하지 말 것보다 할 것:** "마크다운 쓰지 마" 대신 "문단으로 이어지는 글로 써" [출처](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices).
- **제목과 목록으로 묶기:** 빽빽한 문단보다 따르기 쉽다 [출처](https://code.claude.com/docs/en/memory).
- **강조는 한 줄에만:** 계속 무시되는 한 줄에만 "IMPORTANT"를 붙인다. 여러 줄을 강조하면 어느 것도 눈에 띄지 않는다 [출처](https://code.claude.com/docs/en/best-practices).
- **충돌 점검:** 파일끼리 어긋나는 지시는 주기적으로 지운다. `/doctor prompt-audit`가 낡은 지시, 없는 파일 경로, 서로 다른 지시를 찾아 고칠 안을 낸다(파일은 바꾸지 않음) [출처](https://code.claude.com/docs/en/memory).

## 스킬과 훅으로 옮길 것
CLAUDE.md는 **강제가 아니라 참고 문맥**이다. 모델이 따르려 하지만 보장되지 않는다 [출처](https://code.claude.com/docs/en/memory).

- **반드시, 매번 지켜야 하는 것 → 훅이나 권한 설정.** "`.env` 수정 금지"를 CLAUDE.md에 쓰면 부탁이고, `PreToolUse` 훅(도구 실행 직전 검사)으로 막으면 강제다 [출처](https://code.claude.com/docs/en/features-overview).
- **여러 단계 절차, 가끔 필요한 참고 자료 → 스킬.** 배포 순서, 외부 서비스 설정 방법 같은 것. 평소엔 설명 한 줄만 문맥에 있다 [출처](https://code.claude.com/docs/en/features-overview).
- **일부 폴더에만 해당 → 경로 지정 rules나 하위 폴더 CLAUDE.md** [출처](https://code.claude.com/docs/en/memory).
- **개인 취향 → 사용자 전역 파일.** 프로젝트 파일에 넣지 않는다 [출처](https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more).
- **응답 길이·말투 → 출력 스타일(output style).** 끌 수도 있는 응답 형식은 CLAUDE.md보다 이쪽이 맞다 [출처](https://code.claude.com/docs/en/features-overview).

공식 문서의 "늘려 가는 순서"도 같은 기준이다 [출처](https://code.claude.com/docs/en/features-overview).

- 같은 관례를 두 번 틀림 → CLAUDE.md
- 같은 요청문을 계속 입력함 → 사용자가 부르는 스킬
- 같은 절차를 세 번째 붙여 넣음 → 스킬
- 묻지 않아도 매번 일어나야 함 → 훅
- 다른 저장소에도 같은 설정이 필요함 → 플러그인

## 최신 모델과 강한 말투
**공식 안내는 있다. 다만 "Fable 5.1·Opus 5.5에서 대문자 MUST가 품질을 떨어뜨린다"를 그 모델 이름으로 직접 적은 문장은 찾지 못했다.** 확인한 것은 아래와 같다.

- **세대 전반:** Opus 4.5·4.6부터 시스템 프롬프트에 더 민감하다. "CRITICAL: You MUST use this tool when..."은 과하게 발동하므로 "Use this tool when..."처럼 보통 말투로 낮추라고 한다 [출처](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices). 이 안내는 Fable 5.1과 Opus 5.5를 포함한 "현재 모델" 문서에 그대로 실려 있다.
- **Fable 5:** 지시를 잘 따르므로 행동을 하나하나 나열하지 않아도 짧은 지시로 충분하다. 예전 모델용 스킬은 지나치게 처방적이라 출력 품질을 떨어뜨릴 수 있으니 다시 보라고 한다. 이유를 함께 주면 더 잘한다 [출처](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5).
- **Fable 5.1:** "글머리표 쓰지 마" 같은 서식 금지 규칙은 예전 모델의 과한 서식을 누르려던 것이다. 5.1은 오히려 서식을 덜 쓰므로 지우거나 "언제 쓰는지"로 바꾸라고 한다 [출처](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1).
- **Opus 5.5:** 전용 안내 페이지에는 강한 말투에 관한 별도 문장이 없다 [출처](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5).
- **Claude Code 내장 점검 지침:** `/doctor prompt-audit`가 쓰는 내장 `claude-api` 스킬의 `prompt-audit.md`(2.1.295, 공개 웹 주소 없음)는 이렇게 적는다. 현재 모델은 지시를 더 문자 그대로 따르므로, 예전 모델용 강조(MUST·NEVER·CRITICAL 남발)는 과잉 발동과 경직된 행동을 부른다. 여러 줄이 모두 "중요"면 표시가 정보를 잃고, 불안한 말투의 프롬프트는 조심스럽고 얼버무리는 응답을 낳는다. 반대로 "가능하면 ~해" 같은 느슨한 말은 덜 해도 된다는 허락으로 읽힌다.
- 같은 지침의 예외: 이유가 있는 실제 제약(데이터 규칙, 사용자의 확정 선호)은 금지문이어도 남긴다. 문제는 근거 없이 겁주는 말투다.

정리하면, **규칙 자체가 아니라 근거 없는 강조와 남발이 문제**다. 이유를 한 줄 붙이고 보통 말투로 쓰는 것이 권장 방향이다.

## 지금 우리 파일 점검
아래는 2026-10-10에 실제 파일을 읽고 짚은 것이다. 이 PC에서 `C:\Users\minhy\project` 아래 프로젝트를 열면 **전역 파일(45줄) + 상위 파일(84줄) + 각 프로젝트 파일**이 항상 함께 실린다.

### 전역 `~/.claude/CLAUDE.md` (45줄)
**좋은 점**
- 3~8줄 이모지 금지: 대상(응답·코드·화면·커밋), 대안(굵게·CSS·인라인 SVG), 허용 범위(→ 정도)까지 적혀 있다. "하지 말 것"만이 아니라 "대신 할 것"이 있는 좋은 형태다.
- 10~16줄 줄임말 금지: 이유("P0가 프로젝트 번호와 헷갈린다")가 붙어 있다. 공식 권장과 맞다.
- 25~27줄 스킬 설치는 사용자 동의 후: 짧고 이유(서드파티 코드)가 있다.
- 이 세 가지는 사용자의 확정 선호이자 모든 프로젝트 공통이라 전역 자리가 맞다.

**낡았거나 옮길 것**
- **45줄** "llmwiki가 깔린 프로젝트면 `docs/pending.md`": llmwiki는 2026-10-09에 이 PC에서 제거됐다(상위 파일 62줄). 남은 예외는 project_odin뿐이다. 없는 조건을 가리키는 낡은 문장이다.
- **29~39줄** 구글 OAuth 콘솔 절차(11줄): 구글 API를 붙일 때만 필요한 절차다. 모든 세션에 실릴 이유가 없다. 공식 기준상 "가끔 필요한 여러 단계 절차"라 스킬 자리다.
- **18~24줄** skills.sh 검색 방법: 외부 스킬을 찾을 때만 필요하다. 설치 동의 규칙 한 줄만 남기고 나머지는 스킬로 옮겨도 된다(우선순위 낮음).

### 상위 `project/CLAUDE.md` (84줄)
이 파일은 `project` 아래 **모든 프로젝트**에서 시작할 때 실린다. ohmyPM, 유튜브, 게임 프로젝트에서도 마찬가지다.

**좋은 점**
- 3~6줄 언어, 8~9줄 uv, 17~20줄 커밋 관례: 모든 프로젝트 공통이고 짧다.
- 11~15줄 셸 안내: PowerShell에서 `bash`가 WSL로 잡히는 함정과 `.cmd` 동봉 이유가 구체적이다. 공식 "넣을 것"의 "환경 특이점"에 정확히 해당한다. 예시 경로 `secretary_gyuni/scripts/setup-keys.cmd`도 실제로 있다.

**섞인 것: 특정 프로젝트 전용 내용**
- **69~83줄** "프로젝트: Project Odin" 절과 docs 인덱스: Odin 전용이다. 표의 `docs/plan.md`, `src/`, `.env.example`은 `project/` 기준으로는 없고 `project_odin/` 안에 있다. 다른 프로젝트에서 읽으면 "이 저장소의 `src/`"로 오해할 수 있다. `project_odin/CLAUDE.md`에 이미 같은 성격의 docs 인덱스(147줄 부근)가 있다.
- **49~54줄** Odin 모델 매핑: Odin에서만 쓰는 정보다.

**길고 자주 바뀌는 것**
- **22~47줄** OpenAI 단가표와 모델 선택 원칙(26줄): 파일의 약 3분의 1이다. OpenAI를 쓰지 않는 프로젝트(ohmyPM은 Claude Code만 쓴다)에서도 매번 실린다. 단가는 계속 바뀌는 정보라 공식 "뺄 것"에도 해당한다. 판단 원칙은 값지므로 지우지 말고, OpenAI를 다룰 때만 읽히는 스킬로 옮기는 편이 맞다.
- **59~62줄** 킥오프 도구 제거 이력(4줄, 긴 문단): 무엇을 언제 왜 걷어냈는지의 기록이다. 공식 점검 지침은 이런 경과 서술을 "지금 규칙만 남기고 경위는 뺀다"로 본다. 지금 필요한 규칙은 "ohmypm 플러그인·llmwiki·kickoff_pack은 쓰지 않는다" 한 줄이다.

**파일끼리 충돌**
- 상위 파일 22줄은 "2026.09.06 기준" 단가표, `project_odin/CLAUDE.md` 81~86줄은 "2026.04 기준"으로 `gpt-5.4`를 최신 플래그십, `gpt-4.1-mini`를 절약용으로 적었다. Odin에서 작업하면 두 파일이 함께 실려 **서로 다른 모델 안내**가 동시에 보인다. 공식 문서상 이때 Claude는 아무 쪽이나 고를 수 있다.
- 66줄 "CLAUDE.md에는 docs 파일의 인덱스만 남긴다"는 원칙과, 같은 파일이 26줄짜리 단가표를 직접 품은 것이 어긋난다.

**말투**
- "절대 커밋 금지"(20줄), "절대 사용 금지"(38줄), "반드시 `.cmd` 동봉"(15줄)은 모두 이유가 있는 실제 제약이라 문제 삼을 대상이 아니다. 다만 `.env`·API 키 커밋 금지는 "매번 반드시"에 해당하므로, 공식 기준으로는 훅이나 권한 설정으로 강제하는 편이 확실하다.

### ohmyPM `CLAUDE.md` (12줄)
**좋은 점**
- 짧고 구체적이다. 공식 "넣을 것"을 거의 그대로 따른다.
- 8줄 "task 이름을 글자 그대로, TASK_TIER에 먼저 등록": 코드만 봐선 놓치기 쉬운 함정이다.
- 12줄 확인 방법: 테스트 명령과 서버 재기동 명령이 정확히 적혀 있다. 공식 문서가 가장 강조하는 "Claude가 직접 돌려 볼 수 있는 확인 수단"이다.
- 3~4줄은 구조 설명을 직접 쓰지 않고 `docs/` 문서 위치만 가리킨다. import(`@`)를 쓰지 않아 문맥 비용도 없다.
- AGENTS.md 첫 줄에 "Claude는 CLAUDE.md를 읽는다"를 밝혀 두었다. 공식 동작(CLAUDE.md가 있으면 AGENTS.md는 안 읽음)과 맞다.

**다듬을 수 있는 것(우선순위 낮음)**
- 8줄과 11줄에 이유가 반 줄씩 붙으면 더 좋다. 예: 왜 task 이름을 글자 그대로 넘겨야 하는지.

### ohmyPM이 넣는 표식 블록 (`src/install.py` 21~28줄)
**좋은 점**
- 3줄짜리 블록이다. 상세 내용은 `ohmypm/` 폴더에 두고 "질문을 받으면 먼저 읽는다"로 가리키기만 한다. 공식 권장(짧게, 상세는 따로)과 맞다.
- 표식 `<!-- ohmypm:start -->`·`<!-- ohmypm:end -->`는 줄 단위 HTML 주석이라 문맥에 넣기 전에 지워진다. 표식 자체는 토큰을 쓰지 않는다 [출처](https://code.claude.com/docs/en/memory).
- 블록만 지우고 커밋하지 않는 방식이라 사용자 파일을 존중한다.

**확인된 문제**
- **orca 프로젝트에서 블록이 두 번 실린다.** `orca/CLAUDE.md` 5줄이 `@AGENTS.md`를 import하는데, 설치가 CLAUDE.md와 AGENTS.md 양쪽에 블록을 붙였다. 같은 지시가 두 번 들어간다.
- **생길 수 있는 문제.** `_upsert_block`은 CLAUDE.md가 없으면 블록만 든 CLAUDE.md를 새로 만든다. 그 프로젝트에 내용 있는 AGENTS.md만 있었다면, 새 CLAUDE.md가 생기는 순간 Claude Code는 기본값상 **AGENTS.md를 더는 읽지 않는다.** 지금은 해당 프로젝트가 없다(`state`는 양쪽 모두 블록만 있음).
- **다른 도구용 빈 AGENTS.md.** 25개 프로젝트의 AGENTS.md가 블록 크기 그대로인 5줄짜리다(설치가 새로 만든 것으로 보인다). Claude Code는 읽지 않으므로 해는 없다. Codex용으로 의도한 것이면 그대로 둬도 된다.
- 둘째 줄 "작업을 매듭지을 때 state.md 갱신"은 "매번 해야 하는 일"이다. 공식 기준상 확실히 하려면 훅이 맞다. 다만 무엇을 쓸지는 판단이 필요해서 지시문으로 두는 것도 합리적이다. 실제로 잘 지켜지는지 `state.md`를 보고 정할 일이다.

## 고칠 문장 예시
아래는 모두 **제안**이다. 사용자 확인 없이 적용하지 않았다.

**제안 1 · 전역 45줄**
- 지금: 기록처: llmwiki가 깔린 프로젝트면 `docs/pending.md`, 아니면 그 프로젝트 docs의 적절한 문서.
- 바꿀 안: 기록처: 그 프로젝트 `docs/`의 적절한 문서(project_odin은 `docs/pending.md`).

**제안 2 · 상위 파일 69~83줄, 49~54줄**
- 상위 파일에서 두 절을 지우고, Odin 모델 매핑은 `project_odin/CLAUDE.md` 81~86줄의 낡은 "2026.04 기준" 절을 대신하는 자리로 옮긴다.

**제안 3 · 상위 파일 22~47줄**
- 단가표와 선택 원칙을 사용자 스킬(예: `~/.claude/skills/openai-models/SKILL.md`, 설명은 "OpenAI 모델을 고르거나 단가를 따질 때")로 옮긴다.
- 상위 파일에는 한 줄만 남긴다: "OpenAI 모델을 고를 땐 `openai-models` 스킬을 먼저 읽는다(단가가 자주 바뀌어 CLAUDE.md에 두지 않는다)."

**제안 4 · 상위 파일 59~62줄**
- 바꿀 안: "ohmypm 플러그인·llmwiki·kickoff_pack은 이 PC에서 제거됐다. 쓰거나 다시 만들지 않는다(project_odin의 docs 위키 파일은 그 코드가 직접 쓰므로 둔다)."
- 제거 경위는 ohmyPM `docs/plan.md` 같은 기록 문서로 옮긴다.

**제안 5 · 전역 29~39줄**
- OAuth 절차를 사용자 스킬(예: `google-oauth-setup`)로 옮긴다. 개인정보처리방침 페이지 주소 같은 재사용 정보도 스킬 안에 둔다.

**제안 6 · `src/install.py`**
- 블록을 붙이기 전에, CLAUDE.md가 `@AGENTS.md`를 import하면 AGENTS.md 쪽에만 붙인다(orca 중복 해소).
- CLAUDE.md를 새로 만들 때 내용 있는 AGENTS.md가 있으면 첫 줄에 `@AGENTS.md`를 넣는다.

**제안 7 · `.env` 커밋 금지(상위 20줄)**
- 문장은 그대로 두고, `~/.claude/settings.json`의 권한 거부 규칙이나 커밋 전 검사 훅으로 실제로 막는 방안을 검토한다.

## 바꾸지 않을 것
- 이모지 금지, 줄임말 금지, 한국어 응답은 사용자의 확정 선호다. 표현 강도("절대")도 근거가 분명하므로 그대로 둔다.
- 셸 안내(상위 11~15줄)와 ohmyPM 작업 규칙(12줄 전체)은 공식 권장에 맞는 모범 사례다.
- 이 문서의 점검은 내용 판단이다. 실제로 행동이 달라지는지는 고친 뒤 몇 세션을 보고 확인해야 한다. 공식 문서도 "고친 뒤 Claude의 행동이 실제로 바뀌는지 관찰하라"고 한다 [출처](https://code.claude.com/docs/en/best-practices).
