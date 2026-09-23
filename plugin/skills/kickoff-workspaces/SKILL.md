---
name: kickoff-workspaces
description: 프로젝트 파일을 수정하지 않고 ohmyPM 외부 작업 환경을 등록·갱신한다. 작업 구조 세팅/업데이트 요청에 사용하며 기존 설치본 제거는 별도 전환 계획으로 처리한다.
---

# 외부 작업 환경 등록

Python 3.11+, Git, Orca와 역할별 모델 CLI를 사용한다. orca-cli 스킬로 실제 설치본을 확인한다.

```text
python <plugin>/skills/kickoff-workspaces/scripts/ws_upgrade.py <project> --dry-run
python <plugin>/skills/kickoff-workspaces/scripts/ws_upgrade.py <project> --profiles <local-roles.json>
```

설치 결과는 Git 공통 디렉터리 ohmypm/project.json 및 외부의 내용 해시별 runtime이다.
프로젝트 AGENTS.md/CLAUDE.md, .gitignore, orca.yaml, .worktreeinclude, 훅은 수정하지 않는다.
이유(T-006): 프로젝트의 gitignore가 배포 파일을 삼켰고(09-18·09-22), 버전마다 23개 프로젝트를
고쳐야 했으며, 프로젝트 훅이 역할 정책과 얽혀 pl의 커밋을 막았다. 훅을 안 쓴다는 뜻이 아니다 —
훅 본체는 런타임(`scripts/guard.py`)에 실리고, 켤지·무엇을 막을지는 `.git/ohmypm/project.json`의
harness에 적혀 역할 세션 기동 때 `--settings`로 얹힌다. 프로젝트 트리에는 아무것도 생기지 않는다.
모델·effort·approval은 profiles JSON의 roles.main/pl/work에서 선택한다.
pl은 사용자와 합의한 최고 성능 모델이며 Codex pl의 기본 approval은 사용자 지정 bypass다.
설치 결과 runtime.path 아래 scripts/environment_cli.py가 운영 진입점이다.

등록 후 role-connect --role main으로 세션을 준비하고 context 수락을 확인한다.
프로젝트 지침과 공유 의존성 충돌은 보존·보고하며 무관한 터미널을 종료하지 않는다.
역할·판정은 PROTOCOL.md, 명령·복구는 ../dispatch/references/runtime.md를 읽는다.
기존 1.0 작업은 보존된 실행기로 마무리한다. migration-plan의 소유권·충돌·활성 작업을 검토하고
그 digest로 migration-apply한다. 훅 출처가 불명확하면 자동 제거/복원하지 않는다.
실제 타 프로젝트 전환은 별도 범위다. 전체 배포는 명시적 경로 목록에만
ws-rollout.sh <project> ...로 외부 등록한다. 자동 발견·커밋·푸시는 없다.

## 처음 등록할 때 묻는 것 (2026-09-23)

이미 등록된 프로젝트(`.git/ohmypm/project.json`이 있음)를 다시 올릴 때는 묻지 않고 기존 답을 잇는다.
바꾸려면 `--profiles`·`--harness`를 다시 넘긴다. 처음이면 사용자에게 아래를 묻고, 답을 JSON 두 개로
적어 등록 인자로 넘긴다. 스크립트는 대화하지 않는다 — 묻는 쪽은 이 스킬이다.

1. 역할별 모델·effort — main / pl / work. 기본은 `templates/workflow.json`.
2. 역할별 권한 자세 — `bypass`(묻지 않음, 기본) / `default`(CLI 기본 승인). 승인 프롬프트는
   안전장치가 아니라 사람이 온종일 읽고 누르는 일이 된다는 것이 기본을 bypass로 둔 이유다.
3. 가드 — 런타임 가드가 막을 Bash 패턴(`deny`)과 아예 뺄 도구(`disallowed_tools`). 기본은
   `templates/harness.json`(되돌리기 불가·외부 발신). 프로젝트가 더 막거나 풀 것이 있으면 여기서 정한다.

```text
profiles.json  {"roles": {"main": {...}, "pl": {...}, "work": {...}}}
harness.json   {"deny": ["rm -rf", ...], "disallowed_tools": ["WebFetch", ...]}
python <plugin>/skills/kickoff-workspaces/scripts/ws_upgrade.py <project> --profiles profiles.json --harness harness.json
```

답은 `.git/ohmypm/project.json`에 남고 `doctor`가 보여준다. 역할 세션이 뜰 때 `.git/ohmypm/roles/<role>/`에
`<token>.settings.json`·`<token>.deny.json`이 생겨 `--settings`·`--disallowedTools`로 넘어간다.
