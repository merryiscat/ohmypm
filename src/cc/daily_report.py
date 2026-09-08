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
    BOARD_WRITE_SYSTEM,
    FEEDBACK_SYSTEM,
    FOLLOWUP_SYSTEM,
    MANAGE_SYSTEM,
    PM_SYSTEM,
    ROOM_SYSTEM,
    board_comment,
    board_write,
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


def _apply_updates(updates: list, valid_ids: set[int], path: str = "", date: str = "") -> int:
    """PM이 낸 칸반 상태·기한 갱신 + 당일 완결 등재를 이슈 DB에 반영. 반영 건수 반환."""
    n = 0
    for u in updates:
        # 당일 완결 등재({"done": "..."}) — 칸반을 거치지 않고 끝난 일의 흔적(2026-09-07)
        done = (u.get("done") or "").strip() if isinstance(u, dict) else ""
        if done and path and date:
            issues_db.add_done(path, done[:120], date)
            n += 1
            continue
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
        # ★ headless가 실패(None)했고 아직 대화가 없으면 = 그냥 못 돈 것. 게시판에 빈 글은 안 만들되
        #   (09-01 사고 항체), 일간보고 방에는 실패 한 줄을 남긴다 — 안 그러면 그날 목록에서
        #   프로젝트가 통째로 사라져 '조용한 실패'가 된다(09-06 naverblog 미표시 실증).
        if pm.get("failed") and not turns:
            messages_db.add_message(room, "pm",
                                    "(사용량 한도·오류로 오늘 점검을 시작하지 못함 — 리셋 후 재개 예정)")
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
    applied = _apply_updates(_manage_call(name, issue_list, transcript), valid_ids, path, date)
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

    # ★ 시작 시점에 이미 소프트 마감이 지났으면 마감을 없앤다(2026-09-09) — 늦게 시작한
    #   배치(재부팅으로 03시를 놓쳐 05시에 수동 실행 등)가 전 프로젝트를 '마감 초과'로
    #   건너뛰어 통째로 헛도는 것을 막는다. 게시판 단계엔 이미 같은 보호가 있었다.
    if deadline_ts and time.time() > deadline_ts:
        logger.info("[일간보고] 시작 시점에 소프트 마감이 이미 지남 — 마감 없이 진행")
        deadline_ts = None

    done_results: list[dict] = []
    skipped: list[str] = []
    skipped_paths: list[str] = []

    def worker(p: dict) -> dict:
        if deadline_ts and time.time() > deadline_ts:
            # 미처리도 방에 흔적을 남긴다 — 그날 목록에서 사라지는 '조용한 실패' 방지
            messages_db.add_message(_daily_room(date, p["path"]), "pm",
                                    "(마감 초과로 오늘 순서가 오지 않음 — 재개 때 다시 시도)")
            return {"name": p["name"], "path": p["path"], "skipped": True}
        try:
            # ★ 1일안식 보상 — 오늘 안식 중인 담당은 LLM 콜 없이 쉰다(성장 엔진 C층 보상 실효과).
            if agents_db.rested_today(p["path"]):
                messages_db.add_message(_daily_room(date, p["path"]), "pm",
                                        "(1일안식 — 오늘은 보상으로 일간보고를 쉽니다)")
                return {"name": p["name"], "path": p["path"], "skipped": False, "quiet": True,
                        "rounds": 0, "summary": "1일안식(보상)", "headline": "", "updates_applied": 0}
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
            messages_db.add_message(_daily_room(date, p["path"]), "pm", f"(점검 중 오류: {e})")
            return {"name": p["name"], "path": p["path"], "skipped": False,
                    "summary": f"(점검 실패: {e})", "rounds": 0}

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        for res in ex.map(worker, projects):
            if res.get("skipped"):
                skipped.append(res["name"])
                skipped_paths.append(res["path"])
            else:
                done_results.append(res)

    ok_results = [r for r in done_results if not _is_failed(r)]
    failed_n = len(done_results) - len(ok_results)
    quiet_n = sum(1 for r in ok_results if r.get("quiet"))
    logger.info(
        f"[일간보고] 완료 {len(ok_results)}개(점검 {len(ok_results) - quiet_n}·변화없음 {quiet_n}) "
        f"· 실패 {failed_n}개 · 미처리 {len(skipped)}개"
    )
    # ★ 일간보고 요약의 게시판 자동 게시는 폐지(2026-09-06 사용자 확정) — 일간보고는 일간보고
    #   탭 안에서 끝낸다. 게시판 글은 run_board_posts에서 담당이 직접 쓴다(창작물).
    telegram_text = _assemble_telegram(date, ok_results, skipped)
    sent = False
    if notify:
        from src.bot.telegram_bot import send_telegram_sync

        sent = send_telegram_sync(telegram_text)
    return {"date": date, "completed": len(ok_results), "failed": failed_n, "skipped": skipped,
            "telegram_sent": sent, "telegram_preview": telegram_text, "results": ok_results,
            # 한도 재개용 — 실패(무응답 포함)·마감초과 프로젝트의 경로(재실행 대상)
            "failed_paths": [r["path"] for r in done_results if _is_failed(r)],
            "skipped_paths": skipped_paths}


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


# ── 게시판 (2026-09-06 사용자 확정 재설계) ─────────────────────────────────
# 글 = 담당의 창작물(일간보고 요약 게시 폐지). 둘러보기 = 제목 보고 끌리는 글만 열고(조회수),
# 내용이 마음에 들면 댓글. 글쓴이 대댓글 필수 · 대대댓글 선택. 조언은 다음 단계서 실제 반영.
BOARD_TIMEOUT = 150


def _author_of(path: str, fallback: str) -> str:
    """게시판 활동의 작성자 이름 — 보상으로 얻은 프로필 이름 우선(점수 집계 키와 일치)."""
    prof = agents_db.get_profile(path) or {}
    return prof.get("name") or fallback


def run_board_posts(paths: list[str] | None = None, deadline_ts: float | None = None) -> dict:
    """게시판 글쓰기 — 각 담당이 자기 프로젝트에서 글감을 **스스로 골라** 글을 쓴다(0~1편).

    조회·좋아요가 점수(보상)가 되는 유인 구조라, 뭐가 잘 읽힐지도 담당이 판단한다.
    담당당 headless 1콜. 억지 글 방지: 쓸 게 없으면 빈 배열 허용.
    """
    from src.scan.discover import discover_projects

    date = datetime.now().strftime("%Y-%m-%d")
    projects = discover_projects()
    if paths:
        wanted = set(paths)
        projects = [p for p in projects if p["path"] in wanted]
    allowed, disallowed = tools_for("daily_agent")
    posted = 0
    for p in projects:
        if deadline_ts and time.time() > deadline_ts:
            break
        out = run_headless(
            prompt=agents_db.persona_prefix(p["path"]) + board_write(p["name"], p["path"]),
            cwd=_neutral_cwd(),
            allowed_tools=allowed, disallowed_tools=disallowed,
            timeout=BOARD_TIMEOUT, append_system_prompt=BOARD_WRITE_SYSTEM,
            add_dirs=[p["path"]], model=agents_db.model_for(p["path"]),
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
        for it in (items if isinstance(items, list) else [])[:1]:   # 최대 1편
            title = (it.get("title") or "").strip()
            body = (it.get("body") or "").strip()
            if title and body:
                board_db.add_post(author=_author_of(p["path"], p["name"]), title=title[:80],
                                  body=body, project=p["path"], day=date)
                posted += 1
    logger.info(f"[게시판 글쓰기] {posted}편")
    return {"posted": posted}


MAX_COMMENTS_PER_AGENT = 2   # 한 담당이 하룻밤 다는 댓글 상한(공감 홍수 방지, 09-07 재설계)


def _parse_board_response(result: str | None,
                          valid_ids: set[int]) -> tuple[set[int], set[int], list[dict]]:
    """둘러보기 응답에서 {opened, liked, comments}를 추출. 실패는 (빈, 빈, 빈).

    liked·댓글 단 글은 opened에 없어도 연 것으로 친다(반응 = 읽었다는 신호).
    댓글은 상한(MAX_COMMENTS_PER_AGENT)까지만.
    """
    if not result:
        return set(), set(), []
    m = _OBJ_RE.search(result)
    if not m:
        return set(), set(), []
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return set(), set(), []

    def _ids(key: str) -> set[int]:
        out: set[int] = set()
        for x in d.get(key) or []:
            try:
                if int(x) in valid_ids:
                    out.add(int(x))
            except (ValueError, TypeError):
                continue
        return out

    opened = _ids("opened")
    liked = _ids("liked")
    opened |= liked                     # 좋아요 = 읽었다는 신호
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
    return opened, liked, comments[:MAX_COMMENTS_PER_AGENT]


def run_board_discussion(paths: list[str] | None = None, deadline_ts: float | None = None) -> dict:
    """게시판 둘러보기 — 각 담당이 제목을 훑고 **끌리는 글만 열어**(조회수 +1) 마음에 들면 댓글.

    담당당 headless 1콜. 연 글만 조회수가 오른다 — 조회수가 진짜 '읽힘' 신호가 되게.
    자기 글은 열람·댓글 제외. 마감(deadline_ts) 넘겨 시작하는 담당은 스킵.
    """
    from src.scan.discover import discover_projects

    posts = board_db.list_posts(board_db.DAILY_BOARD)
    if not posts:
        return {"commented": 0, "note": "게시판에 글 없음"}
    valid_ids = {p["id"] for p in posts}
    board_text = "\n\n".join(
        f"글#{p['id']} [{p['title']}] (작성자 {p['author']})\n({(p['body'] or '')[:400]})"
        for p in posts
    )
    own_post_ids = {p["project"]: p["id"] for p in posts if p.get("project")}

    projects = discover_projects()
    if paths:
        wanted = set(paths)
        projects = [p for p in projects if p["path"] in wanted]
    allowed, disallowed = tools_for("daily_agent")

    commented = 0
    liked_n = 0
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
        opened, liked, cmts = _parse_board_response(out, valid_ids)
        for pid in opened:
            if pid != own:                # 자기 글 조회는 점수에 안 친다
                board_db.increment_views(pid)
        for pid in liked:
            if pid != own:                # 좋아요 = 값싸고 주력인 투표 신호
                board_db.like_post(pid)
                liked_n += 1
        for it in cmts:
            if it["post_id"] == own:      # 자기 글엔 안 단다
                continue
            board_db.add_comment(it["post_id"], _author_of(p["path"], p["name"]), it["comment"])
            commented += 1
    logger.info(f"[게시판] 좋아요 {liked_n}개 · 댓글 {commented}개")
    return {"commented": commented, "liked": liked_n}


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
        # 이미 글쓴이 답글이 달린 댓글은 제외 — 매일 재실행돼도 중복 반응·중복 답글이 안 쌓이게
        replied = {c.get("parent_id") for c in post.get("comments", [])
                   if c["author"] == post["author"] and c.get("parent_id")}
        top = [c for c in top if c["id"] not in replied]
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
    # ⓪ 신규 편입 검토(2026-09-06 사용자 확정: "처음 등록된 프로젝트는 PM-하네스 전문가 검토 방식")
    #    계약 파일(status.md·pending.md) 없는 프로젝트는 **쓰기 없이** PM+전문가 검토 리포트만 낸다
    #    (분류·시크릿은 코드가 결정론 판정해 주입 — 전문가 자문 P0). 골격 생성은 사용자가 리포트를
    #    보고 룸의 '골격 생성' 버튼으로 승인할 때만. 검토는 프로젝트당 1회(마커)·밤당 상한.
    from pathlib import Path

    from src.cc.onboarding import review_project

    REVIEWS_PER_NIGHT = 6
    unreviewed = [
        p for p in projects
        if not ((Path(p["path"]) / "docs" / "status.md").exists()
                and (Path(p["path"]) / "docs" / "pending.md").exists())
        and not alerts_db.get_setting(f"onboard_reviewed:{p['path']}")
    ]
    todo, deferred = unreviewed[:REVIEWS_PER_NIGHT], unreviewed[REVIEWS_PER_NIGHT:]
    for p in todo:
        try:
            # 검토 리포트는 담당 방에만 — 게시판은 담당 창작 글 전용(운영 리포트 게시 안 함).
            # ★ 성공했을 때만 완료 마커 — 실패(한도 등)가 '검토됨'으로 남던 버그 수정(09-06 새벽 실증)
            if review_project(p["path"], p["name"]):
                alerts_db.set_setting(f"onboard_reviewed:{p['path']}", date)
        except Exception as e:
            logger.warning(f"[신규검토] {p['name']} 실패: {e}")
    if deferred:
        logger.info(f"[신규검토] 오늘 {len(todo)}개 검토, {len(deferred)}개는 다음 밤으로 이월")
    # ⓪b 골격 자동 생성(2026-09-06 사용자 확정 "버튼 없이 무조건 배치로만") —
    #    검토 리포트가 나온 지 **하루 이상 지난** 프로젝트만 자동 생성. 그 사이 사용자가
    #    리포트를 보고 x(제외)하면 자연히 빠진다(하루의 암묵 승인 창). '내 프로젝트' 분류만 —
    #    외부 클론·보관용·비git엔 영원히 안 쓴다.
    from src.cc.harness_audit import run_harness_audit
    from src.cc.onboarding import project_meta

    gen_paths = []
    for p in projects:
        if (Path(p["path"]) / "docs" / "status.md").exists() \
                and (Path(p["path"]) / "docs" / "pending.md").exists():
            continue   # 이미 계약 파일 있음
        mark = alerts_db.get_setting(f"onboard_reviewed:{p['path']}")
        if not mark or mark >= date:
            continue   # 미검토거나 오늘 막 검토됨 — 리포트 열람 여유 하루
        if project_meta(p["path"])["cls"] != "mine":
            continue   # 내 저장소만 자동 생성
        gen_paths.append(p["path"])
    generated = run_harness_audit(paths=gen_paths) if gen_paths else {"audited": 0}
    skeleton = {"reviewed": len(todo), "deferred": len(deferred),
                "generated": generated.get("audited", 0)}
    # ⓪c 기록 정리(2026-09-08 사용자 지시) — **보고 전에** 각 담당이 자기 기록을 실제 작업과
    #    맞추고 docs를 커밋한다. 어긋난 기록 위에서 보고가 돌면 총괄이 틀린 전제로 묻고,
    #    담당이 매번 대화로 정정해야 했다(09-08 youtube_ssalmuk 실증).
    #    정리 뒤 재스캔까지 해야 이슈 테이블이 따라온다 — 안 그러면 PM이 옛 이슈를 본다.
    from src.cc.tidy import run_tidy
    from src.scan import run_scan

    tidied = run_tidy()
    run_scan()
    guidance = manager.plan_day(projects)                        # ① 아침 계획
    report = run_daily_report(deadline_ts=_at(settings.daily_soft_deadline_hour),
                              notify=False, guidance_by_path=guidance)   # ②
    # ★ 한도 재개(2026-09-06 사용자 확정: "3시에 남은 양 소진하고, 리셋되면 마저 해") —
    #   한도(429)로 실패·미처리가 남았고 리셋 시각이 감지됐으면, 그때까지 기다렸다가 이어 돈다.
    from src.cc import client as cc_client

    resume_paths = (report.get("failed_paths") or []) + (report.get("skipped_paths") or [])
    reset_at = cc_client.limit_reset_at()
    if resume_paths and reset_at:
        wait = min(max(reset_at - time.time(), 0) + 120, 6 * 3600)   # 리셋 +2분 버퍼, 최대 6시간
        logger.info(f"[야간] 한도 소진 — 남은 {len(resume_paths)}개, {wait / 60:.0f}분 뒤 리셋에 재개")
        time.sleep(wait)
        cc_client.clear_limit()
        r2 = run_daily_report(paths=resume_paths, notify=False,
                              guidance_by_path=guidance, deadline_ts=None)
        report["results"] = report.get("results", []) + r2.get("results", [])
        report["completed"] = report.get("completed", 0) + r2.get("completed", 0)
        report["failed"] = r2.get("failed", 0)
        report["skipped"] = r2.get("skipped", [])
        report["telegram_preview"] = _assemble_telegram(date, report["results"], r2.get("skipped", []))
        logger.info(f"[야간] 재개 완료 — 추가 {r2.get('completed', 0)}개, 잔여 실패 {report['failed']}개")
    # ★ 대량 실패 가드 — 무응답(사용량/속도 한도 등)으로 성공 0이면 하위 단계를 통째로 건너뛴다.
    #   (안 그러면 빈 게시판 글·헛 재가공 커밋·헛 보상까지 이어져 쓰레기가 번진다 — 09-01 사고)
    attempted = report.get("completed", 0) + report.get("failed", 0)
    if attempted and report.get("completed", 0) == 0:
        msg = (f"일간보고 실패 — {report.get('failed', 0)}개 전부 무응답(사용량/속도 한도 추정). "
               "하위 단계(게시판·재가공·보상·종합) 건너뜀. 로그의 [headless] 종료코드 확인 후 재시도.")
        logger.error(f"[일간보고] {msg}")
        alerts_db.set_setting(f"daily_summary:{date}", f"<b>ohmyPM {date}</b>\n{msg}")
        return {"report": report, "aborted": True, "reason": msg}
    # 글쓰기·둘러보기·반응 모두 **위키 있는 전 담당** 참여.
    #   글쓰기를 '변화 있던 담당'으로 좁혔더니 사용자가 자주 안 건드리는 프로젝트는 글을 쓸 일이
    #   영영 없었다(2026-09-08 사용자: "자주 안 만지면 게시판 글 올릴 일이 없잖아, 주제는 자유").
    #   → 전원에게 기회를 주고 쓸지 말지는 담당이 판단한다(억지 글은 프롬프트가 막는다).
    wiki_paths = [p["path"] for p in projects if p.get("has_wiki")]
    # 재개로 새벽 마감(4시)을 이미 넘겼으면 마감 없이 진행 — 사용량이 리셋 직후라 여유가 있다
    disc_deadline: float | None = _at(settings.discussion_until_hour)
    if time.time() > disc_deadline:
        disc_deadline = None
    posts_res = run_board_posts(paths=wiki_paths, deadline_ts=disc_deadline) \
        if wiki_paths else {"posted": 0}                                             # ③a 글쓰기(창작)
    board = run_board_discussion(paths=wiki_paths, deadline_ts=disc_deadline)        # ③b 둘러보기·댓글
    feedback = run_post_feedback(paths=wiki_paths, deadline_ts=disc_deadline)        # ④ 대댓글 필수
    followup = run_reply_followup(paths=wiki_paths, deadline_ts=disc_deadline)       # ④b 대대댓글 선택
    # ★ 게시판 단계 한도 재개(2026-09-07 실증: 글 3편은 올라갔는데 둘러보기부터 429 전멸 —
    #   조회·댓글 0의 원인. 보고 단계만 감싸던 재개를 게시판 단계에도) — 전멸했을 때만 1회 재시도.
    reset_at2 = cc_client.limit_reset_at()
    if reset_at2 and board.get("commented", 0) == 0 and feedback.get("reacted", 0) == 0:
        wait = min(max(reset_at2 - time.time(), 0) + 120, 6 * 3600)
        logger.info(f"[야간] 게시판 단계 한도 소진 — {wait / 60:.0f}분 뒤 리셋에 재개")
        time.sleep(wait)
        cc_client.clear_limit()
        board = run_board_discussion(paths=wiki_paths, deadline_ts=None)
        feedback = run_post_feedback(paths=wiki_paths, deadline_ts=None)
        followup = run_reply_followup(paths=wiki_paths, deadline_ts=None)
    reprocess = run_reprocess()                                   # ⑤ 문서 재가공(docs 커밋·push 안 함)
    rewards = run_rewards()                                       # ⑥ 보상
    synthesis = manager.close_day(date, report.get("results", []))   # ⑦ 저녁 종합
    # 아침 발송용 요약 = 관리자 종합(없으면 기본 텔레그램 텍스트)
    alerts_db.set_setting(f"daily_summary:{date}", synthesis or report.get("telegram_preview", ""))
    # 재개 대기로 아침 발송 시각(07시)을 넘겨 끝났으면 즉시 발송 — 그날 07시 cron은 요약이
    # 아직 없어 빈손으로 지나갔으므로 중복 발송이 아니다.
    if time.time() > _at(settings.telegram_hour):
        send_daily_telegram(date)
    return {"report": report, "board_posts": posts_res, "board": board, "feedback": feedback,
            "followup": followup, "reprocess": reprocess, "rewards": rewards,
            "skeleton": skeleton, "tidy": tidied, "synthesis_chars": len(synthesis or "")}


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
