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


def add_done(project: str, title: str, day: str) -> None:
    """당일 완결 작업을 완료 카드로 등재 — 칸반(할일·진행중)에 안 올랐던 일도 흔적을 남긴다
    (2026-09-07 사용자 확정). 제목에 날짜를 붙여 다른 날 같은 제목과 구분, 재실행 중복 방지."""
    fp = _fingerprint(project, "done", f"{day} {title}")
    db = get_db()
    db.execute(
        "INSERT INTO issues (project, kind, title, due, source, fingerprint, status, "
        "verdict, review_reason) "
        "VALUES (?, 'done', ?, ?, 'daily_report', ?, 'resolved', 'resolved', '당일 완결(일간보고)') "
        "ON CONFLICT(fingerprint) DO NOTHING",
        (project, title, day, fp),
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


def fill_default_due(days: int = 14) -> int:
    """날짜 없는 활성 이슈(open·consulting)에 기본 재확인일(오늘+days)을 채운다.

    "날짜 없는 카드는 묻힌다"(2026-09-06 사용자 확정) — 모든 활성 이슈가 달력·정렬에
    잡히게 하는 결정론 안전망. PM·판정이 잡은 날짜는 건드리지 않는다(NULL만 채움).
    """
    db = get_db()
    cur = db.execute(
        "UPDATE issues SET due = date('now', ?) "
        "WHERE due IS NULL AND status IN ('open', 'consulting') "
        "AND (verdict IS NULL OR verdict != 'drop')",
        (f"+{days} days",),
    )
    db.commit()
    return cur.rowcount


def set_due(issue_id: int, due: str | None) -> None:
    """이슈 목표일(기한) 설정/해제 — PM이 일정 정리 시 사용."""
    db = get_db()
    db.execute("UPDATE issues SET due = ? WHERE id = ?", (due, issue_id))
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
