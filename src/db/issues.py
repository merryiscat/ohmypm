"""이슈 CRUD (케이스 2·4·8). fingerprint 멱등으로 재스캔 시 같은 이슈 중복 생성 방지."""

import hashlib

from src.db.client import get_db


def _fingerprint(project: str, kind: str, title: str) -> str:
    """(프로젝트+종류+제목) 해시 = 같은 이슈를 매일 재스캔해도 한 번만 만들게 하는 멱등키."""
    return hashlib.sha1(f"{project}|{kind}|{title}".encode("utf-8")).hexdigest()


def upsert_issue(
    project: str,
    kind: str,
    title: str,
    due: str | None = None,
    source: str | None = None,
) -> None:
    """이슈 등록. 같은 (project,kind,title)이면 중복 생성 안 하고 기한만 갱신."""
    fp = _fingerprint(project, kind, title)
    db = get_db()
    db.execute(
        "INSERT INTO issues (project, kind, title, due, source, fingerprint) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(fingerprint) DO UPDATE SET due=excluded.due",
        (project, kind, title, due, source, fp),
    )
    db.commit()


def list_issues(status: str | None = None) -> list[dict]:
    """이슈 목록. 기한 있는 것 먼저(임박순), 그다음 생성순."""
    db = get_db()
    query = "SELECT * FROM issues"
    params: list = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY (due IS NULL), due, created_at"
    return [dict(row) for row in db.execute(query, params)]


def set_status(issue_id: int, status: str) -> None:
    """이슈 상태 변경 (open→consulting→resolved/deferred)."""
    db = get_db()
    db.execute("UPDATE issues SET status = ? WHERE id = ?", (status, issue_id))
    db.commit()
