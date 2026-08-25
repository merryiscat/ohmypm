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
    db.commit()
