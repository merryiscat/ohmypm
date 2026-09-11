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


def list_messages(room: str, limit: int = 200) -> list[dict]:
    """방의 최근 글 목록(오래된→최신 순). 기본 200줄까지."""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM (SELECT * FROM messages WHERE room = ? ORDER BY id DESC LIMIT ?) "
        "ORDER BY id ASC",
        (room, limit),
    )
    return [dict(r) for r in rows]
