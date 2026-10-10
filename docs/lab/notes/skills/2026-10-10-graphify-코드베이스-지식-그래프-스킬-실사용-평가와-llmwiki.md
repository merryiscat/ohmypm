# Graphify 실사용 평가와 llmwiki와의 차이

기준일 2026-10-10 · 핵심 근거: [Graphify 저장소 README](https://github.com/Graphify-Labs/graphify), [벤치마크 원문](https://github.com/Graphify-Labs/graphify/blob/v8/BENCHMARKS.md)

## 핵심 요약

**Graphify는 코드 구조를 자동으로 다시 뽑는 지도라서, 사람 손으로 쓴 llmwiki보다 덜 낡는다. 하지만 "토큰이 크게 준다"는 독립 검증은 아직 없다. 그리고 설치하면 우리 규칙(남의 프로젝트는 ohmypm/ 폴더와 표식 블록만 건드린다)을 어기는 파일을 만든다. 지금은 전면 도입보다 큰 프로젝트 하나에서 시험해 보는 정도가 맞다.**

- 구조는 질문에 적힌 대로다. 코드는 tree-sitter로 내 컴퓨터 안에서 무료로 읽고, 문서·PDF·이미지는 LLM(대형 언어 모델)이 읽는다.
- 홍보성 숫자(49배, 71배 절감)는 출처가 불분명하거나 한 번 측정한 값이다. 실사용자 이슈에는 "오히려 토큰이 늘었다", "안내 문구만 65만 토큰을 먹었다", "그래프가 낡아서 결국 걷어냈다"는 사례가 있다.
- README 벤치마크는 개발사가 자기 실험 환경에서 돌린 것이다. 그중 두 개(LOCOMO, LongMemEval)는 코드가 아니라 대화 기억을 재는 시험이다. 코드 시험(ERPNext)은 질문이 6개뿐이다.
- 대안으로는 Claude Code 공식 LSP 플러그인(언어 서버를 붙여 정의·참조를 기호 단위로 찾는 기능)이 있다. 우리 규칙과 충돌이 적어 이쪽을 먼저 볼 만하다.

## 무엇을 하나

### 구조

- **코드**: tree-sitter라는 구문 분석기로 파일을 읽어 함수·클래스·호출 관계를 뽑는다. 이 과정에는 LLM이 없고, 코드가 밖으로 나가지 않는다고 README에 적혀 있다. 지원 언어는 README 표 기준 37개다(본문에는 "약 40개"로 적혀 있다). [출처](https://github.com/Graphify-Labs/graphify)
- **문서·PDF·이미지**: "의미 추출" 단계를 거친다. Claude Code 안에서 `/graphify`를 실행하면 지금 쓰는 모델이 처리하고, 명령줄 `graphify extract`로 돌리면 따로 설정한 API 키의 모델이 처리한다. 영상·음성은 내 컴퓨터에서 faster-whisper로 받아쓴다. [출처](https://github.com/Graphify-Labs/graphify)
- **묶기**: Leiden이라는 군집 알고리즘으로 관련 있는 것끼리 묶는다. 임베딩(문장을 숫자 벡터로 바꾸는 것)이나 벡터 DB는 쓰지 않는다. [출처](https://github.com/Graphify-Labs/graphify)
- **신뢰도 표시**: 모든 연결선에 EXTRACTED(코드에 실제로 있음), INFERRED(도구가 추정함), AMBIGUOUS(애매함) 중 하나가 붙는다. [출처](https://github.com/Graphify-Labs/graphify)

### 결과물

`graphify-out/` 폴더에 다음이 생긴다. [출처](https://github.com/Graphify-Labs/graphify)

- `graph.html`: 클릭해서 보는 그래프 화면
- `GRAPH_REPORT.md`: 핵심 개념과 의외의 연결을 정리한 보고서
- `graph.json`: 그래프 전체. 에이전트가 `graphify query`, `path`, `explain` 명령이나 MCP 서버(에이전트에 도구를 붙이는 표준 방식)로 질의한다.
- `--wiki` 옵션을 주면 그래프에서 마크다운 위키(`graphify-out/wiki/`)도 만든다. 즉 llmwiki식 결과물도 선택 기능으로 들어 있다.

### 배경

- 2026-04-05에 Safi Shamsi가 시작했다. Karpathy가 "LLM이 쓰는 위키" 개념을 올린 직후다. 회사(Graphify Labs)는 YC(미국 창업 지원 프로그램) 2026 여름 기수다. [출처](https://braindetox.kr/en/posts/graphify_codebase_knowledge_graph_2026.html)
- 별 개수는 출처마다 다르다. 저장소 화면은 약 12.5만 개, 6~7월 기사는 6.3만~8.8만 개다. 한 리뷰는 별이 늘어난 방식에 의문을 제기한 커뮤니티 반응을 전한다. [출처](https://www.roborhythms.com/graphify-review/)
- 버전이 빠르게 오른다. 7~9월 사이에 0.9.38 → 0.9.53 → 0.9.74가 확인된다. [출처](https://wavect.io/es/blog/graphify-review-codebase-knowledge-graph/)

## 실사용 평가

### 개발사·홍보 성격의 글

- **graphify.com 블로그, Augment Code 글**: 개발사이거나 이 분야 업체의 소개 글이다. 사용법 설명이 중심이다. [출처](https://graphify.com/blog/how-to-give-claude-code-a-code-knowledge-graph) [출처](https://www.augmentcode.com/learn/graphify-knowledge-graph-codebase-skill)
- **roborhythms 리뷰(2026-05-28)**: "71배 절감(12.3만 토큰 → 1,700 토큰)"과 "49배" 숫자로 널리 퍼진 글이다. 그런데 71배를 누가 측정했는지 밝히지 않는다. 49배는 글쓴이가 "여러 출처를 읽고" 종합한 값이다. 직접 해 본 시험도 없다. 다만 단점은 정직하게 적었다(훅이 작동을 멈춤, 그래프가 낡음, 줄 번호 없이 경로만 나옴 등). [출처](https://www.roborhythms.com/graphify-review/)
- **Better Stack 가이드(2026-07-17)**: 직접 돌린 화면이 있다. 질문 하나에서 "약 1.4만 토큰 → 수백 토큰"이 됐다고 적었다. 사례는 한 건이고, 본문과 그림 설명의 숫자가 서로 맞지 않는다. 문서 처리에 LLM을 쓰면서 "모든 처리가 로컬"이라고 쓴 부분도 앞뒤가 안 맞는다. [출처](https://betterstack.com/community/guides/ai/ai-development/graphify-codebase/)

### 독립 평가에 가까운 것

- **Wavect 리뷰(2026-07-16, 9월 재검토)**: "후원받지 않았다"고 스스로 밝혔다. 다만 직접 측정한 숫자는 없고, 문서와 개발사 벤치마크를 읽고 평가했다. 결론은 "2주 시험 운영을 해 볼 근거는 되지만, 투자 대비 효과를 약속하지는 않는다"이다. 그래프가 낡거나 불완전하거나 잡음이 많을 수 있다고 지적했고, 보안 정책 문서가 옛 버전(0.3.x) 기준이라는 점도 짚었다. [출처](https://wavect.io/es/blog/graphify-review-codebase-knowledge-graph/)
- **이슈 #580(2026-04-28)**: 실사용자가 "설치 후 토큰이 오히려 늘었다"고 보고했다. 에이전트가 질문마다 "지시받은 대로 그래프 보고서부터 읽겠다"며 `GRAPH_REPORT.md`를 통째로 읽었기 때문이다. 같은 증상을 겪은 사람이 더 있다. 개발사는 "보고서를 먼저 읽으라"는 지시를 빼는 것으로 고치고 5월 16일에 닫았다. 고친 뒤 실제로 토큰이 줄었는지 보여 주는 숫자는 없다. [출처](https://github.com/Graphify-Labs/graphify/issues/580)
- **이슈 #3435(2026-09-09, 아직 열림)**: 한 저장소의 Claude Code 대화 기록 87개를 분석한 결과다. 훅이 "그래프를 쓰라"는 안내 문구를 8,348번 끼워 넣었고, 이것만 약 65.1만 토큰이었다. 같은 기간 graphify 명령 결과 전체는 약 17.6만 토큰이었다. 안내를 받고 에이전트가 실제로 graphify를 호출한 비율은 약 4%였다. 즉 안내 문구 비용이 그래프 사용량의 3.7배였다. [출처](https://github.com/Graphify-Labs/graphify/issues/3435)
- **이슈 #3718(2026-09-21, 아직 열림)**: 그래프를 만든 뒤 커밋이 21개 더 쌓였는데도, 훅은 계속 "반드시(MANDATORY) graphify query를 먼저 쓰라"고 강요했다. 에이전트는 새 모듈이 없는 낡은 그래프에 질의하느라 호출을 낭비했다. 그러고는 결국 Read·Grep으로 돌아갔다. [출처](https://github.com/Graphify-Labs/graphify/issues/3718)
- **이슈 #578(2026-04-27)**: Claude Code 2.1.117부터 Grep·Glob 도구가 Bash로 합쳐지면서 Graphify 훅이 아무 소리 없이 작동을 멈췄다. 지금은 고쳐졌다. Claude Code가 바뀌면 훅이 같이 깨질 수 있다는 사례다. [출처](https://github.com/Graphify-Labs/graphify/issues/578)
- **다른 팀이 걷어낸 사례(eltmon/overdeck, 2026-05)**: CLAUDE.md에 "작업 시작 때 그래프 요약을 읽으라"고 넣었다. 그런데 요약 파일이 2주 동안 갱신되지 않았고, 그사이 병합이 676번 있었다. 원인은 세 가지였다. `graphify update`가 요약 파일은 다시 만들지 않았고, 출력 폴더가 git에서 제외돼 있었고, 커밋하면 병합할 때마다 graph.json(약 32MB)이 바뀌는 부담이 있었다. 이 팀은 결국 Graphify를 모두 걷어내고 234MB를 되찾았다. [출처](https://github.com/eltmon/overdeck/issues/1408)
- **커뮤니티 비교(codebase-memory-mcp 토론, PR #628)**: C 코드 기준으로 비교했다. 함수 정의를 찾는 능력은 둘이 거의 같았다. 의존 관계 연결 수, 질의응답 점수, 속도는 경쟁 도구가 앞섰다. 경쟁 도구 쪽 저장소에서 나온 결과라 그 점은 감안해야 한다. [출처](https://github.com/DeusData/codebase-memory-mcp/discussions/611)

### 정리

Reddit과 Hacker News의 실사용 글은 이번 검색에서 직접 찾지 못했다. 독립적인 "줄었다" 숫자는 단일 사례 몇 건뿐이다. 반대로 "늘었다·별로였다" 쪽은 이슈 기록에 숫자와 함께 남아 있다.

## 벤치마크 신뢰도

- **누가 돌렸나**: 개발사가 만든 공개 실험 환경에서 개발사가 돌렸다. 비교 대상(mem0, supermemory 등)은 이 환경에 끼워 넣어 같은 모델과 예산으로 돌렸다. 답안 채점과 주 모델은 Kimi K2.6이 맡았다. 두 번째 채점자와의 일치율 90.6%를 공개한 점은 다른 벤치마크보다 성실하다. [출처](https://github.com/Graphify-Labs/graphify/blob/v8/BENCHMARKS.md)
- **LOCOMO, LongMemEval**: 둘 다 긴 대화 기록에서 기억을 찾는 시험이다. 코드베이스 탐색과는 다른 문제다. 결과도 압도적이지 않다. LOCOMO 정답률은 Graphify 45.3%로 supermemory 49.7%보다 낮다. LongMemEval은 일반 벡터 검색과 76%로 같다. 같은 표에서 supermemory의 검색 점수는 "임베딩 차이가 섞였다"고 스스로 단서를 달았다. [출처](https://github.com/Graphify-Labs/graphify/blob/v8/BENCHMARKS.md)
- **ERPNext(코드 시험)**: 질문 6개다. 기준선은 "Read·Grep만 쓰는 에이전트"이고, 여기에 Graphify 도구 하나를 더했다. 핵심 사실을 맞힌 비율이 70.8% → 82.0%가 됐다. 질문 수가 적어 우연 범위를 모르고, 원문도 이를 다루지 않는다. 비용은 질의당 약 14만 토큰이다. 그런데 Read·Grep 기준선과의 토큰 비교가 아니라 "저장소 통째로 넣기" 대비 약 20배라고만 적었다. **Read·Grep보다 토큰이 줄었다는 숫자는 개발사 벤치마크에도 없다.** [출처](https://github.com/Graphify-Labs/graphify/blob/v8/BENCHMARKS.md)
- **시간 절감**: 측정값이 없다. [출처](https://github.com/Graphify-Labs/graphify/blob/v8/BENCHMARKS.md)
- **참고(다른 도구의 논문)**: 비슷한 방식의 codebase-memory-mcp 논문이 있다. 저장소 31개에서 토큰은 10배, 도구 호출은 2.1배 줄었다. 하지만 답의 품질은 83%로, 파일을 직접 탐색하는 에이전트(92%)보다 낮았다. 해당 도구 개발자가 쓴 논문이다. [출처](https://arxiv.org/abs/2603.27277)

## llmwiki와 차이

### 다른 점

- llmwiki(Karpathy의 "LLM Wiki" 방식)는 LLM이 원본을 읽고 **글로 된 요약 페이지**를 써서 쌓아 둔다. 요약을 고치는 것도 LLM 몫이다. [출처](https://www.noze.it/en/insights/llm-wiki/)
- Graphify의 코드 부분은 **구문 분석기가 기계적으로 뽑은 관계표**다. 다시 만드는 데 LLM 비용이 들지 않는다. 바뀐 파일만 다시 처리하고, 커밋 때 자동으로 다시 만드는 git 훅도 있다. 따라서 "문서가 금방 낡는다"는 문제는 코드 부분에서는 llmwiki보다 덜하다. [출처](https://github.com/Graphify-Labs/graphify)
- 답의 형태도 다르다. llmwiki는 "이 모듈은 이런 일을 한다" 같은 설명을 준다. Graphify는 "이 함수를 누가 부르나, A에서 B까지 어떻게 이어지나" 같은 연결 관계를 준다.

### 우리가 llmwiki를 버린 이유가 여기에도 해당하나

- **문서가 금방 낡는다** → 부분적으로 해당한다. 자동 갱신을 연결하지 않으면 그래프도 낡는다(#3718, overdeck 사례). 문서·PDF에서 뽑은 부분과 요약 보고서는 LLM으로 다시 돌려야 해서 llmwiki와 같은 문제를 그대로 안는다. 갱신 기능 자체에도, 지워진 기호가 그래프에 남는 버그가 있었다(#1116, 6월에 고침). [출처](https://github.com/safishamsi/graphify/issues/1116)
- **결국 코드를 다시 읽는다** → 해당한다. Graphify는 "어디를 볼지"만 알려 준다. 기본 출력은 경로뿐이고 줄 번호도 없다. 실제로 고치려면 파일을 읽어야 한다. 낡은 그래프에서는 Read·Grep으로 되돌아갔다는 보고가 있다(#3718). 비슷한 도구의 논문에서도 그래프만으로 답하면 품질이 파일 탐색보다 낮았다. [출처](https://www.roborhythms.com/graphify-review/) [출처](https://arxiv.org/abs/2603.27277)
- **새로 생기는 문제** → 훅이 매번 끼워 넣는 안내 문구 비용(#3435), Claude Code가 바뀌면 훅이 깨지는 문제(#578)는 llmwiki에는 없던 비용이다.

## 설치 시 변경

### 건드리는 것

- **CLAUDE.md 구역**: `graphify claude install`이 CLAUDE.md에 "코드 질문은 graphify query부터 쓰라"는 구역을 쓴다. [출처](https://github.com/Graphify-Labs/graphify)
- **PreToolUse 훅**(도구 실행 직전에 끼어드는 스크립트): 검색과 Read·Glob 직전에 `graphify hook-guard`를 실행해 안내 문구를 넣는다. `--strict`를 주면 세션의 첫 원본 파일 읽기를 막고 그래프로 돌린다. [출처](https://github.com/Graphify-Labs/graphify/issues/578)
- **graphify-out/ 폴더**: 프로젝트 안에 생긴다. 기본으로 git에서 제외된다. 팀이 함께 쓰려면 graph.json과 보고서를 강제로 커밋하라고 권한다. [출처](https://github.com/Graphify-Labs/graphify)
- **질의 기록**: `~/.cache/graphify-queries.log`(사용자 홈 폴더). README 안에서 "모든 질의를 기록한다"는 설명과 "기본은 꺼져 있다"는 설명이 엇갈린다. [출처](https://github.com/Graphify-Labs/graphify)
- **선택 사항**: `graphify hook install`은 git 커밋 훅과 브랜치 전환 훅, graph.json 병합 규칙을 추가한다. `--project`로 설치하면 `.claude/skills/graphify/SKILL.md`가 생긴다. 직접 손본 SKILL.md를 재설치 때 덮어쓴다는 이슈(#2847)도 있다. [출처](https://github.com/Graphify-Labs/graphify/issues?q=is%3Aissue+hook+claude)

### 끄거나 좁히는 법

출처는 모두 [README](https://github.com/Graphify-Labs/graphify)다.

- 전부 제거: `graphify uninstall`. 출력 폴더까지 지우려면 `--purge`를 붙인다.
- Claude Code 연동만 제거: `graphify claude uninstall`
- git 훅 제거: `graphify hook uninstall`
- 강제 모드 끄기: `GRAPHIFY_HOOK_STRICT=0`
- 질의 기록 끄기: `GRAPHIFY_QUERY_LOG_DISABLE=1`
- 업그레이드 후 스킬 자동 갱신 끄기: `GRAPHIFY_NO_AUTO_REFRESH=1`
- 범위 좁히기: 프로젝트 맨 위에 `.graphifyignore`를 둔다(`.gitignore`와 같은 문법). 예를 들어 `*` 다음 줄에 `!src/`, `!src/**`를 쓰면 src만 읽는다.
- 코드만, LLM 없이: `graphify extract <폴더> --code-only`
- 출력 위치 바꾸기: 환경변수 `GRAPHIFY_OUT`. 쓸 수는 있지만 일부 안내 문구가 기본 경로로 잘못 표시되는 이슈가 있었다(#4040, 10월에 닫힘). [출처](https://github.com/Graphify-Labs/graphify/issues/4040)
- README는 프롬프트 캐시(같은 앞부분을 다시 계산하지 않게 저장해 두는 기능)가 깨지지 않도록 graph.json과 graphify-out/을 `.claudeignore`에 넣으라고 권한다.

## 대안 비교

| 도구 | 방식 | 강점 | 약점·주의 |
|---|---|---|---|
| Claude Code 공식 LSP 플러그인 | 언어 서버에 실시간으로 질의 | 공식 지원. 정의·참조를 기호 단위로 찾고, 수정 직후 오류를 알려 준다. 미리 만들어 둘 파일이 없어 낡지 않는다. | 언어별 서버 설치가 필요하다. 문서·PDF는 다루지 않는다. 클라우드 세션에서는 안 된다. [출처](https://code.claude.com/docs/en/plugins/code-intelligence) |
| Claude Code 기본 탐색 | Grep·Read로 그때그때 찾기 | 추가 설치가 없다. 개발팀이 벡터 검색을 해 보고 이 방식으로 돌아왔다고 밝혔다(근거는 내부 실험과 "느낌"이라고 스스로 말함). | 큰 저장소에서 토큰이 많이 든다. [출처](https://officechai.com/ai/claude-researcher-explains-how-agentic-search-performed-better-than-rag-for-code-generation/) |
| codebase-memory-mcp | tree-sitter 그래프 + MCP | 코드 전용으로 빠르다. 논문 평가가 있다. | 논문에서도 답의 품질은 파일 탐색보다 낮다. [출처](https://arxiv.org/abs/2603.27277) |
| Serena | 언어 서버를 MCP로 연결 | 기호 탐색과 이름 바꾸기에 강하다. | 공식 LSP 플러그인과 역할이 겹친다. [출처](https://www.knolli.ai/post/graphify-alternatives) |
| GitNexus | 로컬 지식 그래프 | 큰 저장소에 맞다. | 한 비교 글에 비상업 라이선스로 나온다(직접 확인 못 함). [출처](https://www.knolli.ai/post/graphify-alternatives) |
| Aider 저장소 지도 | tree-sitter + 중요도 순위 | 가볍다. | Aider 안에서만 쓸 수 있다. [출처](https://www.knolli.ai/post/graphify-alternatives) |
| Graphify | tree-sitter 그래프 + LLM 문서 추출 | 코드와 문서·PDF·영상을 한 그래프에 담고, 보기 좋은 화면을 준다. | 앞 절의 비용·낡음 문제가 있다. |

여러 비교 글의 공통 의견은 이렇다. 코드만 있는 저장소에는 코드 전용 도구가 낫고, 문서·자료가 많이 섞인 저장소라면 Graphify가 맞는다. [출처](https://github.com/DeusData/codebase-memory-mcp/discussions/611)

## 우리 쪽 적용

**이 절은 제안일 뿐 결정이 아니다.**

1. **전체 40개 프로젝트에 설치하지 않는다.** `graphify claude install`은 각 프로젝트의 CLAUDE.md와 `.claude/settings.json`(훅)을 고친다. git 훅을 켜면 `.git/hooks`도 고친다. 이것은 "남의 프로젝트는 ohmypm/ 폴더와 표식 블록만"이라는 우리 규칙과 정면으로 충돌한다. 훅의 안내 문구 비용(#3435)이 40개 프로젝트에서 곱해지는 것도 위험하다.
2. **먼저 볼 것은 공식 LSP 플러그인이다.** 주력 언어(Python, TypeScript 등) 몇 개만 사용자 범위로 설치하면 된다. 프로젝트 폴더에 파일을 만들지 않고 낡을 것도 없어, 담당 에이전트의 Read·Grep 방식을 그대로 두고 "정의 찾기"만 정확해진다.
3. **Graphify를 시험한다면 이렇게 좁힌다.**
   - 코드 파일이 많은 프로젝트 하나만 고른다. 후보는 project_odin이나 odin_3.0인데, 크기를 재 보지 않았으니 먼저 확인이 필요하다.
   - `claude install`과 `hook install`은 하지 않는다. 명령줄 `graphify extract --code-only`만 쓰고, `GRAPHIFY_OUT`으로 출력을 그 프로젝트의 `ohmypm/` 폴더 아래로 보낸다.
   - CLAUDE.md에는 우리 표식 블록 안에 "구조 질문은 graphify query를 써 볼 수 있다"는 한 줄만 둔다. "반드시 먼저 써라"처럼 강제하지는 않는다.
   - `GRAPHIFY_QUERY_LOG_DISABLE=1`로 질의 기록을 끈다.
   - 문서·PDF 처리(LLM 비용 발생)는 빼고 시작한다.
4. **시험 판정 기준을 미리 정한다.** 같은 작업 몇 개를 Graphify 있이/없이 돌려 세 가지를 비교한다. ① 세션 토큰 ② 끝내는 데 걸린 시간 ③ 결국 원본 파일을 몇 번 다시 읽었는지. llmwiki를 버린 이유가 ③이었으니, ③이 줄지 않으면 접는다.
5. 위 2번과 3번 중 하나만 고른다면, 버려지는 쪽의 재검토 시점을 그 자리에서 정해 해당 프로젝트 `docs/`에 적는다. 예: "LSP 플러그인을 4주 써 본 뒤", "Graphify가 강제 안내 문구의 세션당 횟수 제한(#3435)을 정식으로 반영한 뒤".

## 확인 못 한 것

- `graphify claude install`이 쓰는 CLAUDE.md가 프로젝트 쪽인지 사용자 전역(`~/.claude`)인지 README에 없다. 훅이 저장되는 설정 파일 위치도 Claude Code용으로는 명시돼 있지 않다. 이슈 #578의 우회법이 `.claude/settings.json`을 고치라고 해서 프로젝트 설정으로 보이지만, 확인하지는 못했다.
- 질의 기록이 기본으로 켜져 있는지 꺼져 있는지 README 안에서 엇갈린다.
- 라이선스가 저장소 화면에는 Apache-2.0과 MIT 둘 다로 나오고, 다른 글은 MIT라고만 쓴다.
- 별 개수가 출처마다 다르다(6.3만~12.5만). 부풀려졌다는 의혹은 확인하지 못했다.
- 개발사 표는 "그래프 생성에 LLM 비용 0"이라고 하는데, 같은 README는 문서 처리에 LLM 호출이 든다고 한다. 둘이 맞지 않는다.
- 71배, 49배 절감 수치의 원래 측정자를 찾지 못했다.
- Reddit과 Hacker News의 실사용 토론은 검색에서 찾지 못했다.
- #3435(안내 문구 횟수 제한)와 #3718(낡은 그래프 강제 안내)이 지금 최신 버전에서 고쳐졌는지 확인하지 못했다. 두 이슈 모두 열려 있었고, 고친 코드는 다른 사람의 갈래 저장소(포크)에만 있었다.
- GitNexus의 비상업 라이선스, Serena의 라이선스는 비교 글에만 의존했고 원문은 확인하지 못했다.
- 우리 40개 프로젝트 각각의 코드 파일 수는 재지 못했다. 셸 명령이 막혀 실행하지 못했다. 그래서 어느 프로젝트가 "작아서 Graphify가 이득이 없는지"는 판단하지 못했다.
- 우리가 예전에 llmwiki를 버린 기록은 프로젝트 폴더에서 찾지 못했다(검색 시간 초과). 버린 이유는 이번 요청에 적힌 대로 썼다.
