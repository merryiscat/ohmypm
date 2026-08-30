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
from src.cc.prompts import PM_SYSTEM, ROOM_SYSTEM, daily_agent_answer, pm_turn
from src.cc.room_agent import _neutral_cwd
from src.db import issues as issues_db
from src.db import messages as messages_db
from src.db import projects as projects_db

DAILY_ROOM = "daily"          # PM 전용 방(따로) — 사이드바 '일간보고'가 이 방을 본다
MAX_ROUNDS = 8                # 담당당 최대 왕복(안전 상한)
CONCURRENCY = 6              # 동시 진행 프로젝트 수(headless 병렬)
PM_TIMEOUT = 150
AGENT_TIMEOUT = 200
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)   # PM 응답에서 첫 JSON 객체 추출


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
    """PM 응답에서 {ask,done,summary} 추출. 실패하면 done 처리(무한루프 방지)."""
    if not result:
        return {"ask": None, "done": True, "summary": "(PM 응답 없음)"}
    m = _OBJ_RE.search(result)
    if not m:
        return {"ask": None, "done": True, "summary": result.strip()[:300]}
    try:
        d = json.loads(m.group(0))
        return {
            "ask": d.get("ask"),
            "done": bool(d.get("done")),
            "summary": (d.get("summary") or "").strip(),
        }
    except json.JSONDecodeError:
        return {"ask": None, "done": True, "summary": result.strip()[:300]}


def _pm_call(name: str, facts: str, history: str) -> dict:
    r = run_headless(
        prompt=pm_turn(name, facts, history),
        cwd=_neutral_cwd(),
        allowed_tools=tools_for("daily_pm")[0],
        disallowed_tools=tools_for("daily_pm")[1],
        timeout=PM_TIMEOUT,
        append_system_prompt=PM_SYSTEM,
    )
    return _parse_pm(r)


def _agent_call(name: str, path: str, question: str, history: str) -> str:
    r = run_headless(
        prompt=daily_agent_answer(name, path, question, history),
        cwd=_neutral_cwd(),
        allowed_tools=tools_for("daily_agent")[0],
        disallowed_tools=tools_for("daily_agent")[1],
        timeout=AGENT_TIMEOUT,
        append_system_prompt=ROOM_SYSTEM,
        add_dirs=[path],
    )
    return (r or "").strip() or "(담당 응답 없음)"


def report_one_project(path: str, name: str, max_rounds: int = MAX_ROUNDS) -> dict:
    """한 프로젝트의 PM↔담당 1:1 일간 점검. PM 전용 방에 대화 저장. 결과 dict 반환."""
    facts = build_facts(path)
    turns: list[tuple[str, str]] = []   # (PM 질문, 담당 답)
    summary = ""
    rounds = 0
    for rounds in range(1, max_rounds + 1):
        hist = "\n".join(f"PM: {q}\n담당: {a}" for q, a in turns)
        pm = _pm_call(name, facts, hist)
        summary = pm["summary"] or summary
        # PM 발화 저장(요약 + 질문)
        pm_body = summary + (f"\n▸ 담당에게: {pm['ask']}" if pm["ask"] and not pm["done"] else "")
        messages_db.add_message(DAILY_ROOM, "pm", f"[{name}] {pm_body}".strip())
        if pm["done"] or not pm["ask"]:
            break
        ans = _agent_call(name, path, pm["ask"], hist)
        messages_db.add_message(DAILY_ROOM, name, ans)
        turns.append((pm["ask"], ans))
    return {"name": name, "path": path, "rounds": rounds, "summary": summary or "(요약 없음)",
            "skipped": False}


def run_daily_report(
    paths: list[str] | None = None,
    max_rounds: int = MAX_ROUNDS,
    concurrency: int = CONCURRENCY,
    deadline_ts: float | None = None,
    notify: bool = True,
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
    messages_db.add_message(DAILY_ROOM, "pm", f"━━ {date} 일간보고 시작 (대상 {len(projects)}개) ━━")

    done_results: list[dict] = []
    skipped: list[str] = []

    def worker(p: dict) -> dict:
        if deadline_ts and time.time() > deadline_ts:
            return {"name": p["name"], "path": p["path"], "skipped": True}
        try:
            return report_one_project(p["path"], p["name"], max_rounds)
        except Exception as e:  # 한 프로젝트 실패가 전체를 안 멈춤
            logger.warning(f"[일간보고] {p['name']} 실패: {e}")
            return {"name": p["name"], "path": p["path"], "skipped": False,
                    "summary": f"(점검 실패: {e})", "rounds": 0}

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        for res in ex.map(worker, projects):
            (skipped.append(res["name"]) if res.get("skipped") else done_results.append(res))

    logger.info(f"[일간보고] 완료 {len(done_results)}개 · 미처리 {len(skipped)}개")
    telegram_text = _assemble_telegram(date, done_results, skipped)
    messages_db.add_message(DAILY_ROOM, "pm", f"━━ {date} 일간보고 종료 (완료 {len(done_results)}·미처리 {len(skipped)}) ━━")
    sent = False
    if notify:
        from src.bot.telegram_bot import send_telegram_sync

        sent = send_telegram_sync(telegram_text)
    return {"date": date, "completed": len(done_results), "skipped": skipped,
            "telegram_sent": sent, "telegram_preview": telegram_text}


def _assemble_telegram(date: str, results: list[dict], skipped: list[str]) -> str:
    """직후 종합 1회 텔레그램 본문 — 헤드라인 3줄 + 프로젝트별 요약 + 미처리."""
    lines = [f"<b>📋 ohmyPM 일간보고 {date}</b>"]
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
        lines.append(f"⚠ 미처리 {len(skipped)}개(마감 초과): {', '.join(skipped)}")
    return "\n".join(lines)
