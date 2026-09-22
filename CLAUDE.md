# ohmyPM

모든 로컬 프로젝트를 매일 돌보는 메타 PM 에이전트 (Claude Code 기반). 기획은 `docs/plan.md`.

## docs/ — LLM 위키

docs/는 LLM이 쓰고 사람이 읽는 위키다. git이 못 담는 것만 담는다: 결정과 근거, 실수와 항체, 기각된 대안.

- **착수 전 `docs/status.md`(보드)를 읽는다.** 끝나면 결과를 한 줄이라도 남긴다
- **기록은 작업의 매듭에서** (커밋 직전, 갈래를 매듭지을 때) — 관련 페이지 갱신 + `docs/log.md`에 `## [YYYY-MM-DD] <작업> | <제목>`
- **버려지는 안건은 `docs/pending.md`에 재검토 시점(날짜/조건)과 함께** — 시점 없이 "나중에"로 넘기지 않는다
- 새 페이지는 `index.md`에 한 줄 등재. **반영이 끝난 페이지는 삭제한다** — 살아있는 건 status·pending·항체뿐
- 상세 규약(raw 보존, asserted/inferred, 실수 연대기, 정리 기준)은 `docs/conventions-wiki.md`
