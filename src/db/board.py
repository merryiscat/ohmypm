"""게시판 CRUD — 글(posts) + 댓글(comments).

자유대화(4단계)를 게시판 성격으로: 일간보고에서 나온 각 프로젝트 요약이 '글'로 올라오고,
다른 담당 에이전트가 관심 있는 글에 '댓글'을 남긴다. 지금은 게시판이 'daily' 하나.
"""

from src.db.client import get_db

DAILY_BOARD = "daily"


def add_post(author: str, title: str, body: str, project: str | None = None,
             board: str = DAILY_BOARD, day: str | None = None) -> dict:
    """글 하나 등록. 방금 넣은 행 반환."""
    db = get_db()
    cur = db.execute(
        "INSERT INTO posts (board, project, author, title, body, day) VALUES (?, ?, ?, ?, ?, ?)",
        (board, project, author, title, body, day),
    )
    db.commit()
    return dict(db.execute("SELECT * FROM posts WHERE id = ?", (cur.lastrowid,)).fetchone())


def add_comment(post_id: int, author: str, body: str) -> dict:
    """댓글 하나 등록."""
    db = get_db()
    cur = db.execute(
        "INSERT INTO comments (post_id, author, body) VALUES (?, ?, ?)",
        (post_id, author, body),
    )
    db.commit()
    return dict(db.execute("SELECT * FROM comments WHERE id = ?", (cur.lastrowid,)).fetchone())


def get_post(post_id: int) -> dict | None:
    """글 하나 + 그 댓글들. 없으면 None."""
    db = get_db()
    row = db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not row:
        return None
    p = dict(row)
    p["comments"] = [
        dict(r) for r in db.execute(
            "SELECT * FROM comments WHERE post_id = ? ORDER BY id ASC", (post_id,)
        )
    ]
    return p


def list_posts(board: str = DAILY_BOARD, limit: int = 100) -> list[dict]:
    """게시판 글 목록(최신 글이 위). 각 글에 comments 배열을 붙여 돌려준다."""
    db = get_db()
    posts = [
        dict(r) for r in db.execute(
            "SELECT * FROM posts WHERE board = ? ORDER BY id DESC LIMIT ?", (board, limit)
        )
    ]
    for p in posts:
        p["comments"] = [
            dict(r) for r in db.execute(
                "SELECT * FROM comments WHERE post_id = ? ORDER BY id ASC", (p["id"],)
            )
        ]
    return posts
