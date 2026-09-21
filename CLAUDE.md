# ohmyPM

모든 로컬 프로젝트를 매일 돌보는 메타 PM 에이전트 (Claude Code 기반). 기획은 `docs/plan.md`.

## docs/ — LLM 위키

docs/는 LLM이 쓰고 사람이 읽는 위키다. git이 못 담는 것만 담는다: 결정과 근거, 실수와 항체, 기각된 대안.

- **착수 전 `docs/status.md`(보드)를 읽는다.** 끝나면 결과를 한 줄이라도 남긴다
- **기록은 작업의 매듭에서** (커밋 직전, 갈래를 매듭지을 때) — 관련 페이지 갱신 + `docs/log.md`에 `## [YYYY-MM-DD] <작업> | <제목>`
- **버려지는 안건은 `docs/pending.md`에 재검토 시점(날짜/조건)과 함께** — 시점 없이 "나중에"로 넘기지 않는다
- 새 페이지는 `index.md`에 한 줄 등재. **반영이 끝난 페이지는 삭제한다** — 살아있는 건 status·pending·항체뿐
- 상세 규약(raw 보존, asserted/inferred, 실수 연대기, 정리 기준)은 `docs/conventions-wiki.md`

## 작업 구조 (kickoff-workspaces v1.0.0)
- 역할은 `docs/roles.md`, 모델은 `docs/workflow.json`, 절차는 `docs/protocol.md`, 명령은 `docs/workflow-guide.md`.
- main은 요청 접수·단순 작업·pl 연결·사용자 알림·환경 준비·로컬 머지를 맡고 복잡한 요청은 `ohmypm:dispatch`로 진행한다.
- pl이 사용자와 설계·품질 기준·검증 방법을 충분히 합의하고 최종 판정한다. main은 pl 질문을 사용자에게 안내한다.
- work는 승인된 manifest의 범위만 구현·검증하고 근거를 제출한다. 기준은 수정하지 않는다.
- 독립성이 확인된 work만 최대 두 개 병렬. main의 통합은 순차이며 판정 후 변경되면 재검증한다.
- 상태·증거는 Git 공통 디렉터리에 남기고 Orca가 실행·터미널 생명주기를 소유한다. main이 유일한 코디네이터다.
- 상시 pl2·pl3는 없다. 기존 터미널·진행 중 작업은 보존한다. 푸시·배포·전체 전환은 별도 요청이다.
