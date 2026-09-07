"""이슈 완결 검증 — 새 이슈가 코드에서 이미 끝난 일인지 담당이 확인(2026-09-06 사용자 확정).

판정 에이전트(중립 판정관 — 오탐·분류 담당)와는 별개의 단계다. 이슈가 처음 수집되면,
그 프로젝트를 아는 **담당 에이전트**가 실제 소스 코드와 대조해 "문서만 낡고 실제론 끝난 일"을
가려낸다(2026-09-06 naverblog '출처 권위 강화' 문서 드리프트 실증). 확인된 이슈는
verdict='resolved' + 칸반 완료로 이동한다. 지시문 본문은 prompts/issue_verify.md에 있다.

읽기 전용(도구는 담당과 동일) · 프로젝트당 headless 1콜 · 확신 없으면 열린 채 둔다.
"""

import json
import re

from loguru import logger

from src.cc.client import run_headless
from src.cc.permissions import tools_for
from src.cc.prompts import ISSUE_VERIFY_SYSTEM, issue_verify
from src.cc.room_agent import _neutral_cwd
from src.db import agents as agents_db
from src.db import issues as issues_db

_ARR_RE = re.compile(r"\[.*\]", re.DOTALL)
VERIFY_TIMEOUT = 240
MAX_PER_PROJECT = 15   # 한 콜에 넣는 이슈 상한 — 백로그가 커도 콜 하나가 비대해지지 않게


def verify_project(path: str, name: str, candidates: list[dict]) -> int:
    """한 프로젝트의 새 이슈들을 담당이 코드와 대조. resolved 처리 건수 반환."""
    if not candidates:
        return 0
    items = "\n".join(
        f"{i}. [{c['kind']}] {c['title'][:150]} (출처: {c.get('source') or '?'})"
        for i, c in enumerate(candidates)
    )
    allowed, disallowed = tools_for("daily_agent")   # Read/Grep/Glob 읽기 전용
    out = run_headless(
        prompt=agents_db.persona_prefix(path) + issue_verify(name, path, items),
        cwd=_neutral_cwd(),
        allowed_tools=allowed,
        disallowed_tools=disallowed,
        timeout=VERIFY_TIMEOUT,
        append_system_prompt=ISSUE_VERIFY_SYSTEM,
        add_dirs=[path],
        model=agents_db.model_for(path),
    )
    if not out:
        return 0
    m = _ARR_RE.search(out)
    if not m:
        return 0
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return 0
    resolved = 0
    for v in data if isinstance(data, list) else []:
        try:
            i = int(v["i"])
        except (KeyError, ValueError, TypeError):
            continue
        if not (0 <= i < len(candidates)):
            continue
        issue_id = candidates[i]["id"]
        # 쉬운 제목 — 화면 표시용(내부 기호·약어를 풀어달라는 사용자 확정 2026-09-07)
        easy = (v.get("easy_title") or "").strip()
        if easy and easy.lower() != "null":
            issues_db.set_easy_title(issue_id, easy[:100])
        evidence = (v.get("evidence") or "").strip()
        # 근거 없는 done은 무시 — resolved는 근거가 확실할 때만(프롬프트 규칙의 코드측 방어)
        if not v.get("done") or not evidence or evidence.lower() == "null":
            continue
        issues_db.apply_verdict(issue_id, "resolved", reason=("코드 확인: " + evidence)[:300])
        issues_db.set_status(issue_id, "resolved")
        resolved += 1
    return resolved


def run_issue_verification(paths: list[str] | None = None) -> dict:
    """전(또는 지정) 프로젝트의 미판정 이슈를 담당이 코드 대조. 요약 통계 반환.

    스캔 직후·판정 전에 돈다: 여기서 resolved 처리된 이슈는 verdict가 생겨 판정 대상에서 빠진다.
    """
    from src.scan.discover import discover_projects

    projects = discover_projects()
    if paths:
        wanted = set(paths)
        projects = [p for p in projects if p["path"] in wanted]
    total, resolved_n, checked_projects = 0, 0, 0
    for p in projects:
        try:
            # 대상: ①미판정 새 이슈 ②쉬운 제목이 아직 없는 기존 이슈(백로그 자연 치유)
            mine = [i for i in issues_db.list_issues() if i["project"] == p["path"]]
            cands = [
                i for i in mine
                if i.get("verdict") is None
                or (not i.get("easy_title") and i["kind"] != "done" and i.get("verdict") != "drop")
            ][:MAX_PER_PROJECT]
            if not cands:
                continue
            total += len(cands)
            checked_projects += 1
            resolved_n += verify_project(p["path"], p["name"], cands)
        except Exception as e:   # 한 프로젝트 실패가 배치를 안 멈춤
            logger.warning(f"[완결검증] {p['name']} 실패: {e}")
    logger.info(f"[완결검증] {checked_projects}개 프로젝트 · 이슈 {total}건 대조 · {resolved_n}건 완료 처리")
    return {"projects": checked_projects, "checked": total, "resolved": resolved_n}
