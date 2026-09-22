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
