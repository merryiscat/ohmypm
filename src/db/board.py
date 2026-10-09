"""게시판 CRUD — 글(posts) + 댓글(comments) + 반응 기록(board_reactions).

토론 세션(src/cc/board_session.py)에서 담당 에이전트들이 글을 쓰고 반응한다.
사용자가 화면에서 누르는 좋아요·싫어요·조회는 like_post 등 단순 카운터 함수를 그대로 쓴다.
에이전트의 반응은 react()로만 — 같은 담당이 같은 대상에 같은 반응을 두 번 못 하게 기록이 남는다.
"""

from src.db.client import get_db

DAILY_BOARD = "daily"


def add_post(author: str, title: str, body: str, project: str | None = None,
             board: str = DAILY_BOARD, day: str | None = None,
             session_id: int | None = None) -> dict:
    """글 하나 등록. 방금 넣은 행 반환."""
    db = get_db()
    cur = db.execute(
        "INSERT INTO posts (board, project, author, title, body, day, session_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))",
        (board, project, author, title, body, day, session_id),
    )
    db.commit()
    return dict(db.execute("SELECT * FROM posts WHERE id = ?", (cur.lastrowid,)).fetchone())


def add_comment(post_id: int, author: str, body: str, parent_id: int | None = None,
                session_id: int | None = None) -> dict:
    """댓글 하나 등록. parent_id 주면 대댓글(그 댓글에 달린 답글)."""
    db = get_db()
    cur = db.execute(
        "INSERT INTO comments (post_id, author, body, parent_id, session_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))",
        (post_id, author, body, parent_id, session_id),
    )
    db.commit()
    return dict(db.execute("SELECT * FROM comments WHERE id = ?", (cur.lastrowid,)).fetchone())


# ── 사용자(화면) 반응 — 단순 카운터 ───────────────────────────────────────────
def like_post(post_id: int) -> None:
    db = get_db()
    db.execute("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))
    db.commit()


def dislike_post(post_id: int) -> None:
    """글 싫어요 — 재탕·근거 없는 글에 대한 반대표."""
    db = get_db()
    db.execute("UPDATE posts SET dislikes = COALESCE(dislikes,0) + 1 WHERE id = ?", (post_id,))
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


# ── 에이전트 반응 — 기록이 남고 중복이 막힌다 ─────────────────────────────────
_COUNTER = {("post", "view"): "views", ("post", "like"): "likes", ("post", "dislike"): "dislikes",
            ("comment", "like"): "likes", ("comment", "dislike"): "dislikes"}


def react(author: str, target: str, target_id: int, kind: str, session_id: int | None = None) -> bool:
    """담당 author가 target(post|comment) #target_id에 kind(view|like|dislike) 반응.

    처음이면 기록을 남기고 카운터를 +1 한 뒤 True. 이미 같은 반응이 있으면 아무것도 안 하고 False.
    """
    col = _COUNTER.get((target, kind))
    if not col:
        return False
    db = get_db()
    cur = db.execute(
        "INSERT OR IGNORE INTO board_reactions (session_id, author, target, target_id, kind, created_at) "
        "VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))",
        (session_id, author, target, target_id, kind),
    )
    if cur.rowcount == 0:
        db.commit()
        return False
    table = "posts" if target == "post" else "comments"
    db.execute(f"UPDATE {table} SET {col} = COALESCE({col},0) + 1 WHERE id = ?", (target_id,))
    db.commit()
    return True


def reacted_ids(author: str, target: str, ids: set[int], kinds: tuple[str, ...] = ("like", "dislike")
                ) -> set[int]:
    """author가 이미 kinds 중 하나로 반응한 target id들 — 다시 묻지 않을 대상."""
    if not ids:
        return set()
    db = get_db()
    marks = ",".join("?" * len(ids))
    kmarks = ",".join("?" * len(kinds))
    rows = db.execute(
        f"SELECT DISTINCT target_id FROM board_reactions "
        f"WHERE author = ? AND target = ? AND kind IN ({kmarks}) AND target_id IN ({marks})",
        (author, target, *kinds, *ids),
    )
    return {int(r["target_id"]) for r in rows}


def reactions_for_session(session_id: int) -> list[dict]:
    """한 회차의 반응 기록 전부(복기 집계용)."""
    db = get_db()
    rows = db.execute("SELECT * FROM board_reactions WHERE session_id = ?", (session_id,))
    return [dict(r) for r in rows]


# ── 조회 ───────────────────────────────────────────────────────────────────
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


def list_posts(board: str = DAILY_BOARD, limit: int = 100, since_day: str | None = None) -> list[dict]:
    """게시판 글 목록(최신 글이 위). 각 글에 comments 배열을 붙여 돌려준다.

    since_day(YYYY-MM-DD)를 주면 그 날짜 이후 글만 — 토론이 최근 글만 보게 하는 용도.
    """
    db = get_db()
    if since_day:
        rows = db.execute(
            "SELECT * FROM posts WHERE board = ? AND COALESCE(day, substr(created_at,1,10)) >= ? "
            "ORDER BY id DESC LIMIT ?", (board, since_day, limit))
    else:
        rows = db.execute("SELECT * FROM posts WHERE board = ? ORDER BY id DESC LIMIT ?", (board, limit))
    posts = [dict(r) for r in rows]
    for p in posts:
        p["comments"] = [
            dict(r) for r in db.execute(
                "SELECT * FROM comments WHERE post_id = ? ORDER BY id ASC", (p["id"],)
            )
        ]
    return posts


def posts_for_session(session_id: int) -> list[dict]:
    """한 회차에 쓴 글(댓글 포함)."""
    db = get_db()
    rows = db.execute("SELECT * FROM posts WHERE session_id = ? ORDER BY id ASC", (session_id,))
    posts = [dict(r) for r in rows]
    for p in posts:
        p["comments"] = [dict(r) for r in db.execute(
            "SELECT * FROM comments WHERE post_id = ? ORDER BY id ASC", (p["id"],))]
    return posts


def comments_for_session(session_id: int) -> list[dict]:
    """한 회차에 단 댓글(글 제목·작성자 포함)."""
    db = get_db()
    rows = db.execute(
        "SELECT c.*, p.title AS post_title, p.author AS post_author, p.project AS post_project "
        "FROM comments c JOIN posts p ON p.id = c.post_id WHERE c.session_id = ? ORDER BY c.id ASC",
        (session_id,))
    return [dict(r) for r in rows]


def delete_by_project(project: str) -> int:
    """한 프로젝트가 쓴 글과 그 댓글 전부 삭제. 삭제한 글 수 반환."""
    db = get_db()
    ids = [r["id"] for r in db.execute("SELECT id FROM posts WHERE project = ?", (project,))]
    for pid in ids:
        db.execute("DELETE FROM comments WHERE post_id = ?", (pid,))
    cur = db.execute("DELETE FROM posts WHERE project = ?", (project,))
    db.commit()
    return cur.rowcount
