"""칸반 카드 CRUD — 프로젝트별 할 일 판.

카드를 만들고 옮기는 주체는 셋: 주간보고 PM(점검 대화 끝에), 담당(사용자와 채팅하다가), 사용자(화면에서).
'지연'은 상태가 아니라 계산이다 — 기한이 지났는데 완료가 아니면 화면이 지연 칸에 모은다.
"""

from src.db.client import get_db

# (상태 키, 화면 이름) — 화면 칸 순서와 같다. 지연 칸은 화면이 계산해 맨 앞에 붙인다.
STATUSES = (
    ("needs_user", "사용자 확인 요청"),   # 사람만 할 수 있는 결정·작업
    ("todo", "할 일"),
    ("doing", "진행 중"),
    ("waiting", "대기"),                  # 조건·외부 상황을 기다림 — note에 무엇을 기다리는지
    ("done", "완료"),
)
STATUS_KEYS = tuple(k for k, _ in STATUSES)


def list_cards(project: str) -> list[dict]:
    db = get_db()
    rows = db.execute("SELECT * FROM cards WHERE project = ? ORDER BY id", (project,))
    return [dict(r) for r in rows]


def get_card(card_id: int) -> dict | None:
    row = get_db().execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
    return dict(row) if row else None


def add_card(project: str, title: str, status: str = "todo", note: str | None = None,
             due: str | None = None, created_by: str = "user") -> dict:
    """카드 하나 추가. 같은 프로젝트에 같은 제목의 미완료 카드가 있으면 새로 만들지 않고 그걸 돌려준다."""
    if status not in STATUS_KEYS:
        status = "todo"
    db = get_db()
    dup = db.execute("SELECT * FROM cards WHERE project = ? AND title = ? AND status != 'done'",
                     (project, title)).fetchone()
    if dup:
        return dict(dup)
    cur = db.execute(
        "INSERT INTO cards (project, title, note, status, due, created_by, done_at) "
        "VALUES (?, ?, ?, ?, ?, ?, CASE WHEN ? = 'done' THEN datetime('now','localtime') END)",
        (project, title, note, status, due or None, created_by, status),
    )
    db.commit()
    return get_card(cur.lastrowid)


# 바꿀 수 있는 열 — 그 밖의 키는 무시한다
_EDITABLE = ("title", "note", "status", "due")


def update_card(card_id: int, **fields) -> dict | None:
    """카드 고치기(title·note·status·due 중 준 것만). 없는 카드·잘못된 상태면 None."""
    sets = {k: v for k, v in fields.items() if k in _EDITABLE}
    if "status" in sets and sets["status"] not in STATUS_KEYS:
        return None
    if "due" in sets:
        sets["due"] = sets["due"] or None
    if not sets or not get_card(card_id):
        return get_card(card_id)
    cols = ", ".join(f"{k} = ?" for k in sets)
    done_sql = ""
    if "status" in sets:   # 완료로 가면 완료 시각을 찍고, 완료에서 나오면 지운다
        done_sql = (", done_at = CASE WHEN ? = 'done' THEN COALESCE(done_at, datetime('now','localtime')) "
                    "ELSE NULL END")
    params = [*sets.values()] + ([sets["status"]] if done_sql else []) + [card_id]
    db = get_db()
    db.execute(f"UPDATE cards SET {cols}, updated_at = datetime('now','localtime'){done_sql} WHERE id = ?",
               params)
    db.commit()
    return get_card(card_id)


def delete_card(card_id: int) -> bool:
    db = get_db()
    cur = db.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    db.commit()
    return cur.rowcount > 0


def delete_for_project(project: str) -> None:
    db = get_db()
    db.execute("DELETE FROM cards WHERE project = ?", (project,))
    db.commit()
