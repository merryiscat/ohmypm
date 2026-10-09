"""토론 세션(board_sessions)과 회차별 점수 이력(discussion_scores) CRUD.

세션 = "토론 시작" 버튼 한 번. 상태 전이: running → stopping → stopped / running → done / failed.
점수 이력 = 세션이 끝난 뒤 담당마다 한 행(받은 반응·점수 변화·배운 것).
"""

import json
from datetime import datetime, timedelta

from src.db.client import get_db

ACTIVE_STATUSES = ("running", "stopping")


def create_session(minutes: int, paths: list[str] | None) -> dict:
    db = get_db()
    deadline = (datetime.now() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    cur = db.execute(
        "INSERT INTO board_sessions (minutes, status, phase, paths, stats, started_at, deadline_at) "
        "VALUES (?, 'running', 'write', ?, '{}', datetime('now','localtime'), ?)",
        (minutes, json.dumps(paths, ensure_ascii=False) if paths else None, deadline),
    )
    db.commit()
    return get_session(cur.lastrowid)


def get_session(session_id: int) -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM board_sessions WHERE id = ?", (session_id,)).fetchone()
    return _row(row)


def latest_session() -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM board_sessions ORDER BY id DESC LIMIT 1").fetchone()
    return _row(row)


def active_sessions() -> list[dict]:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM board_sessions WHERE status IN ('running','stopping') ORDER BY id DESC"
    )
    return [_row(r) for r in rows]


def list_sessions(limit: int = 20) -> list[dict]:
    db = get_db()
    rows = db.execute("SELECT * FROM board_sessions ORDER BY id DESC LIMIT ?", (limit,))
    return [_row(r) for r in rows]


def set_phase(session_id: int, phase: str) -> None:
    db = get_db()
    db.execute("UPDATE board_sessions SET phase = ? WHERE id = ?", (phase, session_id))
    db.commit()


def set_status(session_id: int, status: str, error: str | None = None, finished: bool = False) -> None:
    db = get_db()
    fin = ", finished_at = datetime('now','localtime')" if finished else ""
    db.execute(
        f"UPDATE board_sessions SET status = ?, error = COALESCE(?, error){fin} WHERE id = ?",
        (status, error, session_id),
    )
    db.commit()


def merge_stats(session_id: int, more: dict) -> dict:
    """세션 stats(JSON)에 단계 결과를 합친다. 숫자는 더하고 문자열은 덮어쓴다."""
    db = get_db()
    row = db.execute("SELECT stats FROM board_sessions WHERE id = ?", (session_id,)).fetchone()
    stats = json.loads((row["stats"] if row and row["stats"] else None) or "{}")
    for k, v in (more or {}).items():
        if isinstance(v, (int, float)) and isinstance(stats.get(k), (int, float)):
            stats[k] = stats[k] + v
        else:
            stats[k] = v
    db.execute("UPDATE board_sessions SET stats = ? WHERE id = ?",
               (json.dumps(stats, ensure_ascii=False), session_id))
    db.commit()
    return stats


def _row(row) -> dict | None:
    if not row:
        return None
    d = dict(row)
    d["paths"] = json.loads(d["paths"]) if d.get("paths") else None
    d["stats"] = json.loads(d["stats"]) if d.get("stats") else {}
    return d


# ── 회차별 점수 이력 ──────────────────────────────────────────────────────────
SCORE_FIELDS = ("posts", "comments", "views", "post_likes", "post_dislikes",
                "cmt_likes", "cmt_dislikes", "replies_received", "points", "total")


def upsert_score(session_id: int, project: str, name: str, **fields) -> None:
    """담당 한 명의 회차 점수를 저장/갱신. fields는 SCORE_FIELDS와 lesson만 받는다."""
    db = get_db()
    cols = {k: fields[k] for k in SCORE_FIELDS if k in fields}
    lesson = fields.get("lesson")
    db.execute(
        "INSERT INTO discussion_scores (session_id, project, name, created_at) "
        "VALUES (?, ?, ?, datetime('now','localtime')) "
        "ON CONFLICT(session_id, project) DO UPDATE SET name = excluded.name",
        (session_id, project, name),
    )
    sets = [f"{k} = ?" for k in cols]
    params: list = list(cols.values())
    if lesson is not None:
        sets.append("lesson = ?")
        params.append(lesson)
    if sets:
        params += [session_id, project]
        db.execute(f"UPDATE discussion_scores SET {', '.join(sets)} WHERE session_id = ? AND project = ?",
                   params)
    db.commit()


def list_scores(project: str | None = None, limit: int = 50) -> list[dict]:
    """점수 이력(최신 회차 먼저). project를 주면 그 담당 것만."""
    db = get_db()
    if project:
        rows = db.execute(
            "SELECT s.*, b.started_at AS session_started FROM discussion_scores s "
            "JOIN board_sessions b ON b.id = s.session_id "
            "WHERE s.project = ? ORDER BY s.session_id DESC LIMIT ?", (project, limit))
    else:
        rows = db.execute(
            "SELECT s.*, b.started_at AS session_started FROM discussion_scores s "
            "JOIN board_sessions b ON b.id = s.session_id "
            "ORDER BY s.session_id DESC, s.points DESC LIMIT ?", (limit,))
    return [dict(r) for r in rows]


def scores_for_session(session_id: int) -> list[dict]:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM discussion_scores WHERE session_id = ? ORDER BY points DESC", (session_id,))
    return [dict(r) for r in rows]


def last_delta(project: str) -> int | None:
    """이 담당의 가장 최근 회차 점수 변화(points). 이력이 없으면 None."""
    db = get_db()
    row = db.execute(
        "SELECT points FROM discussion_scores WHERE project = ? ORDER BY session_id DESC LIMIT 1",
        (project,)).fetchone()
    return int(row["points"]) if row else None
