"""SQLite 커넥션 + 스키마 초기화. odin의 Supabase client 자리를 로컬 SQLite로 대체."""

import sqlite3
import threading
from pathlib import Path

from src.config.settings import settings

# ★ 커넥션은 **스레드마다 하나**(2026-09-09). 예전엔 싱글톤 하나를 스레드가 공유했는데,
#   일간보고가 ThreadPoolExecutor로 여러 프로젝트를 동시에 돌리면서 두 스레드가 같은
#   커넥션에 commit을 걸어 "cannot commit - no transaction is active"로 배치가 죽었다.
#   sqlite 파일 잠금이 동시 쓰기를 조정하므로, WAL + busy_timeout으로 대기시킨다.
_local = threading.local()


def get_db() -> sqlite3.Connection:
    """이 스레드의 SQLite 커넥션. row_factory=Row 로 행을 딕셔너리처럼 다룬다."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        db_path = Path(settings.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)  # data/ 폴더 보장
        conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")    # 읽기와 쓰기가 서로를 막지 않게
        conn.execute("PRAGMA busy_timeout=30000")  # 잠겨 있으면 실패 대신 최대 30초 대기
        _local.conn = conn
    return conn


def init_db() -> None:
    """schema.sql 을 실행해 테이블 생성(없으면). 실행: python -c 'from src.db.client import init_db; init_db()'"""
    schema = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    db = get_db()
    db.executescript(schema)
    _migrate(db)  # 이미 있던 DB에 신규 열 멱등 추가
    db.commit()


def _migrate(db: sqlite3.Connection) -> None:
    """구버전 DB 보정 — CREATE TABLE IF NOT EXISTS는 기존 테이블에 열을 못 넣으므로
    누락된 열만 ALTER TABLE ADD COLUMN 한다(멱등: 이미 있으면 건너뜀)."""
    # issues에 판정 에이전트 열이 없으면 추가
    have = {row["name"] for row in db.execute("PRAGMA table_info(issues)")}
    for col, ddl in (
        ("verdict", "verdict TEXT"),
        ("review_reason", "review_reason TEXT"),
        ("reviewed_at", "reviewed_at TEXT"),
        ("easy_title", "easy_title TEXT"),   # 쉬운 제목(완결 검증이 부여) — 화면 표시 우선
    ):
        if col not in have:
            db.execute(f"ALTER TABLE issues ADD COLUMN {ddl}")

    # 게시판 인센티브 열(조회수·좋아요·댓글 반응·대댓글) — 기존 DB 보정
    def _ensure(table: str, cols: tuple[tuple[str, str], ...]) -> None:
        # posts/comments 테이블이 아직 없으면 schema가 곧 만드니 건너뜀
        if not db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            return
        present = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
        for col, ddl in cols:
            if col not in present:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")

    _ensure("posts", (("views", "views INTEGER DEFAULT 0"), ("likes", "likes INTEGER DEFAULT 0")))
    _ensure("comments", (
        ("parent_id", "parent_id INTEGER"),
        ("likes", "likes INTEGER DEFAULT 0"),
        ("dislikes", "dislikes INTEGER DEFAULT 0"),
    ))
    _ensure("agent_profiles", (
        ("baseline", "baseline INTEGER DEFAULT 0"),
        ("held", "held INTEGER DEFAULT 0"),
        ("rewards", "rewards TEXT"),
        ("persona", "persona TEXT"),
        ("wish", "wish TEXT"),
        ("model", "model TEXT"),
        # 성장 엔진(2026-09-07) — 죽어 있던 note를 살리고 보상 실효과용 3열 추가
        ("note", "note TEXT"),               # 누적 학습 로그(성장 기록)
        ("expertise", "expertise TEXT"),     # 전문 분야(전문가개업)
        ("mentor_of", "mentor_of TEXT"),     # 멘토 프로젝트 path(후배지명)
        ("rest_until", "rest_until TEXT"),   # 1일안식 만료일
    ))

    _migrate_timestamps_to_localtime(db)


# 2026-09-10 이전에 쌓인 시각은 SQLite datetime('now') = **UTC**로 저장됐다. 파이썬 쪽은
# datetime.now() = 로컬을 써서 한 DB 안에 두 시간대가 섞여 있었고(대시보드가 9시간 어긋나 보임),
# 저장을 로컬로 통일하면서 기존 행도 한 번 옮겨야 이력이 안 끊긴다.
_TZ_MIGRATION_KEY = "migration.tz_localtime_v1"

# (테이블, 시각 열) — schema.sql의 TEXT 시각 열 전부. 새 시각 열을 만들면 여기에도 넣는다.
_TS_COLUMNS = (
    ("projects", "last_scan"),
    ("issues", "created_at"),
    ("issues", "reviewed_at"),
    ("autolog", "created_at"),
    ("messages", "created_at"),
    ("posts", "created_at"),
    ("comments", "created_at"),
    ("agent_profiles", "updated_at"),
    ("ports", "created_at"),
)


def _migrate_timestamps_to_localtime(db: sqlite3.Connection) -> None:
    """기존 UTC 시각을 로컬로 한 번만 이동(멱등 — alerts에 마커를 남긴다).

    두 번 돌면 +18시간이 되므로 마커 확인이 핵심이다. `datetime(col,'localtime')`이
    NULL을 주는 행(형식이 시각이 아님)은 건드리지 않는다 — 데이터를 지우느니 그대로 둔다.
    """
    done = db.execute(
        "SELECT value FROM alerts WHERE key = ?", (_TZ_MIGRATION_KEY,)
    ).fetchone()
    if done:
        return

    moved = 0
    for table, col in _TS_COLUMNS:
        if not db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone():
            continue
        cur = db.execute(
            f"UPDATE {table} SET {col} = datetime({col}, 'localtime') "
            f"WHERE {col} IS NOT NULL AND datetime({col}, 'localtime') IS NOT NULL"
        )
        moved += cur.rowcount or 0

    db.execute(
        "INSERT OR REPLACE INTO alerts (key, value) VALUES (?, datetime('now','localtime'))",
        (_TZ_MIGRATION_KEY,),
    )
    if moved:
        from loguru import logger

        logger.info(f"[마이그레이션] 시각 {moved}건을 UTC→로컬로 이동(1회)")
