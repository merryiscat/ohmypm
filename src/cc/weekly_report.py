"""주간보고 — 지난 7일 커밋과 각 프로젝트의 상태 메모를 모아 "이번 주 뭘 했나" 한 장 보고.

수집은 결정론적 코드(git log + ohmypm/state.md 읽기). 그다음 두 단계:
  ① 점검 대화 — 활동이 있는 프로젝트마다 PM이 담당에게 묻고 담당이 자기 폴더를 읽어 답한다
     (옛 일간보고 방식, 2026-10-10 사용자 요청). 방 `weekly::{날짜}::{path}`에 author 'pm'·'agent'로 쌓인다.
     조용한 프로젝트는 물을 게 없으니 대화하지 않는다.
  ①-2 변경 리뷰 — 커밋이 있는 프로젝트마다 이번 주 diff를 Ponytail 리뷰(/ponytail-review)로 본다
     (2026-10-11 사용자 결정). 플러그인은 설치하지 않고 그 호출에만 --plugin-dir로 싣는다. 읽기 전용.
     같은 방에 author 'review'로 남고, 종합에도 넘겨 '꼭 고칠 것'이 요약에 오르게 한다.
  ② 종합 — 팩트 + 대화를 근거로 LLM 1콜(JSON). 코드가 JSON을 프로젝트별로 나눠 저장한다:
     - 전체 보고 → messages 방 `weekly::{날짜}` (author 'ohmyPM')
     - 프로젝트별 몫 → 같은 방 `weekly::{날짜}::{path}` 맨 끝(author 'ohmyPM')
       + 설치된 프로젝트는 `{path}/ohmypm/weekly.md` 맨 위에 prepend
사용자가 담당과 직접 나누는 대화는 프로젝트 방(room=path)이다 — 그 담당은 최근 점검 대화를 맥락으로 받는다.
정시 배치는 걸지 않는다 — 화면의 '주간보고 실행' 버튼이 src/jobs로 백그라운드 실행한다.
"""

import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.cc.cards import apply_ops, cards_text
from src.cc.client import run_headless_ex
from src.cc.common import is_self_project, neutral_cwd, parse_json_object, tool_commit
from src.cc.permissions import NEVER_ALLOW, tools_for
from src.cc.prompts import load, render
from src.config.settings import ensure_env, settings
from src.db import agents as agents_db
from src.db import messages as messages_db
from src.install import OHMYPM_DIR, is_installed
from src.proc import NO_WINDOW
from src.scan.discover import discover_projects

DAYS = 7              # 보고가 덮는 기간(일)
GIT_TIMEOUT = 30      # 프로젝트 하나의 git log 제한 시간(초)
LLM_TIMEOUT = 300     # 요약 호출 제한 시간(초)
STATE_LIMIT = 600     # 상태 메모를 프롬프트에 넣을 때 자르는 길이(자)
JOB_NAME = "weekly"
MAX_ROUNDS = 3        # 점검 대화에서 PM이 담당에게 묻는 최대 횟수
AGENT_TIMEOUT = 240   # 담당 답 제한 시간(초) — 폴더를 읽고 답하므로 여유 있게
CONVO_WORKERS = 3     # 점검 대화를 동시에 돌릴 프로젝트 수
CONVO_LIMIT = 1500    # 종합 프롬프트에 넣을 프로젝트별 대화 길이(자)
REVIEW_TIMEOUT = 420  # 변경 리뷰 제한 시간(초) — 주변 코드까지 읽으므로 넉넉히
DIFF_LIMIT = 60000    # 리뷰에 넘길 이번 주 diff 길이(자). 넘으면 자르고 나머지는 리뷰가 파일을 직접 읽는다
REVIEW_LIMIT = 1500   # 종합 프롬프트에 넣을 프로젝트별 리뷰 길이(자)


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

    ohmyPM 자신도 넣는다(2026-10-10 사용자 지적 — 가장 바빴던 주에 통째로 빠졌다). 설치·랩실의
    '자기 자신 제외'는 거기서만 맞는 규칙이다. 단 ohmyPM 저장소에는 도구 커밋이 없고 사람이 쓴
    제목에도 'ohmyPM'이 흔히 들어가므로, 자기 저장소에는 도구 커밋 거르기를 하지 않는다.
    """
    ensure_env()
    result: list[dict] = []
    for p in discover_projects():
        is_self = is_self_project(p["path"])
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
                    if line and (is_self or not tool_commit(subject)):
                        commits.append(line)
        except Exception as e:
            logger.warning(f"[주간보고] {p['name']} 커밋 수집 실패: {e}")
        result.append({"path": p["path"], "name": p["name"], "commits": commits,
                       "state": _state_text(p["path"])})
    total = sum(len(x["commits"]) for x in result)
    logger.info(f"[주간보고] 수집 — 프로젝트 {len(result)}개 · 커밋 {total}건 (최근 {days}일)")
    return result


def _project_facts(p: dict) -> str:
    """한 프로젝트의 커밋 목록 + 상태 메모(제목 줄 없이)."""
    lines = [f"- {c}" for c in p["commits"]] or ["- (이번 주 커밋 없음)"]
    if p["state"]:
        lines += ["[지금 상태 메모]", p["state"]]
    return "\n".join(lines)


def _facts_text(collected: list[dict], convos: dict[str, str] | None = None,
                reviews: dict[str, str] | None = None) -> str:
    """종합 프롬프트용 — 프로젝트별 팩트, 점검 대화·변경 리뷰가 있으면 그 아래에 붙인다."""
    lines: list[str] = []
    for p in collected:
        lines += [f"### {p['name']}", _project_facts(p)]
        convo = (convos or {}).get(p["path"])
        if convo:
            lines += ["[PM과 담당의 점검 대화]", convo[:CONVO_LIMIT]]
        review = (reviews or {}).get(p["path"])
        if review:
            lines += ["[이번 주 변경 리뷰]", review[:REVIEW_LIMIT]]
        lines.append("")
    return "\n".join(lines)


def _ponytail_dir() -> str | None:
    """Ponytail 플러그인 폴더(.claude-plugin/plugin.json이 있는 곳). 없으면 None — 리뷰를 건너뛴다."""
    d = Path(settings.ponytail_dir) if settings.ponytail_dir else \
        Path.home() / ".claude" / "plugins" / "marketplaces" / "ponytail"
    return str(d) if (d / ".claude-plugin" / "plugin.json").exists() else None


EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"   # git의 '빈 폴더' — 7일보다 젊은 저장소의 기준점


def _git(path: str, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=path, capture_output=True, text=True, timeout=GIT_TIMEOUT,
                       encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    return (r.stdout or "").strip() if r.returncode == 0 else ""


def _week_diff(path: str, days: int) -> str:
    """최근 N일 동안의 '합친' 변경 — 일주일 전 시점과 지금의 차이(git diff) + 커밋 제목 목록.
    커밋별로 늘어놓으면 같은 곳을 여러 번 고친 주에 금방 길어져 앞 커밋만 실린다(2026-10-11 실측:
    22개 중 7개). ohmypm/ 폴더(도구가 쓰는 곳)는 뺀다. 길면 자른다."""
    base = _git(path, "rev-list", "-1", f"--before={days} days ago", "HEAD") or EMPTY_TREE
    log = _git(path, "log", f"{base}..HEAD" if base != EMPTY_TREE else "HEAD", "--no-merges",
               "--pretty=format:- %h %ad %s", "--date=format:%m-%d")
    body = _git(path, "diff", "--no-color", base, "HEAD", "--", ".", f":(exclude){OHMYPM_DIR}")
    if not body:
        return ""
    diff = f"[커밋 목록]\n{log}\n\n[일주일 동안 바뀐 내용 — 합친 diff]\n{body}"
    if len(diff) > DIFF_LIMIT:
        diff = diff[:DIFF_LIMIT] + f"\n\n(잘림 — 전체 {len(diff):,}자 중 앞 {DIFF_LIMIT:,}자만 실었다)"
    return diff


def review(p: dict, date: str, days: int = DAYS) -> str:
    """이번 주 커밋을 Ponytail 리뷰로 본다(읽기 전용). 방에 남기고 리뷰 본문을 돌려준다.
    커밋이 없거나, 플러그인이 없거나, 변경이 ohmypm/뿐이면 빈 문자열(조용히 건너뜀)."""
    if not p["commits"]:
        return ""
    plugin = _ponytail_dir()
    if not plugin:
        logger.warning("[주간보고] Ponytail 플러그인 폴더가 없어 변경 리뷰를 건너뜀 (.env PONYTAIL_DIR)")
        return ""
    diff = _week_diff(p["path"], days)
    if not diff:
        return ""
    prompt = render("weekly_review", project_name=p["name"], project_path=p["path"], days=str(days), diff=diff)
    allowed, disallowed = tools_for("weekly_review")     # 미등록 태스크 → 읽기 전용 기본(Read·Grep·Glob)
    meta = run_headless_ex(
        prompt, cwd=neutral_cwd(), allowed_tools=allowed, disallowed_tools=disallowed,
        timeout=REVIEW_TIMEOUT, add_dirs=[p["path"]], plugin_dirs=[plugin], task="weekly_review",
    )
    text = (meta.get("result") or "").strip()
    messages_db.add_message(_room(date, p["path"]), "review",
                            text or "(변경 리뷰 호출이 실패했다 — 이번 주는 리뷰 없이 넘어간다)")
    return text


def _transcript(turns: list[tuple[str, str]]) -> str:
    return "\n".join(f"PM: {q}\n담당: {a}" for q, a in turns)


def _pm_turn(p: dict, days: int, today: str, history: str) -> dict | None:
    """PM 한 턴 — {ask, done, summary, cards}. 응답이 없거나 깨졌으면 None."""
    prompt = render("weekly_pm", project_name=p["name"], days=str(days), today=today,
                    facts=_project_facts(p), cards=cards_text(p["path"]),
                    history=history or "(아직 없음 — 첫 질문이다)")
    meta = run_headless_ex(
        prompt, cwd=neutral_cwd(), allowed_tools=[], disallowed_tools=NEVER_ALLOW,
        timeout=LLM_TIMEOUT, append_system_prompt=load("weekly_pm_system"), task="weekly_pm",
    )
    return parse_json_object(meta.get("result"))


def _agent_answer(p: dict, question: str, history: str) -> str:
    """담당이 자기 폴더를 읽고 PM 질문에 답한다(읽기 전용 — 파일은 안 고친다)."""
    prompt = agents_db.persona_prefix(p["path"]) + render(
        "weekly_agent", project_name=p["name"], project_path=p["path"],
        history=history or "(아직 없음)", question=question)
    allowed, disallowed = tools_for("weekly_agent")      # 미등록 태스크 → 읽기 전용 기본
    meta = run_headless_ex(
        prompt, cwd=neutral_cwd(), allowed_tools=allowed, disallowed_tools=disallowed,
        timeout=AGENT_TIMEOUT, append_system_prompt=load("room_system"), add_dirs=[p["path"]],
        model=agents_db.model_for(p["path"]), task="weekly_agent",
    )
    return (meta.get("result") or "").strip() or "(담당 응답 없음)"


def converse(p: dict, date: str, days: int = DAYS) -> str:
    """한 프로젝트의 PM↔담당 점검 대화. 방에 쌓고, 종합에 넘길 대화록을 돌려준다.

    PM 발화 = 지금까지의 요약 + (더 물을 게 있으면) 담당에게 하는 질문. 끝낼 때 PM이 칸반을
    정리한다(src/cc/cards.py가 검사·반영). 실패해도 방에 한 줄을
    남긴다 — 그 주 목록에서 프로젝트가 소리 없이 빠지지 않게(놓침0).
    """
    room = _room(date, p["path"])
    turns: list[tuple[str, str]] = []
    summary = ""
    for _ in range(MAX_ROUNDS):
        pm = _pm_turn(p, days, date, _transcript(turns))
        if not pm:
            if not turns:
                messages_db.add_message(room, "pm", "(PM 점검 호출이 실패해 이번 주 대화를 시작하지 못했다 — 커밋 기록만으로 요약한다)")
            break
        summary = str(pm.get("summary") or "").strip() or summary
        ask = pm.get("ask").strip() if isinstance(pm.get("ask"), str) else ""
        done = bool(pm.get("done")) or not ask
        body = summary + ("" if done else f"\n\n담당에게: {ask}")
        moved = apply_ops(p["path"], pm.get("cards"), by="pm")    # 칸반 정리(대개 마지막 턴에만 온다)
        if moved:
            body += f"\n\n(칸반 {moved}건 정리)"
        messages_db.add_message(room, "pm", body.strip() or "(요약 없음)")
        if done:
            break
        ans = _agent_answer(p, ask, _transcript(turns))
        messages_db.add_message(room, "agent", ans)
        turns.append((ask, ans))
    return (_transcript(turns) + (f"\nPM 정리: {summary}" if summary else "")).strip()


def _converse_all(collected: list[dict], date: str, days: int) -> tuple[dict[str, str], dict[str, str]]:
    """활동이 있는 프로젝트만 점검 대화 → 변경 리뷰를 돌린다(동시 CONVO_WORKERS개).
    반환: ({path: 대화록}, {path: 리뷰}). 둘 다 실패해도 나머지 프로젝트는 간다."""
    active = [p for p in collected if p["commits"] or p["state"]]

    def work(p: dict) -> tuple[str, str, str]:
        convo = rev = ""
        try:
            convo = converse(p, date, days)
        except Exception as e:                       # 한 프로젝트가 실패해도 나머지는 간다
            logger.warning(f"[주간보고] {p['name']} 점검 대화 실패: {e}")
            messages_db.add_message(_room(date, p["path"]), "pm", f"(점검 대화 중 오류: {e})")
        try:
            rev = review(p, date, days)
        except Exception as e:
            logger.warning(f"[주간보고] {p['name']} 변경 리뷰 실패: {e}")
        return p["path"], convo, rev

    with ThreadPoolExecutor(max_workers=CONVO_WORKERS) as ex:
        results = list(ex.map(work, active))
    logger.info(f"[주간보고] 점검 대화·변경 리뷰 {len(active)}개 프로젝트 완료")
    return {path: c for path, c, _ in results}, {path: r for path, _, r in results if r}


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


def _merge_report(body: str, items: list[tuple[str, str]]) -> str:
    """이미 있는 전체 보고 본문에 프로젝트 몫을 끼워 넣는다 — 같은 이름 절이 있으면 바꾸고, 없으면
    '조용했던 프로젝트' 줄 앞에 붙인다. 넣은 이름은 조용했던 목록에서 뺀다. '이번 주 한 줄'은 그대로."""
    lines = body.rstrip("\n").split("\n")
    quiet_idx = next((i for i, ln in enumerate(lines) if ln.startswith("**조용했던 프로젝트**")), None)
    for name, summary in items:
        head = f"## {name}"
        if head in lines:                                   # 이미 있는 절 → 다음 절 전까지 교체
            i = lines.index(head)
            j = next((k for k in range(i + 1, len(lines))
                      if lines[k].startswith("## ") or lines[k].startswith("**조용했던")), len(lines))
            lines[i:j] = [head, summary, ""]
        else:
            at = quiet_idx if quiet_idx is not None else len(lines)
            lines[at:at] = [head, summary, ""]
        quiet_idx = next((i for i, ln in enumerate(lines) if ln.startswith("**조용했던 프로젝트**")), None)
        if quiet_idx is not None:                          # 조용했던 목록에서 이름 빼기
            names = [n.strip() for n in lines[quiet_idx].split("—", 1)[-1].split(",")]
            rest = [n for n in names if n and n != name]
            if rest:
                lines[quiet_idx] = f"**조용했던 프로젝트** — {', '.join(rest)}"
            else:
                del lines[quiet_idx]
                quiet_idx = None
    return "\n".join(lines).strip() + "\n"


def run_weekly_report(days: int = DAYS, paths: list[str] | None = None, date: str | None = None) -> dict:
    """주간보고 1회: 수집 → 점검 대화 → LLM 종합(JSON) → 방 저장 + 프로젝트 폴더 기록. 통계와 본문 반환.

    paths를 주면 그 프로젝트만 돌려 date(기본 오늘) 보고에 끼워 넣는다 — 한 프로젝트가 빠졌다고
    전체를 다시 돌리지 않게(2026-10-10 사용자 요청). 그날 보고가 없으면 새 보고로 만든다.
    """
    collected = collect_weekly_commits(days)
    if paths:
        collected = [p for p in collected if p["path"] in set(paths)]
    total = sum(len(x["commits"]) for x in collected)
    today = date or datetime.now().strftime("%Y-%m-%d")
    convos, reviews = _converse_all(collected, today, days)
    prompt = render("weekly_report", days=str(days), today=today, facts=_facts_text(collected, convos, reviews))
    meta = run_headless_ex(
        prompt, cwd=neutral_cwd(), allowed_tools=[], disallowed_tools=NEVER_ALLOW,
        timeout=LLM_TIMEOUT, append_system_prompt=load("weekly_system"), task="weekly_report",
    )
    raw = meta.get("result")
    data = parse_json_object(raw)
    written, not_written = [], []
    if data:
        by_name = {p["name"]: p for p in collected}
        old = messages_db.list_messages(_room(today), limit=1) if paths else []
        if old:   # 부분 실행 → 그날 보고에 끼워 넣기
            items = [((it.get("name") or "").strip(), (it.get("summary") or "").strip())
                     for it in data.get("projects") or []]
            report = _merge_report(old[-1]["body"], [(n, s) for n, s in items if n in by_name and s])
        else:
            report = _render_report(today, data)
        messages_db.add_message(_room(today), "ohmyPM", report)
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
    elif raw and paths and messages_db.list_messages(_room(today), limit=1):
        # 부분 실행에서 JSON이 깨지면 그날 전체 보고를 덮지 않고 고른 프로젝트 방에만 원문을 남긴다
        report = raw.strip()
        for p in collected:
            messages_db.add_message(_room(today, p["path"]), "ohmyPM", report)
        logger.warning("[주간보고] 부분 실행 JSON 파싱 실패 — 프로젝트 방에만 원문 저장")
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


def latest_conversation(path: str) -> str:
    """이 프로젝트의 가장 최근 주간 점검 대화 — 사용자와의 룸 대화에 맥락으로 준다. 없으면 빈 문자열."""
    suffix = f"::{path}"
    rooms = [r for r in messages_db.list_rooms_like("weekly::") if r.endswith(suffix) and r.count("::") == 2]
    if not rooms:
        return ""
    room = max(rooms)                                   # weekly::YYYY-MM-DD::path — 문자열순 = 날짜순
    who = {"pm": "PM", "agent": "나(담당)", "review": "변경 리뷰", "ohmyPM": "주간보고 몫"}
    lines = [f"- {who.get(m['author'], m['author'])}: {(m['body'] or '')[:600]}"
             for m in messages_db.list_messages(room, limit=40)]
    return f"[{room.split('::')[1]} 주간보고]\n" + "\n".join(lines)
