"""조언 반영(#4) — 당일 게시판에서 받은 조언을 담당이 프로젝트에 실제로 반영한다.
반영처(docs·코드 주석·설정 등)는 조언 성격에 맞게 에이전트가 판단한다(2026-09-06 사용자
확정: "꼭 docs가 아니더라도 반영할 수 있는 방법을 찾고 반영해"). 게시판 원본은 남긴다.

안전 설계:
- 에이전트는 Write/Edit만(Bash 없음). 임의 명령·git 푸시를 물리적으로 못 한다.
- git 커밋은 코드가 대신 하되, **에이전트가 이번에 새로 바꾼 파일만** 스테이징한다 —
  실행 전 이미 더러웠던(사용자 작업 중) 파일은 건드리지 않는다(WIP 보호). push 없음.
- cwd=대상 프로젝트라 그 프로젝트 규약(CLAUDE.md·docs)을 그대로 따른다.
"""

import subprocess
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.cc.client import run_headless
from src.cc.permissions import tools_for
from src.cc.prompts import REPROCESS_SYSTEM, reprocess_docs
from src.db import board as board_db

REPROCESS_TIMEOUT = 300


def _git(path: str, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", path, *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )


def _material_for(path: str, posts: list[dict]) -> str:
    """이 프로젝트가 쓴 글 + 그 글에 달린 조언을 스레드(댓글→답글) 구조로 텍스트화.

    왕복(대댓글·대대댓글)까지 이어진 논의는 결론이 아래쪽에 있으므로, 들여쓰기로
    흐름이 보이게 해서 에이전트가 '정리된 결론'을 집어내기 쉽게 한다.
    """
    own = [p for p in posts if p.get("project") == path]
    lines: list[str] = []
    for p in own:
        cmts = p.get("comments", [])
        if not cmts:
            continue
        lines.append(f"[내 글] {p['title']}\n{(p['body'] or '')[:400]}")
        def _who(c: dict) -> str:
            return "사용자" if c["author"] == "user" else c["author"]
        def _thread(parent_id: int | None, depth: int) -> None:
            for c in cmts:
                if c.get("parent_id") != parent_id:
                    continue
                pad = "  " * (depth + 1)
                label = "조언" if depth == 0 else "답글"
                lines.append(f"{pad}- {label}({_who(c)}): {(c['body'] or '')[:300]}")
                _thread(c["id"], depth + 1)
        _thread(None, 0)
    return "\n".join(lines)


def _dirty_files(path: str) -> set[str]:
    """git이 보는 변경 파일 목록(스테이징 여부 무관). 커밋 범위 산정용."""
    out = _git(path, "status", "--porcelain").stdout
    return {ln[3:].strip().strip('"') for ln in out.splitlines() if ln.strip()}


def _commit_changes(path: str, date: str, before: set[str]) -> dict:
    """에이전트 실행으로 **새로 바뀐 파일만** 커밋(push 안 함).

    before = 실행 전 변경 파일 스냅샷. 그 전부터 더러웠던 파일(사용자 작업 중)은
    스테이징하지 않는다 — 사용자 WIP가 에이전트 커밋에 섞이는 사고 방지.
    """
    if not (Path(path) / ".git").exists():
        return {"committed": False, "reason": "git 저장소 아님"}
    new_files = sorted(_dirty_files(path) - before)
    if not new_files:
        return {"committed": False, "reason": "새 변경 없음"}
    _git(path, "add", "--", *new_files)
    staged = _git(path, "diff", "--cached", "--name-only").stdout.strip()
    if not staged:
        return {"committed": False, "reason": "스테이징 실패"}
    msg = f"chore: {date} 게시판 조언 반영 (ohmyPM 담당)"
    c = _git(path, "commit", "-m", msg)
    ok = c.returncode == 0
    if not ok:
        logger.warning(f"[조언반영] {path} 커밋 실패: {(c.stderr or '')[:160]}")
    return {"committed": ok, "files": staged.splitlines(), "msg": msg}


def reprocess_one(path: str, name: str, posts: list[dict], date: str) -> dict:
    """한 프로젝트: 받은 조언을 반영(반영처는 에이전트 판단) → 코드가 새 변경만 커밋. 결과 dict."""
    material = _material_for(path, posts)
    if not material.strip():
        return {"name": name, "path": path, "skipped": True, "reason": "받은 조언 없음"}
    allowed, disallowed = tools_for("reprocess")
    from src.db import agents as agents_db

    before = _dirty_files(path)   # 실행 전 스냅샷 — 사용자 WIP와 에이전트 변경을 구분
    run_headless(
        prompt=reprocess_docs(name, path, material),
        cwd=path,
        allowed_tools=allowed,
        disallowed_tools=disallowed,
        permission_mode="acceptEdits",   # 파일 저장 자동 승인(임의 명령은 애초에 도구가 없음)
        timeout=REPROCESS_TIMEOUT,
        append_system_prompt=REPROCESS_SYSTEM,
        model=agents_db.model_for(path),
    )
    result = _commit_changes(path, date, before)
    return {"name": name, "path": path, "skipped": False, **result}


def run_reprocess(paths: list[str] | None = None) -> dict:
    """당일 게시판 조언을 각 담당이 자기 docs에 반영(git 커밋, push 안 함). 커밋 건수 반환."""
    date = datetime.now().strftime("%Y-%m-%d")
    all_posts = board_db.list_posts(board_db.DAILY_BOARD)
    # ★ 오늘(day=date) 올라온 글만 재가공 대상 — 안 그러면 어제 조언을 매일 다시 반영해
    #   중복 커밋이 쌓인다(09-01 야간에 08-31 조언이 재처리된 버그). material도 오늘 글 기준.
    posts = [p for p in all_posts if p.get("day") == date]
    targets: dict[str, str] = {}
    for p in posts:
        if p.get("project") and p.get("comments"):
            targets.setdefault(p["project"], p["author"])
    if paths:
        wanted = set(paths)
        targets = {k: v for k, v in targets.items() if k in wanted}

    committed, results = 0, []
    for path, name in targets.items():
        try:
            r = reprocess_one(path, name, posts, date)
        except Exception as e:  # 한 프로젝트 실패가 전체를 안 멈춤
            logger.warning(f"[재가공] {name} 실패: {e}")
            r = {"name": name, "path": path, "skipped": False, "committed": False, "reason": str(e)}
        results.append(r)
        if r.get("committed"):
            committed += 1
    logger.info(f"[조언반영] {committed}개 프로젝트 커밋(push 안 함)")
    return {"committed": committed, "results": results}
