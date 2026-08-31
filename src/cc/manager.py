"""총괄 통합 관리자 — 매일 전 프로젝트를 지휘. 연속성은 저널(docs/manager/journal.md)로 유지.

아침(plan_day): 저널+오늘 현황 → 프로젝트별 '오늘의 지침'을 만들어 각 담당 실행에 주입.
저녁(close_day): 각 프로젝트 결과를 통합해 전사 종합을 쓰고 저널에 남긴다(텔레그램으로도 나감).
저널 파일 쓰기는 코드가 한다(관리자는 텍스트만 반환).
"""

import json
import re
import tempfile
from pathlib import Path

from loguru import logger

from src.cc.client import run_headless
from src.cc.permissions import tools_for
from src.cc.prompts import MANAGER_SYSTEM, manager_close, manager_plan
from src.db import issues as issues_db

ROOT = Path(__file__).resolve().parents[2]
JOURNAL = ROOT / "docs" / "manager" / "journal.md"
MANAGER_TIMEOUT = 200
_OBJ = re.compile(r"\{.*\}", re.DOTALL)

_NEUTRAL: str | None = None


def _neutral() -> str:
    global _NEUTRAL
    if _NEUTRAL is None or not Path(_NEUTRAL).exists():
        _NEUTRAL = tempfile.mkdtemp(prefix="ohmypm_mgr_")
    return _NEUTRAL


def read_journal() -> str:
    return JOURNAL.read_text(encoding="utf-8") if JOURNAL.exists() else ""


def _facts_brief(path: str) -> str:
    items = [i for i in issues_db.list_issues()
             if i["project"] == path and i.get("verdict") != "drop"]
    if not items:
        return "이슈 없음"
    u = sum(1 for i in items if i["kind"] == "unresolved")
    d = sum(1 for i in items if i["kind"] == "deadline")
    dues = sorted(i["due"] for i in items if i.get("due"))
    return f"미해결 {u}·기한 {d}" + (f", 임박 {dues[0]}" if dues else "")


def plan_day(projects: list[dict]) -> dict[str, str]:
    """{path: 오늘의 지침}. projects: [{path,name}] 순서 고정. 지침 없는 프로젝트는 빠짐."""
    digest = "\n".join(f"{i}. {p['name']} — {_facts_brief(p['path'])}" for i, p in enumerate(projects))
    allowed, disallowed = tools_for("daily_pm")
    r = run_headless(
        prompt=manager_plan(read_journal(), digest), cwd=_neutral(),
        allowed_tools=allowed, disallowed_tools=disallowed,
        timeout=MANAGER_TIMEOUT, append_system_prompt=MANAGER_SYSTEM,
    )
    out: dict[str, str] = {}
    if not r:
        return out
    m = _OBJ.search(r)
    if not m:
        return out
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return out
    for g in d.get("guidance", []) if isinstance(d, dict) else []:
        try:
            idx = int(g["i"]); note = (g.get("note") or "").strip()
        except (KeyError, ValueError, TypeError):
            continue
        if note and 0 <= idx < len(projects):
            out[projects[idx]["path"]] = note
    return out


def close_day(date: str, results: list[dict]) -> str:
    """각 프로젝트 결과를 통합한 전사 종합(마크다운). 저널에 append하고 반환(텔레그램용)."""
    digest = "\n".join(f"- {r.get('name')}: {(r.get('summary') or '')[:150]}" for r in results)
    allowed, disallowed = tools_for("daily_pm")
    out = run_headless(
        prompt=manager_close(read_journal(), digest), cwd=_neutral(),
        allowed_tools=allowed, disallowed_tools=disallowed,
        timeout=MANAGER_TIMEOUT, append_system_prompt=MANAGER_SYSTEM,
    )
    synthesis = (out or "").strip()
    if synthesis:
        JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        entry = f"\n\n# [{date}] 전사 종합\n\n{synthesis}\n"
        with JOURNAL.open("a", encoding="utf-8") as f:
            f.write(entry)
        logger.info(f"[총괄] {date} 저널 갱신 {len(synthesis)}자")
    return synthesis
