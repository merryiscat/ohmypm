"""주간보고 — 지난 7일 커밋과 각 프로젝트의 상태 메모를 모아 "이번 주 뭘 했나" 한 장 보고.

수집은 결정론적 코드(git log + ohmypm/state.md 읽기), LLM은 요약만(1콜, JSON). 코드가 JSON을
프로젝트별로 나눠 저장한다:
  - 전체 보고 → messages 방 `weekly::{날짜}` (author 'ohmyPM')
  - 프로젝트별 몫 → `weekly::{날짜}::{path}` + 설치된 프로젝트는 `{path}/ohmypm/weekly.md` 맨 위에 prepend
정시 배치는 걸지 않는다 — 화면의 '주간보고 실행' 버튼이 src/jobs로 백그라운드 실행한다.
"""

import subprocess
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.cc.client import run_headless_ex
from src.cc.common import is_self_project, neutral_cwd, parse_json_object, tool_commit
from src.cc.permissions import NEVER_ALLOW
from src.cc.prompts import load, render
from src.config.settings import ensure_env
from src.db import messages as messages_db
from src.install import OHMYPM_DIR, is_installed
from src.proc import NO_WINDOW
from src.scan.discover import discover_projects

DAYS = 7              # 보고가 덮는 기간(일)
GIT_TIMEOUT = 30      # 프로젝트 하나의 git log 제한 시간(초)
LLM_TIMEOUT = 300     # 요약 호출 제한 시간(초)
STATE_LIMIT = 600     # 상태 메모를 프롬프트에 넣을 때 자르는 길이(자)
JOB_NAME = "weekly"


def _room(date: str, path: str | None = None) -> str:
    return f"weekly::{date}" + (f"::{path}" if path else "")


def _state_text(path: str) -> str:
    """프로젝트의 ohmypm/state.md 본문(있으면). 뼈대 그대로면 빈 문자열."""
    f = Path(path) / OHMYPM_DIR / "state.md"
    if not f.exists():
        return ""
    text = f.read_text(encoding="utf-8", errors="replace").strip()
    if "(아직 기록 없음" in text and text.count("(없음)") >= 2:
        return ""
    return text[:STATE_LIMIT]


def collect_weekly_commits(days: int = DAYS) -> list[dict]:
    """프로젝트별 최근 N일 커밋 제목 + 상태 메모(결정론 수집 — LLM 없음).

    반환: [{path, name, commits: ["10-05 커밋제목", ...], state: str}] — 커밋 없는 프로젝트도 포함
    (조용한 프로젝트가 소리 없이 사라지지 않게). 도구 커밋(ohmypm 표식)은 사람 활동이 아니라 뺀다.
    """
    ensure_env()
    result: list[dict] = []
    for p in discover_projects():
        if is_self_project(p["path"]):
            continue
        commits: list[str] = []
        try:
            r = subprocess.run(
                ["git", "log", f"--since={days} days ago", "--pretty=format:%ad %s", "--date=format:%m-%d"],
                cwd=p["path"], capture_output=True, text=True, timeout=GIT_TIMEOUT,
                encoding="utf-8", errors="replace", creationflags=NO_WINDOW,
            )
            if r.returncode == 0:
                for line in (r.stdout or "").splitlines():
                    line = line.strip()
                    subject = line.split(" ", 1)[1] if " " in line else line
                    if line and not tool_commit(subject):
                        commits.append(line)
        except Exception as e:
            logger.warning(f"[주간보고] {p['name']} 커밋 수집 실패: {e}")
        result.append({"path": p["path"], "name": p["name"], "commits": commits,
                       "state": _state_text(p["path"])})
    total = sum(len(x["commits"]) for x in result)
    logger.info(f"[주간보고] 수집 — 프로젝트 {len(result)}개 · 커밋 {total}건 (최근 {days}일)")
    return result


def _facts_text(collected: list[dict]) -> str:
    lines: list[str] = []
    for p in collected:
        lines.append(f"### {p['name']}")
        lines += [f"- {c}" for c in p["commits"]] or ["- (이번 주 커밋 없음)"]
        if p["state"]:
            lines.append("[지금 상태 메모]")
            lines.append(p["state"])
        lines.append("")
    return "\n".join(lines)


def _render_report(date: str, data: dict) -> str:
    out = [f"# 주간보고 {date}", "", f"**이번 주 한 줄** — {data.get('headline', '').strip()}", ""]
    for it in data.get("projects") or []:
        out.append(f"## {it.get('name', '').strip()}")
        out.append((it.get("summary") or "").strip())
        out.append("")
    quiet = [q for q in (data.get("quiet") or []) if isinstance(q, str) and q.strip()]
    if quiet:
        out.append(f"**조용했던 프로젝트** — {', '.join(q.strip() for q in quiet)}")
    return "\n".join(out).strip() + "\n"


def _prepend_weekly_md(path: str, date: str, summary: str) -> None:
    """프로젝트 ohmypm/weekly.md 맨 위에 이번 주 몫을 붙인다(최신이 위)."""
    f = Path(path) / OHMYPM_DIR / "weekly.md"
    old = f.read_text(encoding="utf-8", errors="replace") if f.exists() else "# 주간보고 — 이 프로젝트 몫\n\n"
    head, _, rest = old.partition("\n\n")
    if not head.startswith("# "):
        head, rest = "# 주간보고 — 이 프로젝트 몫", old
    block = f"## {date}\n{summary.strip()}\n\n"
    f.write_text(f"{head}\n\n{block}{rest.lstrip()}", encoding="utf-8", newline="")


def run_weekly_report(days: int = DAYS) -> dict:
    """주간보고 1회: 수집 → LLM 요약(JSON) → 방 저장 + 프로젝트 폴더 기록. 통계와 본문 반환."""
    collected = collect_weekly_commits(days)
    total = sum(len(x["commits"]) for x in collected)
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = render("weekly_report", days=str(days), today=today, facts=_facts_text(collected))
    meta = run_headless_ex(
        prompt, cwd=neutral_cwd(), allowed_tools=[], disallowed_tools=NEVER_ALLOW,
        timeout=LLM_TIMEOUT, append_system_prompt=load("weekly_system"), task="weekly_report",
    )
    raw = meta.get("result")
    data = parse_json_object(raw)
    written, not_written = [], []
    if data:
        report = _render_report(today, data)
        messages_db.add_message(_room(today), "ohmyPM", report)
        by_name = {p["name"]: p for p in collected}
        for it in data.get("projects") or []:
            p = by_name.get((it.get("name") or "").strip())
            summary = (it.get("summary") or "").strip()
            if not p or not summary:
                continue
            messages_db.add_message(_room(today, p["path"]), "ohmyPM", summary)
            if is_installed(p["path"]):
                try:
                    _prepend_weekly_md(p["path"], today, summary)
                    written.append(p["name"])
                except Exception as e:
                    logger.warning(f"[주간보고] {p['name']} weekly.md 기록 실패: {e}")
                    not_written.append(p["name"])
            else:
                not_written.append(p["name"])
    elif raw:
        # JSON이 깨졌어도 본문은 버리지 않는다(놓침0) — 전체 방에만 원문 저장
        report = raw.strip()
        messages_db.add_message(_room(today), "ohmyPM", report)
        logger.warning("[주간보고] JSON 파싱 실패 — 원문만 저장")
    else:
        report = None
        logger.warning("[주간보고] 요약 실패 — 보고 없음(수집 통계만 반환)")
    return {"date": today, "projects": len(collected), "commits": total, "model": meta.get("model"),
            "cost_usd": meta.get("cost_usd"), "written": written, "not_written": not_written,
            "ok": bool(report)}


def list_reports() -> list[dict]:
    """[{date, overall_room, projects:[{project, name, room, written}]}] — 최신 날짜 먼저."""
    from src.db import projects as projects_db

    names = {p["path"]: p["name"] for p in projects_db.list_projects(enabled_only=False)}
    by_date: dict[str, dict] = {}
    for room in messages_db.list_rooms_like("weekly::"):
        parts = room.split("::", 2)
        if len(parts) == 2:
            by_date.setdefault(parts[1], {"date": parts[1], "overall_room": room, "projects": []})
        elif len(parts) == 3:
            d = by_date.setdefault(parts[1], {"date": parts[1], "overall_room": _room(parts[1]), "projects": []})
            path = parts[2]
            d["projects"].append({"project": path, "name": names.get(path, path), "room": room,
                                  "written": (Path(path) / OHMYPM_DIR / "weekly.md").exists()})
    return [by_date[d] for d in sorted(by_date, reverse=True)]
