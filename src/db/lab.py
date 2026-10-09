"""랩실 제안서(lab_proposals) CRUD — 연구원이 낸 "이 프로젝트에 이걸 적용하자"."""

from src.db.client import get_db

DEDUP_DAYS = 60   # 같은 연구원·같은 제목이 이 기간 안에 있으면 다시 넣지 않는다


def add_proposal(researcher: str, title: str, body: str, target_project: str | None,
                 source_url: str | None) -> dict | None:
    """제안 하나 저장. 최근 DEDUP_DAYS 안에 같은 연구원·제목이 있으면 None(중복)."""
    db = get_db()
    dup = db.execute(
        "SELECT id FROM lab_proposals WHERE researcher = ? AND title = ? "
        "AND created_at >= datetime('now','localtime', ?)",
        (researcher, title, f"-{DEDUP_DAYS} days"),
    ).fetchone()
    if dup:
        return None
    cur = db.execute(
        "INSERT INTO lab_proposals (researcher, title, body, target_project, source_url, created_at) "
        "VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))",
        (researcher, title, body, target_project, source_url),
    )
    db.commit()
    return dict(db.execute("SELECT * FROM lab_proposals WHERE id = ?", (cur.lastrowid,)).fetchone())


def mark_written(proposal_id: int) -> None:
    db = get_db()
    db.execute("UPDATE lab_proposals SET written = 1 WHERE id = ?", (proposal_id,))
    db.commit()


def set_status(proposal_id: int, status: str) -> bool:
    if status not in ("open", "done", "dismissed"):
        return False
    db = get_db()
    db.execute("UPDATE lab_proposals SET status = ? WHERE id = ?", (status, proposal_id))
    db.commit()
    return True


def list_proposals(researcher: str | None = None, project: str | None = None, limit: int = 100) -> list[dict]:
    """제안 목록(최신 먼저). researcher·project로 거른다. project는 그 프로젝트 대상 + 전체 대상(NULL)."""
    db = get_db()
    where, params = [], []
    if researcher:
        where.append("researcher = ?"); params.append(researcher)
    if project:
        where.append("(target_project = ? OR target_project IS NULL)"); params.append(project)
    sql = "SELECT * FROM lab_proposals" + (" WHERE " + " AND ".join(where) if where else "") + \
          " ORDER BY CASE status WHEN 'open' THEN 0 ELSE 1 END, id DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in db.execute(sql, params)]
