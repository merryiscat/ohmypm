# Claude Code에서 쓰는 모델 — 고르는 법·한도·단가

2026-10-10 공식 문서 조사 기준 · Claude Code v2.1.293 시점 문서 · [모델 설정 문서](https://code.claude.com/docs/en/model-config)

## 핵심 요약
**지금 Claude Code의 기본 모델은 Opus 5.5이고, 생각의 깊이(effort)는 기본이 '중간'이다. 맥스 요금제에서 Fable은 주간 한도의 절반까지만 쓸 수 있다.**

- **별칭:** `opus`·`sonnet`·`haiku`·`fable`은 각각 Opus 5.5·Sonnet 5.5·Haiku 5.5·Fable 5.1로 풀린다(Anthropic 직접 연결 기준).
- **값:** 100만 토큰당 입력/출력 기준 Fable 5.1 $10/$50, Opus 5.5 $4/$20, Sonnet 5.5 $2/$10, Haiku 5.5 $0.10/$0.50.
- **한도:** 맥스는 5시간 창과 주간 한도 두 가지. 숫자는 공개되지 않았고, Opus가 Sonnet보다 한도를 "몇 배" 빨리 쓴다는 정도만 공개돼 있다.
- **우리 쪽 판단(제안):** 헤드리스 호출에 effort를 명시하고, 가벼운 작업은 Haiku 5.5로 더 내리는 것을 시험해 볼 만하다.

## 고를 수 있는 모델
`/model` 명령이나 `--model` 옵션에 아래 별칭을 쓴다. 별칭은 시간이 지나면 새 버전으로 자동으로 바뀐다. 버전을 고정하려면 `claude-opus-5-5`처럼 전체 이름을 쓴다. [출처](https://code.claude.com/docs/en/model-config)

- `opus` → Opus 5.5. 복잡한 추론용.
- `sonnet` → Sonnet 5.5. 일상 코딩용.
- `haiku` → Haiku 5.5. 단순·빠른 작업용.
- `fable` → Fable 5.1. 가장 어렵고 오래 걸리는 작업용. 어떤 요금제에서도 기본값이 아니라 직접 골라야 한다.
- `best` → Fable을 쓸 수 있으면 Fable, 아니면 Opus.
- `opusplan` → 계획 모드(plan mode, 실행 전에 계획만 세우는 단계)에서는 Opus, 실행할 때는 Sonnet.
- `default` → 별칭이 아니라 "지정 해제". 계정 기본값으로 돌아간다.

별칭이 언제 바뀌었는지도 문서에 있다. Opus 5.5는 v2.1.280, Sonnet 5.5는 v2.1.284, Haiku 5.5는 v2.1.293부터 기본 연결이다. [출처](https://code.claude.com/docs/en/model-config)

## 기본 모델과 지정 순서
**기본 모델:** 프로·맥스·팀·엔터프라이즈와 API 키 사용자 모두 Opus 5.5다. 마이크로소프트 Foundry만 Sonnet 4.5. [출처](https://code.claude.com/docs/en/model-config)

**우선순위**(위가 이긴다):
1. 세션 중 `/model <이름>`
2. 시작할 때 `claude --model <이름>`
3. 환경 변수 `ANTHROPIC_MODEL`
4. 설정 파일(settings.json)의 `"model"`
5. 새 세션 기본값 `ANTHROPIC_DEFAULT_MODEL`

- `/model` 선택 화면에서 Enter는 "바꾸고 기본값으로 저장", `s`는 "이번 세션만"이다.
- 다시 이어 연 세션은 그 대화에 기록된 모델을 그대로 쓴다.
- 별칭이 가리키는 모델을 바꾸려면 `ANTHROPIC_DEFAULT_OPUS_MODEL`·`_SONNET_MODEL`·`_HAIKU_MODEL`·`_FABLE_MODEL`을 쓴다. 이 중 HAIKU 변수는 백그라운드 작업 모델도 정한다.

[출처](https://code.claude.com/docs/en/model-config)

## 추론 강도(effort)
effort는 "얼마나 깊이 생각하고 답할지"를 정하는 단계다. 높을수록 품질이 오르고 토큰(=한도)도 더 쓴다.

- **단계:** `low` → `medium` → `high` → `xhigh` → `max`. 5.5 세대와 Fable은 다섯 단계 모두 지원한다.
- **Claude Code 기본값:** Opus 5.5·Sonnet 5.5·Haiku 5.5는 `medium`, 그 밖의 모델은 대부분 `high`(Opus 4.7만 `xhigh`). [출처](https://code.claude.com/docs/en/model-config)
- **바꾸는 법:** `/effort`, `--effort`, 환경 변수 `CLAUDE_CODE_EFFORT_LEVEL`, 설정의 `effortLevel`(모델별은 `modelSettings`), 스킬·서브에이전트의 `effort` 항목.
- **우선순위:** 환경 변수·옵션·`/effort` → 저장된 설정 → 모델 기본값.
- **생각 끄기:** Opus 5.5·Sonnet 5.5·Haiku 5.5·Fable은 생각 기능을 끌 수 없다. 비용을 줄이려면 effort를 낮춘다. [출처](https://code.claude.com/docs/en/costs)
- **울트라코드(ultracode):** effort 단계가 아니라 별도 스위치다. 켜면 큰 작업을 여러 에이전트 작업 흐름으로 나눠 돌린다. `--effort ultracode`는 `xhigh`로 시작한다.

## 빠른 모드와 1M 문맥
### 빠른 모드(fast mode)
같은 Opus를 최대 2.5배 빠르게 돌리는 설정이다. 모델이 바뀌는 것이 아니라 비용을 더 내고 속도를 사는 방식이다. [출처](https://code.claude.com/docs/en/fast-mode)

- **지원:** Opus 5.5·Opus 5·Opus 4.8만. Sonnet·Haiku·Fable은 안 된다.
- **단가:** Opus 5.5 기준 $8/$40로, 일반 단가의 2배.
- **요금제 사용자 주의:** 프로·맥스에서는 **구독 한도에서 빠지지 않고 사용량 크레딧(별도 결제)에서만** 나간다. 크레딧을 켜 두지 않으면 쓸 수 없다.
- **켜는 법:** `/fast`. 대화 중간에 켜면 그때까지의 대화 전체를 빠른 모드 단가로 한 번 다시 읽으므로, 켤 거면 시작할 때 켠다.

### 1M 문맥
문맥(context)은 모델이 한 번에 볼 수 있는 분량이다. 1M 토큰은 약 55만 단어다. [출처](https://platform.claude.com/docs/en/about-claude/models/overview)

- Fable 5.1·Fable 5·Opus 4.7 이후·Sonnet 5 이후·Haiku 5.5는 **기본이 1M**이라 따로 켤 것이 없다.
- Opus 4.6·Sonnet 4.6만 `[1m]` 접미사가 필요하다.
- 1M 모델은 약 967K 토큰에서 자동 요약(auto-compact)이 일어난다. 200K로 줄이려면 `CLAUDE_CODE_DISABLE_1M_CONTEXT=1`.

[출처](https://code.claude.com/docs/en/model-config)

## 맥스 요금제 한도
### 공개된 사실
- **두 가지 한도:** 5시간마다 초기화되는 세션 한도와, 계정마다 정해진 시각에 초기화되는 주간 한도가 있다. [출처](https://support.claude.com/en/articles/11049741-what-is-the-max-plan)
- **배수:** 맥스 5x는 프로의 5배, 20x는 20배. 이 배수는 세션 한도 기준이다. [출처](https://support.claude.com/en/articles/11049741-what-is-the-max-plan)
- **공유:** 한도는 claude.ai 채팅과 Claude Code가 함께 쓴다. IDE 사용도 포함된다. [출처](https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan)
- **Fable:** 맥스에 포함되며 **주간 한도의 50%까지** 추가 비용 없이 쓴다. 다른 모델보다 한도를 빨리 쓴다. 넘으면 크레딧으로 계속 쓰거나 모델을 바꾼다. 2026-09-02 갱신 문서 기준. [출처](https://support.claude.com/en/articles/15424964-claude-fable-models-on-your-plan)
- **모델별 소모 속도:** "Opus는 한 번 주고받을 때 Sonnet보다 몇 배 더 들고, Sonnet은 Haiku보다 더 든다." 정확한 배수는 공개하지 않았다. [출처](https://support.claude.com/en/articles/14552983-models-usage-and-limits-in-claude-code)
- **한도에 걸렸을 때:** 세션·주간 한도는 모든 모델 공통이라 모델을 바꿔도 풀리지 않는다. "Opus 한도"처럼 모델별 문구가 뜬 경우에는 다른 계열로 바꾸면 계속 쓸 수 있다. [출처](https://code.claude.com/docs/en/costs)
- **확인:** `/usage`에서 남은 한도와, 스킬·서브에이전트·MCP별 사용 비중을 볼 수 있다.

### 확인 못 한 것
- 5시간·주간 한도의 실제 수치(메시지 수·토큰 수). 공식 문서에 없다.
- 모델별 정확한 소모 배수.
- 맥스에 "Sonnet 전용 주간 한도"가 따로 있는지. 제3자 글끼리 엇갈리고, 공식 맥스 문서는 "모든 모델 공통 주간 한도"만 적는다.

## 서브에이전트·스킬·헤드리스
### 서브에이전트
정의 파일 머리말(frontmatter)의 `model:`에 `sonnet`·`opus`·`haiku`·`fable`·전체 이름·`inherit`(메인과 같게)를 쓴다. `effort:`도 따로 지정할 수 있다. [출처](https://code.claude.com/docs/en/sub-agents)

모델 결정 순서:
1. 호출할 때 넘긴 `model`
2. 정의 파일의 `model`
3. 환경 변수 `CLAUDE_CODE_SUBAGENT_MODEL`
4. 메인 대화의 모델

- 모든 서브에이전트를 한 모델로 강제하려면 `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1`을 함께 설정한다.
- 기본 Explore는 Haiku가 아니라 메인 모델을 따른다. 메인이 Fable이면 Explore는 Opus로 돈다.

### 스킬
SKILL.md 머리말의 `model:`은 **그 턴 동안만** 적용되고 다음 프롬프트에서 원래 모델로 돌아온다. `effort:`도 지정할 수 있지만, 턴이 끝나면 풀리는지는 문서에 명시돼 있지 않다. [출처](https://code.claude.com/docs/en/skills)

### 헤드리스(`claude -p`)
- `claude -p --model sonnet --effort low "..."`처럼 옵션으로 지정한다. `--effort`는 그 실행에만 적용되고 저장되지 않는다.
- `--fallback-model sonnet,haiku`를 쓰면 주 모델이 과부하·사용 불가일 때 순서대로 바꿔 시도한다(최대 3개, 그 턴만).
- `--max-budget-usd`로 예상 비용 상한을 둘 수 있다. 다만 이 값은 Claude Code가 정가로 계산한 추정치다.

[출처](https://code.claude.com/docs/en/cli-reference)

### 안전 필터에 걸렸을 때
Fable·Opus 5.5·Sonnet 5.5는 안전 분류기가 있다. 생물학·사이버보안 내용으로 걸리면 Claude Code가 다른 모델로 자동으로 다시 돌린다(예: Opus 5.5의 사이버보안 건 → Opus 4.8). 그 뒤 세션은 바뀐 모델로 계속된다. [출처](https://code.claude.com/docs/en/model-config)

## 최신 라인업 비교
단가는 API 정가이며, 100만 토큰당 입력/출력이다. 요금제 사용자는 직접 내지 않지만 한도 소모의 상대 크기를 가늠하는 데 쓴다. [출처](https://platform.claude.com/docs/en/about-claude/models/overview)

| 모델 | 성격 | 단가 | 속도 | API 기본 effort |
|---|---|---|---|---|
| Fable 5.1 | 어려운 추론·장시간 에이전트 작업 | $10 / $50 | 느림 | high |
| Opus 5.5 | 장시간 코딩·지식 작업, 현재 기본 추천 | $4 / $20 | 보통 | medium |
| Sonnet 5.5 | 속도와 지능의 균형 | $2 / $10 | 빠름 | high |
| Haiku 5.5 | 분류·추출·라우팅 같은 대량 작업 | $0.10 / $0.50부터 | 가장 빠름 | medium |

- 네 모델 모두 1M 문맥, 최대 출력 128K, 지식 기준 시점 2026년 6월.
- Haiku 5.5는 프롬프트가 10만 토큰을 넘으면 $0.50/$2.50로 오른다.
- 캐시 읽기는 Fable 5.1이 입력가의 2.5%, Opus 5.5·Sonnet 5.5가 5%, 그 밖은 10%다. 배치 처리는 50% 할인.
- Opus 5.5는 이전 Opus 5($5/$25)보다 싸다. 같은 Opus라도 세대가 바뀌며 단가가 내려갔다.
- Mythos 5.1은 Fable 5.1과 성능·단가가 같지만, Project Glasswing 참가자만 쓸 수 있다.
- 공식 문서의 첫 추천은 "모르겠으면 Opus 5.5, 그래도 부족하면 Fable 5.1"이다.

참고: Sonnet 5.5의 기본 effort가 API는 `high`인데 Claude Code는 `medium`이다. 쓰는 곳에 따라 기본값이 다르다.

## 우리 쪽 적용
아래는 **제안일 뿐 결정이 아니다.** 적용 여부와 시점은 사용자가 정한다.

### 지금 구조
- 헤드리스 호출은 모두 작업 이름 → 등급 → 모델을 거친다(`src/cc/models.py`). light=haiku, standard=sonnet, heavy=opus(`.env.example`).
- 호출마다 `--model`을 반드시 붙인다. Fable·Mythos는 `ALLOW_FRONTIER_HEADLESS=true`가 아니면 heavy로 내린다.
- 담당 모델은 기본 sonnet, ohmyPM 자기 담당만 opus.
- 비용은 '세션'으로 본다. 1세션 = 맥스 100달러 요금제의 5시간 한도 = API 단가로 약 80달러, 하루 4세션.

### 이번 조사로 달라진 점
- 별칭이 이미 5.5 세대로 넘어갔다. 우리 haiku·sonnet·opus 호출은 코드 수정 없이 Haiku 5.5·Sonnet 5.5·Opus 5.5로 돈다.
- 우리 호출에는 `--effort`가 없다. 그래서 개인 설정에 `effortLevel`이 없으면 세 모델 모두 기본값 `medium`으로 돈다. 개인 설정이 있으면 그 값을 따른다. 2026-09-28 모델 사고와 같은 종류의 빈틈이다.

### 제안
1. **등급별 effort 명시.** 예: light=`low`, standard=`medium`, heavy=`high`. 주간보고처럼 종합 글쓰기는 `high`로 두고, 짧은 댓글은 `low`로 낮춘다. 모델처럼 effort도 개인 기본값에 기대지 않게 된다.
2. **light 등급 범위 재검토.** Haiku 5.5는 Sonnet 5.5의 1/20 단가다. 게시판 댓글·후속 정도는 지금처럼 light가 맞다. 정형 JSON 추출(`model_catalog_extract`)을 light로 내리는 것은, 정확도가 중요한 추출이므로 몇 건을 비교 확인한 뒤에만 고려한다.
3. **모델 추적 목록 갱신.** `.env.example`의 `MODEL_TRACK_CLAUDE`가 아직 Opus 5·Sonnet 5·Haiku 4.5다. Opus 5.5·Sonnet 5.5·Haiku 5.5로 바꾸는 것을 검토한다.
4. **세션 환산값 재점검.** `SESSION_USD=80`은 공식 수치가 아니라 우리 추정이다. Opus 단가가 $5/$25에서 $4/$20로 내려간 만큼 같은 5시간 분량의 달러 환산이 달라졌을 수 있다. CLI가 돌려주는 `cost_usd`도 정가 기준 추정이다. 몇 번 실제 세션을 재서 다시 맞추는 것을 제안한다.
5. **헤드리스에 대체 모델 지정.** `--fallback-model`을 붙이면 과부하 때 배치가 통째로 실패하지 않는다. 예: heavy는 `sonnet`, standard는 `haiku`.
6. **Fable 금지 유지.** Fable은 주간 한도의 절반까지만 쓸 수 있고 소모도 빠르다. 헤드리스 기본 금지는 그대로 두는 것이 맞다.
7. **대화 세션 기본 모델.** 이 PC의 개인 기본이 Fable 5.1이라면 대화 세션도 주간 Fable 몫을 빨리 쓴다. 평소는 Opus 5.5(공식 기본)로 두고, 어려운 작업에서만 `/model fable`로 바꾸는 방식을 검토한다.
8. **빠른 모드는 쓰지 않는다.** 맥스 한도가 아니라 별도 크레딧에서 2배 단가로 나간다. 무인 배치에는 이점이 없다.

## 출처끼리 엇갈린 점
- **Fable 5.1 필요 버전:** 모델 설정 문서는 v2.1.257 이상, 고객센터 문서는 v2.1.255 이상이라고 적는다. [출처](https://code.claude.com/docs/en/model-config) [출처](https://support.claude.com/en/articles/15424964-claude-fable-models-on-your-plan)
- **Sonnet 5.5 기본 effort:** API 문서는 `high`, Claude Code 문서는 `medium`. 서로 다른 제품의 기본값이라 둘 다 맞을 수 있다.
- **맥스의 두 번째 주간 한도:** 제3자 글에서 "Sonnet 전용"과 "Opus 전용"으로 엇갈린다. 공식 문서에서는 확인 못 함.
- **맥스 100달러 = 5x:** 제3자 가격 비교 글에만 있다. 공식 가격표는 이번에 확인 못 함.
