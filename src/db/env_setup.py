"""환경 세팅 기록(env_setup_runs·env_setup_items) — 실행 하나 = 제안 한 번 + 승인·적용 한 번 + 되돌리기.

상태를 바꿀 때는 transition()으로 '지금 이 상태일 때만' 바꾼다(같은 실행을 두 번 적용하는 일을 막는 자물쇠).
시각은 다른 표와 같이 로컬 시각으로 저장한다.
"""

import json
from datetime import datetime

from src.db.client import get_db

RUN_STATUSES = ("queued", "running", "proposed", "applying", "applied", "partial", "failed", "reverting", "reverted")
ITEM_STATUSES = ("proposed", "approved", "applied", "skipped", "rejected", "reverted")
ACTIVE = ("queued", "running", "applying", "reverting")   # 이 상태인 실행이 있으면 같은 프로젝트에 새 일을 받지 않는다

_RUN_COLS = {"status", "snapshot_json", "materials_json", "raw_response", "model", "cost_usd", "output_tokens",
             "error", "backup_dir", "finished_at", "applied_at", "reverted_at"}
_ITEM_COLS = {"status", "reason", "applicable", "existed_before", "source_hash", "planned_hash", "applied_hash",
              "backup_path", "approved_at", "applied_at", "reverted_at"}


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_run(project: str) -> int:
    db = get_db()
    cur = db.execute("INSERT INTO env_setup_runs (project, status, created_at) VALUES (?, 'queued', ?)",
                     (project, now()))
    db.commit()
    return cur.lastrowid


def get_run(run_id: int) -> dict | None:
    row = get_db().execute("SELECT * FROM env_setup_runs WHERE id = ?", (run_id,)).fetchone()
    return dict(row) if row else None


def list_runs(project: str, limit: int = 20) -> list[dict]:
    rows = get_db().execute("SELECT * FROM env_setup_runs WHERE project = ? ORDER BY id DESC LIMIT ?",
                            (project, limit))
    return [dict(r) for r in rows]


def active_run(project: str) -> dict | None:
    marks = ",".join("?" * len(ACTIVE))
    row = get_db().execute(f"SELECT * FROM env_setup_runs WHERE project = ? AND status IN ({marks}) "
                           "ORDER BY id DESC LIMIT 1", (project, *ACTIVE)).fetchone()
    return dict(row) if row else None


def runs_with_status(statuses: tuple[str, ...]) -> list[dict]:
    marks = ",".join("?" * len(statuses))
    return [dict(r) for r in get_db().execute(
        f"SELECT * FROM env_setup_runs WHERE status IN ({marks}) ORDER BY id", statuses)]


def update_run(run_id: int, **fields) -> None:
    bad = set(fields) - _RUN_COLS
    if bad:
        raise ValueError(f"모르는 열: {bad}")
    if "status" in fields and fields["status"] not in RUN_STATUSES:
        raise ValueError(f"모르는 실행 상태: {fields['status']}")
    db = get_db()
    sets = ", ".join(f"{k} = ?" for k in fields)
    db.execute(f"UPDATE env_setup_runs SET {sets} WHERE id = ?", (*fields.values(), run_id))
    db.commit()


def transition(run_id: int, from_statuses: tuple[str, ...], to: str, **fields) -> bool:
    """지금 상태가 from_statuses 중 하나일 때만 to로 바꾼다. 바꿨으면 True(다른 요청이 먼저 바꿨으면 False)."""
    if to not in RUN_STATUSES:
        raise ValueError(f"모르는 실행 상태: {to}")
    bad = set(fields) - _RUN_COLS
    if bad:
        raise ValueError(f"모르는 열: {bad}")
    db = get_db()
    marks = ",".join("?" * len(from_statuses))
    sets = ", ".join(["status = ?"] + [f"{k} = ?" for k in fields])
    cur = db.execute(f"UPDATE env_setup_runs SET {sets} WHERE id = ? AND status IN ({marks})",
                     (to, *fields.values(), run_id, *from_statuses))
    db.commit()
    return cur.rowcount == 1


def add_items(run_id: int, items: list[dict]) -> None:
    """검증을 거친 항목들을 한 번에 저장한다. 각 항목: proposal(dict), target, applicable, reason,
    existed_before, source_hash."""
    db = get_db()
    for pos, it in enumerate(items):
        db.execute(
            "INSERT INTO env_setup_items (run_id, proposal_id, position, proposal_json, target, status, reason, "
            "applicable, existed_before, source_hash) VALUES (?, ?, ?, ?, ?, 'proposed', ?, ?, ?, ?)",
            (run_id, it["proposal"]["id"], pos, json.dumps(it["proposal"], ensure_ascii=False), it["target"],
             it.get("reason"), 1 if it.get("applicable") else 0,
             None if it.get("existed_before") is None else int(bool(it["existed_before"])), it.get("source_hash")))
    db.commit()


def list_items(run_id: int) -> list[dict]:
    rows = get_db().execute("SELECT * FROM env_setup_items WHERE run_id = ? ORDER BY position", (run_id,))
    return [dict(r) for r in rows]


def update_item(item_id: int, **fields) -> None:
    bad = set(fields) - _ITEM_COLS
    if bad:
        raise ValueError(f"모르는 열: {bad}")
    if "status" in fields and fields["status"] not in ITEM_STATUSES:
        raise ValueError(f"모르는 항목 상태: {fields['status']}")
    db = get_db()
    sets = ", ".join(f"{k} = ?" for k in fields)
    db.execute(f"UPDATE env_setup_items SET {sets} WHERE id = ?", (*fields.values(), item_id))
    db.commit()
