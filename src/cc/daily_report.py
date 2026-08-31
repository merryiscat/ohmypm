"""매일 새벽 일간보고 오케스트레이션 (비전 2·3단계).

흐름(grill 확정): 01:00 시작 → 전 프로젝트를 **병렬**로, 각 프로젝트는 PM↔담당 **1:1** 대화
(하이브리드: 결정론 팩트를 PM 프롬프트에 주입, 대화·판단은 headless PM). PM이 {ask,done,summary}
JSON으로 종료를 스스로 판정(담당당 최대 8왕복 안전상한). **소프트 마감**(기본 03:00)을 넘기면 남은
프로젝트는 스킵하고 '미처리'로 표시(놓침0 — 조용히 사라지지 않게). 끝나면 텔레그램 종합 1회.

저장: PM 전용 방(messages room='daily')에 대화를 누적 — 대시보드 사이드바 '일간보고'에서 본다.
자유대화(4단계)·cron 배선은 별도. 이 모듈은 수동 트리거(/api/daily-report)로도 돈다.
"""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from loguru import logger

from src.cc.client import run_headless
from src.cc.permissions import tools_for
from src.cc.prompts import (
    BOARD_SYSTEM,
    FEEDBACK_SYSTEM,
    MANAGE_SYSTEM,
    PM_SYSTEM,
    ROOM_SYSTEM,
    board_comment,
    daily_agent_answer,
    pm_manage,
    post_feedback,
    pm_turn,
)
from src.cc.room_agent import _neutral_cwd
from src.config.settings import settings
from src.db import agents as agents_db
from src.db import board as board_db
from src.db import issues as issues_db
from src.db import messages as messages_db

DAILY_PREFIX = "daily::"       # 일간보고 대화 방 키: daily::{날짜}::{프로젝트path} (일자·프로젝트별 분리)


def _daily_room(date: str, path: str) -> str:
    return f"{DAILY_PREFIX}{date}::{path}"

MAX_ROUNDS = 8                # 담당당 최대 왕복(안전 상한)
CONCURRENCY = 6              # 동시 진행 프로젝트 수(headless 병렬)
PM_TIMEOUT = 150
AGENT_TIMEOUT = 200
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)   # PM 응답에서 첫 JSON 객체 추출
_ARR_RE = re.compile(r"\[.*\]", re.DOTALL)   # 게시판 댓글 응답에서 JSON 배열 추출


def _cancelled(title: str) -> bool:
    return bool(re.search(r"~~.+~~", title or ""))


def build_facts(path: str) -> str:
    """결정론 현황(팩트) 문자열 — PM 프롬프트에 주입(환각 방지). issues DB에서 뽑는다."""
    items = [
        i for i in issues_db.list_issues()
        if i["project"] == path and i.get("verdict") != "drop" and not _cancelled(i["title"])
    ]
    if not items:
        return "추적 중인 이슈 없음(조용한 프로젝트)."
    u = sum(1 for i in items if i["kind"] == "unresolved")
    d = sum(1 for i in items if i["kind"] == "deadline")
    st = {"open": 0, "consulting": 0, "resolved": 0, "deferred": 0}
    for i in items:
        st[i.get("status") or "open"] = st.get(i.get("status") or "open", 0) + 1
    deadlines = sorted(
        (i for i in items if i.get("due")), key=lambda i: i["due"]
    )
    dl_txt = "\n".join(f"  - {i['due']} {i['title'][:80]}" for i in deadlines[:8]) or "  (없음)"
    top = "\n".join(f"  - [{i['kind']}] {i['title'][:90]}" for i in items[:12])
    return (
        f"이슈 {len(items)}건 (미해결 {u}·기한 {d}) / 칸반 상태: 할일 {st['open']}·"
        f"진행중 {st['consulting']}·완료 {st['resolved']}\n"
        f"임박/기한:\n{dl_txt}\n"
        f"이슈 목록(일부):\n{top}"
    )


def _parse_pm(result: str | None) -> dict:
    """PM 응답에서 {ask,done,summary,headline} 추출. 실패하면 done 처리(무한루프 방지)."""
    if not result:
        return {"ask": None, "done": True, "summary": "(PM 응답 없음)", "headline": ""}
    m = _OBJ_RE.search(result)
    if not m:
        return {"ask": None, "done": True, "summary": result.strip()[:300], "headline": ""}
    try:
        d = json.loads(m.group(0))
        upd = d.get("updates")
        return {
            "ask": d.get("ask"),
            "done": bool(d.get("done")),
            "summary": (d.get("summary") or "").strip(),
            "headline": (d.get("headline") or "").strip(),
            "updates": upd if isinstance(upd, list) else [],
        }
    except json.JSONDecodeError:
        return {"ask": None, "done": True, "summary": result.strip()[:300], "headline": "", "updates": []}


def _pm_call(name: str, facts: str, history: str, issues: str) -> dict:
    r = run_headless(
        prompt=pm_turn(name, facts, history, issues),
        cwd=_neutral_cwd(),
        allowed_tools=tools_for("daily_pm")[0],
        disallowed_tools=tools_for("daily_pm")[1],
        timeout=PM_TIMEOUT,
        append_system_prompt=PM_SYSTEM,
    )
    return _parse_pm(r)


def _project_issues(path: str) -> list[dict]:
    """이 프로젝트의 활성 이슈(drop·취소선 제외)."""
    return [
        i for i in issues_db.list_issues()
        if i["project"] == path and i.get("verdict") != "drop" and not _cancelled(i["title"])
    ]


def _manage_call(name: str, issue_list: str, transcript: str) -> list:
    """대화 종료 후 PM이 칸반 상태·일정을 확정(JSON 배열). 실패는 빈 리스트."""
    r = run_headless(
        prompt=pm_manage(name, issue_list, transcript),
        cwd=_neutral_cwd(),
        allowed_tools=tools_for("daily_pm")[0],
        disallowed_tools=tools_for("daily_pm")[1],
        timeout=PM_TIMEOUT,
        append_system_prompt=MANAGE_SYSTEM,
    )
    if not r:
        return []
    m = _ARR_RE.search(r)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _apply_updates(updates: list, valid_ids: set[int]) -> int:
    """PM이 낸 칸반 상태·기한 갱신을 이슈 DB에 반영. 반영 건수 반환."""
    n = 0
    for u in updates:
        try:
            iid = int(u["id"])
        except (KeyError, ValueError, TypeError):
            continue
        if iid not in valid_ids:
            continue
        st = u.get("status")
        if st in ("open", "consulting", "resolved", "deferred"):
            issues_db.set_status(iid, st)
            n += 1
        if "due" in u:
            due = u.get("due")
            issues_db.set_due(iid, None if due in ("", "null", None) else due)
            n += 1
    return n


def _agent_call(name: str, path: str, question: str, history: str) -> str:
    r = run_headless(
        prompt=agents_db.persona_prefix(path) + daily_agent_answer(name, path, question, history),
        cwd=_neutral_cwd(),
        allowed_tools=tools_for("daily_agent")[0],
        disallowed_tools=tools_for("daily_agent")[1],
        timeout=AGENT_TIMEOUT,
        append_system_prompt=ROOM_SYSTEM,
        add_dirs=[path],
    )
    return (r or "").strip() or "(담당 응답 없음)"


def report_one_project(path: str, name: str, date: str, guidance: str = "",
                       max_rounds: int = MAX_ROUNDS) -> dict:
    """한 프로젝트의 PM↔담당 1:1 일간 점검. (날짜·프로젝트)별 방에 대화 저장. 결과 dict 반환.

    guidance: 총괄 관리자가 오늘 이 프로젝트에 준 지침(있으면 PM 팩트에 얹는다).
    저장 방 = daily::{date}::{path}. PM 발화 author='pm'(화면 오른쪽), 담당 author='agent'(왼쪽).
    """
    room = _daily_room(date, path)
    facts = build_facts(path)
    if guidance:
        facts = f"[총괄 관리자의 오늘 지침] {guidance}\n\n" + facts
    # PM이 상태·기한을 갱신할 수 있게 이슈를 id와 함께 목록화
    issue_rows = _project_issues(path)
    valid_ids = {i["id"] for i in issue_rows}
    issue_list = "\n".join(
        f"[{i['id']}] ({i.get('status') or 'open'}/{i['kind']}"
        f"{', 기한 ' + i['due'] if i.get('due') else ''}) {i['title'][:75]}"
        for i in issue_rows
    )
    turns: list[tuple[str, str]] = []   # (PM 질문, 담당 답)
    summary = ""
    headline = ""
    rounds = 0
    for rounds in range(1, max_rounds + 1):
        hist = "\n".join(f"PM: {q}\n담당: {a}" for q, a in turns)
        pm = _pm_call(name, facts, hist, issue_list)
        summary = pm["summary"] or summary
        headline = pm["headline"] or headline
        pm_body = summary + (f"\n▸ 담당에게: {pm['ask']}" if pm["ask"] and not pm["done"] else "")
        messages_db.add_message(room, "pm", pm_body.strip())
        if pm["done"] or not pm["ask"]:
            break
        ans = _agent_call(name, path, pm["ask"], hist)
        messages_db.add_message(room, "agent", ans)
        turns.append((pm["ask"], ans))
    # 대화 종료 후: PM이 칸반 상태·일정을 확정해 실제 반영(전용 관리 호출)
    transcript = "\n".join(f"PM: {q}\n담당: {a}" for q, a in turns) or summary
    applied = _apply_updates(_manage_call(name, issue_list, transcript), valid_ids)
    return {"name": name, "path": path, "rounds": rounds, "summary": summary or "(요약 없음)",
            "headline": headline, "updates_applied": applied, "skipped": False}


def run_daily_report(
    paths: list[str] | None = None,
    max_rounds: int = MAX_ROUNDS,
    concurrency: int = CONCURRENCY,
    deadline_ts: float | None = None,
    notify: bool = True,
    guidance_by_path: dict[str, str] | None = None,
) -> dict:
    """전(또는 지정) 프로젝트 일간보고. 병렬 + 소프트 마감. 끝나면 텔레그램 종합 발송.

    deadline_ts: 이 epoch를 넘겨 '시작'하는 프로젝트는 스킵(미처리). None이면 무제한(수동 테스트).
    paths: 지정 시 그 프로젝트만(테스트용). None이면 위키 있는 전 프로젝트.
    """
    from src.scan.discover import discover_projects

    projects = discover_projects()
    if paths:
        wanted = set(paths)
        projects = [p for p in projects if p["path"] in wanted]
    date = datetime.now().strftime("%Y-%m-%d")
    guidance_by_path = guidance_by_path or {}

    done_results: list[dict] = []
    skipped: list[str] = []

    def worker(p: dict) -> dict:
        if deadline_ts and time.time() > deadline_ts:
            return {"name": p["name"], "path": p["path"], "skipped": True}
        try:
            return report_one_project(p["path"], p["name"], date,
                                      guidance_by_path.get(p["path"], ""), max_rounds)
        except Exception as e:  # 한 프로젝트 실패가 전체를 안 멈춤
            logger.warning(f"[일간보고] {p['name']} 실패: {e}")
            return {"name": p["name"], "path": p["path"], "skipped": False,
                    "summary": f"(점검 실패: {e})", "rounds": 0}

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        for res in ex.map(worker, projects):
            (skipped.append(res["name"]) if res.get("skipped") else done_results.append(res))

    logger.info(f"[일간보고] 완료 {len(done_results)}개 · 미처리 {len(skipped)}개")
    # 각 프로젝트 요약을 게시판 글로 올린다 — 제목은 PM이 뽑은 눈길 끄는 헤드라인
    for r in done_results:
        title = r.get("headline") or f"{r['name']}: {(r.get('summary') or '').splitlines()[0][:35]}"
        board_db.add_post(
            author=r["name"], title=title,
            body=r.get("summary", ""), project=r.get("path"), day=date,
        )
    telegram_text = _assemble_telegram(date, done_results, skipped)
    sent = False
    if notify:
        from src.bot.telegram_bot import send_telegram_sync

        sent = send_telegram_sync(telegram_text)
    return {"date": date, "completed": len(done_results), "skipped": skipped,
            "telegram_sent": sent, "telegram_preview": telegram_text, "results": done_results}


def _assemble_telegram(date: str, results: list[dict], skipped: list[str]) -> str:
    """직후 종합 1회 텔레그램 본문 — 헤드라인 3줄 + 프로젝트별 요약 + 미처리."""
    lines = [f"<b>ohmyPM 일간보고 {date}</b>"]
    # 헤드라인: 요약 첫 줄이 있는 프로젝트 상위 3개
    heads = [r for r in results if r.get("summary") and "요약 없음" not in r["summary"]][:3]
    if heads:
        lines.append("")
        for r in heads:
            first = r["summary"].splitlines()[0][:120]
            lines.append(f"• <b>{r['name']}</b> — {first}")
    lines.append("")
    lines.append("─────")
    for r in sorted(results, key=lambda x: x["name"].lower()):
        lines.append(f"<b>{r['name']}</b>\n{r.get('summary', '')}")
    if skipped:
        lines.append("─────")
        lines.append(f"[미처리] {len(skipped)}개(마감 초과): {', '.join(skipped)}")
    return "\n".join(lines)


# ── 게시판 토론 (4단계) — 담당이 관심 있는 글에만 댓글 ───────────────────────
BOARD_TIMEOUT = 150


def _parse_comments(result: str | None, valid_ids: set[int]) -> list[dict]:
    """담당 응답에서 [{post_id, comment}] 추출. 유효한 글 번호만 통과."""
    if not result:
        return []
    m = _ARR_RE.search(result)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out = []
    for it in data if isinstance(data, list) else []:
        try:
            pid = int(it["post_id"])
            c = (it.get("comment") or "").strip()
            if pid in valid_ids and c:
                out.append({"post_id": pid, "comment": c})
        except (KeyError, ValueError, TypeError):
            continue
    return out


def run_board_discussion(paths: list[str] | None = None, deadline_ts: float | None = None) -> dict:
    """게시판 토론(4단계) — 각 담당이 오늘 게시판 글을 읽고 **관심 있는 글에만** 댓글.

    한 담당당 headless 1콜(게시판 전체를 주고 [{post_id,comment}] 배열을 받음) → 코드가 댓글 삽입.
    자기 프로젝트 글에는 안 단다. 마감(deadline_ts) 넘겨 시작하는 담당은 스킵.
    """
    from src.scan.discover import discover_projects

    posts = board_db.list_posts(board_db.DAILY_BOARD)
    if not posts:
        return {"commented": 0, "note": "게시판에 글 없음"}
    valid_ids = {p["id"] for p in posts}
    board_text = "\n".join(
        f"글#{p['id']} [{p['author']}] {p['title']}: {(p['body'] or '')[:220]}" for p in posts
    )
    own_post_ids = {p["project"]: p["id"] for p in posts if p.get("project")}

    projects = discover_projects()
    if paths:
        wanted = set(paths)
        projects = [p for p in projects if p["path"] in wanted]
    allowed, disallowed = tools_for("daily_agent")

    commented = 0
    for p in projects:
        if deadline_ts and time.time() > deadline_ts:
            break
        out = run_headless(
            prompt=agents_db.persona_prefix(p["path"]) + board_comment(p["name"], p["path"], board_text),
            cwd=_neutral_cwd(),
            allowed_tools=allowed,
            disallowed_tools=disallowed,
            timeout=BOARD_TIMEOUT,
            append_system_prompt=BOARD_SYSTEM,
            add_dirs=[p["path"]],
        )
        own = own_post_ids.get(p["path"])
        for it in _parse_comments(out, valid_ids):
            if it["post_id"] == own:      # 자기 글엔 안 단다
                continue
            board_db.add_comment(it["post_id"], p["name"], it["comment"])
            commented += 1
    logger.info(f"[게시판] 댓글 {commented}개 작성")
    return {"commented": commented}


def run_post_feedback(paths: list[str] | None = None, deadline_ts: float | None = None) -> dict:
    """글쓴이 에이전트가 자기 글에 달린 댓글에 좋아요/싫어요/대댓글로 반응(강화학습 보상 신호).

    한 글당 headless 1콜(글+댓글 주고 [{comment_id,reaction,reply}] 받음) → 코드가 반영.
    """
    posts = board_db.list_posts(board_db.DAILY_BOARD)
    if paths:
        wanted = set(paths)
        posts = [p for p in posts if p.get("project") in wanted]
    allowed, disallowed = tools_for("daily_agent")
    reacted = 0
    for post in posts:
        if not post.get("project"):
            continue
        top = [c for c in post.get("comments", []) if not c.get("parent_id")]
        if not top:
            continue
        if deadline_ts and time.time() > deadline_ts:
            break
        cids = {c["id"] for c in top}
        ctext = "\n".join(f"[{c['id']}] {c['author']}: {(c['body'] or '')[:200]}" for c in top)
        out = run_headless(
            prompt=agents_db.persona_prefix(post["project"]) + post_feedback(post["author"], post["project"], post["title"], post["body"], ctext),
            cwd=_neutral_cwd(),
            allowed_tools=allowed, disallowed_tools=disallowed,
            timeout=BOARD_TIMEOUT, append_system_prompt=FEEDBACK_SYSTEM,
            add_dirs=[post["project"]],
        )
        if not out:
            continue
        m = _ARR_RE.search(out)
        if not m:
            continue
        try:
            items = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        for it in items if isinstance(items, list) else []:
            try:
                cid = int(it["comment_id"])
            except (KeyError, ValueError, TypeError):
                continue
            if cid not in cids:
                continue
            if it.get("reaction") in ("like", "dislike"):
                board_db.react_comment(cid, it["reaction"])
                reacted += 1
            rep = (it.get("reply") or "").strip()
            if rep and rep.lower() != "null":
                board_db.add_comment(post["id"], post["author"], rep, parent_id=cid)
    logger.info(f"[게시판 피드백] 반응 {reacted}건")
    return {"reacted": reacted}


def run_nightly() -> dict:
    """01:00 cron 진입점 — 총괄 관리자가 지휘하는 하루.

    ① 관리자 아침 계획(저널+현황→프로젝트별 지침) ② 일간보고(지침 주입, 병렬, 소프트마감 03시)
    ③ 게시판 토론 ④ 글쓴이 반응 ⑤ 보상 처리 ⑥ 관리자 저녁 종합(저널 갱신) → 요약 저장(07시 발송).
    """
    from src.cc import manager
    from src.cc.rewards import run_rewards
    from src.db import alerts as alerts_db
    from src.scan.discover import discover_projects

    now = datetime.now()
    date = now.strftime("%Y-%m-%d")

    def _at(hour: int) -> float:
        return now.replace(hour=hour, minute=0, second=0, microsecond=0).timestamp()

    projects = discover_projects()
    guidance = manager.plan_day(projects)                        # ① 아침 계획
    report = run_daily_report(deadline_ts=_at(settings.daily_soft_deadline_hour),
                              notify=False, guidance_by_path=guidance)   # ②
    board = run_board_discussion(deadline_ts=_at(settings.discussion_until_hour))    # ③
    feedback = run_post_feedback(deadline_ts=_at(settings.discussion_until_hour))    # ④
    rewards = run_rewards()                                       # ⑤ 보상
    synthesis = manager.close_day(date, report.get("results", []))   # ⑥ 저녁 종합
    # 아침 발송용 요약 = 관리자 종합(없으면 기본 텔레그램 텍스트)
    alerts_db.set_setting(f"daily_summary:{date}", synthesis or report.get("telegram_preview", ""))
    return {"report": report, "board": board, "feedback": feedback,
            "rewards": rewards, "synthesis_chars": len(synthesis or "")}


def send_daily_telegram(date: str | None = None) -> bool:
    """저장된 그날 일간보고 요약을 텔레그램으로 발송(아침 07시 cron)."""
    from src.bot.telegram_bot import send_telegram_sync
    from src.db import alerts as alerts_db

    date = date or datetime.now().strftime("%Y-%m-%d")
    text = alerts_db.get_setting(f"daily_summary:{date}")
    if not text:
        logger.info(f"[텔레그램] {date} 발송할 일간보고 요약 없음")
        return False
    return send_telegram_sync(text)
