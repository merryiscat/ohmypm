"""포트 레지스트리 CRUD — 프로젝트가 점유하는 로컬 포트 등록(표시·충돌 감지·실행 관리)."""

from src.db.client import get_db


def register(project: str, port: int, label: str = "", start_cmd: str = "") -> dict:
    """포트 등록. 같은 (project,port)면 라벨·명령만 갱신."""
    db = get_db()
    existing = db.execute(
        "SELECT id FROM ports WHERE project = ? AND port = ?", (project, port)
    ).fetchone()
    if existing:
        db.execute(
            "UPDATE ports SET label = ?, start_cmd = ? WHERE id = ?",
            (label, start_cmd, existing["id"]),
        )
        pid = existing["id"]
    else:
        cur = db.execute(
            "INSERT INTO ports (project, port, label, start_cmd) VALUES (?, ?, ?, ?)",
            (project, port, label, start_cmd),
        )
        pid = cur.lastrowid
    db.commit()
    return dict(db.execute("SELECT * FROM ports WHERE id = ?", (pid,)).fetchone())


def list_ports() -> list[dict]:
    """등록된 포트 전체(포트 오름차순)."""
    db = get_db()
    return [dict(r) for r in db.execute("SELECT * FROM ports ORDER BY port, project")]


def get_port(port_id: int) -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM ports WHERE id = ?", (port_id,)).fetchone()
    return dict(row) if row else None


def delete(port_id: int) -> None:
    db = get_db()
    db.execute("DELETE FROM ports WHERE id = ?", (port_id,))
    db.commit()
