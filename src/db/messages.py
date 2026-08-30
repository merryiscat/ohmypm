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
        "INSERT INTO messages (room, author, body) VALUES (?, ?, ?)",
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


def list_messages(room: str, limit: int = 200) -> list[dict]:
    """방의 최근 글 목록(오래된→최신 순). 기본 200줄까지."""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM (SELECT * FROM messages WHERE room = ? ORDER BY id DESC LIMIT ?) "
        "ORDER BY id ASC",
        (room, limit),
    )
    return [dict(r) for r in rows]
