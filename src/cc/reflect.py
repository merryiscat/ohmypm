"""토론 복기 — 회차가 끝나면 담당마다 받은 반응을 모아 점수 이력을 남기고, 한 번 더 물어 '배운 것'을 뽑는다.

점수 집계(record_scores)는 결정론(모델 호출 없음). 복기(run)는 담당당 light 모델 1콜이며,
그 답 한두 줄이 프로필 note에 쌓여 다음 호출(게시판·룸 채팅)의 프롬프트 앞에 붙는다.
이것이 "점수는 강화학습 재료"의 실제 통로다(2026-10-09 사용자 결정).
"""

import threading

from loguru import logger

from src.cc.board import _board_parallel
from src.cc.client import run_headless_ex
from src.cc.common import neutral_cwd, parse_json_object
from src.cc.permissions import NEVER_ALLOW
from src.cc.prompts import load, render
from src.db import agents as agents_db
from src.db import board as board_db
from src.db import projects as projects_db
from src.db import sessions as sessions_db

REFLECT_TIMEOUT = 90


def _name_map() -> dict[str, str]:
    """담당 이름 → 프로젝트 경로(프로필 이름 우선)."""
    out: dict[str, str] = {}
    for p in projects_db.list_projects(enabled_only=True):
        prof = agents_db.get_profile(p["path"]) or {}
        out[prof.get("name") or p["name"]] = p["path"]
    return out


def session_stats(session_id: int) -> dict[str, dict]:
    """회차 집계 — {project: {name, posts, comments, views, post_likes, ..., points, total, my_posts, my_comments}}."""
    names = _name_map()
    stats: dict[str, dict] = {}

    def row(name: str) -> dict | None:
        path = names.get(name)
        if not path:
            return None
        return stats.setdefault(path, {
            "name": name, "posts": 0, "comments": 0, "views": 0, "post_likes": 0, "post_dislikes": 0,
            "cmt_likes": 0, "cmt_dislikes": 0, "replies_received": 0, "points": 0, "total": 0,
            "my_posts": [], "my_comments": []})

    posts = board_db.posts_for_session(session_id)
    post_author: dict[int, str] = {}
    for p in posts:
        r = row(p["author"])
        if r:
            r["posts"] += 1
            r["my_posts"].append(p)
        post_author[p["id"]] = p["author"]
    comments = board_db.comments_for_session(session_id)
    cmt_author: dict[int, str] = {c["id"]: c["author"] for c in comments}
    for c in comments:
        r = row(c["author"])
        if r and c["author"] != c.get("post_author"):     # 자기 글에 단 답글은 '댓글'로 안 센다
            r["comments"] += 1
            r["my_comments"].append(c)
        # 답글을 받은 쪽: 부모 댓글 작성자
        parent_author = cmt_author.get(c.get("parent_id") or 0)
        if parent_author and parent_author != c["author"]:
            rr = row(parent_author)
            if rr:
                rr["replies_received"] += 1
    # 반응 — 대상의 작성자가 받은 것
    all_posts_author = dict(post_author)
    for rx in board_db.reactions_for_session(session_id):
        if rx["target"] == "post":
            author = all_posts_author.get(rx["target_id"])
            if author is None:
                p = board_db.get_post(rx["target_id"])
                author = p["author"] if p else None
                all_posts_author[rx["target_id"]] = author
            r = row(author) if author else None
            if not r:
                continue
            key = {"view": "views", "like": "post_likes", "dislike": "post_dislikes"}.get(rx["kind"])
        else:
            author = cmt_author.get(rx["target_id"])
            if author is None:
                author = _comment_author(rx["target_id"])
                cmt_author[rx["target_id"]] = author
            r = row(author) if author else None
            if not r:
                continue
            key = {"like": "cmt_likes", "dislike": "cmt_dislikes"}.get(rx["kind"])
        if key:
            r[key] += 1
    totals = agents_db.compute_scores()
    for path, r in stats.items():
        r["points"] = (r["post_likes"] * agents_db.W_POST_LIKE + r["views"] * agents_db.W_POST_VIEW
                       - r["post_dislikes"] * agents_db.W_POST_DISLIKE
                       + r["cmt_likes"] * agents_db.W_CMT_LIKE - r["cmt_dislikes"] * agents_db.W_CMT_DISLIKE)
        r["total"] = totals.get(r["name"], 0)
    return stats


def _comment_author(comment_id: int) -> str | None:
    from src.db.client import get_db

    row = get_db().execute("SELECT author FROM comments WHERE id = ?", (comment_id,)).fetchone()
    return row["author"] if row else None


def record_scores(session_id: int) -> dict[str, dict]:
    """점수 이력만 저장(모델 호출 없음). 중지·복구 때도 쓴다."""
    stats = session_stats(session_id)
    for path, r in stats.items():
        sessions_db.upsert_score(session_id, path, r["name"],
                                 **{k: r[k] for k in sessions_db.SCORE_FIELDS})
    return stats


def _material(r: dict) -> tuple[str, str]:
    """복기 프롬프트에 넣을 내 글·내 댓글 요약 텍스트."""
    posts = []
    for p in r["my_posts"]:
        cm = [c for c in p.get("comments", []) if c["author"] != p["author"]]
        posts.append(f"- '{p['title']}' — 조회 {p.get('views', 0)}·좋아요 {p.get('likes', 0)}·싫어요 {p.get('dislikes', 0)}, 댓글 {len(cm)}개"
                     + ("".join(f"\n    · {c['author']}: {(c['body'] or '')[:200]}" for c in cm[:4])))
    cmts = []
    for c in r["my_comments"]:
        cmts.append(f"- 글 '{(c.get('post_title') or '')[:50]}'에 단 댓글: {(c['body'] or '')[:160]} "
                    f"(좋아요 {c.get('likes', 0)}·싫어요 {c.get('dislikes', 0)})")
    return ("\n".join(posts) or "(이번 회차에 쓴 글 없음)"), ("\n".join(cmts) or "(이번 회차에 단 댓글 없음)")


def run(session_id: int, stop: threading.Event | None = None) -> dict:
    """점수 이력 저장 + 참여 담당마다 복기 1콜 → note에 '배운 것' 추가. 반환 {reflected, cost_usd}."""
    stats = record_scores(session_id)
    system = load("board_reflect_system")
    items = [(path, r) for path, r in stats.items()
             if r["posts"] or r["comments"] or r["views"] or r["post_likes"] or r["cmt_likes"]]

    def worker(item: tuple[str, dict]) -> tuple[int, float]:
        path, r = item
        if stop is not None and stop.is_set():
            return 0, 0.0
        my_posts, my_comments = _material(r)
        prompt = render("board_reflect", name=r["name"], project_name=projects_db_name(path),
                        my_posts=my_posts, my_comments=my_comments,
                        score_delta=f"{r['points']:+d}", total=str(r["total"]),
                        past_note=agents_db.get_note(path) or "(아직 없음)")
        meta = run_headless_ex(prompt, cwd=neutral_cwd(), allowed_tools=[], disallowed_tools=NEVER_ALLOW,
                               timeout=REFLECT_TIMEOUT, append_system_prompt=system,
                               model=agents_db.model_for(path), task="board_reflect")
        d = parse_json_object(meta.get("result")) or {}
        lesson = (d.get("lesson") or "").strip()
        if lesson:
            agents_db.append_note(path, lesson)
            sessions_db.upsert_score(session_id, path, r["name"], lesson=lesson)
        return int(bool(lesson)), float(meta.get("cost_usd") or 0)

    results = _board_parallel(items, worker, "복기")
    out = {"reflected": sum(x[0] for x in results), "cost_usd": sum(x[1] for x in results)}
    logger.info(f"[복기] #{session_id} 담당 {len(items)}명 중 {out['reflected']}명 배운 것 기록")
    return out


def projects_db_name(path: str) -> str:
    for p in projects_db.list_projects(enabled_only=False):
        if p["path"] == path:
            return p["name"]
    return path
