---
name: kickoff-workspaces
description: 프로젝트 파일을 수정하지 않고 ohmyPM 외부 작업 환경을 등록·갱신한다. 작업 구조 세팅/업데이트 요청에 사용하며 기존 설치본 제거는 별도 전환 계획으로 처리한다.
---

# 외부 작업 환경 등록

Python 3.11+, Git, Orca와 역할별 모델 CLI를 사용한다. orca-cli 스킬로 실제 설치본을 확인한다.
규칙과 그 이유·대신·출처는 PROTOCOL.md의 [P-nn] 항목에 있다 — 여기서는 인용만 한다 [P-20].

```text
python <plugin>/skills/kickoff-workspaces/scripts/ws_upgrade.py <project> --dry-run
python <plugin>/skills/kickoff-workspaces/scripts/ws_upgrade.py <project> --profiles <roles.json> --harness <harness.json>
```

설치 결과는 Git 공통 디렉터리 ohmypm/project.json 및 외부의 내용 해시별 runtime이다 [P-17].
프로젝트 트리에는 아무것도 생기지 않는다 — AGENTS.md/CLAUDE.md·.gitignore·orca.yaml·.worktreeinclude·훅 그대로 [P-16].
가드는 런타임에 실려 세션에 얹힌다. 왜 그렇게 나뉘는지는 PROTOCOL.md [P-16]의 이유·대신을 읽는다.
모델·effort·approval은 profiles JSON의 roles.main/pl/work에서 선택한다. 기본 approval은 전 역할 bypass다 [P-15].
pl은 사용자와 합의한 최고 성능 모델이다 [P-03].
설치 결과 runtime.path 아래 scripts/environment_cli.py가 운영 진입점이다.

등록 후 role-connect --role main으로 세션을 준비하고 context 수락을 확인한다 [P-11].
프로젝트 지침과 공유 의존성 충돌은 보존·보고한다 [P-20]. 무관한 터미널은 그대로 둔다 [P-12].
역할·판정은 PROTOCOL.md, 명령·복구는 ../dispatch/references/runtime.md를 읽는다.
기존 1.0 작업은 보존된 실행기로 마무리한다 [P-18]. migration-plan의 소유권·충돌·활성 작업을 검토하고
그 digest로 migration-apply한다. 훅 출처가 불명확하면 자동 제거/복원하지 않는다 [P-18].
타 프로젝트 전환과 전체 배포는 사용자의 별도 요청으로만 한다 [P-09]. 전체 배포는 명시적 경로 목록에만
ws-rollout.sh <project> ...로 외부 등록한다. 발견·커밋·푸시는 자동으로 하지 않는다 [P-09].

## 처음 등록할 때 묻는 것 (2026-09-23)

이미 등록된 프로젝트(`.git/ohmypm/project.json`이 있음)를 다시 올릴 때는 묻지 않고 기존 답을 잇는다.
바꾸려면 `--profiles`·`--harness`를 다시 넘긴다. 처음이면 사용자에게 아래를 묻고, 답을 JSON 두 개로
적어 등록 인자로 넘긴다. 묻는 쪽은 이 스킬이다 — 스크립트는 인자만 받는다.

1. 역할별 모델·effort — main / pl / work. 기본은 `templates/workflow.json`.
2. 역할별 권한 자세 — `bypass`(묻지 않음, 기본) / `default`(CLI 기본 승인). 기본이 bypass인 이유는 [P-15].
3. 가드 — 런타임 가드가 막을 Bash 패턴(`deny`)과 아예 뺄 도구(`disallowed_tools`). 기본은
   `templates/harness.json`(되돌리기 불가·외부 발신). 프로젝트가 더 막거나 풀 것이 있으면 여기서 정한다 [P-15].

```text
profiles.json  {"roles": {"main": {...}, "pl": {...}, "work": {...}}}
harness.json   {"deny": ["rm -rf", ...], "disallowed_tools": ["WebFetch", ...]}
python <plugin>/skills/kickoff-workspaces/scripts/ws_upgrade.py <project> --profiles profiles.json --harness harness.json
```

답은 `.git/ohmypm/project.json`에 남고 `doctor`가 보여준다. 역할 세션이 뜰 때 `.git/ohmypm/roles/<role>/`에
`<token>.settings.json`·`<token>.deny.json`이 생겨 `--settings`·`--disallowedTools`로 넘어간다 [P-16].
