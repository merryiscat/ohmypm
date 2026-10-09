"""게시판 토론 4단계 — 담당 에이전트들이 글을 쓰고, 둘러보고, 반응하고, 한 번 더 답한다.

2026-10-09 일간보고 모듈(daily_report.py)에서 떼어 왔다. 야간 배치가 돌리던 것을 이제는
토론 세션(board_session.py)이 "토론 시작" 버튼 한 번에 마감 시각까지 순서대로 돌린다.

네 단계 공통 계약:
  run_xxx(paths=None, deadline_ts=None, stop=None, session_id=None) -> dict
  - paths: 지정하면 그 프로젝트들만(없으면 enabled 전체)
  - deadline_ts: 이 epoch를 넘겨 '시작'하는 호출은 건너뛴다(이미 도는 호출은 끝까지 간다)
  - stop: threading.Event — set되면 새 호출을 띄우지 않는다(중지 버튼)
  - session_id: 이번 회차 번호 — 글·댓글·반응에 찍혀 복기(reflect.py)의 집계 단위가 된다
  반환 dict에는 단계별 건수와 cost_usd(이 단계의 모델 비용 합)가 든다.

옛 코드에서 고친 것(2026-10-09):
  - 글쓰기: 그날 이미 쓴 담당은 건너뛴다(하루 1편) — 재실행하면 같은 날 글이 또 생기던 것
  - 둘러보기: 최근 7일 글만 대상, 반응은 board_reactions 표로 한 번만(같은 담당이 같은 글에 두 번 못 누름)
  - 자기 글 제외: 프로젝트당 글 하나만 담아 최근 자기 글을 스스로 추천하던 것 → 전부 제외
  - 글쓴이 반응: 이미 반응한 댓글은 다시 묻지 않는다(답글 유무가 아니라 반응 기록 기준)
  - 대대댓글: '오늘 글'이 아니라 최근 7일 글 중 아직 안 단 스레드
  - 담당 순서를 섞는다 — 같은 프로젝트만 매번 마감에 걸려 굶지 않게
"""

import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from loguru import logger

from src.cc.client import run_headless_ex
from src.cc.common import neutral_cwd, parse_json_array, parse_json_object
from src.cc.permissions import tools_for
from src.cc.prompts import (
    BOARD_SYSTEM,
    BOARD_WRITE_SYSTEM,
    FEEDBACK_SYSTEM,
    FOLLOWUP_SYSTEM,
    board_comment,
    board_write,
    comment_followup,
    post_feedback,
)
from src.config.settings import settings
from src.db import agents as agents_db
from src.db import board as board_db

BOARD_TIMEOUT = 150          # 담당 한 명의 헤드리스 호출 제한(초)
RECENT_DAYS = 7              # 둘러보기·반응·대대댓글이 보는 글의 기간(일)
PAST_POSTS_DAYS = 30         # 재탕 금지 기간 — 30일 지난 이야기는 다시 써도 된다
PAST_POSTS_CAP = 30          # 글쓰기 프롬프트에 넣는 자기 글 최대 편수
MAX_COMMENTS_PER_AGENT = 2   # 한 담당이 한 회차에 다는 댓글 상한(공감 홍수 방지)


def _since_day(days: int = RECENT_DAYS) -> str:
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")


def _targets(paths: list[str] | None) -> list[dict]:
    """토론에 참여할 프로젝트 — enabled 전체 또는 지정 목록. 순서는 섞는다."""
    from src.scan.discover import discover_projects

    projects = discover_projects()
    if paths:
        wanted = set(paths)
        projects = [p for p in projects if p["path"] in wanted]
    random.shuffle(projects)
    return projects


def _author_of(path: str, fallback: str) -> str:
    """게시판 활동의 작성자 이름 — 프로필 이름 우선(점수 집계 키와 일치)."""
    prof = agents_db.get_profile(path) or {}
    return prof.get("name") or fallback


def _should_skip(deadline_ts: float | None, stop: threading.Event | None) -> bool:
    """새 호출을 띄우면 안 되는가 — 마감이 지났거나 중지 신호가 왔으면 True."""
    if stop is not None and stop.is_set():
        return True
    return bool(deadline_ts and time.time() > deadline_ts)


def _board_parallel(items: list, worker, label: str) -> list:
    """담당(또는 글)별 헤드리스 호출을 settings.board_concurrency만큼 동시에 돌린다.

    한 담당의 예외가 단계 전체를 멈추지 않게 삼키고 로그만 남긴다(실패는 결과에서 빠짐).
    """
    def guarded(item):
        try:
            return worker(item)
        except Exception as e:
            logger.warning(f"[{label}] 항목 실패: {e}")
            return None

    with ThreadPoolExecutor(max_workers=settings.board_concurrency) as ex:
        return [r for r in ex.map(guarded, items) if r is not None]


def _kwargs(system: str, path: str) -> dict:
    """담당 한 명의 헤드리스 호출 공통 인자 — 호출부는 task 이름만 글자 그대로 적는다(정책 테스트가 확인)."""
    allowed, disallowed = tools_for("board")
    return dict(cwd=neutral_cwd(), allowed_tools=allowed, disallowed_tools=disallowed,
                timeout=BOARD_TIMEOUT, append_system_prompt=system,
                add_dirs=[path], model=agents_db.model_for(path))


def _unpack(meta: dict) -> tuple[str | None, float]:
    """(응답 텍스트, 비용) — 실패면 (None, 0)."""
    return meta.get("result"), float(meta.get("cost_usd") or 0)


# ── 1) 글쓰기 ───────────────────────────────────────────────────────────────
def _past_posts_text(project_path: str, posts: list[dict]) -> str:
    """이 담당이 최근 30일 올린 글 목록 — 글쓰기 프롬프트에 넣어 재탕을 막는다."""
    cutoff = _since_day(PAST_POSTS_DAYS)
    mine = [p for p in posts
            if p.get("project") == project_path and (p.get("day") or "") >= cutoff][:PAST_POSTS_CAP]
    if not mine:
        return ""
    lines = []
    for p in mine:
        lines.append(f"- [{p.get('day') or ''}] {p['title']} "
                     f"(조회 {p.get('views', 0)}·좋아요 {p.get('likes', 0)})")
        lines.append(f"    요지: {(p.get('body') or '').strip()[:90]}…")
    return "\n".join(lines)


def run_board_posts(paths: list[str] | None = None, deadline_ts: float | None = None,
                    stop: threading.Event | None = None, session_id: int | None = None) -> dict:
    """글쓰기 — 각 담당이 자기 프로젝트에서 글감을 스스로 골라 글을 쓴다(0~1편, 하루 1편)."""
    date = datetime.now().strftime("%Y-%m-%d")
    past = board_db.list_posts(board_db.DAILY_BOARD)
    wrote_today = {p["project"] for p in past if p.get("day") == date and p.get("project")}
    projects = [p for p in _targets(paths) if p["path"] not in wrote_today]

    def worker(p: dict) -> tuple[int, float]:
        if _should_skip(deadline_ts, stop):
            return 0, 0.0
        prompt = agents_db.persona_prefix(p["path"]) + board_write(
            p["name"], p["path"], _past_posts_text(p["path"], past))
        out, cost = _unpack(run_headless_ex(prompt, task="board_write", **_kwargs(BOARD_WRITE_SYSTEM, p["path"])))
        items = parse_json_array(out) or []
        n = 0
        for it in items[:1]:                       # 최대 1편
            if not isinstance(it, dict):
                continue
            title = (it.get("title") or "").strip()
            body = (it.get("body") or "").strip()
            if title and body:
                board_db.add_post(author=_author_of(p["path"], p["name"]), title=title[:80],
                                  body=body, project=p["path"], day=date, session_id=session_id)
                n += 1
        return n, cost

    results = _board_parallel(projects, worker, "게시판 글쓰기")
    posted = sum(r[0] for r in results)
    cost = sum(r[1] for r in results)
    logger.info(f"[게시판 글쓰기] {posted}편 (이미 쓴 담당 {len(wrote_today)}명 건너뜀)")
    return {"posted": posted, "skipped_written": len(wrote_today), "cost_usd": cost}


# ── 2) 둘러보기·댓글 ─────────────────────────────────────────────────────────
def _parse_board_response(result: str | None, valid_ids: set[int]
                          ) -> tuple[set[int], set[int], set[int], list[dict]]:
    """둘러보기 응답에서 {opened, liked, disliked, comments}를 추출. 실패는 전부 빈 값.

    liked·disliked·댓글 단 글은 opened에 없어도 연 것으로 친다(반응 = 읽었다는 신호).
    같은 글을 좋아요와 싫어요 둘 다에 넣으면 좋아요를 버린다(모순은 반대표 우선).
    """
    d = parse_json_object(result)
    if not d:
        return set(), set(), set(), []

    def _ids(key: str) -> set[int]:
        out: set[int] = set()
        for x in d.get(key) or []:
            try:
                if int(x) in valid_ids:
                    out.add(int(x))
            except (ValueError, TypeError):
                continue
        return out

    opened, liked, disliked = _ids("opened"), _ids("liked"), _ids("disliked")
    liked -= disliked
    opened |= liked | disliked
    comments: list[dict] = []
    for it in d.get("comments") or []:
        try:
            pid = int(it["post_id"])
            c = (it.get("comment") or "").strip()
        except (KeyError, ValueError, TypeError):
            continue
        if pid in valid_ids and c:
            comments.append({"post_id": pid, "comment": c})
            opened.add(pid)
    return opened, liked, disliked, comments[:MAX_COMMENTS_PER_AGENT]


def run_board_discussion(paths: list[str] | None = None, deadline_ts: float | None = None,
                         stop: threading.Event | None = None, session_id: int | None = None) -> dict:
    """둘러보기 — 각 담당이 최근 글 제목을 훑고 끌리는 글만 열어(조회) 마음에 들면 좋아요·댓글."""
    posts = board_db.list_posts(board_db.DAILY_BOARD, since_day=_since_day())
    if not posts:
        return {"commented": 0, "liked": 0, "disliked": 0, "cost_usd": 0.0, "note": "최근 글 없음"}
    valid_ids = {p["id"] for p in posts}
    board_text = "\n\n".join(
        f"글#{p['id']} [{p['title']}] (작성자 {p['author']})\n({(p['body'] or '')[:400]})"
        for p in posts
    )
    own_ids: dict[str, set[int]] = {}
    for p in posts:
        if p.get("project"):
            own_ids.setdefault(p["project"], set()).add(p["id"])
    projects = _targets(paths)

    def worker(p: dict) -> tuple[int, int, int, float]:
        if _should_skip(deadline_ts, stop):
            return 0, 0, 0, 0.0
        prompt = agents_db.persona_prefix(p["path"]) + board_comment(p["name"], p["path"], board_text)
        out, cost = _unpack(run_headless_ex(prompt, task="board_comment", **_kwargs(BOARD_SYSTEM, p["path"])))
        own = own_ids.get(p["path"], set())
        author = _author_of(p["path"], p["name"])
        opened, liked, disliked, cmts = _parse_board_response(out, valid_ids)
        likes = dislikes = comments = 0
        for pid in opened - own:
            board_db.react(author, "post", pid, "view", session_id)
        for pid in liked - own:
            likes += int(board_db.react(author, "post", pid, "like", session_id))
        for pid in disliked - own:
            dislikes += int(board_db.react(author, "post", pid, "dislike", session_id))
        for it in cmts:
            if it["post_id"] in own:
                continue
            board_db.add_comment(it["post_id"], author, it["comment"], session_id=session_id)
            comments += 1
        return likes, dislikes, comments, cost

    results = _board_parallel(projects, worker, "게시판 둘러보기")
    out = {"liked": sum(r[0] for r in results), "disliked": sum(r[1] for r in results),
           "commented": sum(r[2] for r in results), "cost_usd": sum(r[3] for r in results)}
    logger.info(f"[게시판 둘러보기] 좋아요 {out['liked']} · 싫어요 {out['disliked']} · 댓글 {out['commented']}")
    return out


# ── 3) 글쓴이 반응 ───────────────────────────────────────────────────────────
def run_post_feedback(paths: list[str] | None = None, deadline_ts: float | None = None,
                      stop: threading.Event | None = None, session_id: int | None = None) -> dict:
    """글쓴이가 자기 글에 달린 댓글에 좋아요/싫어요/대댓글로 반응한다(한 글당 1콜)."""
    posts = board_db.list_posts(board_db.DAILY_BOARD, since_day=_since_day())
    if paths:
        wanted = set(paths)
        posts = [p for p in posts if p.get("project") in wanted]
    by_project: dict[str, list[dict]] = {}
    for post in posts:
        if post.get("project"):
            by_project.setdefault(post["project"], []).append(post)

    def _react_one(post: dict) -> tuple[int, float]:
        top = [c for c in post.get("comments", []) if not c.get("parent_id")]
        done = board_db.reacted_ids(post["author"], "comment", {c["id"] for c in top})
        top = [c for c in top if c["id"] not in done]
        if not top or _should_skip(deadline_ts, stop):
            return 0, 0.0
        cids = {c["id"] for c in top}
        ctext = "\n".join(f"[{c['id']}] {c['author']}: {(c['body'] or '')[:200]}" for c in top)
        prompt = agents_db.persona_prefix(post["project"]) + post_feedback(
            post["author"], post["project"], post["title"], post["body"], ctext)
        out, cost = _unpack(run_headless_ex(prompt, task="board_feedback", **_kwargs(FEEDBACK_SYSTEM, post["project"])))
        n = 0
        for it in parse_json_array(out) or []:
            if not isinstance(it, dict):
                continue
            try:
                cid = int(it["comment_id"])
            except (KeyError, ValueError, TypeError):
                continue
            if cid not in cids:
                continue
            if it.get("reaction") in ("like", "dislike"):
                n += int(board_db.react(post["author"], "comment", cid, it["reaction"], session_id))
            rep = (it.get("reply") or "").strip()
            if rep and rep.lower() != "null":
                board_db.add_comment(post["id"], post["author"], rep, parent_id=cid,
                                     session_id=session_id)
        return n, cost

    def worker(item: tuple[str, list[dict]]) -> tuple[int, float]:
        pairs = [_react_one(post) for post in item[1]]
        return sum(p[0] for p in pairs), sum(p[1] for p in pairs)

    results = _board_parallel(list(by_project.items()), worker, "게시판 피드백")
    out = {"reacted": sum(r[0] for r in results), "cost_usd": sum(r[1] for r in results)}
    logger.info(f"[게시판 피드백] 반응 {out['reacted']}건")
    return out


# ── 4) 대대댓글 ─────────────────────────────────────────────────────────────
def run_reply_followup(paths: list[str] | None = None, deadline_ts: float | None = None,
                       stop: threading.Event | None = None, session_id: int | None = None) -> dict:
    """글쓴이의 대댓글을 받은 담당이 덧붙일 말이 있을 때만 한 번 더 답한다(담당당 1콜)."""
    posts = board_db.list_posts(board_db.DAILY_BOARD, since_day=_since_day())
    if not posts:
        return {"replied": 0, "cost_usd": 0.0, "note": "최근 글 없음"}

    projects = _targets(paths)
    path_by_name: dict[str, str] = {}
    for p in projects:
        path_by_name[_author_of(p["path"], p["name"])] = p["path"]

    threads_by_agent: dict[str, list[str]] = {}
    post_of_reply: dict[int, int] = {}
    valid_by_agent: dict[str, set[int]] = {}
    for post in posts:
        cmts = post.get("comments", [])
        by_id = {c["id"]: c for c in cmts}
        for r in cmts:
            parent = by_id.get(r.get("parent_id") or 0)
            if not parent:
                continue
            # 글쓴이가 남의 댓글에 단 대댓글만(사용자 댓글·자기 글엔 해당 없음)
            if r["author"] != post["author"] or parent["author"] in ("user", post["author"]):
                continue
            if parent["author"] not in path_by_name:
                continue
            if any(c.get("parent_id") == r["id"] for c in cmts):   # 이미 답한 스레드
                continue
            agent = parent["author"]
            threads_by_agent.setdefault(agent, []).append(
                f"[대댓글#{r['id']}] 글 '{(post['title'] or '')[:60]}'\n"
                f"  내 댓글: {(parent['body'] or '')[:200]}\n"
                f"  글쓴이({post['author']}) 답글: {(r['body'] or '')[:200]}"
            )
            post_of_reply[r["id"]] = post["id"]
            valid_by_agent.setdefault(agent, set()).add(r["id"])

    def worker(item: tuple[str, list[str]]) -> tuple[int, float]:
        agent, threads = item
        if _should_skip(deadline_ts, stop):
            return 0, 0.0
        path = path_by_name[agent]
        prompt = agents_db.persona_prefix(path) + comment_followup(agent, path, "\n\n".join(threads))
        out, cost = _unpack(run_headless_ex(prompt, task="board_followup", **_kwargs(FOLLOWUP_SYSTEM, path)))
        n = 0
        for it in parse_json_array(out) or []:
            if not isinstance(it, dict):
                continue
            try:
                rid = int(it["reply_id"])
            except (KeyError, ValueError, TypeError):
                continue
            body = (it.get("comment") or "").strip()
            if rid not in valid_by_agent.get(agent, set()) or not body or body.lower() == "null":
                continue
            board_db.add_comment(post_of_reply[rid], agent, body, parent_id=rid, session_id=session_id)
            n += 1
        return n, cost

    results = _board_parallel(list(threads_by_agent.items()), worker, "대대댓글")
    out = {"replied": sum(r[0] for r in results), "cost_usd": sum(r[1] for r in results)}
    logger.info(f"[대대댓글] {out['replied']}건")
    return out
