---
name: kickoff-workspaces
description: 킥오프 2부(마지막) — 프로젝트에 작업 구조를 깐다. main(통합)·pl(기획·설계·검토, 이종 모델 둘 + 코디네이터 하위 모델)·구현 워커(난이도 등급별 모델)로 Orca 워크트리를 나누고, 역할표·작업 스펙·검토서 템플릿·브랜치 가드를 설치한 뒤 pl 워크트리를 연다. 발동 — 1부(plan.md) 직후, "작업 구조 세팅하자"·"pl 구조 붙이자"·"워크스페이스 나누자", 기존 프로젝트에 소급 적용할 때, 그리고 "구조 업데이트하자"(플러그인 버전을 프로젝트 복사본에 반영).
---

# 킥오프 2부 — 작업 구조

**생각하는 자리와 손대는 자리를 나눈다.** 기획·설계·검토는 서로 다른 벤더의 프론티어 모델 둘이 한 워크트리에서
하고, 구현은 작업 스펙의 난이도 등급에 맞는 모델이 별도 워크트리에서 한다. main은 합치기만 한다.
둘 사이의 계약은 **작업 스펙(검증 가능한 완료 기준)** 하나다 — 스펙 없이 구현 워커를 띄우지 않는다.

> **산출물 계약**: 대상 프로젝트에 역할표(`docs/roles.md`)·스펙/검토 폴더·`orca.yaml`·`.worktreeinclude`·
> `AGENTS.md`/`CLAUDE.md` 역할 블록·브랜치 가드가 설치되고, pl 워크트리가 세 터미널(작성자·검토자·코디네이터)로 열려
> 첫 작업 스펙(T-001)이 pl에 지시된 상태.
> **이 절차는 접근법이지 정답 경로가 아니다** — 프로젝트가 작으면 구조를 깔지 않는 것이 정답이다.
> 절차 상세와 근거는 [PROTOCOL.md](PROTOCOL.md)(설치 시 대상 프로젝트 `docs/protocol.md`로 복사 — Codex는 플러그인을 못 읽는다),
> 파일 원형은 `templates/`, 하네스 참고는 `references/`. 이 스킬은 ohmypm 플러그인(`${CLAUDE_PLUGIN_ROOT}/skills/kickoff-workspaces`)에 산다.

구 3부(kickoff-harness, 2026-09-17 폐기)가 하던 "프로필로 스킬·MCP 사전 설치"는 하지 않는다.
**작업 스펙 전 설치 금지** — 도구는 스펙의 '필요 도구' 항목으로 워커가 그때 설치한다.
스택 확정은 설계 결정이므로 pl의 첫 작업(T-001 `docs/design.md`)이 한다.

## 0. 전제와 규모 판단

`docs/plan.md`(1부 요약)만 있으면 된다. `docs/usecases.md`·`references.md`는 있으면 pl의 T-001 재료가 되고, 없으면 pl이 필요할 때 스펙으로 요구한다.

먼저 묻는다 — **이 구조가 밥값을 하나?** 기준: 케이스가 다섯을 넘거나, 운영 환경(실서비스·자동 실행)이
있거나, 되돌리기 어려운 변경이 예상되면 깐다. 아니면 단일 워크트리로 두고 여기서 끝낸다
(ohmyPM plan.md: "작고 미완인 프로젝트에선 관리 비용이 이득을 넘본다"). 결정과 이유를 `docs/plan.md`에 한 줄 남긴다.

## 1. 역할·모델 확인

기본값은 아래. 바꾸면 `docs/roles.md`에만 적는다(다른 문서에 모델명을 복붙하지 않는다 — 썩는다).

| 역할 | 자리 | 에이전트 | 모델 | 쓰는 경로 |
|---|---|---|---|---|
| main | 원본 체크아웃 | claude | 기본 | 머지·커밋·푸시만 |
| pl 작성자 | 워크트리 `pl` 터미널 1 | codex | `gpt-6-astra` xhigh | `docs/tasks/`, 설계 문서 |
| pl2 검토자 | 워크트리 `pl` 터미널 2 | claude | `claude-fable-5-1` | `docs/reviews/`만 — 검토서 한 장, 태스크마다 `/clear` |
| pl3 코디네이터 | 워크트리 `pl` 터미널 3 | claude | `claude-opus-5` | 스펙 "검증" 절. 게이트·배정·대기·판정 — 배관은 하위 모델 |

페이블 한도가 소진된 주에는 `scripts/ws-model.sh fable-out <프로젝트>`로 페이블 자리를 오퍼스로 내리고 pl3를 열지 않는다(PROTOCOL "모델 모드"). 쿼터 소진은 Claude Code가 자동으로 내려 주지 않는다.
| 구현 워커 | 워크트리 `T-NNN-<slug>` | claude | 등급표(S 소넷 5 / M 오퍼스 5 / L 페이블 5.1) | 스펙의 '손대는 파일' |

작성자·검토자를 서로 다른 벤더로 두는 이유와 검토자에게 재작성을 금지하는 이유는 PROTOCOL "근거". 코디네이터를 검토자와 분리해 하위 모델에 두는 이유는 PROTOCOL "토큰 규율"(최상위 모델 세션이 오케스트레이션 JSON을 끌어안고 커지지 않게).
전제 확인: `codex --version`·`claude --version`이 돌고, Codex 전역 설정(`~/.codex/config.toml`)에
`model`·`model_reasoning_effort`가 있어야 한다 — Orca의 `--agent codex`는 모델 플래그를 못 받는다.

## 2. 파일 세트 설치 (대상 프로젝트)

설치는 스크립트 하나로 한다 — 관리 파일에 버전 도장을 찍고, 프로젝트 소유 파일은 없을 때만 만든다:
```
"${CLAUDE_PLUGIN_ROOT}"/skills/kickoff-workspaces/scripts/ws-upgrade.sh <프로젝트경로> --install "<공유 폴더들>" "<setup 명령>"
```
스크립트가 하는 일(손으로 할 때의 기준이기도 하다):

0. `PROTOCOL.md` → `docs/protocol.md` (프로젝트가 자급자족해야 pl(Codex)과 다른 PC가 읽는다)

1. `orca.yaml` — `worktree.sharedDirectories`(`.venv`·`node_modules` 등 무거운 gitignore 폴더)와
   `scripts.setup`(의존성 설치 한 줄). 프로젝트 스택에 맞춰 고친다
2. `.worktreeinclude` — 워크트리마다 **복사**할 gitignore 파일: `.env`, 개인 설정, 로컬 전용 위키 파일.
   DB·로그처럼 한 곳에만 있어야 하는 것은 넣지 않는다
3. `AGENTS.md`(Codex가 읽는다)와 `CLAUDE.md`에 역할 블록 — 각 **10줄 이하**(llmwiki 블록과 같은 예산)
4. `docs/roles.md` — 1의 표 + 등급표 + 이름 규칙. 프로젝트별 값은 여기만
5. `docs/tasks/`·`docs/reviews/` — 각각 템플릿 사본(`_template.md`)과 함께 생성
6. `.githooks/pre-commit` + `git config core.hooksPath .githooks` — 브랜치 이름이 `pl`(또는 `*/pl`, `pl-*`)이면
   `docs/` 밖 변경 커밋을 거부한다. 지시문이 아니라 훅으로 막는다(HARNESS "강제할 것은 훅으로")
7. 운영 환경이 있으면 `templates/RUNBOOK.md`·`SECURITY.md`를 `docs/`로 복사해 T-00x 스펙으로 채우게 한다

설치 후 `index.md`에 protocol·roles·tasks·reviews를 등재하고 커밋한다(main에서).

## 3. pl 워크트리 개설

```
orca repo list --json                                   # <repoId> 확인
orca worktree create --repo id:<repoId> --name pl --agent codex --no-parent --comment "기획·설계·검토" --json
orca terminal create --worktree name:pl --title pl2 --command "claude --model claude-fable-5-1 --dangerously-skip-permissions" --json
orca terminal create --worktree name:pl --title pl3 --command "claude --model claude-opus-5 --dangerously-skip-permissions" --json   # roles.md가 fable-out이면 열지 않는다
orca terminal wait --terminal <handle> --for tui-idle --timeout-ms 60000 --json      # pl2·pl3 각각
```
`wait.satisfied`가 true일 때만 send 한다. 세 터미널에 각각 `templates/prompt-pl.md`·`prompt-pl2.md`·`prompt-pl3.md`의
역할 지시를 첫 메시지로 보낸다(`orca terminal send --text ... --enter`). 새 폴더 신뢰창이 뜨면 프롬프트가 먹힌다 — wait 뒤 화면을 한 번 본다.
브랜치는 Orca가 워크트리 이름에서 만든다(`<git-username>/pl` 꼴) — 가드는 마지막 세그먼트로 판정한다.

## 4. 첫 스펙 지시

pl에 **T-001**을 지시한다: plan(있으면 usecases)의 필요 기술·공통 전제를 집계해 스택을 확정하고 `docs/design.md`
(구성 한 장 — 산출물 대장의 설계 산출물)를 쓰는 작업. 화면이 있으면 T-002로 screen-plan(와이어프레임)을 잇는다.
이후 흐름은 PROTOCOL: 스펙 v1 → pl2 단일 패스 검토 → v2 → 사용자 게이트 → pl3 워커 배정 → pl3 검증 → main 머지.

## 5. 기록

`docs/plan.md`에 "작업 구조" 절(규모 판단·역할 요약·roles.md 링크), `log.md`에 매듭 한 줄.
설치한 것과 건너뛴 것(이유)을 남긴다.

## 업데이트 — "구조 업데이트하자"

플러그인이 바뀌면 프로젝트 복사본은 낡는다. 버전은 프로젝트 `docs/protocol.md` 첫 줄, 플러그인은 `plugin.json`. 차이가 나면:
```
"${CLAUDE_PLUGIN_ROOT}"/skills/kickoff-workspaces/scripts/ws-upgrade.sh <프로젝트경로>
```
관리 파일(protocol·템플릿 2·pre-commit·AGENTS/CLAUDE 블록)만 갈아 끼우고 diff를 보여 준다. 그 diff를 보고 main이 커밋 → pl 워크트리 ff → **pl·pl2·pl3 `/clear`**(규칙 파일이 바뀌었다). 스크립트가 `WARN`을 찍으면 프로젝트 소유 파일에 손댈 게 있다는 뜻 — CHANGELOG 항목대로 손으로. 무엇이 바뀌었는지는 플러그인 `CHANGELOG.md`.
프로젝트 소유 파일(roles·orca.yaml·.worktreeinclude·.gitignore)은 건드리지 않으므로, 템플릿 쪽 변화가 거기 필요하면 CHANGELOG가 그 항목을 따로 부른다.

## 기존 프로젝트에 소급 적용

0의 규모 판단을 똑같이 하고, 2의 파일 세트만 깐다. 이미 진행 중인 작업이 있으면 그것을 T-001 스펙으로
역기입해 pl2 검토를 한 번 받는다 — 구조를 깔았는데 첫 태스크가 없으면 아무도 안 쓴다.
