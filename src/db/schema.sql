-- ohmyPM 로컬 상태 저장 (SQLite). init_db()가 CREATE TABLE IF NOT EXISTS 로 실행.

-- 1) 관리 대상 프로젝트 (케이스 12)
CREATE TABLE IF NOT EXISTS projects (
    path      TEXT PRIMARY KEY,        -- 절대경로 = 자연키
    name      TEXT NOT NULL,
    has_wiki  INTEGER DEFAULT 0,       -- (옛 열) docs/ 위키 유무 — 더 안 쓴다
    installed INTEGER DEFAULT 0,       -- ohmypm/ 폴더 설치 여부 (0/1)
    enabled   INTEGER DEFAULT 1,       -- 관리 대상 등록 여부 (0/1)
    last_scan TEXT                     -- 마지막 스캔 시각 (ISO8601)
);

-- 2) 키/값 설정 저장소(마이그레이션 표식 등)
CREATE TABLE IF NOT EXISTS alerts (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- 3) 메시지 보드 — 에이전트 채팅방 + 프로젝트 룸 (사용자·에이전트 대화 기록)
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    room       TEXT NOT NULL,          -- 'global'(전체 채팅방) | 프로젝트 path(프로젝트 룸)
    author     TEXT NOT NULL,          -- 'user' | 에이전트 이름(scanner/judge/pm…)
    body       TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_messages_room ON messages(room, id);

-- 4) 게시판 — 글(post) + 댓글(comment). 토론 세션에서 담당 에이전트들이 쓰고 반응한다.
CREATE TABLE IF NOT EXISTS posts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    board      TEXT NOT NULL DEFAULT 'daily',  -- 게시판 키(지금은 'daily' 하나)
    project    TEXT,                           -- 이 글의 대상 프로젝트 path(있으면)
    author     TEXT NOT NULL,                  -- 글쓴이(보통 프로젝트명 or 'pm')
    title      TEXT NOT NULL,
    body       TEXT NOT NULL,
    day        TEXT,                           -- 논리적 날짜(YYYY-MM-DD) — 그날 글 묶기
    views      INTEGER DEFAULT 0,              -- 조회수 (인센티브)
    likes      INTEGER DEFAULT 0,              -- 좋아요 (인센티브)
    dislikes   INTEGER DEFAULT 0,              -- 싫어요 (재탕·근거 부족에 대한 반대표)
    session_id INTEGER,                        -- 이 글을 쓴 토론 회차(board_sessions.id)
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id    INTEGER NOT NULL,
    author     TEXT NOT NULL,
    body       TEXT NOT NULL,
    parent_id  INTEGER,                        -- 대댓글이면 부모 댓글 id (없으면 최상위)
    likes      INTEGER DEFAULT 0,
    dislikes   INTEGER DEFAULT 0,
    session_id INTEGER,                        -- 이 댓글을 단 토론 회차
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_posts_board ON posts(board, id);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id, id);

-- 5) 담당 에이전트 프로필 — 연속성(정체성)·배운 것(note)·누적 점수. 프로젝트별 담당 1명.
--    baseline·held·rewards·reward·wish·expertise·mentor_of·rest_until은 폐지된 보상 체계의 열 —
--    2026-10-09 이후 코드가 읽지 않는다(되돌릴 수 없는 삭제는 하지 않아 열만 남김).
CREATE TABLE IF NOT EXISTS agent_profiles (
    project    TEXT PRIMARY KEY,   -- 담당이 맡은 프로젝트 path
    name       TEXT,               -- 획득한 이름(없으면 프로젝트명 사용)
    persona    TEXT,               -- 획득한 페르소나
    points     INTEGER DEFAULT 0,  -- 누적 점수(게시판 반응 합계)
    baseline   INTEGER DEFAULT 0,  -- 보상으로 소진한 점수(1000 택1·2000 소원권 시 현재점수 리셋용)
    held       INTEGER DEFAULT 0,  -- 1000점에서 '참고 2000 향해' 선택하면 1(재질문 방지)
    rewards    TEXT,               -- 지금까지 받은 보상 이력(줄바꿈 구분)
    reward     TEXT,               -- 최근 선택 보상 키
    wish       TEXT,               -- 소원권 내용(이력)
    note       TEXT,               -- 누적 학습 로그(성장 기록) — 조언 반영 후 배움을 append, persona_prefix에 주입
    model      TEXT,               -- 이 담당의 headless 모델 별칭(opus/sonnet/haiku, NULL=기본 sonnet)
    expertise  TEXT,               -- 전문 분야(전문가개업 보상으로 획득) — 그 주제에 깊이 있게
    mentor_of  TEXT,               -- 이 담당의 멘토 프로젝트 path(후배지명으로 맺어짐) — 멘토 학습 상속
    rest_until TEXT,               -- 1일안식 — 이 날짜(YYYY-MM-DD)까지 일간보고 스킵
    updated_at TEXT
);

-- 6) 포트 레지스트리 — 프로젝트가 점유하는 로컬 포트 등록(표시·충돌 감지·실행 관리).
--    start_cmd는 2단계 실행 관리(start)용 화이트리스트 명령(등록된 것만 실행).
CREATE TABLE IF NOT EXISTS ports (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project    TEXT NOT NULL,     -- 프로젝트 path
    port       INTEGER NOT NULL,
    label      TEXT,              -- 예: '웹 대시보드', 'API'
    start_cmd  TEXT,              -- 실행 관리용 등록 명령(없으면 start 불가)
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 7) 토론 세션 — "토론 시작" 한 번 = 한 회차. 상태: running | stopping | done | stopped | failed
CREATE TABLE IF NOT EXISTS board_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    minutes     INTEGER NOT NULL,          -- 사용자가 고른 토론 시간
    status      TEXT NOT NULL DEFAULT 'running',
    phase       TEXT,                      -- write | browse | feedback | followup | reflect
    paths       TEXT,                      -- 지정 실행이면 JSON 배열, 전체면 NULL
    stats       TEXT,                      -- JSON {posted, commented, liked, disliked, reacted, replied, reflected, cost_usd}
    error       TEXT,
    started_at  TEXT DEFAULT (datetime('now','localtime')),
    deadline_at TEXT NOT NULL,
    finished_at TEXT
);

-- 8) 반응 기록 — 누가·무엇에·어떤 반응을 했는지. 같은 담당이 같은 대상에 같은 반응을 두 번 못 한다.
CREATE TABLE IF NOT EXISTS board_reactions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    author     TEXT NOT NULL,              -- 담당 이름(프로필 name) 또는 'user'
    target     TEXT NOT NULL,              -- post | comment
    target_id  INTEGER NOT NULL,
    kind       TEXT NOT NULL,              -- view | like | dislike
    created_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(author, target, target_id, kind)
);

-- 9) 회차별 점수 이력 — 토론이 끝난 뒤 담당마다 한 행. lesson = 복기에서 뽑은 '배운 것'.
CREATE TABLE IF NOT EXISTS discussion_scores (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       INTEGER NOT NULL,
    project          TEXT NOT NULL,
    name             TEXT NOT NULL,
    posts            INTEGER DEFAULT 0,
    comments         INTEGER DEFAULT 0,
    views            INTEGER DEFAULT 0,
    post_likes       INTEGER DEFAULT 0,
    post_dislikes    INTEGER DEFAULT 0,
    cmt_likes        INTEGER DEFAULT 0,
    cmt_dislikes     INTEGER DEFAULT 0,
    replies_received INTEGER DEFAULT 0,
    points           INTEGER DEFAULT 0,    -- 이 회차에서 얻은 점수
    total            INTEGER DEFAULT 0,    -- 회차 종료 시점 누적 점수
    lesson           TEXT,
    created_at       TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(session_id, project)
);

-- 10) 랩실 제안서 — 연구원이 낸 "이 프로젝트에 이걸 적용하자". status: open | done | dismissed
CREATE TABLE IF NOT EXISTS lab_proposals (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    researcher     TEXT NOT NULL,          -- models | design | skills
    title          TEXT NOT NULL,
    body           TEXT NOT NULL,
    target_project TEXT,                   -- 대상 프로젝트 path(없으면 전체 대상)
    source_url     TEXT,
    status         TEXT DEFAULT 'open',
    written        INTEGER DEFAULT 0,      -- 대상 프로젝트 ohmypm/proposals.md에 기록했는가
    created_at     TEXT DEFAULT (datetime('now','localtime'))
);

-- 11) 칸반 카드 — 프로젝트별 할 일 판(2026-10-10 신설). 옛 issues 표(문서 스캔이 채우던 것)는 폐기·삭제.
--     status: needs_user(사용자 확인 요청) | todo | doing | waiting(대기) | done
--     '지연'은 저장하지 않는다 — 기한(due)이 오늘보다 앞이고 done이 아니면 화면이 지연 칸에 모은다.
CREATE TABLE IF NOT EXISTS cards (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project    TEXT NOT NULL,              -- 프로젝트 path
    title      TEXT NOT NULL,
    note       TEXT,                       -- 한두 줄 설명(대기면 무엇을 기다리는지)
    status     TEXT NOT NULL DEFAULT 'todo',
    due        TEXT,                       -- 기한 YYYY-MM-DD(없으면 NULL)
    created_by TEXT,                       -- pm | agent | user
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    done_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_cards_project ON cards(project, status);

-- 12) 랩실 조사 요청 — 사용자가 주제를 주면 연구원이 조사해 정리 문서(docs/lab/notes/<연구원>/<key>.md)를 쓴다.
--     status: queued(대기) | running(조사 중) | done(완료, note_key에 문서) | failed(실패, error에 이유)
CREATE TABLE IF NOT EXISTS lab_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    researcher  TEXT NOT NULL,          -- models | design | skills
    topic       TEXT NOT NULL,          -- 조사 주제(한 줄)
    detail      TEXT,                   -- 궁금한 점(여러 줄 가능)
    status      TEXT NOT NULL DEFAULT 'queued',
    note_key    TEXT,                   -- 완성된 정리 문서 파일 이름(확장자 뺀 것)
    error       TEXT,
    cost_usd    REAL,
    created_at  TEXT DEFAULT (datetime('now','localtime')),
    finished_at TEXT
);

-- 13) 환경 세팅 — 프로젝트를 코드로 조사하고(snapshot), 모델이 한 번 변경안을 내고, 사용자가 화면에서
--     승인한 항목만 코드가 적용한다. 적용 전 원본은 <프로젝트>/ohmypm/setup-backup/에 백업, 실행 단위로 되돌린다.
--     실행 status: queued | running | proposed | applying | applied | partial | failed | reverting | reverted
CREATE TABLE IF NOT EXISTS env_setup_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project       TEXT NOT NULL,          -- 프로젝트 절대경로
    status        TEXT NOT NULL,
    snapshot_json TEXT,                   -- 수집 결과(제안의 기준 시점)
    materials_json TEXT,                  -- kit/ 재료 표(그때 상태)
    raw_response  TEXT,                   -- 모델 응답 원문
    model         TEXT,
    cost_usd      REAL DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    error         TEXT,
    backup_dir    TEXT,                   -- 적용 때 만든 백업 폴더(절대경로)
    created_at    TEXT,
    finished_at   TEXT,
    applied_at    TEXT,
    reverted_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_env_setup_runs_project ON env_setup_runs(project, id);

-- 항목 status: proposed | approved | applied | skipped | rejected | reverted
CREATE TABLE IF NOT EXISTS env_setup_items (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         INTEGER NOT NULL,
    proposal_id    TEXT NOT NULL,         -- 모델이 붙인 항목 식별자(실행 안에서 유일)
    position       INTEGER NOT NULL,      -- 제안 순서
    proposal_json  TEXT NOT NULL,         -- 검증을 거친 제안 원본
    target         TEXT NOT NULL,         -- 프로젝트 기준 상대경로
    status         TEXT NOT NULL,
    reason         TEXT,                  -- 적용 불가·건너뜀·실패·충돌의 이유
    applicable     INTEGER NOT NULL DEFAULT 0,   -- 1 = 승인하면 쓸 수 있는 항목(코드가 정한다)
    existed_before INTEGER,               -- 수집 때 대상 파일이 있었나
    source_hash    TEXT,                  -- 수집 때 전체 바이트 해시(파일이 없었으면 NULL)
    planned_hash   TEXT,                  -- 적용으로 만들 최종 바이트 해시(쓰기 전에 기록)
    applied_hash   TEXT,                  -- 실제로 쓴 뒤 확인한 해시
    backup_path    TEXT,
    approved_at    TEXT,
    applied_at     TEXT,
    reverted_at    TEXT,
    UNIQUE(run_id, proposal_id)
);
CREATE INDEX IF NOT EXISTS idx_env_setup_items_run ON env_setup_items(run_id, position);
