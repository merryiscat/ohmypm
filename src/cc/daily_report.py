"""주간보고 오케스트레이션 (비전 2·3단계) — 매주 토요일 새벽(2026-09-23 주간 전환).

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
from datetime import datetime, timedelta

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
    pm_turn,
    post_feedback,
)
from src.cc.room_agent import _neutral_cwd
from src.config.settings import settings
from src.db import agents as agents_db
from src.db import board as board_db
from src.db import issues as issues_db
from src.db import messages as messages_db
from src.proc import NO_WINDOW

DAILY_PREFIX = "daily::"       # 일간보고 대화 방 키: daily::{날짜}::{프로젝트path} (일자·프로젝트별 분리)


def _daily_room(date: str, path: str) -> str:
    return f"{DAILY_PREFIX}{date}::{path}"

MAX_ROUNDS = 8                # 담당당 최대 왕복(안전 상한)
# 동시 진행 프로젝트 수(headless 병렬). 6은 버스트 속도제한 트립(09-01) → 3으로 내렸고,
# 2026-09-11 PM 승인으로 3 → 2로 한 번 더 내렸다. 이유: 09-11 새벽 배치가 03:16(일간보고가
# 막 시작하는 지점)에서 통째로 멈췄고, 원인 후보 1순위가 시스템 메모리 부족이기 때문이다.
# claude 프로세스 하나가 메모리를 크게 먹어서 3개를 동시에 띄우면 이 PC가 못 버틴다는 가설.
# 확인 방법: 오늘 밤 2로 완주하면 원인은 메모리 부족 확정, 같은 지점에서 또 끊기면 다른 원인.
# ※ 이 값은 서버가 뜰 때 한 번 읽힌다 — 고친 뒤 서버를 재시작해야 새벽 배치에 실제로 반영된다
#   (2026-09-08에 이걸 잊어 배치가 통째로 죽었다. 자동 확인 장치는 src/scheduler.py 최상단 참조).
CONCURRENCY = 2
PM_TIMEOUT = 150
AGENT_TIMEOUT = 200
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)   # PM 응답에서 첫 JSON 객체 추출
_ARR_RE = re.compile(r"\[.*\]", re.DOTALL)   # 게시판 댓글 응답에서 JSON 배열 추출


def _cancelled(title: str) -> bool:
    return bool(re.search(r"~~.+~~", title or ""))


# 조용한 프로젝트(변화 없음)의 고정 요약 — LLM 없이 코드가 만든다.
QUIET_SUMMARY = "작업 내용 없음(지난 배치 이후 새 커밋·새 이슈 없음) — 점검 생략"


# 활동 신호에서 제외할 커밋 — 제목에 이 말이 들어간 커밋은 도구가 만든 것으로 본다(대소문자 무시).
#   ohmypm             : ohmyPM이 밤마다 스스로 남기는 커밋
#                        (재가공 '(ohmyPM 담당)'·하네스감사 '(ohmyPM)')
#   kickoff-workspaces : 작업 구조 배포(T-003)가 대상 프로젝트에 남기는 커밋. 2026-09-18 하루에
#                        23개 프로젝트에 찍힐 예정이었고, 그러면 다음 날 전 프로젝트가
#                        '활동 있음'으로 잡혀 점검 23회가 헛돌 판이었다.
# ★ 대소문자를 무시하는 이유: 종전 판정은 대문자 'ohmyPM' 글자 그대로만 찾아서, 커밋 제목을
#   소문자로 쓴 자동 커밋('chore: ohmypm ...')은 사람 커밋으로 새어 나갔다.
TOOL_COMMIT_MARKS = ("ohmypm", "kickoff-workspaces")

# PM 팩트·활동 판정에서 '열린 이슈'로 보는 칸반 상태 — 할일·진행중·내 차례.
# resolved(완료)·deferred(보류)·stale(소스에서 사라진 것)은 열린 것이 아니다.
OPEN_STATUSES = ("open", "consulting", "needs_user")
# 끝난·멈춘 상태 — 팩트에는 제목·기한 없이 개수만 넣는다(괄호 안은 PM에게 보여줄 우리말 이름).
CLOSED_STATUS_LABELS = (("resolved", "완료"), ("deferred", "보류"), ("stale", "지난 것"))


def _tool_commit(subject: str) -> bool:
    """커밋 제목이 도구가 만든 것인지 — 대소문자를 구분하지 않고 표식을 찾는다."""
    low = subject.lower()
    return any(mark in low for mark in TOOL_COMMIT_MARKS)


def _issue_activity(path: str, now: datetime) -> bool:
    """판정 창 안에 생긴 '사람이 문서를 고쳐서 생긴 이슈'가 있는지.

    창의 길이는 settings.activity_window_hours — 매일 돌던 시절의 24시간이 아니라,
    2026-09-23 주간 전환 뒤로는 168시간(7일)이다. 배치 주기보다 창이 좁으면
    그 사이에 한 작업이 '변화 없음'으로 걸러져 담당을 아예 안 부른다.

    ★ 2026-09-18 T-004. 그전엔 "창 안에 생긴 이슈가 하나라도 있으면 활동"이었는데,
      이슈가 생기는 길이 사람의 문서 수정만은 아니어서 두 가지로 오탐했다:
        ① 09-17 파서 변경 — 제목·fingerprint가 바뀌자 옛 안건이 '새 이슈'로 다시 등재돼
           09-18에 13개 프로젝트를 점검했다. 문서는 아무도 안 고쳤다.
        ② 일간보고 자신이 만드는 당일 완결 카드(source='daily_report') — 어제 점검이
           오늘 점검을 부르는 자기 되먹임이 된다.
      그래서 **원본 문서를 확인할 수 있는 스캔 이슈만** 활동으로 인정하고, 그 원본 파일의
      mtime까지 같은 창 안에 있을 때만 통과시킨다. 파서만 바뀐 재등재는 문서 mtime을
      건드리지 않으므로 여기서 걸러진다 — 스키마나 스캔 회차 기록을 늘리지 않고 되는 방법.

    판정 시각(now)은 호출부에서 한 번 받아 창의 양끝을 같은 기준으로 잡는다.
    창은 [now-activity_window_hours, now] 닫힌 구간 — mtime이 미래인 파일(시계 뒤틀림)은
    인정하지 않는다.
    """
    from pathlib import Path as _P

    lo = now - timedelta(hours=settings.activity_window_hours)
    # issues.created_at은 로컬시각 문자열(2026-09-10 UTC→로컬 통일) → 로컬 문자열로 비교.
    # 예전엔 저장이 UTC라 여기서만 UTC로 맞췄는데, 그 보정을 잊은 자리가 생기면 9시간 어긋난다.
    cutoff = lo.strftime("%Y-%m-%d %H:%M:%S")
    for i in issues_db.list_issues():
        if i["project"] != path or (i.get("created_at") or "") < cutoff:
            continue
        if i.get("verdict") == "drop" or (i.get("status") or "open") not in OPEN_STATUSES:
            continue
        src = (i.get("source") or "").strip()
        if src not in issues_db.SCANNED_SOURCES:
            continue   # 도구 출처('daily_report' 등)·출처 없음 — 대조할 원본 문서가 없다
        try:
            mtime = datetime.fromtimestamp((_P(path) / "docs" / src).stat().st_mtime)
        except OSError:
            continue   # 원본 파일이 없거나 못 읽음 — 확인 불가는 인정하지 않는다
        if lo <= mtime <= now:
            return True
    return False


def _has_activity(path: str) -> bool:
    """지난 배치 이후 '사람의 작업'이 있었는지 — 없으면 LLM을 아예 안 부른다(토큰 절약의 핵심).

    변화 없는 프로젝트도 매번 PM↔담당 인터뷰를 돌면, 지난번과 똑같은 보고를 같은
    토큰을 들여 재생산한다(2026-09-02 사용자 지적). 신호 두 가지로 변화를 판정한다:
      ① 판정 창 안의 git 커밋 — 단, 도구가 만든 커밋(TOOL_COMMIT_MARKS)은 제외.
      ② 판정 창 안의 새 이슈 중 원본 문서도 그 창 안에 고쳐진 것(_issue_activity).
    git 확인이 실패하면 True(모르면 점검하는 쪽 — 놓침0 원칙).

    ★ 창의 길이는 settings.activity_window_hours이고 **배치 주기와 묶여 있다**.
      2026-09-23에 배치를 매주 토요일로 바꾸면서 24시간 → 168시간(7일)으로 넓혔다.
      여기를 24로 두면 일요일~목요일에 한 작업이 전부 '변화 없음'이 된다.
    """
    from pathlib import Path as _P

    now = datetime.now()   # 판정 시각 — 커밋·문서 mtime을 같은 기준으로 본다
    if (_P(path) / ".git").exists():
        try:
            r = subprocess.run(
                ["git", "-C", path, "log",
                 f"--since={settings.activity_window_hours} hours ago", "--format=%s"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=NO_WINDOW,
            )
            if r.returncode != 0:
                return True  # git 조회 실패 — 모르면 점검하는 쪽으로
            if any(s.strip() and not _tool_commit(s) for s in r.stdout.splitlines()):
                return True  # 사람(또는 도구 아닌 다른 것)의 커밋이 있다
        except Exception:
            return True
    # 커밋 신호가 없어도(비git 폴더·도구 커밋만) 문서 수정으로 생긴 새 이슈는 활동이다
    return _issue_activity(path, now)


def _fact_rows(path: str) -> list[dict]:
    """팩트 집계 대상 — 이 프로젝트 이슈 중 drop·취소선만 뺀 전부(stale 포함).

    list_issues()는 기본 조회에서 stale을 빼므로 stale은 따로 한 번 더 읽는다.
    stale은 '지난 것' 개수로만 쓰이고 제목·기한은 어디에도 나가지 않는다.
    """
    rows = issues_db.list_issues() + issues_db.list_issues(status="stale")
    return [
        i for i in rows
        if i["project"] == path and i.get("verdict") != "drop" and not _cancelled(i["title"])
    ]


def build_facts(path: str) -> str:
    """결정론 현황(팩트) 문자열 — PM 프롬프트에 주입(환각 방지). issues DB에서 뽑는다.

    ★ 2026-09-18 T-004: **제목·기한은 열린 이슈만** 넣는다(할일·진행중·내 차례).
      그전엔 verdict=drop만 빼고 전부 넣어서, 이미 끝난 안건이 기한 목록에 그대로 남아
      PM이 매일 같은 것을 되물었다 — 사용자가 09-06에 "구글 권한 공개해뒀다"고 알려
      완료로 옮긴 건이 09-15 기한으로 매일 다시 주입됐다. 끝난·보류·지난 것은 개수만
      알려준다: PM이 '남은 게 이만큼'은 알되, 되물을 실마리(제목·날짜)는 못 얻게.
      drop(판정이 버린 것)은 개수에서도 빠진다.
    """
    rows = _fact_rows(path)
    items = [i for i in rows if (i.get("status") or "open") in OPEN_STATUSES]
    closed = " · ".join(
        f"{label} {sum(1 for i in rows if (i.get('status') or 'open') == status)}"
        for status, label in CLOSED_STATUS_LABELS
    )
    if not items:
        return f"열린 이슈 없음(조용한 프로젝트). 끝난·멈춘 것(개수만): {closed}"
    u = sum(1 for i in items if i["kind"] == "unresolved")
    d = sum(1 for i in items if i["kind"] == "deadline")
    st = {k: sum(1 for i in items if (i.get("status") or "open") == k) for k in OPEN_STATUSES}
    deadlines = sorted((i for i in items if i.get("due")), key=lambda i: i["due"])
    dl_txt = "\n".join(f"  - {i['due']} {i['title'][:80]}" for i in deadlines[:8]) or "  (없음)"
    top = "\n".join(f"  - [{i['kind']}] {i['title'][:90]}" for i in items[:12])
    return (
        f"열린 이슈 {len(items)}건 (미해결 {u}·기한 {d}) / 칸반 상태: 할일 {st['open']}·"
        f"진행중 {st['consulting']}·내 차례 {st['needs_user']}\n"
        f"끝난·멈춘 것(개수만 — 제목·기한은 주지 않는다): {closed}\n"
        f"임박/기한(열린 것만):\n{dl_txt}\n"
        f"열린 이슈 목록(일부):\n{top}"
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
    r = run_headless(task="daily_pm",
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
    r = run_headless(task="daily_manage",
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
        if st in ("open", "consulting", "resolved", "deferred", "needs_user"):
            issues_db.set_status(iid, st)
            n += 1
        if "due" in u:
            due = u.get("due")
            issues_db.set_due(iid, None if due in ("", "null", None) else due)
            n += 1
    return n


def _agent_call(name: str, path: str, question: str, history: str) -> str:
    # ★ 기록 자동 반영은 프로젝트별 스위치(2026-09-17 사용자 확정, 기본 끔). 꺼진 프로젝트의
    #   담당은 읽기만 하고 답한다 — 도구 자체를 빼서(Edit/Write 없음) 프롬프트가 아니라 층에서 막는다.
    from src.db import alerts as alerts_db

    writable = alerts_db.docs_autowrite(path)
    task = "daily_agent" if writable else "daily_pm"
    prompt = agents_db.persona_prefix(path) + daily_agent_answer(name, path, question, history)
    if not writable:
        prompt += ("\n\n[주의] 이 프로젝트는 '기록 자동 반영'이 꺼져 있다. 파일을 고치지 말고 "
                   "읽고 답만 하라. 고쳐야 할 것이 보이면 답에 '기록장에 반영 필요: …'로 적어라.")
    r = run_headless(task="daily_agent",
        prompt=prompt,
        cwd=_neutral_cwd(),
        allowed_tools=tools_for(task)[0],
        disallowed_tools=tools_for(task)[1],
        permission_mode="acceptEdits" if writable else "default",
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
    # ★ 사용자가 직접 한 말을 PM이 먼저 본다(2026-09-12 사용자 지적: "말한 게 다음으로 안 이어진다").
    #   칸반 카드가 배치가 읽는 상태이고 재스캔도 그 상태를 덮지 않는데, 사용자 발언은 카드를
    #   움직이지 못했다 — PM이 카드만 보고 사흘 내리 같은 질문을 다시 한 이유가 이것이다.
    #   PM에게 주면 PM이 대화 끝에 updates로 카드를 옮긴다(needs_user·resolved 등).
    from src.cc.reprocess import pending_user_says

    says, _ = pending_user_says(path)
    if says:
        facts = ("[사용자가 직접 한 말 — 담당의 보고보다 우선하는 사실이다.\n"
                 " 사용자가 '했다/해뒀다'고 한 항목은 다시 묻지 말고 updates로 완료 처리하라.\n"
                 " 사용자만 할 수 있는 일은 needs_user(내 차례) 칸으로 옮겨라]\n"
                 + says + "\n\n") + facts
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
    # 담당이 대화 중 고친 기록장을 나중에 커밋하려면 '고치기 전' 상태를 알아야 한다.
    #   (실행 전부터 더러웠던 파일 = 사용자 작업 중 → 커밋에 섞지 않는다)
    from src.cc.reprocess import _commit_changes, _dirty_files

    before_files = _dirty_files(path)
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
        # ★ 2026-09-18 T-004: 룸 피드 이중 저장 폐지. 09-04엔 일간보고를 룸 대화로 이으려고
        #   같은 발화를 프로젝트 방에도 넣었는데, 담당 방 패널이 매일 보고 사본으로 덮여
        #   사용자와 담당의 실제 대화가 묻혔다(사용자 지적). 보고는 일간 방에만 쌓고,
        #   룸 담당은 필요하면 reprocess.daily_transcript로 그날 방을 읽는다.
        if pm["done"] or not pm["ask"]:
            break
        ans = _agent_call(name, path, pm["ask"], hist)
        messages_db.add_message(room, "agent", ans)
        turns.append((pm["ask"], ans))
    # 대화 종료 후: PM이 칸반 상태·일정을 확정해 실제 반영(전용 관리 호출)
    transcript = "\n".join(f"PM: {q}\n담당: {a}" for q, a in turns) or summary
    applied = _apply_updates(_manage_call(name, issue_list, transcript), valid_ids, path, date)
    # 담당이 대화하면서 고친 기록장을 커밋한다 — docs/ 범위만, push 없음(2026-09-09).
    #   PM은 칸반(ohmyPM DB), 담당은 기록장(프로젝트 docs)으로 역할이 갈린다.
    new_docs = {f for f in (_dirty_files(path) - before_files) if f.startswith("docs/")}
    committed = False
    if new_docs:
        guard = before_files | ((_dirty_files(path) - before_files) - new_docs)
        res = _commit_changes(path, date, guard, msg=f"chore: {date} 일간보고 반영 (ohmyPM 담당)")
        committed = bool(res.get("committed"))
        if committed:
            logger.info(f"[일간보고] {name} 기록장 반영 커밋 {len(new_docs)}개 파일")
    return {"name": name, "path": path, "rounds": rounds, "summary": summary or "(요약 없음)",
            "headline": headline, "updates_applied": applied, "skipped": False,
            "docs_committed": committed}


def run_daily_report(
    paths: list[str] | None = None,
    max_rounds: int = MAX_ROUNDS,
    concurrency: int = CONCURRENCY,
    deadline_ts: float | None = None,
    guidance_by_path: dict[str, str] | None = None,
) -> dict:
    """전(또는 지정) 프로젝트 일간보고. 병렬 + 소프트 마감.

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
    return {"date": date, "completed": len(ok_results), "failed": failed_n, "skipped": skipped,
            "results": ok_results,
            # 한도 재개용 — 실패(무응답 포함)·마감초과 프로젝트의 경로(재실행 대상)
            "failed_paths": [r["path"] for r in done_results if _is_failed(r)],
            "skipped_paths": skipped_paths}


# ── 게시판 (2026-09-06 사용자 확정 재설계) ─────────────────────────────────
# 글 = 담당의 창작물(일간보고 요약 게시 폐지). 둘러보기 = 제목 보고 끌리는 글만 열고(조회수),
# 내용이 마음에 들면 댓글. 글쓴이 대댓글 필수 · 대대댓글 선택. 조언은 다음 단계서 실제 반영.
BOARD_TIMEOUT = 150


def _author_of(path: str, fallback: str) -> str:
    """게시판 활동의 작성자 이름 — 보상으로 얻은 프로필 이름 우선(점수 집계 키와 일치)."""
    prof = agents_db.get_profile(path) or {}
    return prof.get("name") or fallback


def _board_parallel(items: list, worker, label: str) -> list:
    """게시판 4단계 공통 실행기 — 담당(또는 글)별 headless 콜을 CONCURRENCY만큼 동시에 돌린다.

    ★ 2026-09-10: 네 단계가 전부 순차 `for` 루프라, 위키 25개면 단계당 25콜이 줄을 서서
      댓글이 몇 시간씩 밀렸다(09-09 실측: 06:07 글쓰기 시작 → 06:27 글 21편·댓글 1건).
      일간보고와 같은 병렬 방식으로 통일. DB는 스레드별 커넥션(커밋 d589f2b)이라 안전하고,
      담당은 각자 자기 프로젝트만 건드려 작업 디렉터리 충돌도 없다.

    한 담당의 예외가 단계 전체를 멈추지 않게 삼키고 로그만 남긴다(실패는 결과에서 빠짐).
    """
    def guarded(item):
        try:
            return worker(item)
        except Exception as e:
            logger.warning(f"[{label}] 항목 실패: {e}")
            return None

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        return [r for r in ex.map(guarded, items) if r is not None]


PAST_POSTS_DAYS = 30        # 재탕 금지 기간 — 30일 지난 이야기는 다시 써도 된다
PAST_POSTS_CAP = 30         # 프롬프트에 넣는 최대 편수(기간 안이라도 이 이상은 안 넣는다)


def _past_posts_text(project_path: str, posts: list[dict]) -> str:
    """이 담당이 최근 30일 올린 글 목록 — 글쓰기 프롬프트에 넣어 재탕을 막는다(2026-09-11).

    ★ 코드는 **알려주기만** 한다. 같은 글인지 판정하거나 저장을 막는 일은 하지 않는다
      (사용자 확정: 게시판은 코드 개입을 최소로 — 판단은 담당이, 심판은 독자의 좋아요·싫어요가).
      그전엔 자기가 뭘 썼는지 몰라서, 프로젝트에서 제일 재미있는 사건 하나를 제목만 바꿔
      사흘 내리 다시 쓰는 일이 24개 담당 중 최소 12개에서 나왔다.
    ★ 기간을 30일로 둔 근거(2026-09-12 사용자 확정): 무기한이면 오래된 좋은 이야기를
      새 독자에게 영영 못 쓰고, 프롬프트도 계속 길어진다. naverblog_ssalmuk이 같은 문제에
      쓰는 재탕 금지 기간(사용자가 3일→30일로 올림)과 맞췄다.
    """
    cutoff = (datetime.now() - timedelta(days=PAST_POSTS_DAYS)).strftime("%Y-%m-%d")
    mine = [p for p in posts
            if p.get("project") == project_path and (p.get("day") or "") >= cutoff][:PAST_POSTS_CAP]
    if not mine:
        return ""
    lines = []
    for p in mine:
        head = (f"- [{p.get('day') or ''}] {p['title']} "
                f"(조회 {p.get('views', 0)}·좋아요 {p.get('likes', 0)})")
        lines.append(head)
        lines.append(f"    요지: {(p.get('body') or '').strip()[:90]}…")
    return "\n".join(lines)


def run_board_posts(paths: list[str] | None = None, deadline_ts: float | None = None) -> dict:
    """게시판 글쓰기 — 각 담당이 자기 프로젝트에서 글감을 **스스로 골라** 글을 쓴다(0~1편).

    조회·좋아요가 점수(보상)가 되는 유인 구조라, 뭐가 잘 읽힐지도 담당이 판단한다.
    담당당 headless 1콜, 담당끼리는 병렬. 억지 글 방지: 쓸 게 없으면 빈 배열 허용.
    자기가 전에 쓴 글 목록을 프롬프트로 함께 준다 — 같은 이야기를 다시 쓰지 않도록.
    """
    from src.scan.discover import discover_projects

    date = datetime.now().strftime("%Y-%m-%d")
    projects = discover_projects()
    if paths:
        wanted = set(paths)
        projects = [p for p in projects if p["path"] in wanted]
    allowed, disallowed = tools_for("daily_agent")
    past = board_db.list_posts(board_db.DAILY_BOARD)      # 최신순 — 담당별로 걸러 쓴다

    def worker(p: dict) -> int:
        # 마감을 넘겨 '시작'하는 담당만 스킵(이미 도는 콜은 끝까지 간다) — 순차 때의 break 자리
        if deadline_ts and time.time() > deadline_ts:
            return 0
        out = run_headless(task="board_write",
            prompt=agents_db.persona_prefix(p["path"])
                   + board_write(p["name"], p["path"], _past_posts_text(p["path"], past)),
            cwd=_neutral_cwd(),
            allowed_tools=allowed, disallowed_tools=disallowed,
            timeout=BOARD_TIMEOUT, append_system_prompt=BOARD_WRITE_SYSTEM,
            add_dirs=[p["path"]], model=agents_db.model_for(p["path"]),
        )
        if not out:
            return 0
        m = _ARR_RE.search(out)
        if not m:
            return 0
        try:
            items = json.loads(m.group(0))
        except json.JSONDecodeError:
            return 0
        n = 0
        for it in (items if isinstance(items, list) else [])[:1]:   # 최대 1편
            title = (it.get("title") or "").strip()
            body = (it.get("body") or "").strip()
            if title and body:
                board_db.add_post(author=_author_of(p["path"], p["name"]), title=title[:80],
                                  body=body, project=p["path"], day=date)
                n += 1
        return n

    posted = sum(_board_parallel(projects, worker, "게시판 글쓰기"))
    logger.info(f"[게시판 글쓰기] {posted}편")
    return {"posted": posted}


MAX_COMMENTS_PER_AGENT = 2   # 한 담당이 하룻밤 다는 댓글 상한(공감 홍수 방지, 09-07 재설계)


def _parse_board_response(
    result: str | None, valid_ids: set[int]
) -> tuple[set[int], set[int], set[int], list[dict]]:
    """둘러보기 응답에서 {opened, liked, disliked, comments}를 추출. 실패는 전부 빈 값.

    liked·disliked·댓글 단 글은 opened에 없어도 연 것으로 친다(반응 = 읽었다는 신호).
    댓글은 상한(MAX_COMMENTS_PER_AGENT)까지만.
    ★ disliked는 2026-09-11 신설 — 재탕·근거 부족에 대한 반대표(점수에서 차감).
      같은 글을 좋아요와 싫어요 둘 다에 넣으면 좋아요를 버린다(모순은 반대표 우선).
    """
    if not result:
        return set(), set(), set(), []
    m = _OBJ_RE.search(result)
    if not m:
        return set(), set(), set(), []
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
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

    opened = _ids("opened")
    liked = _ids("liked")
    disliked = _ids("disliked")
    liked -= disliked                   # 둘 다 찍힌 글은 반대표만 남긴다
    opened |= liked | disliked          # 좋아요·싫어요 = 읽었다는 신호
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


def run_board_discussion(paths: list[str] | None = None, deadline_ts: float | None = None) -> dict:
    """게시판 둘러보기 — 각 담당이 제목을 훑고 **끌리는 글만 열어**(조회수 +1) 마음에 들면 댓글.

    담당당 headless 1콜, 담당끼리는 병렬. 연 글만 조회수가 오른다 — 조회수가 진짜 '읽힘' 신호가 되게.
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

    def worker(p: dict) -> tuple[int, int, int]:
        """한 담당의 둘러보기 → (좋아요 수, 싫어요 수, 댓글 수)."""
        if deadline_ts and time.time() > deadline_ts:
            return 0, 0, 0
        out = run_headless(task="board_comment",
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
        opened, liked, disliked, cmts = _parse_board_response(out, valid_ids)
        likes = dislikes = comments = 0
        for pid in opened:
            if pid != own:                # 자기 글 조회는 점수에 안 친다
                board_db.increment_views(pid)
        for pid in liked:
            if pid != own:                # 좋아요 = 값싸고 주력인 투표 신호
                board_db.like_post(pid)
                likes += 1
        for pid in disliked:
            if pid != own:                # 싫어요 = 반대표(자기 글엔 못 누른다)
                board_db.dislike_post(pid)
                dislikes += 1
        for it in cmts:
            if it["post_id"] == own:      # 자기 글엔 안 단다
                continue
            board_db.add_comment(it["post_id"], _author_of(p["path"], p["name"]), it["comment"])
            comments += 1
        return likes, dislikes, comments

    results = _board_parallel(projects, worker, "게시판 둘러보기")
    liked_n = sum(r[0] for r in results)
    disliked_n = sum(r[1] for r in results)
    commented = sum(r[2] for r in results)
    logger.info(f"[게시판] 좋아요 {liked_n}개 · 싫어요 {disliked_n}개 · 댓글 {commented}개")
    return {"commented": commented, "liked": liked_n, "disliked": disliked_n}


def run_post_feedback(paths: list[str] | None = None, deadline_ts: float | None = None) -> dict:
    """글쓴이 에이전트가 자기 글에 달린 댓글에 좋아요/싫어요/대댓글로 반응(강화학습 보상 신호).

    한 글당 headless 1콜(글+댓글 주고 [{comment_id,reaction,reply}] 받음) → 코드가 반영.
    병렬 단위는 **프로젝트** — 한 담당이 글 여러 편을 가진 경우 그 글들은 순서대로 처리한다
    (같은 작업 디렉터리에 같은 담당을 동시에 두지 않기 위해). 담당끼리는 동시에 돈다.
    """
    posts = board_db.list_posts(board_db.DAILY_BOARD)
    if paths:
        wanted = set(paths)
        posts = [p for p in posts if p.get("project") in wanted]
    allowed, disallowed = tools_for("daily_agent")

    posts_by_project: dict[str, list[dict]] = {}
    for post in posts:
        if post.get("project"):
            posts_by_project.setdefault(post["project"], []).append(post)

    def _react_one(post: dict) -> int:
        top = [c for c in post.get("comments", []) if not c.get("parent_id")]
        # 이미 글쓴이 답글이 달린 댓글은 제외 — 매일 재실행돼도 중복 반응·중복 답글이 안 쌓이게
        replied = {c.get("parent_id") for c in post.get("comments", [])
                   if c["author"] == post["author"] and c.get("parent_id")}
        top = [c for c in top if c["id"] not in replied]
        if not top:
            return 0
        if deadline_ts and time.time() > deadline_ts:
            return 0
        cids = {c["id"] for c in top}
        ctext = "\n".join(f"[{c['id']}] {c['author']}: {(c['body'] or '')[:200]}" for c in top)
        out = run_headless(task="board_feedback",
            prompt=agents_db.persona_prefix(post["project"]) + post_feedback(post["author"], post["project"], post["title"], post["body"], ctext),
            cwd=_neutral_cwd(),
            allowed_tools=allowed, disallowed_tools=disallowed,
            timeout=BOARD_TIMEOUT, append_system_prompt=FEEDBACK_SYSTEM,
            add_dirs=[post["project"]],
            model=agents_db.model_for(post["project"]),
        )
        if not out:
            return 0
        m = _ARR_RE.search(out)
        if not m:
            return 0
        try:
            items = json.loads(m.group(0))
        except json.JSONDecodeError:
            return 0
        n = 0
        for it in items if isinstance(items, list) else []:
            try:
                cid = int(it["comment_id"])
            except (KeyError, ValueError, TypeError):
                continue
            if cid not in cids:
                continue
            if it.get("reaction") in ("like", "dislike"):
                board_db.react_comment(cid, it["reaction"])
                n += 1
            rep = (it.get("reply") or "").strip()
            if rep and rep.lower() != "null":
                board_db.add_comment(post["id"], post["author"], rep, parent_id=cid)
        return n

    def worker(item: tuple[str, list[dict]]) -> int:
        return sum(_react_one(post) for post in item[1])

    reacted = sum(_board_parallel(list(posts_by_project.items()), worker, "게시판 피드백"))
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

    def worker(item: tuple[str, list[str]]) -> int:
        """한 담당의 스레드 묶음 → 단 대대댓글 수. 담당끼리는 병렬."""
        agent, threads = item
        if deadline_ts and time.time() > deadline_ts:
            return 0
        path = path_by_name[agent]
        out = run_headless(task="board_followup",
            prompt=agents_db.persona_prefix(path) + comment_followup(agent, path, "\n\n".join(threads)),
            cwd=_neutral_cwd(),
            allowed_tools=allowed, disallowed_tools=disallowed,
            timeout=BOARD_TIMEOUT, append_system_prompt=FOLLOWUP_SYSTEM,
            add_dirs=[path], model=agents_db.model_for(path),
        )
        if not out:
            return 0
        m = _ARR_RE.search(out)
        if not m:
            return 0
        try:
            items = json.loads(m.group(0))
        except json.JSONDecodeError:
            return 0
        n = 0
        for it in items if isinstance(items, list) else []:
            try:
                rid = int(it["reply_id"])
            except (KeyError, ValueError, TypeError):
                continue
            body = (it.get("comment") or "").strip()
            if rid not in valid_by_agent.get(agent, set()) or not body or body.lower() == "null":
                continue
            board_db.add_comment(post_of_reply[rid], agent, body, parent_id=rid)
            n += 1
        return n

    replied = sum(_board_parallel(list(threads_by_agent.items()), worker, "대대댓글"))
    logger.info(f"[대대댓글] {replied}건")
    return {"replied": replied}
