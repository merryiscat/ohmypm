---
name: dispatch
description: main(원본 체크아웃) 세션이 업무 요청을 받았을 때 직접 하지 않고 pl(스펙 작성) → pl2(검토·배정·검증) → main(머지)로 넘기는 중계 절차. 발동 — 작업 구조(kickoff-workspaces)가 깔린 프로젝트의 main에서 "~해줘"·"~만들어"·"~분석해"·"~고쳐" 같은 업무 요청을 받았을 때. 예외(직접 처리): 문서 한 줄 수정, 머지·푸시, 질문 답변.
---

# dispatch — main은 넘기고, 합친다

main에서 일을 직접 하면 구조가 죽는다. 요청을 받으면 **① 스펙 지시 한 줄을 pl에 → ② pl2에 검토 지시 → ③ 사용자 게이트 → ④ pl2가 배정·검증 → ⑤ main이 머지**.
절차의 규칙은 `docs/protocol.md`가 소유하고, 이 스킬은 **명령줄만** 소유한다. pl(Codex)은 종량 쿼터 — 이 스킬이 pl에 보내는 메시지는 스펙 v1·v2 두 번뿐이다.

## 0. 차선 판정 (10초) — protocol 0절

| 차선 | 기준 | 이 스킬에서 |
|---|---|---|
| **S 즉시** | 파일 1~2개 · 요청이 곧 완료 기준 · revert 한 번으로 되돌림 · 운영 영향 없음 | **main이 직접** 한다. 커밋 메시지에 요청 원문 한 줄. 끝. (커지면 그 자리에서 멈추고 M으로) |
| **M 표준** | 여러 파일 · 판단 조금 · 되돌릴 수 있음 | 2절(짧은 스펙) → 3절(차단만) → 4절(게이트 없이 배정) → 5절 |
| **L 중대** | 운영 · 되돌리기 어려움 · 구조 변경 · 미지 | 2~5절 전부, 게이트 있음 |

사용자가 "가볍게"·"제대로"라고 하면 그게 이긴다. 판정 결과를 한 줄로 말하고 시작한다("M으로 갑니다 — 파일 셋, 되돌릴 수 있음").
**반복 운영 업무**(예: 금일 로그 검토)는 첫 회 차선대로 하고, 이후는 스펙 파일을 재사용해 **pl 없이 pl2가 워커만 재배정**한다(4절 — pl 턴 0). 첫 회가 S였으면 계속 S.

## 1. 자리 찾기

```
orca terminal list --worktree name:pl --json
```
`pl` 워크트리의 터미널 중 **Codex 프로세스 = pl, Claude 프로세스 = pl2**(제목이 아니라 명령으로 판별). 둘이 없으면 kickoff-workspaces 3절대로 연다.
main이 원격보다 뒤져 있으면 먼저 `git fetch` + ff — 워커 워크트리는 origin/main에서 뜬다(protocol 4절).

## 2. pl에 스펙 지시 (Codex 턴 1)

한 줄. 요청 원문을 그대로 싣고, 무엇을 만들라는지만 덧붙인다:
```
orca terminal send --terminal <pl> --enter --wait-submit 10 --json --text \
 "사용자 요청: <원문>. 차선 <M|L>. 이걸 docs/tasks/T-NNN-<slug>.md 스펙 하나로 써라(_template.md 형식, M이면 완료 기준 ≤ 5·30줄, L이면 ≤ 8·한 장). 셸은 docs 읽기·쓰기에만, src·코드 실행 금지. 다 쓰면 한 줄 보고하고 멈춰라."
```
번호 NNN은 `docs/tasks/`의 다음 번호. **보내기 전에 pl이 비어 있는지** 확인한다 — 이전 태스크 문맥이 남아 있으면 `/clear`부터(종량). 끝났는지는 **파일 생성 + 화면에 "esc to interrupt"가 사라짐**으로 판단(폴링 5초). `terminal wait --for tui-idle`은 Codex에서 이르게 풀린다.

## 3. pl2에 검토 지시

```
orca terminal send --terminal <pl2> --enter --wait-submit 10 --json --text \
 "pl이 docs/tasks/T-NNN-<slug>.md v1을 완성했다(차선 <M|L>). protocol 2절대로 docs/reviews/T-NNN.review-v1.md를 한 번만 쓰고 결론을 한 줄로 보고하라. M이면 차단 항목만 10줄 이내, 차단 없으면 지적 없음 한 줄. 다른 파일은 건드리지 않는다."
```
검토서의 `결론`이 **차단 없음**이면 4절로(M은 v2 없이 바로). 차단 있음이면 pl에 v2 지시(Codex 턴 2) — 사용자 결정이 필요한 지적이 섞여 있으면 **v2 지시 전에** 사용자에게 물어 결정을 지시문에 싣는다(턴 절약):
```
... --text "pl2 검토서 docs/reviews/T-NNN.review-v1.md가 나왔다. [사용자 결정: …] 지적마다 '검토 반영' 표에 수용/기각(근거)을 적고 본문을 v2로 고쳐라(상태: 검토 반영 v2, 기준 ≤ 8). 이 턴 하나로 끝낸다. 끝나면 '차단 기각 있음/없음' 한 줄만."
```

## 4. 게이트와 배정 (pl2) — 배정·대기와 검증 사이에 `/compact`

스펙·검토서를 pl 브랜치에 커밋 → main에 ff 머지 → **푸시**(원격이 있으면) → **L만** 사용자에게 승인 질문(스펙 목표·범위 밖·산출물을 두 문장으로; M은 roles.md에 `게이트: M`이 있을 때만). 그 다음 **4a 배정·대기**:
```
orca terminal send --terminal <pl2> --enter --wait-submit 10 --json --text  "사용자가 T-NNN v2를 승인했다. protocol 4·5절대로: run-create(있으면 재사용) → task-create --spec '<스펙 경로를 읽고 완료 기준 전부 만족. 손대는 파일·금지는 스펙대로. worker_done에 기준별 통과/실패>' → worker-start --task <id> --worktree new-top-level --name T-NNN-<slug> --agent claude --model <등급 모델> --effort high (launch.effective 확인) → check --wait(질문은 스펙으로 답할 수 있는 것만) → worker_done을 받으면 검증은 하지 말고 '워커 완료, 워크트리 <경로>, 커밋 <sha>' 한 줄만 보고하고 멈춰라."
```
반복 업무 재배정은 같은 메시지에서 "스펙 T-NNN 재사용, 기준일 오늘"만 바꾼다.
완료 한 줄이 오면(pl2 화면에 "esc to interrupt / ctrl+b to run / Waiting for"가 없을 때) **main이 압축을 보낸다**(protocol 8절 — 상태를 들고 있어 clear는 못 한다):
```
orca terminal send --terminal <pl2> --text "/compact" --enter --json
```
그 다음 **4b 검증**:
```
orca terminal send --terminal <pl2> --enter --wait-submit 10 --json --text  "이제 protocol 6절: 워커 산출물을 스펙의 완료 기준마다 통과/실패로 판정해 docs/tasks/T-NNN-<slug>.md '검증' 표에 적어라(M이면 기준별 한 줄, 재조회는 차단 기준만). 고치지 않는다. 실패면 사유를 적어 같은 워커에 한 번 되돌린다. 끝나면 한 문단 보고."
```
끝났는지는 스펙의 "검증" 표에 행이 생기고 pl2가 멈췄을 때. 반복 업무를 같은 세션에서 다음 회차로 넘길 때도 회차 사이에 `/compact`.
**대기는 언제나 백그라운드.** 긴 작업은 괜찮다 — 판단 기준은 시간이 아니라 **진행 신호**다. 주기적으로(10분마다) pl2 화면과 산출물 파일을 본다: 출력·파일·로그가 바뀌고 있으면 계속 기다린다. 같은 명령이 신호 없이 오래(기본 10분, 성격에 따라 더) 서 있으면 멈춘 것이다: `orca terminal send --terminal <pl2> --interrupt --json` 뒤 "그 명령은 신호 없이 멈춰 있어 끊었다. 오래 걸릴 실행은 백그라운드로 돌리고 진행 로그를 남겨라. 산출물부터 읽어 기준별로 판정하라"를 보낸다. main이 전경 루프로 기다리면 main도 같이 멈춘다(실측).

## 5. 머지 (main)

pl2 판정을 pl 브랜치에 커밋 → main ff → 워커 브랜치 머지(로컬 전용 산출물이면 파일을 main·pl로 복사) → 푸시 → `orca worktree rm --force` 워커 정리 → 스펙 상태 줄을 `머지`로 → `docs/log.md` 한 줄.
마지막으로 **세션을 비운다**(protocol 8절) — pl은 v2 보고 직후에 이미 비웠어야 하고, pl2는 여기서:
```
orca terminal send --terminal <pl> --text "/clear" --enter --json     # 아직 안 비웠으면
orca terminal send --terminal <pl2> --text "/clear" --enter --json
```
규칙 파일(AGENTS·CLAUDE·protocol·roles)을 고쳤을 때도 둘 다 즉시 비운다.

## 6. 동시 요청 — main은 하나, 기다림은 백그라운드

- **main은 한 자리**다. main2를 만들지 않는다 — 같은 폴더에 머지·푸시하는 에이전트가 둘이면 충돌한다.
- pl·pl2를 기다리는 폴링은 **백그라운드**로 건다(Claude Code `run_in_background`, 완료 조건 = 파일 생성·상태 줄·검증 표). 기다리는 동안 다음 요청을 받는다. 알림이 오면 그 태스크를 이어간다.
- **pl은 직렬**: 한 번에 스펙 하나. 다음 태스크의 v1 지시는 앞 태스크의 v2 보고(+ `/clear`) 뒤에 보낸다. 대기 중인 요청은 `docs/status.md`에 "대기: T-NNN 후보 — <원문>"으로 적어 두고 순서대로.
- **워커는 병렬**(워크트리 하나씩), **pl2는 여러 태스크의 배정 상태를 동시에** 들 수 있다 — 단 compact 시점(4절)은 태스크마다 지킨다.
- 태스크 상태의 단일 출처는 스펙 파일의 `상태:` 줄이다. 무엇이 어디까지 갔는지는 세션 기억이 아니라 `docs/tasks/`를 읽어 판단한다.
- 기획을 병렬로 돌려야 하면 main2가 아니라 `pl-<주제>` 워크트리를 하나 더 연다(roles.md 이름 규칙). Codex 세션이 하나 더 생기는 비용을 사용자에게 먼저 말한다.

## 하지 않는 것

- M·L 요청을 main이 직접 하기("금방 하니까"가 구조를 죽인다). S는 직접 하는 게 맞다 — 차선을 먼저 말하고 한다
- pl에 조사·질문·대기 시키기, pl에 세 번째 메시지 보내기
- 목록으로 터미널 닫기 — 내가 만든 핸들만 닫는다
- 사용자 세션(제목에 ✳, 또는 pl 워크트리 밖) 건드리기
- main2 만들기, pl에 두 스펙을 동시에 시키기, 대기를 전경(foreground)에서 돌려 main을 막기
- 일하는 중인 터미널("esc to interrupt / ctrl+b")에 메시지·`/clear`·`/compact` 보내기 — 실행 중 명령의 입력으로 들어간다. 여러 터미널에 목록으로 뿌리지 않는다
