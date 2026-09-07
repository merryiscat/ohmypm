"""기록 정리(야간 ①전) — 담당이 자기 프로젝트 기록을 실제 작업과 맞추고, 코드가 커밋한다.

배경(2026-09-08 사용자 지시): 일간보고가 어긋난 기록 위에서 돌았다. 이미 끝낸 일이
status에 '착수 전'으로 남아 총괄이 틀린 전제로 물었고, 담당이 매번 대화로 정정해야 했다.
→ **보고 전에 기록부터 실제와 맞춘다.** 정리 후 재스캔까지 해야 이슈 테이블도 따라온다.

안전 설계는 조언 반영(reprocess)과 동일하다:
- 에이전트는 Read/Write/Edit만 — Bash가 없어 임의 명령·푸시를 물리적으로 못 한다.
- 커밋은 코드가 하되 **에이전트가 이번에 새로 바꾼 파일만**(실행 전 더러웠던 사용자 WIP 보호).
- docs 밖 파일이 바뀌면 커밋에서 제외한다 — 정리 단계는 기록만 건드린다.
- push 없음.
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

from src.cc.client import run_headless
from src.cc.permissions import tools_for
from src.cc.prompts import TIDY_SYSTEM, tidy_docs
from src.cc.reprocess import _commit_changes, _dirty_files, _git
from src.db import agents as agents_db
from src.db import alerts as alerts_db

TIDY_TIMEOUT = 300
LOOKBACK_DAYS = 7          # 마지막 정리 기록이 없을 때 거슬러 볼 기간
MAX_COMMITS = 40           # 프롬프트에 넣을 커밋 수 상한(토큰 보호)
MAX_DIRTY = 30
_OBJ = re.compile(r"\{.*\}", re.DOTALL)


def _since_for(path: str) -> str:
    """이 프로젝트를 마지막으로 정리한 날짜(없으면 LOOKBACK_DAYS 전)."""
    last = alerts_db.get_setting(f"tidy_last:{path}")
    if last:
        return last
    return (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")


def collect_facts(path: str, since: str) -> str:
    """에이전트에 넣을 '실제로 있었던 일' — 커밋 목록 + 지금 작업 중인 파일.

    에이전트에겐 Bash가 없으므로 git 사실은 코드가 모아서 넘긴다.
    """
    log = _git(path, "log", f"--since={since}", "--date=short",
               "--pretty=format:%h %ad %s").stdout.strip()
    commits = log.splitlines()[:MAX_COMMITS]
    dirty = sorted(_dirty_files(path))[:MAX_DIRTY]

    parts = [f"(기준: {since} 이후)"]
    parts.append("[커밋 기록]\n" + ("\n".join(f"- {c}" for c in commits) if commits else "- (없음)"))
    if dirty:
        parts.append("[지금 작업 중인 파일 — 아직 커밋 안 됨]\n"
                     + "\n".join(f"- {f}" for f in dirty))
    return "\n\n".join(parts)


def _has_change(path: str, since: str) -> bool:
    """정리할 거리가 있는가 — 새 커밋이나 작업 중 파일이 하나라도 있으면 돈다.

    변화가 없으면 LLM 콜 0회(09-02 변화 게이트와 같은 원칙).
    """
    log = _git(path, "log", f"--since={since}", "--pretty=format:%h").stdout.strip()
    return bool(log) or bool(_dirty_files(path))


def tidy_one(path: str, name: str, date: str) -> dict:
    """한 프로젝트의 기록을 실제와 맞춘다 → docs 변경만 커밋. 결과 dict."""
    if not (Path(path) / "docs" / "status.md").exists():
        return {"name": name, "path": path, "skipped": True, "reason": "작업 보드 없음"}
    since = _since_for(path)
    if not _has_change(path, since):
        alerts_db.set_setting(f"tidy_last:{path}", date)
        return {"name": name, "path": path, "skipped": True, "reason": "변화 없음"}

    allowed, disallowed = tools_for("reprocess")   # Read/Grep/Glob/Edit/Write — Bash 없음
    before = _dirty_files(path)
    out = run_headless(
        prompt=tidy_docs(name, path, collect_facts(path, since)),
        cwd=path,
        allowed_tools=allowed,
        disallowed_tools=disallowed,
        permission_mode="acceptEdits",
        timeout=TIDY_TIMEOUT,
        append_system_prompt=TIDY_SYSTEM,
        model=agents_db.model_for(path),
    )
    if out is None:
        return {"name": name, "path": path, "skipped": False, "committed": False,
                "reason": "호출 실패"}

    summary, needs_user = "", ""
    m = _OBJ.search(out)
    if m:
        try:
            d = json.loads(m.group(0))
            summary = (d.get("summary") or "").strip()
            needs_user = (d.get("needs_user") or "").strip()
        except json.JSONDecodeError:
            pass

    # 커밋 범위는 docs/ 안으로 못 박는다 — 정리 단계가 코드를 커밋하는 일은 없어야 한다.
    new_docs = {f for f in (_dirty_files(path) - before) if f.startswith("docs/")}
    if not new_docs:
        alerts_db.set_setting(f"tidy_last:{path}", date)
        return {"name": name, "path": path, "skipped": False, "committed": False,
                "reason": "고칠 것 없음", "summary": summary, "needs_user": needs_user}
    # _commit_changes는 (전체 dirty − before)를 커밋하므로, docs 밖 변경은 before에 얹어 제외한다
    guard = before | ((_dirty_files(path) - before) - new_docs)
    res = _commit_changes(path, date, guard, msg=f"chore: {date} 작업 기록 정리 (ohmyPM 담당)")
    alerts_db.set_setting(f"tidy_last:{path}", date)
    return {"name": name, "path": path, "skipped": False, "summary": summary,
            "needs_user": needs_user, **res}


def run_tidy(paths: list[str] | None = None) -> dict:
    """전 프로젝트 기록 정리 → docs 커밋(push 안 함). 일간보고 **앞에** 돈다."""
    from src.scan.discover import discover_projects

    date = datetime.now().strftime("%Y-%m-%d")
    projects = discover_projects()
    if paths:
        wanted = set(paths)
        projects = [p for p in projects if p["path"] in wanted]

    committed, asks, results = 0, [], []
    for p in projects:
        try:
            r = tidy_one(p["path"], p["name"], date)
        except Exception as e:   # 한 프로젝트 실패가 배치를 안 멈춤
            logger.warning(f"[기록정리] {p['name']} 실패: {e}")
            r = {"name": p["name"], "path": p["path"], "committed": False, "reason": str(e)}
        results.append(r)
        if r.get("committed"):
            committed += 1
        if r.get("needs_user"):
            asks.append(f"{p['name']}: {r['needs_user']}")
    logger.info(f"[기록정리] {committed}개 커밋 · 사용자 확인 요청 {len(asks)}건")
    return {"committed": committed, "asks": asks, "results": results}
