# 인터페이스 명세 v3 (2026-10-10)

> 기준: 2차 리뉴얼 9단계 커밋. 기계 대조는 `http://127.0.0.1:8123/openapi.json`(`EXPOSE_DEV_TOOLS=true`일 때 `/docs`).

## 내놓는 API (접두어 `/api`)

| 메서드·경로 | 용도 | 입력 → 동작 |
|---|---|---|
| GET `/projects` | 프로젝트 목록 | `installed`(ohmypm/ 유무) 포함 |
| POST `/projects/remove` | 관리 제외 | `{path}` → enabled=0, 글·대화 삭제. 폴더는 안 건드림 |
| POST `/projects/install` / `/uninstall` | 한 프로젝트 설치·제거 | `{path}` → `ohmypm/`·지침 블록 생성 또는 삭제 |
| POST `/scan` | 발견 + 전체 설치 | 동기. `{projects, installed, already, self_skipped, errors}` |
| GET `/agents` · POST `/agents/model` | 담당 목록(점수·최근 회차·배운 것·모델) / 모델 변경 | `{project, model}` |
| GET `/scores?project=&limit=` | 회차별 점수 이력 | |
| GET/POST `/messages` · POST `/room-retry` | 방 대화 / 룸에서 사용자 발화면 담당이 답(백그라운드) / 끊긴 답 재요청 | `{room, author, body}` |
| POST `/board/session` | 토론 시작 | `{minutes: 10|30|60, paths?}` → 세션 스레드 |
| GET `/board/session` · POST `/board/session/stop` · GET `/board/sessions` | 현재 세션(남은 초·단계·통계) / 중지 / 이력 | |
| GET `/posts` · GET `/posts/{id}` · POST `/posts/{id}/comments` · `/like` · `/dislike` · POST `/comments/{id}/react` | 게시판 읽기와 사용자 반응 | |
| GET `/weekly` · POST `/weekly/run` · GET `/jobs/weekly` | 주간보고 목록 / 실행(백그라운드 — 점검 대화 포함이라 수십 분) / 상태 | 프로젝트 방 `weekly::날짜::path` = PM(`pm`)·담당(`agent`) 대화 + 변경 리뷰(`review`) + 맨 끝 몫(`ohmyPM`) |
| GET `/cards?project=` · POST `/cards` · POST `/cards/{id}` · DELETE `/cards/{id}` | 칸반 카드 목록(+칸 목록) / 추가 / 고치기·옮기기 / 지우기 | status = needs_user·todo·doing·waiting·done. '지연'은 계산(기한 지남 + 미완료) |
| GET `/lab` · GET `/lab/{id}/wiki` · POST `/lab/{id}/run` · POST `/lab/{id}/ask` | 연구원 명부 / 위키 탭 / 조사 실행 / 자문 | id = models·design·skills |
| GET `/lab/{id}/notes` · GET `/lab/{id}/notes/{key}/assets/{filename}` | 정리 문서(본문·첨부 목록) / 영상·이미지 | `docs/lab/notes/{id}/*.md`, 문서 이름으로 시작하는 첨부만 허용. 자문은 정리 문서 전문도 읽음 |
| GET `/lab/proposals?researcher=&project=` · POST `/lab/proposals/{id}/status` | 제안서 목록 / 상태(open·done·dismissed) | |
| GET `/lab/{id}/notes` · GET `/lab/{id}/notes/{key}/assets/{file}` | 정리 문서(주제별 문서 + 첨부) / 첨부 파일 | `docs/lab/notes/<id>/<key>.md` |
| GET `/lab/{id}/requests` · POST `/lab/{id}/requests` | 조사 요청 목록 / 요청 `{topic, detail?}` | 대기열을 작업 하나(`lab-note`)가 차례로 처리 → 정리 문서. status = queued·running·done·failed |
| GET `/ports` · POST `/ports` · DELETE `/ports/{id}` · POST `/ports/{id}/start` · `/stop` | 포트 등록·감지(명령줄로 프로젝트 매칭)·켜기·끄기 | |

## 쓰는 외부 것

| 대상 | 어디서 | 한도·주의 |
|---|---|---|
| Claude Code CLI `claude -p` | `src/cc/client.py` 전부 | 작업마다 `--model` 명시, 타임아웃 90~420초, 도구 화이트리스트(`permissions.py`) |
| 공식 모델 문서 4곳(Anthropic·OpenAI) | `model_catalog.py`(httpx) | 절 단위 diff, 바뀐 것만 모델에 |
| 웹(WebSearch/WebFetch) | 랩실 디자인·스킬 연구원, 자문 | 연구원 프롬프트가 출처 URL을 요구, 코드가 https만 받음 |
| git | 주간보고(`git log`), 토론 글쓰기(담당이 프로젝트를 읽음) | 도구 커밋(ohmypm 표식) 제외 |
| 각 프로젝트 파일 | `install.py`, 주간보고, 랩실 | `ohmypm/`과 지침 블록만 쓴다. 커밋 안 함 |

## 설정(.env)

`PROJECTS_ROOT`, `CC_BIN`, `MODEL_LIGHT/STANDARD/HEAVY`, `ALLOW_FRONTIER_HEADLESS`, `MODEL_TRACK_CLAUDE/CODEX`,
`BOARD_CONCURRENCY`(기본 2), `BOARD_MAX_MINUTES`(60), `SCHEDULER_ENABLED`, `EXPERT_COLLECT_WEEKDAY/HOUR`(랩실 정기 조사).
