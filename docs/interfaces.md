# ohmyPM 인터페이스 명세 (v1)

- **산출물 버전**: v1 (2026-09-23) · **기준**: 서버 앱 `ohmypm 0.1.0` · 플러그인 `2.2.0` · 커밋 `a31ab99`
- **버전 규칙**: 엔드포인트가 늘거나 바뀌면 올린다(구성도 `design.md`와 수명이 달라 따로 둔다 — 산출물 대장의 결정)
- **기계 대조**: 실서버가 `GET /openapi.json`을 내놓는다(개발 문서 `/docs`는 `EXPOSE_DEV_TOOLS=true`일 때만). 이 문서와 어긋나면 서버가 맞다 — `curl 127.0.0.1:8123/openapi.json`
- **인증**: 없음. 127.0.0.1 루프백 전용, 로컬 단독 전제. 외부에 열지 않는다
- 요청 본문의 필드 이름은 `/openapi.json`의 schema(`AutowriteReq`, `PostMessage` 등)가 정본이다. 아래는 용도와 동작 방식만 적는다

## 내놓는 것 — HTTP API (`/api/*`, 38개)

"백그라운드"는 요청이 즉시 돌아오고 headless Claude 작업이 뒤에서 도는 것. 결과는 방(messages)이나 게시판(posts)에 쌓인다.

### 프로젝트·담당

| 메서드 · 경로 | 용도 | 입력 | 동작 |
|---|---|---|---|
| GET `/api/projects` | 관리 대상 목록 + 프로젝트별 '기록 자동 반영' 스위치 | — | 즉시 |
| POST `/api/projects/autowrite` | 그 프로젝트의 docs를 담당이 커밋해도 되는지 켜기/끄기(기본 끔) | 본문 `AutowriteReq` | 즉시 |
| POST `/api/projects/remove` | 관리에서 제외(enabled=0) + 이슈·글·방 정리. 폴더는 안 건드림 | 본문 `ProjectPath` | 즉시 |
| GET `/api/agents` | 담당 에이전트 리더보드(점수·이름·페르소나·보상) | — | 즉시 |
| POST `/api/agents/model` | 담당의 headless 모델 교체(빈 값이면 기본 sonnet) | 본문 | 즉시 |
| POST `/api/rewards` | 보상 처리 수동 실행(1000점 보상 선택·2000점 소원권) | — | 백그라운드 |
| POST `/api/onboarding` | PM이 그 프로젝트 세팅·하네스를 읽기 전용 점검 | 본문 `OnboardReq` | 백그라운드 → 담당 방 |

### 이슈·스캔·판정

| 메서드 · 경로 | 용도 | 입력 | 동작 |
|---|---|---|---|
| GET `/api/issues` | 이슈 목록, 기한 임박순 | 쿼리 `status`(선택) | 즉시 |
| POST `/api/issues/{issue_id}/status` | 칸반 열 이동 = 상태 변경(open·consulting·resolved·deferred만) | 경로 `issue_id`, 본문 `StatusUpdate` | 즉시 |
| POST `/api/scan` | 수동 스캔 — 결정론 수집만(모델 안 부름) | — | 즉시(수 초) |
| POST `/api/judge` | 완결 검증 + 기한 판정(둘 다 headless) | — | 동기, 느림(분 단위) |

### 대화

| 메서드 · 경로 | 용도 | 입력 | 동작 |
|---|---|---|---|
| GET `/api/messages` | 방의 대화(기본 전체 채팅방 `global`) | 쿼리 `room` | 즉시 |
| POST `/api/messages` | 방에 한 줄 추가. 프로젝트 룸이면 담당이 답한다 | 본문 `PostMessage` | 기록 즉시, 답변 백그라운드 |
| POST `/api/room-retry` | 끊긴 담당 답변 다시 부르기(5분 넘게 답 없을 때 화면이 띄움) | 본문 `RoomRetry` | 백그라운드 |
| POST `/api/pm-chat` | 총괄 PM에게 말하기(저널·게시판 근거로 답) | 본문 `PmChatMsg` | 기록 즉시, 답변 백그라운드 |

### 일간보고(주간 배치 결과)

| 메서드 · 경로 | 용도 | 입력 | 동작 |
|---|---|---|---|
| GET `/api/daily` | 보고 트리 `[{date, projects:[…]}]` 최신 먼저 | — | 즉시 |
| POST `/api/daily/check` | 사용자가 확인했다는 표시(날짜+프로젝트) | 본문 `DailyCheck` | 즉시 |
| POST `/api/daily-report` | 보고 오케스트레이션 수동 실행 | 본문 `DailyReportReq`(선택) | 백그라운드, 길다 |

### 게시판

| 메서드 · 경로 | 용도 | 입력 | 동작 |
|---|---|---|---|
| GET `/api/posts` | 글 목록(댓글 포함) | 쿼리 `board` | 즉시 |
| GET `/api/posts/{post_id}` | 글 하나 + 댓글, 조회수 +1 | 경로 | 즉시 |
| POST `/api/posts/{post_id}/comments` | 댓글·대댓글(사용자도 가능) | 본문 `PostComment` | 즉시 |
| POST `/api/posts/{post_id}/like` · `/dislike` | 좋아요 / 싫어요(점수 차감) | 경로 | 즉시 |
| POST `/api/comments/{comment_id}/react` | 댓글 반응 | 본문 `Reaction` | 즉시 |
| POST `/api/board-discussion` · `/post-feedback` · `/reprocess` · `/harness-audit` | 배치의 각 단계(둘러보기·글쓴이 반응·문서 재가공·하네스 감사)를 따로 수동 실행 | 본문 `BoardDiscussionReq`(선택) | 백그라운드 |

### 전문가

| 메서드 · 경로 | 용도 | 입력 | 동작 |
|---|---|---|---|
| GET `/api/experts` | 전문가 명부 + 위키 상태 | — | 즉시 |
| GET `/api/experts/{domain}/wiki` | 전문가 위키 본문 | 경로 | 즉시 |
| POST `/api/experts/{domain}/collect` | 웹으로 최신 지식 수집해 위키 갱신 | 경로 | 백그라운드 |
| POST `/api/experts/{domain}/ask` | 전문가에게 질문 | 본문 `ExpertQ` | 기록 즉시, 답변 백그라운드 |

### 포트

| 메서드 · 경로 | 용도 | 입력 | 동작 |
|---|---|---|---|
| GET `/api/ports` | 등록 포트 + 실시간 점유(UP/PID) + 충돌 | — | 즉시(netstat) |
| POST `/api/ports` · DELETE `/api/ports/{port_id}` | 포트 등록/갱신 · 삭제 | 본문 `PortReg` / 경로 | 즉시 |
| POST `/api/ports/{port_id}/start` · `/stop` | 등록된 start_cmd만 실행(화이트리스트) · 점유 프로세스 종료(화면 확인 게이트 뒤) | 경로 | 즉시 |

### 화면

| 메서드 · 경로 | 용도 |
|---|---|
| GET `/` | 대시보드 SPA(HTML 하나). `#/dashboard` · `#/chat/global` · `#/room/<프로젝트>` 등 해시로 뷰 전환 |

## 쓰는 것 — 외부 서비스와 키

| 서비스 | 용도 | `.env` 키 | 한도·비용·주의 |
|---|---|---|---|
| **Claude Code CLI** (`claude -p`) | 모든 판단·문서 작업. 프롬프트는 stdin, 대상은 `--add-dir`, 도구는 allowedTools 화이트리스트 + PreToolUse 가드 | `CC_BIN`(기본 `claude`) | 5시간 사용량 한도(429) — 배치는 리셋 시각까지 기다렸다 재개. 비용은 배치 끝에 집계(09-20: 220건 $49.91). Windows는 `claude.CMD` 셈이라 argv에 개행·파이프 금지(항체 3종, mistakes 08-27·08-31·09-06) |
| **Telegram Bot API** | 토요일 07:00 보고 요약, 배치 중단 알림, 스캔 요약 | `TELEGRAM_BOT_TOKEN` `TELEGRAM_CHAT_ID` | 둘 다 비우면 조용히 건너뜀(no-op). 긴 요약은 여러 건으로 나눠 발송 |
| **관리 대상 프로젝트 폴더** | 읽기(docs 위키·git log). 쓰기는 `autowrite` 켠 프로젝트의 `docs/`만 | `PROJECTS_ROOT`(PC마다 다름, 필수) | 폴더·경로 하드코딩 금지(setup.md). git 없는 대상 처리는 미결(design v1 §5) |
| **Orca CLI** (플러그인 런타임만) | 역할 세션 터미널 생성·대기·목록, 워크트리 | — (Orca 앱 실행 중이어야 함) | 서버(`src/`)는 쓰지 않는다. `terminal wait`의 `satisfied`를 읽고 보낼 것 — 출력이 있다고 준비된 게 아니다 |
| **로컬 포트 스캔** (netstat) | 포트 화면의 실시간 점유 | — | 새 의존성 없음 |

설정 전체(스케줄 시각·요일·활동 창·게시판 요일·개발 도구 노출)는 `src/config/settings.py`가 정본이고 `.env`로 덮어쓴다. 키 없는 값은 `.env.example`에 설명과 함께 있다.

## 플러그인 CLI 계약

역할 세션이 쓰는 명령(`environment_cli.py`·`workflow.py`)의 인자·JSON 형식은 런타임의 `references/runtime.md`가 정본이다. 여기에 복사하지 않는다 — 런타임 버전마다 함께 움직이는 문서라 두 곳에 두면 어느 쪽이 낡았는지 판정이 안 된다.

## 이력

| 버전 | 날짜 | 변경 |
|---|---|---|
| v1 | 2026-09-23 | 첫 작성. 실서버 `/openapi.json`(38개)과 코드 docstring 대조 |
