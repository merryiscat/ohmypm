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


def add_comment(post_id: int, author: str, body: str, parent_id: int | None = None) -> dict:
    """댓글 하나 등록. parent_id 주면 대댓글(그 댓글에 달린 답글)."""
    db = get_db()
    cur = db.execute(
        "INSERT INTO comments (post_id, author, body, parent_id) VALUES (?, ?, ?, ?)",
        (post_id, author, body, parent_id),
    )
    db.commit()
    return dict(db.execute("SELECT * FROM comments WHERE id = ?", (cur.lastrowid,)).fetchone())


def like_post(post_id: int) -> None:
    db = get_db()
    db.execute("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))
    db.commit()


def increment_views(post_id: int) -> None:
    db = get_db()
    db.execute("UPDATE posts SET views = views + 1 WHERE id = ?", (post_id,))
    db.commit()


def react_comment(comment_id: int, reaction: str) -> None:
    """댓글 좋아요/싫어요. reaction='like'|'dislike'."""
    col = "likes" if reaction == "like" else "dislikes"
    db = get_db()
    db.execute(f"UPDATE comments SET {col} = {col} + 1 WHERE id = ?", (comment_id,))
    db.commit()


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


def delete_by_project(project: str) -> int:
    """한 프로젝트가 쓴 글과 그 댓글 전부 삭제. 삭제한 글 수 반환."""
    db = get_db()
    ids = [r["id"] for r in db.execute("SELECT id FROM posts WHERE project = ?", (project,))]
    for pid in ids:
        db.execute("DELETE FROM comments WHERE post_id = ?", (pid,))
    cur = db.execute("DELETE FROM posts WHERE project = ?", (project,))
    db.commit()
    return cur.rowcount


def best_of_day(day: str) -> dict:
    """오늘의 베스트 — 글(좋아요*10 + 조회) 1위 + 댓글(좋아요) 1위. 표창용. 없으면 None.

    글은 그날(day) 올라온 것, 댓글은 그날 글에 달린 것 중에서. user 댓글은 제외.
    """
    db = get_db()
    post = db.execute(
        "SELECT author, title, COALESCE(likes,0) AS likes, COALESCE(views,0) AS views, "
        "(COALESCE(likes,0)*10 + COALESCE(views,0)) AS score "
        "FROM posts WHERE day = ? ORDER BY score DESC, id DESC LIMIT 1",
        (day,),
    ).fetchone()
    cmt = db.execute(
        "SELECT c.author AS author, c.body AS body, COALESCE(c.likes,0) AS likes, "
        "p.title AS post_title FROM comments c JOIN posts p ON c.post_id = p.id "
        "WHERE p.day = ? AND c.author != 'user' AND COALESCE(c.likes,0) > 0 "
        "ORDER BY c.likes DESC, c.id DESC LIMIT 1",
        (day,),
    ).fetchone()
    return {"post": dict(post) if post else None, "comment": dict(cmt) if cmt else None}


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
