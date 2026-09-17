# T-003 다른 프로젝트에 작업 구조 자동 배포

- 상태: 검토 반영 v2
- 등급: L (차선 L) — 운영 저장소를 포함한 여러 프로젝트의 구조·Git 설정 변경과 커밋
- 작성: pl, 2026-09-18

## 목표
`ohmypm@ohmypm-local 0.3.3`(원본 `plugin/`)에서 다른 프로젝트를 탐색하여 작업 구조를 자동 설치·갱신한다.
반복 가능한 배포 기능과 로컬 허용 목록에 대한 실행 결과를 남긴다.

## 범위
- 안: 발동어 `구조 전체 배포하자`와 `scripts/ws-rollout.sh` 한 명령을 진입점으로 탐색·배포·한국어 커밋·결과 저장까지 수행한다. 기존 `ws-upgrade.sh <경로> --install "<공유폴더들>" "<setup 명령>"`을 재사용하며 플러그인 설치 훅은 만들지 않는다.
- 로컬 입력: main이 `docs/rollout-targets.md`에 허용 경로·제외 대상과 사유·탐색 방식을 작성한다. `.gitignore`·`.worktreeinclude`에 이 파일과 결과 디렉터리 `docs/rollouts/`를 등재하며, 둘 다 Git 미추적·`index.md` 미등재로 유지한다. 입력 부재·형식 오류·로컬 전용 설정 누락이면 배포 전에 실패한다. 다른 PC의 `docs/setup-rollout.md`에는 의존하지 않는다.
- 밖: 대상 `.env`·비밀 파일 읽기/복사, 운영 코드 수정·실행, setup·패키지 설치·대상 테스트·서버 기동, 푸시, dirty 상태 정리(stash/reset/clean), pl 워크트리·터미널 개설. 공개 파일에는 사용자 경로·대상 이름·개수·커밋 SHA 등 로컬 식별 정보를 옮겨 적지 않는다.

## 완료 기준 (관찰 가능한 문장 — 기준 하나에 확인 방법 하나)
1. [ ] `SKILL.md`의 발동어 `구조 전체 배포하자`가 `scripts/ws-rollout.sh` 한 명령으로 연결되고, `docs/setup.md` 설치 ③ 뒤에도 같은 명령이 안내된다. 플러그인 훅 없이 이 진입점에서 프로젝트별 추가 지시 없이 결과 저장까지 진행하며 재실행 가능하다. — 확인: 임시 저장소를 대상으로 한 진입점 통합 실행 기록.
2. [ ] 탐색은 `http://127.0.0.1:8123/api/projects`(서버의 enabled 필터와 별도로 클라이언트가 `has_wiki=1`을 필터링) 또는 명시한 `PROJECTS_ROOT` 직하위 폴더를 사용한다. API 실패는 실패로 기록하고 임의로 탐색 범위를 넓히지 않는다. 정규화한 저장소 루트로 중복을 제거한 뒤 로컬 허용 목록과 교집합을 취하며, 허용 목록의 미발견 경로도 사유를 기록한다. — 확인: API 주소·필터·실패·폴더 탐색·중복·허용 목록을 포함한 임시 입력의 대상 목록.
3. [ ] 쓰기 전에 Git 저장소 루트 여부, staged/unstaged/untracked 변경, 설치 버전, 유효한 `core.hooksPath`를 검사한다. Git 없음·경로 없음·dirty 및 훅 경로 값이 있으면서 `.githooks`가 아닌 경우는 사유와 함께 건너뛴다. 설치 버전이 플러그인 버전과 같으면 파일·Git 설정·커밋을 바꾸지 않는다. — 확인: 해당 상태별 임시 폴더의 실행 전후 비교.
4. [ ] 스택 선언·잠금 파일에서 공유 폴더와 setup 문자열을 정하고 근거를 결과에 남긴다. Python은 `.venv`, Node는 `node_modules`, 혼합은 합집합이며 setup은 잠금 파일/패키지 관리자에 맞춘다. 공유 환경을 지우는 정확 동기화(`uv sync` 등)는 피하고 판별 불가는 사유를 남겨 건너뛴다. setup은 설정에만 기록한다. — 확인: Python·Node·혼합·미확정 임시 저장소의 생성 설정 비교.
5. [ ] 미설치 대상은 `ws-upgrade.sh --install`로 설치하고, 버전이 다른 기존 설치는 같은 설치기의 정상 동작대로 관리 파일·작업 구조 블록을 교체하여 갱신한다. `CLAUDE.md`·`AGENTS.md`의 블록 밖 원문과 기존 프로젝트 소유 파일(`docs/roles.md`·`orca.yaml`·`.worktreeinclude`·`.gitignore`)은 보존한다. — 확인: 신규·다른 버전 설치와 기존 원문·소유 파일을 넣은 임시 저장소의 전후 비교.
6. [ ] 변경이 생긴 프로젝트에 배포 파일만 명시적으로 stage하여 `작업 구조 설치/갱신: kickoff-workspaces v<버전>` 형식의 한국어 커밋을 한 번 남기고 푸시하지 않는다. 커밋 훅은 정상 실행하며 `--no-verify` 등 우회는 금지한다. 훅 거부를 포함한 커밋 실패는 실패로 기록한다. — 확인: 훅 통과·거부 임시 저장소의 명령 기록과 커밋 파일 목록.
7. [ ] 한 프로젝트의 실패 후에도 나머지를 처리한다. 로컬 보고서에 `프로젝트·경로·설치/갱신/건너뜀/실패·사유·버전·공유폴더·setup·커밋 SHA` 표, 실패 시 변경 잔존 여부를 남기며 실패가 있으면 전체 종료도 실패로 표시한다. 성공 대상 재실행에는 추가 커밋이 없다. — 확인: 중간 실패를 포함한 배포와 재실행의 로컬 결과 표.
8. [ ] 로컬 허용 목록의 각 대상에 설치·갱신 또는 규칙에 따른 건너뜀 결과가 있고 미해결 실패는 없다. `docs/rollouts/T-003-structure-rollout.md`에 실행 일시·명령·탐색 출처·제외 사유·기준별 증거를 남긴다. 입력과 결과 디렉터리는 gitignore·.worktreeinclude 등재, Git 미추적, index 미등재 상태이며 공개 검증 표에는 로컬 식별 정보를 전재하지 않는다. — 확인: 로컬 보고서·커밋 기록·로컬 전용 설정의 대조.

## 손대는 파일
- `plugin/skills/kickoff-workspaces/scripts/ws-rollout.sh`(새 파일), `plugin/skills/kickoff-workspaces/SKILL.md` — 반복 배포 명령과 발동어. 기존 `scripts/ws-upgrade.sh` 호출.
- `docs/setup.md` — 설치 ③ 뒤에 전체 배포 명령 한 줄 추가.
- 이 저장소의 `.gitignore`, `.worktreeinclude` — `docs/rollout-targets.md`와 `docs/rollouts/` 등재. 입력 파일은 main이 생성하며 워커는 읽기만 한다. 두 로컬 경로는 `index.md`에 등재하지 않는다.
- 허용 대상의 `docs/protocol.md`, `docs/tasks/_template.md`, `docs/reviews/_template.md`, `.githooks/pre-commit`, `AGENTS.md`, `CLAUDE.md` — 관리 파일/블록 설치·갱신; `docs/roles.md`, `orca.yaml`, `.worktreeinclude` — 없을 때만 생성. `.git`은 사전 검사를 통과한 훅 경로 설정·stage·커밋에 한정한다.
- `docs/rollouts/T-003-structure-rollout.md` — 구현 워커가 남기는 로컬 전용 실행 결과와 증거. 스펙 밖 변경 금지.

## 필요 도구
설치할 도구 없음. 기존 Git Bash(sh·sed 등), Git, Python 표준 라이브러리(설치기·JSON/HTTP 처리)를 사용한다. 부족하면 실패 사유를 보고하며 임의 설치하지 않는다.

## 검토 반영 (v2)
| # | 지적(요약) | 처리 | 근거·변경 |
|---|---|---|---|
| 1 | 공개 스펙에 로컬 대상 정보 노출 | 수용 | 경로·이름 목록·개수를 삭제. main 작성의 로컬 전용 `docs/rollout-targets.md`를 입력으로 지정하고 다른 PC 산출물 의존 제거. |
| 2 | 결과 보고서의 공개 추적·index 처리 누락 | 수용 | `docs/rollouts/` 전체와 입력 파일을 gitignore·.worktreeinclude 등재, Git 미추적·index 미등재로 명시. 공개 검증 표 전재 금지. |
| 3 | 기존 설치 갱신과 보존 규칙 충돌 | 수용 | 같은 버전만 무변경. 다른 버전은 관리 파일·블록 교체, 블록 밖 원문·프로젝트 소유 파일 보존. 보존 충돌 건너뜀 삭제. |
| 4 | 기존 훅 경로 덮어쓰기와 훅 실행 규칙 충돌 | 수용 | core.hooksPath가 비어 있지 않고 .githooks가 아니면 사전 건너뜀. 커밋 훅 정상 실행·거부 시 실패, --no-verify 등 우회 금지. |
| 5 | 기준 버전 불일치 | 수용 | 기준 버전을 0.3.3으로 수정. 실행 시 버전은 플러그인 메타데이터를 따른다. |
| 6 | 배포 진입점 불명확 | 수용 | SKILL.md 발동어와 ws-rollout.sh 한 명령으로 확정. 플러그인 훅 없음, docs/setup.md 설치 ③ 뒤 명령 추가를 범위에 포함. |
| 7 | API 주소와 has_wiki 필터 주체 누락 | 수용 | 로컬 API 주소를 명시하고 has_wiki는 클라이언트 필터로 확정. |

## 검증 (pl2, 구현 후)
| 기준 | 판정 | 확인한 방법 |
|---|---|---|
