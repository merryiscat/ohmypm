"""SQLite 커넥션 + 스키마 초기화. odin의 Supabase client 자리를 로컬 SQLite로 대체."""

import sqlite3
from pathlib import Path

from src.config.settings import settings

_conn: sqlite3.Connection | None = None


def get_db() -> sqlite3.Connection:
    """로컬 SQLite 커넥션(싱글톤). row_factory=Row 로 행을 딕셔너리처럼 다룬다."""
    global _conn
    if _conn is None:
        db_path = Path(settings.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)  # data/ 폴더 보장
        # 단일 워커 전제라 스레드 공유 허용
        _conn = sqlite3.connect(db_path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


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
