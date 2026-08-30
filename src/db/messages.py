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


def list_messages(room: str, limit: int = 200) -> list[dict]:
    """방의 최근 글 목록(오래된→최신 순). 기본 200줄까지."""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM (SELECT * FROM messages WHERE room = ? ORDER BY id DESC LIMIT ?) "
        "ORDER BY id ASC",
        (room, limit),
    )
    return [dict(r) for r in rows]
