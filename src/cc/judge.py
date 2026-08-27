"""판정 에이전트 (자가 확인형) — 결정론 파서가 뽑은 이슈 후보를 headless Claude Code가
대상 프로젝트에서 직접 소스를 열어보고 keep/drop/reclass로 가린다.

레퍼런스: AI-Codereview의 Agentic Review Mode(탐색권을 안전하게 부여), learn-claude-code.
"수집=결정론(scan), 판단=LLM(여기)" 원칙. 읽기 전용 도구만 — 되돌릴 수 없는 행동은 물리 차단.
"""

import json
import re
import tempfile
from pathlib import Path

from loguru import logger

from src.cc.client import run_headless
from src.cc.permissions import tools_for
from src.cc.prompts import JUDGE_SYSTEM, judge_issues
from src.db import issues as issues_db
from src.scan.discover import discover_projects

# 에이전트 응답에서 JSON 배열만 뽑아내는 가드 — 프로즈·펜스가 섞여 와도 첫 [...] 블록을 집는다.
_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)

# 판정 대상 종류 — 첫 적용은 기한 오탐 문제라 deadline만. (unresolved 등은 뒤 관문에서 확대)
DEFAULT_KINDS: tuple[str, ...] = ("deadline",)

# 프로젝트당 판정 타임아웃(초). 콜드스타트+탐색 여유.
JUDGE_TIMEOUT = 180

# 판정은 어느 프로젝트 설정도 안 걸리는 중립 cwd에서 돈다(대상 SessionStart 훅·CLAUDE.md 격리).
# add_dirs로 대상 docs만 읽게 연다. 프로세스당 한 번 만들어 재사용.
_NEUTRAL_CWD: str | None = None


def _neutral_cwd() -> str:
    global _NEUTRAL_CWD
    if _NEUTRAL_CWD is None or not Path(_NEUTRAL_CWD).exists():
        _NEUTRAL_CWD = tempfile.mkdtemp(prefix="ohmypm_judge_")
    return _NEUTRAL_CWD


def _parse_verdicts(result: str | None) -> list[dict] | None:
    """에이전트 최종 텍스트에서 판정 JSON 배열 추출. 실패는 None(미판정 유지 신호)."""
    if not result:
        return None
    m = _ARRAY_RE.search(result)
    if not m:
        logger.warning("[판정] 응답에서 JSON 배열을 못 찾음 — 미판정 유지")
        return None
    try:
        data = json.loads(m.group(0))
        if not isinstance(data, list):
            return None
        return data
    except json.JSONDecodeError as e:
        logger.warning(f"[판정] JSON 파싱 실패({e}) — 미판정 유지")
        return None


def judge_project(project_path: str, name: str, candidates: list[dict]) -> int:
    """한 프로젝트의 후보들을 판정 에이전트에 넘겨 verdict를 이슈에 반영. 반영 건수 반환.

    candidates: DB에서 뽑은 미판정 이슈 dict 목록(id·kind·title·source 포함).
    실패(호출/파싱)면 0을 반환하고 후보는 미판정으로 남는다(이슈 안 잃음).
    """
    if not candidates:
        return 0
    # 에이전트에 넘길 후보 표(i=인덱스) + i→issue_id 매핑
    items = [
        {"i": idx, "kind_guess": c["kind"], "title": c["title"], "source": c.get("source")}
        for idx, c in enumerate(candidates)
    ]
    id_by_i = {idx: c["id"] for idx, c in enumerate(candidates)}

    docs_path = str(Path(project_path) / "docs")
    prompt = judge_issues(name, items, docs_path)
    allowed, disallowed = tools_for("judge")
    result = run_headless(
        prompt=prompt,
        cwd=_neutral_cwd(),  # 중립 cwd — 대상 프로젝트 훅·CLAUDE.md 격리
        allowed_tools=allowed,
        disallowed_tools=disallowed,
        permission_mode="default",
        timeout=JUDGE_TIMEOUT,
        append_system_prompt=JUDGE_SYSTEM,
        add_dirs=[project_path],  # 대상 docs를 읽기 허용
    )
    verdicts = _parse_verdicts(result)
    if verdicts is None:
        return 0

    applied = 0
    for v in verdicts:
        try:
            issue_id = id_by_i.get(int(v["i"]))
            if issue_id is None:
                continue
            verdict = v.get("verdict")
            if verdict not in ("keep", "drop", "reclass"):
                continue
            due = v.get("due")
            if due in ("null", "", None):  # 문자열 "null"·빈값 정규화
                due = None
            issues_db.apply_verdict(
                issue_id=issue_id,
                verdict=verdict,
                kind=v.get("kind"),
                due=due,
                reason=(v.get("reason") or "")[:300],
            )
            applied += 1
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"[판정] {name} 항목 반영 실패({e}): {v}")
    return applied


def run_judgment(kinds: tuple[str, ...] = DEFAULT_KINDS) -> dict:
    """전 프로젝트 순회 → 미판정 후보(해당 종류)만 판정 에이전트에 넘김. 요약 통계 반환.

    per-project try/except — 한 프로젝트 판정 실패가 배치를 안 멈춘다(scan과 동일 원칙).
    """
    projects = discover_projects()
    total_candidates = 0
    total_applied = 0
    judged_projects = 0
    for p in projects:
        try:
            unjudged = [i for i in issues_db.list_unjudged(p["path"]) if i["kind"] in kinds]
            if not unjudged:
                continue
            total_candidates += len(unjudged)
            applied = judge_project(p["path"], p["name"], unjudged)
            total_applied += applied
            if applied:
                judged_projects += 1
        except Exception as e:  # 한 프로젝트 실패 → 로그만, 다음 계속
            logger.warning(f"[판정] {p['name']} 판정 실패: {e}")
    logger.info(
        f"[판정] 프로젝트 {judged_projects}개에서 후보 {total_candidates}건 중 {total_applied}건 반영"
    )
    return {
        "candidates": total_candidates,
        "applied": total_applied,
        "projects": judged_projects,
    }
