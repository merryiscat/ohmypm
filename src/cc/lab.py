"""랩실(연구소) — 연구원 3명이 모델·디자인·스킬 동향을 계속 모아 "프로젝트를 더 잘 만드는 법"을 제안한다.

연구원(RESEARCHERS):
  models  모델 연구원  — 공식 문서 수집은 기존 model_catalog(코드 수집, 벤더별 위키)를 그대로 쓰고,
                         그 동향 요약으로 제안서만 모델에게 한 번 묻는다(lab_proposal)
  design  디자인 연구원 — 웹 조사형(lab_research): 제품·웹 UI/UX·디자인 시스템·접근성·AI 제품 인터페이스
  skills  스킬 연구원  — 웹 조사형: Claude Code 스킬·훅·서브에이전트·MCP·하네스 설계 동향

산출물: 연구원별 위키(docs/lab/<id>.md, 모델 연구원은 벤더별 docs/lab/models-*.md)와 제안서(lab_proposals 표).
특정 프로젝트 대상 제안은 그 프로젝트의 ohmypm/proposals.md에도 쓴다(설치된 프로젝트만).
실행: 주 1회 스케줄러(research_all) + 랩실 탭 '조사 실행'(src/jobs로 백그라운드).
파일 쓰기는 전부 코드가 한다 — 연구원(모델)은 읽기+웹만.
"""

import json
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.cc import expert, model_catalog
from src.cc.client import run_headless_ex
from src.cc.common import REPO_ROOT, neutral_cwd, parse_json_object
from src.cc.permissions import NEVER_ALLOW, tools_for
from src.cc.prompts import load, render
from src.db import lab as lab_db
from src.db import messages as messages_db
from src.db import projects as projects_db
from src.install import OHMYPM_DIR, is_installed

LAB_DIR = REPO_ROOT / "docs" / "lab"            # 위키(런타임 산출물, git 미추적)
STATE_DIR = REPO_ROOT / "data" / "lab"          # 연구원별 마지막 실행 상태·실패 원문
RESEARCH_TIMEOUT = 420
WIKI_RECENT_CHARS = 3000

RESEARCHERS: dict[str, dict] = {
    "models": {
        "name": "모델 연구원",
        "topic": "Claude·Codex 모델 라인업의 변화와 우리 하네스(모델 선택·프롬프트·추론 설정)를 어떻게 바꿀지",
        "mode": "catalog",
        "domains": list(expert.EXPERTS.keys()),
    },
    "design": {
        "name": "디자인 연구원",
        "topic": "제품·웹 UI/UX, 디자인 시스템, 접근성, AI 제품 인터페이스 패턴",
        "mode": "web",
        "focus": [
            "AI 제품(채팅·에이전트·대시보드) 인터페이스에서 최근 자리 잡은 패턴과 실패 사례",
            "디자인 시스템·컴포넌트 라이브러리의 최근 변화(토큰·다크모드·접근성 기준)",
            "작은 팀이 바로 쓰는 UI 도구·템플릿(Figma→코드, 와이어프레임, 타이포·색 팔레트)",
            "접근성·가독성 가이드의 최신 권고(WCAG 갱신, 폰트·대비·모션)",
        ],
    },
    "skills": {
        "name": "스킬 연구원",
        "topic": "Claude Code 스킬(SKILL.md)·훅·서브에이전트·MCP·하네스 설계 동향과 우리 프로젝트에 넣을 스킬",
        "mode": "web",
        "focus": [
            "Claude Code 공식 문서·changelog의 최근 변화(스킬·훅·서브에이전트·MCP·설정)",
            "공개된 스킬·플러그인 저장소에서 많이 쓰이는 스킬과 그 구조(트리거 문구·참조 파일)",
            "에이전트 하네스 설계 사례(프롬프트 분리·권한 화이트리스트·테스트·비용 통제)",
            "다른 코딩 에이전트(Codex·Cursor 등)의 비슷한 기능과 차이",
        ],
    },
}
_RUNNING: set[str] = set()


def list_researchers() -> list[dict]:
    from src import jobs

    out = []
    for rid, r in RESEARCHERS.items():
        st = _load_state(rid)
        out.append({"id": rid, "name": r["name"], "topic": r["topic"], "mode": r["mode"],
                    "wiki_chars": sum(len(t["wiki"]) for t in wiki_tabs(rid)),
                    "last_run": st.get("last_run"), "last_ok": st.get("ok"),
                    "running": jobs.is_running(job_name(rid))})
    return out


def job_name(rid: str) -> str:
    return f"lab:{rid}"


def lab_room(rid: str) -> str:
    return f"lab::{rid}"


def wiki_tabs(rid: str) -> list[dict]:
    """화면 탭 — 모델 연구원은 벤더별 위키 2개, 나머지는 자기 위키 1개."""
    r = RESEARCHERS.get(rid)
    if not r:
        return []
    if r["mode"] == "catalog":
        return [{"key": d, "title": expert.EXPERTS[d]["name"], "wiki": expert.read_wiki(d)} for d in r["domains"]]
    p = LAB_DIR / f"{rid}.md"
    return [{"key": rid, "title": r["name"], "wiki": p.read_text(encoding="utf-8") if p.exists() else ""}]


def _state_file(rid: str) -> Path:
    return STATE_DIR / f"{rid}.json"


def _load_state(rid: str) -> dict:
    p = _state_file(rid)
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(rid: str, **fields) -> None:
    st = _load_state(rid)
    st.update(fields)
    model_catalog._atomic_write(_state_file(rid), json.dumps(st, ensure_ascii=False, indent=2))


def _projects_text() -> tuple[str, dict[str, str]]:
    """프롬프트용 프로젝트 목록과 이름→경로 지도(enabled, ohmyPM 자신 제외)."""
    from src.cc.common import is_self_project

    rows, by_name = [], {}
    for p in projects_db.list_projects(enabled_only=True):
        if is_self_project(p["path"]):
            continue
        by_name[p["name"]] = p["path"]
        state = Path(p["path"]) / OHMYPM_DIR / "state.md"
        hint = ""
        if state.exists():
            lines = [ln.strip() for ln in state.read_text(encoding="utf-8", errors="replace").splitlines()
                     if ln.strip() and not ln.startswith("#") and "(아직 기록 없음" not in ln and ln.strip() != "(없음)"]
            hint = lines[0][:80] if lines else ""
        rows.append(f"- {p['name']}" + (f" — {hint}" if hint else ""))
    return ("\n".join(rows) or "(관리 중인 프로젝트 없음)"), by_name


def _valid_url(u) -> str | None:
    return u if isinstance(u, str) and u.startswith("https://") else None


def _store_proposals(rid: str, items: list, by_name: dict[str, str]) -> dict:
    """제안 목록을 DB에 넣고, 대상 프로젝트가 설치돼 있으면 ohmypm/proposals.md에도 쓴다."""
    added = written = dup = 0
    for it in items or []:
        if not isinstance(it, dict):
            continue
        title = (it.get("title") or "").strip()[:120]
        body = (it.get("body") or "").strip()
        if not title or not body:
            continue
        target_name = (it.get("target_project") or "").strip() if isinstance(it.get("target_project"), str) else ""
        target = by_name.get(target_name)
        row = lab_db.add_proposal(rid, title, body, target, _valid_url(it.get("source_url")))
        if not row:
            dup += 1
            continue
        added += 1
        if target and is_installed(target):
            try:
                _prepend_proposal(target, rid, row)
                lab_db.mark_written(row["id"])
                written += 1
            except Exception as e:
                logger.warning(f"[랩실] {target_name} proposals.md 기록 실패: {e}")
    return {"proposals": added, "written": written, "dup": dup}


def _prepend_proposal(project_path: str, rid: str, row: dict) -> None:
    f = Path(project_path) / OHMYPM_DIR / "proposals.md"
    old = f.read_text(encoding="utf-8", errors="replace") if f.exists() else "# 랩실 제안 — 이 프로젝트 대상\n\n"
    head, _, rest = old.partition("\n\n")
    if not head.startswith("# "):
        head, rest = "# 랩실 제안 — 이 프로젝트 대상", old
    date = (row.get("created_at") or datetime.now().strftime("%Y-%m-%d"))[:10]
    block = (f"## {date} · {RESEARCHERS[rid]['name']} · {row['title']}\n{row['body'].strip()}\n"
             + (f"출처: {row['source_url']}\n" if row.get("source_url") else "") + "\n")
    f.write_text(f"{head}\n\n{block}{rest.lstrip()}", encoding="utf-8", newline="")


def _prepend_wiki(rid: str, date: str, findings: list) -> int:
    """연구 위키 맨 위에 이번 조사 절을 붙인다. 넣은 건수 반환."""
    rows = []
    for it in findings or []:
        if not isinstance(it, dict):
            continue
        title = (it.get("title") or "").strip()
        summary = (it.get("summary") or "").strip()
        url = _valid_url(it.get("source_url"))
        if not title or not summary or not url:
            continue
        when = (it.get("date") or "").strip()
        rows.append(f"- **{title}**{f' ({when})' if when else ''} — {summary} [출처]({url})")
    if not rows:
        return 0
    p = LAB_DIR / f"{rid}.md"
    old = p.read_text(encoding="utf-8") if p.exists() else f"# {RESEARCHERS[rid]['name']} 연구 위키\n\n{RESEARCHERS[rid]['topic']}\n\n"
    head, _, rest = old.partition("\n\n")
    block = f"## {date} 조사\n" + "\n".join(rows) + "\n\n"
    model_catalog._atomic_write(p, f"{head}\n\n{block}{rest.lstrip()}")
    return len(rows)


def _research_web(rid: str) -> dict:
    r = RESEARCHERS[rid]
    today = datetime.now().strftime("%Y-%m-%d")
    projects_text, by_name = _projects_text()
    recent = (wiki_tabs(rid)[0]["wiki"] or "")[:WIKI_RECENT_CHARS] or "(아직 비어 있음)"
    prompt = render("lab_research", researcher=r["name"], topic=r["topic"], today=today,
                    focus="\n".join(f"{i + 1}. {f}" for i, f in enumerate(r["focus"])),
                    projects=projects_text, wiki_recent=recent)
    allowed, disallowed = tools_for("expert")
    meta = run_headless_ex(prompt, cwd=neutral_cwd(), allowed_tools=allowed, disallowed_tools=disallowed,
                           timeout=RESEARCH_TIMEOUT, append_system_prompt=load("lab_research_system"),
                           task="lab_research")
    data = parse_json_object(meta.get("result"))
    if not data or not isinstance(data.get("findings"), list):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        (STATE_DIR / f"{rid}.llm-failed.txt").write_text(meta.get("result") or "(응답 없음)", encoding="utf-8")
        raise RuntimeError("연구원 응답이 형식에 맞지 않음 — data/lab/*.llm-failed.txt 참조")
    n = _prepend_wiki(rid, today, data["findings"])
    out = _store_proposals(rid, data.get("proposals") or [], by_name)
    out.update({"findings": n, "cost_usd": meta.get("cost_usd"), "model": meta.get("model")})
    return out


def _research_models(rid: str) -> dict:
    """모델 연구원 — 공식 문서 수집(model_catalog) 뒤 동향 요약으로 제안서만 1콜."""
    collected = expert.collect_all()
    today = datetime.now().strftime("%Y-%m-%d")
    trend = model_catalog.trend_brief(limit=5) or "(최근 변경 없음)"
    profiles = "\n\n".join(t["wiki"][:2500] for t in wiki_tabs(rid) if t["wiki"]) or "(프로필 없음)"
    projects_text, by_name = _projects_text()
    prompt = render("lab_proposal", today=today, trend=trend, profiles=profiles, projects=projects_text)
    meta = run_headless_ex(prompt, cwd=neutral_cwd(), allowed_tools=[], disallowed_tools=NEVER_ALLOW,
                           timeout=300, append_system_prompt=load("lab_research_system"), task="lab_proposal")
    data = parse_json_object(meta.get("result")) or {}
    out = _store_proposals(rid, data.get("proposals") or [], by_name)
    out.update({"collected": collected, "cost_usd": meta.get("cost_usd"), "model": meta.get("model")})
    return out


def research(rid: str) -> dict:
    """연구원 하나의 조사 1회. 결과 통계 반환, 상태 파일 갱신."""
    r = RESEARCHERS.get(rid)
    if not r:
        return {"ok": False, "error": "unknown researcher"}
    if rid in _RUNNING:
        return {"ok": False, "error": "이미 조사 중"}
    _RUNNING.add(rid)
    try:
        out = _research_models(rid) if r["mode"] == "catalog" else _research_web(rid)
        _save_state(rid, last_run=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ok=True, last=out)
        logger.info(f"[랩실] {r['name']} 조사 끝 — {out}")
        return {"ok": True, **out}
    except Exception as e:
        _save_state(rid, last_run=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ok=False, error=str(e)[:300])
        logger.warning(f"[랩실] {r['name']} 조사 실패: {e}")
        return {"ok": False, "error": str(e)[:300]}
    finally:
        _RUNNING.discard(rid)


def research_all() -> dict:
    """세 연구원 순차 조사(주 1회 스케줄러용). 한 명 실패가 나머지를 막지 않는다."""
    results = {rid: research(rid) for rid in RESEARCHERS}
    logger.info(f"[랩실] 정기 조사 — 성공 {sum(1 for v in results.values() if v.get('ok'))}/{len(results)}")
    return results


def consult(rid: str, question: str) -> str:
    """연구원에게 질문 — 자기 위키(모델 연구원은 두 벤더 위키 합본)를 1차 근거로 답한다."""
    r = RESEARCHERS.get(rid)
    if not r:
        return ""
    from src.cc.prompts import EXPERT_SYSTEM, expert_consult

    wiki = "\n\n".join(f"## {t['title']}\n{t['wiki'][:4000]}" for t in wiki_tabs(rid) if t["wiki"])
    allowed, disallowed = tools_for("expert")
    meta = run_headless_ex(expert_consult(r["topic"], wiki, question), cwd=neutral_cwd(),
                           allowed_tools=allowed, disallowed_tools=disallowed,
                           timeout=expert.EXPERT_TIMEOUT, append_system_prompt=EXPERT_SYSTEM,
                           task="expert_consult")
    return (meta.get("result") or "").strip()


def ask(rid: str, question: str) -> None:
    """질문에 답해 lab 방에 남긴다(사용자 질문은 API가 먼저 방에 기록)."""
    answer = consult(rid, question)
    messages_db.add_message(lab_room(rid), RESEARCHERS.get(rid, {}).get("name", rid),
                            answer or "(답변을 만들지 못했어)")
