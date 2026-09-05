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
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from loguru import logger

from src.cc.client import run_headless
from src.cc.permissions import tools_for
from src.cc.prompts import (
    BOARD_SYSTEM,
    FEEDBACK_SYSTEM,
    FOLLOWUP_SYSTEM,
    MANAGE_SYSTEM,
    PM_SYSTEM,
    ROOM_SYSTEM,
    board_comment,
    comment_followup,
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
CONCURRENCY = 3              # 동시 진행 프로젝트 수(headless 병렬) — 6은 버스트 속도제한 트립(09-01)
PM_TIMEOUT = 150
AGENT_TIMEOUT = 200
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)   # PM 응답에서 첫 JSON 객체 추출
_ARR_RE = re.compile(r"\[.*\]", re.DOTALL)   # 게시판 댓글 응답에서 JSON 배열 추출


def _cancelled(title: str) -> bool:
    return bool(re.search(r"~~.+~~", title or ""))


# 조용한 프로젝트(변화 없음)의 고정 요약 — LLM 없이 코드가 만든다.
QUIET_SUMMARY = "작업 내용 없음(어제 이후 새 커밋·새 이슈 없음) — 점검 생략"


def _has_activity(path: str) -> bool:
    """어제 이후 '사람의 작업'이 있었는지 — 없으면 LLM을 아예 안 부른다(토큰 절약의 핵심).

    변화 없는 프로젝트도 매일 PM↔담당 인터뷰를 돌면, 어제와 똑같은 보고를 어제와 같은
    토큰을 들여 재생산한다(2026-09-02 사용자 지적). 신호 두 가지로 변화를 판정한다:
      ① 최근 24시간 git 커밋 — 단, ohmyPM이 밤마다 만드는 자동 커밋(재가공 '(ohmyPM 담당)'·
         하네스감사 '(ohmyPM)')은 제외. 안 그러면 매일 '변화 있음'으로 오탐한다.
      ② 최근 24시간 새 이슈(정시 스캔이 docs에서 발견) — 커밋 없이 docs만 고쳐도 잡힌다.
    git 확인이 실패하면 True(모르면 점검하는 쪽 — 놓침0 원칙).
    """
    from pathlib import Path as _P

    if (_P(path) / ".git").exists():
        try:
            r = subprocess.run(
                ["git", "-C", path, "log", "--since=24 hours ago", "--format=%s"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
            )
            if r.returncode != 0:
                return True  # git 조회 실패 — 모르면 점검하는 쪽으로
            if any(s.strip() and "ohmyPM" not in s for s in r.stdout.splitlines()):
                return True  # 사람(또는 다른 도구)의 커밋이 있다
        except Exception:
            return True
    # 비git 폴더는 커밋 신호가 없다 — 매일 점검(콜 낭비) 대신 새 이슈 신호만 본다
    # 새 이슈: issues.created_at은 SQLite datetime('now') = UTC 문자열 → UTC로 비교
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    return any(
        i["project"] == path and (i.get("created_at") or "") >= cutoff
        for i in issues_db.list_issues()
    )


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
    """PM 응답에서 {ask,done,summary,headline} 추출. 실패하면 done 처리(무한루프 방지).

    failed=True는 headless 자체가 실패(None)했다는 뜻 — 호출부가 '응답없음' 글/메시지를 안 만들게 구분.
    """
    if not result:
        return {"ask": None, "done": True, "summary": "(PM 응답 없음)", "headline": "", "failed": True}
    m = _OBJ_RE.search(result)
    if not m:
        return {"ask": None, "done": True, "summary": result.strip()[:300], "headline": "", "failed": False}
    try:
        d = json.loads(m.group(0))
        upd = d.get("updates")
        return {
            "ask": d.get("ask"),
            "done": bool(d.get("done")),
            "summary": (d.get("summary") or "").strip(),
            "headline": (d.get("headline") or "").strip(),
            "updates": upd if isinstance(upd, list) else [],
            "failed": False,
        }
    except json.JSONDecodeError:
        return {"ask": None, "done": True, "summary": result.strip()[:300], "headline": "",
                "updates": [], "failed": False}


def _is_failed(r: dict) -> bool:
    """일간보고 결과가 실패/빈 것인지 — 게시판 글·재가공에서 걸러낼 판단."""
    if r.get("failed"):
        return True
    s = (r.get("summary") or "").strip()
    return (not s) or s.startswith("(PM 응답") or s.startswith("(요약 없음") or "점검 실패" in s


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
        model=agents_db.model_for(path),   # 담당별 지정 모델(없으면 기본)
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
        # ★ headless가 실패(None)했고 아직 대화가 없으면 = 그냥 못 돈 것. 방에 '응답없음'을 남기지
        #   말고 실패로 반환(2026-09-01 야간 한도 전량실패가 게시판에 빈 글 18개를 만든 사고 방지).
        if pm.get("failed") and not turns:
            return {"name": name, "path": path, "rounds": rounds, "summary": "(점검 실패: headless 무응답)",
                    "headline": "", "updates_applied": 0, "skipped": False, "failed": True}
        summary = pm["summary"] or summary
        headline = pm["headline"] or headline
        pm_body = summary + (f"\n▸ 담당에게: {pm['ask']}" if pm["ask"] and not pm["done"] else "")
        pm_out = pm_body.strip()
        messages_db.add_message(room, "pm", pm_out)
        # ★ 룸 피드에도 그대로 흘린다 — 일간보고가 프로젝트 룸 대화로 곧장 이어지게
        #   (2026-09-04 사용자 확정). 첫 발화에만 날짜 태그를 붙여 어디부터가 보고인지 표시.
        messages_db.add_message(path, "pm", (f"[일간보고 {date}]\n" if rounds == 1 else "") + pm_out)
        if pm["done"] or not pm["ask"]:
            break
        ans = _agent_call(name, path, pm["ask"], hist)
        messages_db.add_message(room, "agent", ans)
        messages_db.add_message(path, "agent", ans)
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
            # ★ 변화 없는 프로젝트는 LLM 콜 0회 — 코드가 '작업 내용 없음' 한 줄로 끝낸다.
            #   (매일 같은 보고를 재생산하며 한도를 태우던 낭비 제거, 2026-09-02)
            if not _has_activity(p["path"]):
                messages_db.add_message(_daily_room(date, p["path"]), "pm", QUIET_SUMMARY)
                return {"name": p["name"], "path": p["path"], "skipped": False, "quiet": True,
                        "rounds": 0, "summary": QUIET_SUMMARY, "headline": "", "updates_applied": 0}
            return report_one_project(p["path"], p["name"], date,
                                      guidance_by_path.get(p["path"], ""), max_rounds)
        except Exception as e:  # 한 프로젝트 실패가 전체를 안 멈춤
            logger.warning(f"[일간보고] {p['name']} 실패: {e}")
            return {"name": p["name"], "path": p["path"], "skipped": False,
                    "summary": f"(점검 실패: {e})", "rounds": 0}

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        for res in ex.map(worker, projects):
            (skipped.append(res["name"]) if res.get("skipped") else done_results.append(res))

    ok_results = [r for r in done_results if not _is_failed(r)]
    failed_n = len(done_results) - len(ok_results)
    quiet_n = sum(1 for r in ok_results if r.get("quiet"))
    logger.info(
        f"[일간보고] 완료 {len(ok_results)}개(점검 {len(ok_results) - quiet_n}·변화없음 {quiet_n}) "
        f"· 실패 {failed_n}개 · 미처리 {len(skipped)}개"
    )
    # 각 프로젝트 요약을 게시판 글로 올린다 — 제목은 PM이 뽑은 눈길 끄는 헤드라인.
    # ★ 실패/빈 결과(headless 한도 등)는 글로 올리지 않는다 — '(PM 응답 없음)' 쓰레기 글 방지.
    # ★ 변화없음(quiet)도 글로 안 올린다 — '작업 내용 없음' 글 18개가 게시판을 덮는 것 방지.
    for r in ok_results:
        if r.get("quiet"):
            continue
        # 제목에 프로젝트명 접두어를 안 붙인다 — 작성자가 메타줄(조회수 옆)에 따로 표시됨
        title = r.get("headline") or (r.get("summary") or "").splitlines()[0][:35]
        board_db.add_post(
            author=r["name"], title=title,
            body=r.get("summary", ""), project=r.get("path"), day=date,
        )
    telegram_text = _assemble_telegram(date, ok_results, skipped)
    sent = False
    if notify:
        from src.bot.telegram_bot import send_telegram_sync

        sent = send_telegram_sync(telegram_text)
    return {"date": date, "completed": len(ok_results), "failed": failed_n, "skipped": skipped,
            "telegram_sent": sent, "telegram_preview": telegram_text, "results": ok_results}


def _assemble_telegram(date: str, results: list[dict], skipped: list[str]) -> str:
    """직후 종합 1회 텔레그램 본문 — 헤드라인 3줄 + 프로젝트별 요약 + 변화없음 묶음 + 미처리."""
    active = [r for r in results if not r.get("quiet")]
    quiet = [r for r in results if r.get("quiet")]
    lines = [f"<b>ohmyPM 일간보고 {date}</b>"]
    # 헤드라인: 요약 첫 줄이 있는 프로젝트 상위 3개
    heads = [r for r in active if r.get("summary") and "요약 없음" not in r["summary"]][:3]
    if heads:
        lines.append("")
        for r in heads:
            first = r["summary"].splitlines()[0][:120]
            lines.append(f"• <b>{r['name']}</b> — {first}")
    if active:
        lines.append("")
        lines.append("─────")
        for r in sorted(active, key=lambda x: x["name"].lower()):
            lines.append(f"<b>{r['name']}</b>\n{r.get('summary', '')}")
    if quiet:
        lines.append("─────")
        names = ", ".join(sorted(r["name"] for r in quiet))
        lines.append(f"[변화 없음] {len(quiet)}개: {names}")
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
            model=agents_db.model_for(p["path"]),
        )
        own = own_post_ids.get(p["path"])
        if out is not None:
            # 담당이 게시판 전체를 읽었다 = 자기 글 빼고 조회수 +1 (인센티브 조회 카운팅)
            for post in posts:
                if post["id"] != own:
                    board_db.increment_views(post["id"])
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
            model=agents_db.model_for(post["project"]),
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


def run_reply_followup(paths: list[str] | None = None, deadline_ts: float | None = None) -> dict:
    """대대댓글(선택) — 글쓴이의 대댓글을 받은 담당이 **덧붙일 말이 있을 때만** 한 번 더 답한다.

    규칙(사용자 확정 2026-09-03): 댓글이 달리면 글쓴이 대댓글은 필수(run_post_feedback),
    그 대댓글에 대한 원 댓글 작성자의 대대댓글은 선택. 담당당 headless 1콜(자기 스레드 묶음).
    오늘 글만 대상 + 이미 대대댓글 단 스레드는 제외(재실행돼도 중복 안 생김).
    """
    from src.scan.discover import discover_projects

    date = datetime.now().strftime("%Y-%m-%d")
    posts = [p for p in board_db.list_posts(board_db.DAILY_BOARD) if p.get("day") == date]
    if not posts:
        return {"replied": 0, "note": "오늘 글 없음"}

    # 담당 이름 → 프로젝트 path (보상으로 개명했을 수 있어 프로필 이름 우선)
    projects = discover_projects()
    if paths:
        wanted = set(paths)
        projects = [p for p in projects if p["path"] in wanted]
    path_by_name: dict[str, str] = {}
    for p in projects:
        prof = agents_db.get_profile(p["path"]) or {}
        path_by_name[prof.get("name") or p["name"]] = p["path"]

    # 글쓴이의 대댓글을 '원 댓글 작성자(담당)'별로 모은다
    threads_by_agent: dict[str, list[str]] = {}
    post_of_reply: dict[int, int] = {}          # 대댓글 id → 글 id (대대댓글 달 위치)
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
            # 이미 대대댓글이 달린 스레드는 제외(중복 방지)
            if any(c.get("parent_id") == r["id"] for c in cmts):
                continue
            agent = parent["author"]
            threads_by_agent.setdefault(agent, []).append(
                f"[대댓글#{r['id']}] 글 '{(post['title'] or '')[:60]}'\n"
                f"  내 댓글: {(parent['body'] or '')[:200]}\n"
                f"  글쓴이({post['author']}) 답글: {(r['body'] or '')[:200]}"
            )
            post_of_reply[r["id"]] = post["id"]
            valid_by_agent.setdefault(agent, set()).add(r["id"])

    allowed, disallowed = tools_for("daily_agent")
    replied = 0
    for agent, threads in threads_by_agent.items():
        if deadline_ts and time.time() > deadline_ts:
            break
        path = path_by_name[agent]
        out = run_headless(
            prompt=agents_db.persona_prefix(path) + comment_followup(agent, path, "\n\n".join(threads)),
            cwd=_neutral_cwd(),
            allowed_tools=allowed, disallowed_tools=disallowed,
            timeout=BOARD_TIMEOUT, append_system_prompt=FOLLOWUP_SYSTEM,
            add_dirs=[path], model=agents_db.model_for(path),
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
                rid = int(it["reply_id"])
            except (KeyError, ValueError, TypeError):
                continue
            body = (it.get("comment") or "").strip()
            if rid not in valid_by_agent.get(agent, set()) or not body or body.lower() == "null":
                continue
            board_db.add_comment(post_of_reply[rid], agent, body, parent_id=rid)
            replied += 1
    logger.info(f"[대대댓글] {replied}건")
    return {"replied": replied}


def run_nightly() -> dict:
    """01:00 cron 진입점 — 총괄 관리자가 지휘하는 하루.

    ① 관리자 아침 계획(저널+현황→프로젝트별 지침) ② 일간보고(지침 주입, 병렬, 소프트마감 03시)
    ③ 게시판 토론 ④ 글쓴이 반응 ⑤ 문서 재가공(받은 조언을 자기 docs에, git 커밋·push 안 함)
    ⑥ 보상 처리 ⑦ 관리자 저녁 종합(저널 갱신) → 요약 저장(07시 발송).
    """
    from src.cc import manager
    from src.cc.reprocess import run_reprocess
    from src.cc.rewards import run_rewards
    from src.db import alerts as alerts_db
    from src.scan.discover import discover_projects

    now = datetime.now()
    date = now.strftime("%Y-%m-%d")

    def _at(hour: int) -> float:
        return now.replace(hour=hour, minute=0, second=0, microsecond=0).timestamp()

    projects = discover_projects()
    # ⓪ 관리 계약 파일(status.md·pending.md) 없는 프로젝트는 골격부터 만든다 —
    #    프로젝트를 처음 들일 때 관리 구조를 깔아두는 건 ohmyPM 책임(2026-09-05 사용자 확정).
    #    새로 발견된 프로젝트는 첫 야간에 자동으로 이 단계를 거치고, 그다음 스캔부터 칸반이 찬다.
    from pathlib import Path

    from src.cc.harness_audit import run_harness_audit

    #    git 저장소인 폴더만 — 감사 커밋(롤백 단위)이 가능해야 파일 생성이 안전하다.
    #    비git 폴더는 발견·표시만 되고, 사용자가 git init하거나 제외할 때까지 건드리지 않는다.
    need_skeleton = [
        p["path"] for p in projects
        if (Path(p["path"]) / ".git").exists()
        and not ((Path(p["path"]) / "docs" / "status.md").exists()
                 and (Path(p["path"]) / "docs" / "pending.md").exists())
    ]
    skeleton = run_harness_audit(paths=need_skeleton) if need_skeleton else {"audited": 0}
    guidance = manager.plan_day(projects)                        # ① 아침 계획
    report = run_daily_report(deadline_ts=_at(settings.daily_soft_deadline_hour),
                              notify=False, guidance_by_path=guidance)   # ②
    # ★ 대량 실패 가드 — 무응답(사용량/속도 한도 등)으로 성공 0이면 하위 단계를 통째로 건너뛴다.
    #   (안 그러면 빈 게시판 글·헛 재가공 커밋·헛 보상까지 이어져 쓰레기가 번진다 — 09-01 사고)
    attempted = report.get("completed", 0) + report.get("failed", 0)
    if attempted and report.get("completed", 0) == 0:
        msg = (f"일간보고 실패 — {report.get('failed', 0)}개 전부 무응답(사용량/속도 한도 추정). "
               "하위 단계(게시판·재가공·보상·종합) 건너뜀. 로그의 [headless] 종료코드 확인 후 재시도.")
        logger.error(f"[일간보고] {msg}")
        alerts_db.set_setting(f"daily_summary:{date}", f"<b>ohmyPM {date}</b>\n{msg}")
        return {"report": report, "aborted": True, "reason": msg}
    # ★ 게시판 토론·반응은 '변화 있던' 프로젝트 담당만 — 조용한 프로젝트 담당까지 부르면
    #   콜 수가 도로 프로젝트 수만큼 늘어 절약이 무의미해진다. (재가공은 글 있는 프로젝트만이라 자동 제외)
    active_paths = [r["path"] for r in report.get("results", []) if not r.get("quiet")]
    if active_paths:
        board = run_board_discussion(paths=active_paths,
                                     deadline_ts=_at(settings.discussion_until_hour))    # ③
        feedback = run_post_feedback(paths=active_paths,
                                     deadline_ts=_at(settings.discussion_until_hour))    # ④ 대댓글 필수
        followup = run_reply_followup(paths=active_paths,
                                      deadline_ts=_at(settings.discussion_until_hour))   # ④b 대대댓글 선택
    else:
        board = {"commented": 0, "note": "변화 있는 프로젝트 없음"}
        feedback = {"reacted": 0}
        followup = {"replied": 0}
    reprocess = run_reprocess()                                   # ⑤ 문서 재가공(docs 커밋·push 안 함)
    rewards = run_rewards()                                       # ⑥ 보상
    synthesis = manager.close_day(date, report.get("results", []))   # ⑦ 저녁 종합
    # 아침 발송용 요약 = 관리자 종합(없으면 기본 텔레그램 텍스트)
    alerts_db.set_setting(f"daily_summary:{date}", synthesis or report.get("telegram_preview", ""))
    return {"report": report, "board": board, "feedback": feedback, "followup": followup,
            "reprocess": reprocess, "rewards": rewards, "skeleton": skeleton,
            "synthesis_chars": len(synthesis or "")}


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
