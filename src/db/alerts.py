"""알림 설정 + 화이트리스트 (케이스 13 + 자율경계). key/value 저장 — 별도 테이블 안 만듦."""

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


def is_whitelisted(action: str) -> bool:
    """자율 허용 행동인지 확인 (화이트리스트). 'whitelist.<action>'='on' 이면 허용.

    ★ 자율 경계의 결정론적 판정 — 에이전트가 '안전한가'를 스스로 판단하지 않고
    사용자가 등록한 목록에 있는지만 확인한다(confused-deputy 방지).
    """
    return get_setting(f"whitelist.{action}") == "on"
