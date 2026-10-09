"""키/값 설정 저장소(alerts 표). 마이그레이션 표식 같은 작은 상태를 담는다."""

from src.db.client import get_db


def get_setting(key: str, default: str | None = None) -> str | None:
    """설정값 조회."""
    db = get_db()
    row = db.execute("SELECT value FROM alerts WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    """설정값 저장/갱신."""
    db = get_db()
    db.execute(
        "INSERT INTO alerts (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    db.commit()
