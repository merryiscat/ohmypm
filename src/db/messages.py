"""메시지 보드 CRUD — 에이전트 채팅방(room='global')과 프로젝트 룸(room=프로젝트 path).

사람과 에이전트가 같은 방에 글을 쌓는다. 에이전트 자동 포스팅은 다음 단계에서 author를
에이전트 이름으로 넣어 이 add_message를 그대로 호출하면 된다.
"""

from src.db.client import get_db

GLOBAL_ROOM = "global"  # 전체(에이전트) 채팅방의 고정 room 키


def add_message(room: str, author: str, body: str) -> dict:
    """방에 글 한 줄 추가. 방금 넣은 행을 딕셔너리로 돌려준다."""
    db = get_db()
    cur = db.execute(
        "INSERT INTO messages (room, author, body, created_at) "
        "VALUES (?, ?, ?, datetime('now','localtime'))",
        (room, author, body),
    )
    db.commit()
    row = db.execute("SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def list_rooms_like(prefix: str) -> list[str]:
    """접두사로 시작하는 방(room) 키 목록(중복 제거). 일간보고 daily::{날짜}::{path} 조회용."""
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT room FROM messages WHERE room LIKE ? ORDER BY room", (prefix + "%",)
    )
    return [r["room"] for r in rows]


def delete_for_project(path: str) -> None:
    """프로젝트의 대화 방 삭제 — 룸 채팅(room=path)과 일간보고 방(daily::*::path)."""
    db = get_db()
    db.execute("DELETE FROM messages WHERE room = ? OR room LIKE ?", (path, f"daily::%::{path}"))
    db.commit()


def user_says_for_project(path: str, after_id: int = 0, limit: int = 50) -> list[dict]:
    """이 프로젝트에 **사용자가 직접 남긴** 글(오래된→최신) — 담당 방과 일간보고 방 둘 다.

    ★ 사용자가 화면에서 쓴 글은 담당 방(room=프로젝트 path)에 들어가고, PM↔담당 대화는
      날짜별 방(daily::{날짜}::{path})에 들어간다. 반영 단계는 날짜별 방만 읽고 있어서
      **사용자가 한 말은 파이프라인에 아예 들어오지 못했다**(2026-09-12 확인).
      게다가 날짜별 방이라 어제 방에 적힌 답은 오늘 배치가 보지도 못한다.
      두 갈래를 함께, 날짜를 가로질러 모은다.
    """
    db = get_db()
    rows = db.execute(
        "SELECT * FROM messages WHERE (room = ? OR room LIKE ?) AND author = 'user' AND id > ? "
        "ORDER BY id ASC LIMIT ?",
        (path, f"daily::%::{path}", after_id, limit),
    )
    return [dict(r) for r in rows]


DAILY_PREFIX = "daily::"   # 일간보고 방 키 접두사 — daily::{날짜}::{프로젝트 path}

# 프로젝트 방(room=프로젝트 path)에서 **일간보고 방과 겹치는 PM·담당 발화만** 조회에서 숨기는 조건.
#
# ★ 2026-09-18 T-004. 2026-09-04~09-17 사이 일간보고는 같은 발화를 일간 방과 프로젝트 방에
#   이중 저장했다(daily_report가 룸 피드로도 흘림). 그래서 담당 방 패널이 매일 아침 보고
#   사본으로 덮여 사용자와 담당의 실제 대화가 묻혔다(사용자 지적). 새 저장은 daily_report
#   쪽에서 끊었고, 이미 쌓인 사본은 **지우지 않고 조회에서만 가린다** — 되돌릴 수 없는 삭제는
#   자동으로 하지 않는다는 원칙, 그리고 일간 방 원본이 살아 있으므로 내용이 사라지지 않는다.
#
# 숨기는 기준: 같은 프로젝트 · 같은 일자(KST) · 같은 작성자 · 같은 본문.
#   - 일자: created_at이 로컬시각 문자열이므로 date()가 곧 KST 날짜다
#           (일간보고 방 키의 날짜와 같은 기준).
#   - 작성자: 'pm'·'agent'만. **사용자 발화는 어떤 경우에도 숨기지 않는다.**
#   - 본문: 그날 첫 PM 발화 사본에는 코드가 '[일간보고 {날짜}]' 머리줄을 붙였으므로, 그 머리줄을
#     떼어낸 나머지가 일간 방 본문과 같으면 같은 발화로 본다(안 그러면 하루에 한 줄씩 남는다).
DAILY_DUP_HIDDEN = (
    "NOT (m.author IN ('pm', 'agent') AND EXISTS ("
    "  SELECT 1 FROM messages d"
    f"   WHERE d.room = '{DAILY_PREFIX}' || date(m.created_at) || '::' || m.room"
    "     AND d.author = m.author"
    "     AND (d.body = m.body"
    "          OR m.body = '[일간보고 ' || date(m.created_at) || ']' || char(10) || d.body)"
    "))"
)


def list_messages(room: str, limit: int = 200) -> list[dict]:
    """방의 최근 글 목록(오래된→최신 순). 기본 200줄까지.

    프로젝트 방을 조회할 때는 일간보고 방과 겹치는 PM·담당 발화를 숨긴다(DAILY_DUP_HIDDEN).
    전체 채팅방·일간보고 방 조회는 종전 그대로 — DB 원본도 그대로 남는다.
    """
    db = get_db()
    where = "m.room = ?"
    if room != GLOBAL_ROOM and not room.startswith(DAILY_PREFIX):
        where += " AND " + DAILY_DUP_HIDDEN
    rows = db.execute(
        f"SELECT * FROM (SELECT m.* FROM messages m WHERE {where} ORDER BY m.id DESC LIMIT ?) "
        "ORDER BY id ASC",
        (room, limit),
    )
    return [dict(r) for r in rows]
