"""관리 대상 프로젝트 CRUD (케이스 12)."""

from src.db.client import get_db


def upsert_project(path: str, name: str, has_wiki: bool) -> None:
    """프로젝트 등록/갱신. 이미 있으면 이름·위키유무·스캔시각만 업데이트."""
    db = get_db()
    db.execute(
        "INSERT INTO projects (path, name, has_wiki, last_scan) "
        "VALUES (?, ?, ?, datetime('now')) "
        "ON CONFLICT(path) DO UPDATE SET "
        "  name=excluded.name, has_wiki=excluded.has_wiki, last_scan=excluded.last_scan",
        (path, name, int(has_wiki)),
    )
    db.commit()


def list_projects(enabled_only: bool = True) -> list[dict]:
    """관리 대상 목록. enabled_only면 등록된 것만."""
    db = get_db()
    query = "SELECT * FROM projects"
    if enabled_only:
        query += " WHERE enabled = 1"
    query += " ORDER BY name"
    return [dict(row) for row in db.execute(query)]


def set_enabled(path: str, enabled: bool) -> None:
    """관리 대상 등록/제외 (케이스 12)."""
    db = get_db()
    db.execute("UPDATE projects SET enabled = ? WHERE path = ?", (int(enabled), path))
    db.commit()


def disabled_paths() -> set[str]:
    """제외(enabled=0)된 프로젝트 path 집합 — 스캔이 다시 안 잡게 discover가 참조."""
    db = get_db()
    return {r["path"] for r in db.execute("SELECT path FROM projects WHERE enabled = 0")}
