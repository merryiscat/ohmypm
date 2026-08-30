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


def delete_by_project(project: str) -> int:
    """한 프로젝트의 이슈 전부 삭제(프로젝트 관리 제외 시). 삭제 건수 반환."""
    db = get_db()
    cur = db.execute("DELETE FROM issues WHERE project = ?", (project,))
    db.commit()
    return cur.rowcount


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


def list_unjudged(project: str | None = None) -> list[dict]:
    """아직 판정 에이전트를 안 거친 후보(verdict IS NULL). 프로젝트별로 좁힐 수 있음."""
    db = get_db()
    query = "SELECT * FROM issues WHERE verdict IS NULL"
    params: list = []
    if project:
        query += " AND project = ?"
        params.append(project)
    query += " ORDER BY created_at"
    return [dict(row) for row in db.execute(query, params)]


def apply_verdict(
    issue_id: int,
    verdict: str,
    kind: str | None = None,
    due: str | None = None,
    reason: str | None = None,
) -> None:
    """판정 에이전트 결과를 이슈에 반영.

    reclass면 kind·due를 정정하고, 모든 판정은 verdict·근거·시각을 남긴다.
    fingerprint는 그대로 둔다(판정 캐시 키 — 재스캔 시 이미 판정됨을 이 verdict로 안다).
    """
    db = get_db()
    if verdict == "reclass" and kind is not None:
        db.execute(
            "UPDATE issues SET verdict=?, kind=?, due=?, review_reason=?, "
            "reviewed_at=datetime('now') WHERE id=?",
            (verdict, kind, due, reason, issue_id),
        )
    else:
        db.execute(
            "UPDATE issues SET verdict=?, review_reason=?, reviewed_at=datetime('now') "
            "WHERE id=?",
            (verdict, reason, issue_id),
        )
    db.commit()
