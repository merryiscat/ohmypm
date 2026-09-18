# 멀티 에이전트 코딩 구조 — 외부 실측과 실무 후기 (2026-09-18 조사)

> 우리 구조(main·pl·pl2·pl3·워커)가 값을 하는지 판단하려고 모았다. **결정이 끝나면 이 페이지는 지운다.**
> 절차 문서의 근거 절과 중복되지 않게, 여기엔 **바깥 사례**만 둔다.

## 요약 — 우리 구조를 부위별로 채점하면

| 부위 | 근거 등급 | 판정 |
|---|---|---|
| Codex가 쓰고 Claude가 검토(방향) | **통제 실험 1편** | 유지. **반대 방향은 해롭다**(91.4→82.8) |
| 검토자는 지적만, 재작성 금지 | 설계 논거 + 1인칭 보고 | 유지. 정량 A/B는 **아무도 안 했다** |
| S는 직접, M·L만 절차 | 실측 다수 | 유지. 가장 잘 측정된 결과 |
| 요청 원문 verbatim + 검문 | 벤더 버그 + 실패 분류 통계 | 유지. 0.6.0이 맞았다 |
| 코디네이터·게이트·배정 층(pl3) | **없음** | 근거 없음. 실무자들이 반복해서 접은 부분 |
| 워커 병렬 | **반대 실측** | 우리 작업 크기에선 손해 |

## 1. 거의 만장일치인 것

**쓰기는 단일 스레드로 두고, 추가 에이전트는 "판단"만 보탠다.**
Cognition은 2025년 "멀티에이전트 만들지 마라"에서 2026-04 입장을 뒤집으면서도 규칙은 그대로 뒀다 — 병렬 **작성자**는 여전히 신뢰할 수 없고, 추가 에이전트는 action이 아니라 intelligence를 기여해야 한다.
Anthropic 엔지니어링 글도 **"코딩은 리서치보다 진짜로 병렬화 가능한 부분이 훨씬 적다"**고 직접 단서를 단다.

**병렬 워커는 토큰 5~15배이고, 작은 작업에선 더 느리다.** 가장 정직한 실측(감독자 + worktree 워커):

| 과제 | 단독 | 워커 수 자유선택 | 강제 병렬 |
|---|---|---|---|
| 4모듈 | 171.5초 | 120초(워커 0명) | 250초 |
| 6모듈 | 189.5초 | 186.5초 | 394.5초 |

자유선택 6회 런에서 **감독자가 여섯 번 다 워커를 0명 골랐다.** 강제 병렬은 토큰 약 5배에 46~108% 더 느렸다.

**별도 컨텍스트 검토자는 값을 한다.** Cognition 보고로 PR당 평균 2건, 그중 58%가 severe. 이종 모델 페어링은 실제 이슈의 30%를 한쪽만 잡았다(60%는 양쪽, 10%는 사람).

**작은 작업에 스펙·게이트는 과하다.** Spec Kit 완주 = 생성 57분 + 리뷰 4.5시간. 같은 기능을 반복 코딩으로는 23분. 게다가 스펙이 실제 버그(변수 초기화 누락)를 못 잡았다.

**실무 병렬 상한은 3~5.** 그 이상은 조율·리뷰 부담이 속도 이득을 먹는다. 서로 다른 모델 워커를 붙이면 충돌률이 2배(41.7% vs 19.8%, 에이전트 PR 33,596건 분석).

## 2. 우리 T-003 실패와 정확히 같은 사례

**Cursor 오케스트레이터가 사용자 프롬프트를 다시 써서 서브에이전트에 넘긴다.** 낡거나 틀린 레포 컨텍스트가 주입돼 서브에이전트가 자기 지시를 무시했다. 벤더 답변은 "시스템 프롬프트가 상세히 넘기라고 지시하기 때문"이며 **수정 없음**. 신고자는 중간 에이전트를 "불필요한 병목"이라 부르며 이탈했다.

**실패 분류 통계**(트레이스 1,642건 주석): **44.2%가 명세·설계 계열, 32.3%가 에이전트 간 정렬 실패**, 23.5%가 검증·종료. 즉 "잘못 짠 코드"보다 **"잘못 전달된 의도"가 다수**다. 검증 강화로 +15.6%p, 역할 명세 조임으로 +9.4%p.

**핸드오프에서 먼저 사라지는 것**: 인과(왜 그렇게 정했나), 암묵적 제약, 불확실성 신호(확신으로 납작해짐), 시도·실패의 시간 순서, **기각된 접근**(사라지면 하류가 실패한 길을 다시 간다). 우리 `pending.md`가 마지막 항목에 대응한다.

## 3. 가장 불편한 반대 근거

**추론 토큰 예산을 동일하게 고정하면 단일 에이전트가 멀티에이전트를 일관되게 따라잡거나 이긴다**(Stanford, 2026-04). 근거는 Data Processing Inequality — **"에이전트 간 핸드오프는 정보를 잃을 수만 있고 만들어낼 수는 없다."** 보고된 멀티에이전트 이득의 상당 부분이 "아무도 세지 않은 추가 연산"으로 설명된다고 본다.

이게 맞다면 우리 구조의 이득 중 상당 부분은 "토큰을 더 썼다"는 말의 다른 표현이다.

## 4. 갈리는 것 — 검토자에게 앞선 맥락을 줄 것인가

정반대 처방이 둘 다 근거를 갖고 있다. 주지 말라는 쪽은 context rot과 독립성을 든다("같은 세션에서 리뷰하면 리뷰어는 자기가 방금 정당화한 결정을 심판하는 셈"). 더 주라는 쪽은 구조화된 인계 컨텍스트가 토큰 42~63%를 아꼈다는 측정을 든다.

**화해 가능한 해석**: 요청 원문·스펙·결정 근거는 **더 줄수록** 좋고, 구현자의 추론 로그는 **줄수록** 나쁘다. 이 화해를 명시적으로 검증한 글은 없다. 우리 0.6.0이 정확히 이 선을 그었다.

## 5. 선례가 없는 지점

작성자↔검토자 2계층 후기는 많고 오케스트레이터+워커 후기도 있다. 그런데 **검토자와 코디네이터를 따로 두고 구현까지 분리한 3계층 + 이종 모델 + worktree** 구조를 몇 달 굴린 후기는 **찾지 못했다**. 우리가 선례 없는 곳에 있다.

못 찾은 것 또 있음: 검토자 "지적만 vs 재작성"의 정량 A/B, 요청 원문 손상의 1인칭 정량 보고, 한국어권 실무 후기, 규모 임계의 숫자(전부 "작업의 모양"으로 답한다 — 하위 과제가 진짜 독립이고 도구가 겹치지 않을 때).

## 6. 우리가 당장 취할 처방

1. **Codex→Claude 검토 방향은 뒤집지 않는다.** 반대는 통제 실험에서 점수를 떨어뜨렸다
2. **검토자에게 워커 세션 로그·추론을 주지 않는다.** 스펙과 산출물만
3. **검토 지적마다 실패 시나리오를 요구한다.** 안 그러면 15건 중 12건이 노이즈라는 보고
4. **워커 병렬은 "추론이 갈릴 때"만.** 같은 변환의 반복은 결정론적 전처리 후 단일 세션이 낫다
5. **구조 판단은 1회 런으로 하지 않는다.** 1회 성공 뒤 3회 연속 타임아웃한 사례가 있다. 최소 3회 반복

## 출처

- [Cognition — Multi-Agents: What's Actually Working](https://cognition.com/blog/multi-agents-working) (2026-04-22) · [Don't Build Multi-Agents](https://cognition.com/blog/dont-build-multi-agents) (2025)
- [Anthropic — Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- [오케스트레이터가 워커를 0명 골랐다](https://dev.to/mahadansar/i-built-a-multi-agent-coding-orchestrator-it-kept-choosing-zero-workers-4bc3) (2026-08-15)
- [Single-Agent LLMs Outperform Multi-Agent Under Equal Thinking Token Budgets](https://www.researchgate.net/publication/403529711_Single-Agent_LLMs_Outperform_Multi-Agent_Systems_on_Multi-Hop_Reasoning_Under_Equal_Thinking_Token_Budgets) (Stanford, 2026-04)
- [Cross-Model LLM Code Review](https://arxiv.org/abs/2607.21656) (2026-07-22)
- [Cursor — 오케스트레이터가 프롬프트를 덧씌운다](https://forum.cursor.com/t/orchestrator-agent-pollutes-and-overrides-prompt-context-passed-to-sub-agents/161339) (2026-05-22)
- [A Field Guide to Multi-Agent Failure Modes](https://dev.to/tuomo_pisama/a-field-guide-to-multi-agent-failure-modes-59on) (트레이스 1,642건)
- [Handoff Debt](https://arxiv.org/pdf/2606.02875) (2026-06)
- [Spec Kit 실측 — 57분+4.5시간 vs 23분](https://blog.scottlogic.com/2025/11/26/putting-spec-kit-through-its-paces-radical-idea-or-reinvented-waterfall.html) (2025-11-26)
- [Spec-Driven Development: The Waterfall Strikes Back](https://news.ycombinator.com/item?id=45935763) (HN, 2025-11)
- [Don't Build Multi-Agents 토론](https://news.ycombinator.com/item?id=45096962) (HN, 2025-09-01)
- [읽기전용 리뷰어](https://dev.to/mahirhir/read-only-reviewer-agents-catch-what-your-main-agent-waves-through-3ggc) · [Claude와 Codex를 일주일 싸움시켰다](https://dev.to/brianmello/i-let-claude-and-codex-argue-about-my-code-for-a-week-heres-what-they-caught-gg0) · [서브에이전트를 이렇게 쓰지 마라](https://dev.to/atul_joshi_f/how-not-to-use-sub-agents-1p38)
- [AI 코드 리뷰 노이즈 — 15건 중 12건](https://photostructure.com/coding/claude-code-review/) (2026-03-11)
- [1회 성공 런은 거의 아무것도 증명하지 않는다](https://gptcode.dev/blog/2026-07-29-one-successful-agent-run-proves-almost-nothing) (2026-07-29)
- [에이전트 PR 충돌 분석 33,596건](https://codex.danielvaughan.com/2026/07/28/agent-pr-merge-conflicts-concurrent-coding-agents-codex-cli-worktree-isolation-coordination-defence/) (2026-07-28)
- [Addy Osmani — The Code Agent Orchestra](https://addyosmani.com/blog/code-agent-orchestra/) (2026-03-26) · [6개월간 에이전트로만 코딩](https://blog.exe.dev/engineering-with-ai) (2026-08-27)

**날짜 주의**: dev.to 일부 글은 페이지가 상대 날짜만 줘서 추출 날짜가 본문과 모순된다. 내용만 취한다.
**빠진 출처**: Reddit 전체(크롤러 차단), Prezi Engineering의 SDD 4팀 적용기(403).
