-- ohmyPM 로컬 상태 저장 (SQLite). init_db()가 CREATE TABLE IF NOT EXISTS 로 실행.

-- 1) 관리 대상 프로젝트 (케이스 12)
CREATE TABLE IF NOT EXISTS projects (
    path      TEXT PRIMARY KEY,        -- 절대경로 = 자연키
    name      TEXT NOT NULL,
    has_wiki  INTEGER DEFAULT 0,       -- docs/ llmwiki 유무 (0/1)
    enabled   INTEGER DEFAULT 1,       -- 관리 대상 등록 여부 (0/1)
    last_scan TEXT                     -- 마지막 스캔 시각 (ISO8601)
);

-- 2) 이슈 — status/pending 파싱 산출 + 상담 상태 (케이스 2·4·8)
CREATE TABLE IF NOT EXISTS issues (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project       TEXT NOT NULL,
    kind          TEXT NOT NULL,         -- unresolved | deadline | conditional | stale | format
    title         TEXT NOT NULL,
    due           TEXT,                  -- 기한(pending 재검토 시점), NULL=미정
    status        TEXT DEFAULT 'open',   -- open | consulting | resolved | deferred
    source        TEXT,                  -- status.md | pending.md | mistakes.md
    fingerprint   TEXT UNIQUE,           -- (project+kind+title) 해시 = 재스캔 중복 방지
    -- 판정 에이전트(자가 확인형) 결과. NULL = 미판정(결정론 파서가 막 뽑은 후보)
    verdict       TEXT,                  -- keep | drop | reclass (NULL=미판정)
    review_reason TEXT,                  -- 판정 한 줄 근거
    reviewed_at   TEXT,                  -- 판정 시각 (ISO8601)
    created_at    TEXT DEFAULT (datetime('now'))
);

-- 3) 자율 행동 로그 (케이스 15 — 롤백 단위)
CREATE TABLE IF NOT EXISTS autolog (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project    TEXT NOT NULL,
    action     TEXT NOT NULL,          -- 화이트리스트 행동 유형
    commit_sha TEXT,                   -- 되돌림 단위
    reason     TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 4) 알림 설정 + 화이트리스트 (케이스 13 + 자율경계)
CREATE TABLE IF NOT EXISTS alerts (
    key   TEXT PRIMARY KEY,            -- 예: 'whitelist.format_standardize'='on'
    value TEXT
);

-- 5) 메시지 보드 — 에이전트 채팅방 + 프로젝트 룸 (사용자·에이전트 대화 기록)
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    room       TEXT NOT NULL,          -- 'global'(전체 채팅방) | 프로젝트 path(프로젝트 룸)
    author     TEXT NOT NULL,          -- 'user' | 에이전트 이름(scanner/judge/pm…)
    body       TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_messages_room ON messages(room, id);

-- 6) 게시판 — 글(post) + 댓글(comment). 자유대화를 게시판 성격으로(글 올리고 관심 글에 댓글).
--    글 = 일간보고에서 나온 각 프로젝트 요약. 댓글 = 다른 담당이 관심 있는 글에 남김.
CREATE TABLE IF NOT EXISTS posts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    board      TEXT NOT NULL DEFAULT 'daily',  -- 게시판 키(지금은 'daily' 하나)
    project    TEXT,                           -- 이 글의 대상 프로젝트 path(있으면)
    author     TEXT NOT NULL,                  -- 글쓴이(보통 프로젝트명 or 'pm')
    title      TEXT NOT NULL,
    body       TEXT NOT NULL,
    day        TEXT,                           -- 논리적 날짜(YYYY-MM-DD) — 그날 글 묶기
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id    INTEGER NOT NULL,
    author     TEXT NOT NULL,
    body       TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_posts_board ON posts(board, id);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id, id);

-- 7) 포트 레지스트리 — 프로젝트가 점유하는 로컬 포트 등록(표시·충돌 감지·실행 관리).
--    start_cmd는 2단계 실행 관리(start)용 화이트리스트 명령(등록된 것만 실행).
CREATE TABLE IF NOT EXISTS ports (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project    TEXT NOT NULL,     -- 프로젝트 path
    port       INTEGER NOT NULL,
    label      TEXT,              -- 예: '웹 대시보드', 'API'
    start_cmd  TEXT,              -- 실행 관리용 등록 명령(없으면 start 불가)
    created_at TEXT DEFAULT (datetime('now'))
);
