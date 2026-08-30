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
