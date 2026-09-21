---
name: kickoff-workspaces
description: Orca 프로젝트에 ohmyPM 1.0의 main·pl·work 역할, 실행 도구, 스펙·검증 계약과 특화 작업 환경 준비 절차를 설치하거나 갱신한다. "작업 구조 세팅하자", "구조 업데이트하자", 기존 프로젝트에 1.0을 적용할 때 사용한다. 프로젝트 전체 배포는 별도 요청일 때만 수행한다.
---

# 작업 구조 — ohmyPM 1.0

main은 접수·환경 준비·알림·머지, pl은 사용자와의 설계·품질 판단, work는 구현을 맡는다.
상시 pl2·pl3는 없다. 작은 작업에는 main 직접 처리를 유지한다.

## 설치와 이전

Python 3.11+, Git, Orca와 역할별 모델 CLI가 필요하다. `orca-cli` 스킬로 실제 설치본을 확인한다.

```text
python <plugin>/skills/kickoff-workspaces/scripts/ws_upgrade.py <project> --dry-run
python <plugin>/skills/kickoff-workspaces/scripts/ws_upgrade.py <project>
```

0.x 작업 구조가 있으면 진행 중 작업을 완료하거나 보존한 후 합의된 범위에서 `--migrate-v1`을 사용한다.
프로젝트 소유 모델 설정·Orca 설정·기존 작업 파일은 유지하고 바뀌는 관리 파일과 역할표는 Git 공통
디렉터리에 백업한다. 프로젝트 밖을 일괄 갱신하지 않는다.

설치 결과:
- `docs/protocol.md`, `docs/roles.md`, `docs/workflow.json`, 스펙·검토 템플릿, 실행 가이드
- `.ohmypm/bin/workflow.py`와 표준 라이브러리 실행 모듈
- AGENTS/CLAUDE 작업 구조 블록. 블록 밖 내용과 사용자 훅은 보존한다.

`docs/workflow.json`이 역할별 모델의 단일 출처다. pl에는 사용자가 선택한 최고 성능 모델을 둔다.
기존 역할표에 사용자 모델 선택이 있으면 이 파일로 옮기고 확인한다.

## Orca 설정과 자리

새 설치는 `worktree.sharedDirectories: []`이고 공용 setup을 자동 실행하지 않는다.
기존 `orca.yaml`은 설치기가 덮지 않는다. work 준비 전에 `.venv`·`node_modules` 공유를 제거하는
프로젝트 설정 변경을 검토한다. 기존 폴더·심볼릭 링크 자체를 지우지 않는다.
`.worktreeinclude`는 프로젝트가 정한 파일만 유지하며 비밀·DB·로그를 일괄 복사하지 않는다.

기존 pl이 있으면 재사용한다. 새 pl이 필요하면 `orca-cli`로 워크트리·터미널을 준비하고
`templates/prompt-pl.md`의 역할을 전달한다. 모델·effort 지정은 설치된 Orca의 지원 경로를 사용한다.
기존 pl2 터미널을 임의 종료하지 않는다. 처음 요청은 `dispatch`로 이어진다.
절차는 [PROTOCOL.md](PROTOCOL.md), 하네스 예시는 `templates/workflow-manifest.json`을 사용한다.

## 전체 배포

1.0은 ohmypm부터 시험한다. `ws-rollout.sh`는 명시적인 전체 배포 요청에만 사용한다.
0.x 전환 대상에는 별도의 `--migrate-v1`이 필요하다. dry-run·로컬 허용 목록·dirty 상태·훅 검사·
프로젝트별 결과 보고를 유지한다. 푸시는 하지 않는다.
