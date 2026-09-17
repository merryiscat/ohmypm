# ohmyPM

모든 로컬 프로젝트를 매일 돌보는 메타 PM 에이전트 (Claude Code 기반). 기획은 `docs/plan.md`.

## docs/ — LLM 위키

docs/는 LLM이 쓰고 사람이 읽는 위키다. git이 못 담는 것만 담는다: 결정과 근거, 실수와 항체, 기각된 대안.

- **착수 전 `docs/status.md`(보드)를 읽는다.** 끝나면 결과를 한 줄이라도 남긴다
- **기록은 작업의 매듭에서** (커밋 직전, 갈래를 매듭지을 때) — 관련 페이지 갱신 + `docs/log.md`에 `## [YYYY-MM-DD] <작업> | <제목>`
- **버려지는 안건은 `docs/pending.md`에 재검토 시점(날짜/조건)과 함께** — 시점 없이 "나중에"로 넘기지 않는다
- 새 페이지는 `index.md`에 한 줄 등재. **반영이 끝난 페이지는 삭제한다** — 살아있는 건 status·pending·항체뿐
- 상세 규약(raw 보존, asserted/inferred, 실수 연대기, 정리 기준)은 `docs/conventions-wiki.md`

## 작업 구조 (kickoff-workspaces v0.3.1)
- 자리·모델·경로는 `docs/roles.md`, 절차는 `docs/protocol.md`
- `pl` 워크트리의 Claude 터미널 = pl2: ① 검토자 — `docs/reviews/T-NNN.review-vN.md`에 지적만(근거·심각도·차단, 재작성 금지, 없으면 "지적 없음") ② 코디네이터 — 게이트·워커 배정·`check --wait`·검증(스펙 "검증" 절) ③ 구현·문서 작성은 하지 않는다(워커 몫). pl(Codex)은 종량 쿼터라 pl 몫(스펙 v1·v2) 외엔 pl을 부르지 않는다
- `T-NNN-*` 워크트리의 Claude = 구현 워커: 스펙 밖 변경 금지, `worker_done`에 완료 기준을 항목별 통과/실패로 보고. 스펙에 없는 도구는 설치하지 않는다
- 원본 체크아웃(main): 요청을 받으면 **차선부터**(protocol 0절) — S(파일 1~2·명확·되돌리기 쉬움)는 직접 하고 커밋, M·L은 `ohmypm:dispatch`로 pl→pl2에 넘긴다. 차선을 한 줄로 말하고 시작한다. 반복 운영 업무는 첫 회만 스펙, 이후는 pl2가 워커 재배정
