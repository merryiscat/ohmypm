"""문서 재가공(#4) — 당일 게시판에서 자기 프로젝트에 유용한 정보(받은 조언 등)를
그 프로젝트 자신의 docs에 반영한다. 게시판 원본 글·댓글은 남긴다(삭제 아님).

안전 설계:
- 에이전트는 Write/Edit만(Bash 없음). 임의 명령·git 푸시를 물리적으로 못 한다.
- git 커밋은 **코드가 docs/ 경로만 스코프**해서 대신 한다(push 없음 = 로컬에서 되돌리기 가능).
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
    """이 프로젝트가 쓴 글 + 그 글에 달린 (남들이 준) 조언 댓글/대댓글을 텍스트로."""
    own = [p for p in posts if p.get("project") == path]
    lines: list[str] = []
    for p in own:
        cmts = p.get("comments", [])
        if not cmts:
            continue
        lines.append(f"[내 글] {p['title']}\n{(p['body'] or '')[:400]}")
        for c in cmts:
            who = "사용자" if c["author"] == "user" else c["author"]
            lines.append(f"  - 조언({who}): {(c['body'] or '')[:300]}")
    return "\n".join(lines)


def _commit_docs(path: str, date: str) -> dict:
    """대상 프로젝트에서 docs/ 변경만 git 커밋(push 안 함). 변경 없거나 git 아니면 skip."""
    if not (Path(path) / ".git").exists():
        return {"committed": False, "reason": "git 저장소 아님"}
    if not (Path(path) / "docs").exists():
        return {"committed": False, "reason": "docs 없음"}
    _git(path, "add", "docs")
    staged = _git(path, "diff", "--cached", "--name-only", "--", "docs").stdout.strip()
    if not staged:
        return {"committed": False, "reason": "docs 변경 없음"}
    msg = f"docs: {date} 게시판 조언 재가공 (ohmyPM 담당)"
    c = _git(path, "commit", "-m", msg, "--", "docs")
    ok = c.returncode == 0
    if not ok:
        logger.warning(f"[재가공] {path} 커밋 실패: {(c.stderr or '')[:160]}")
    return {"committed": ok, "files": staged.splitlines(), "msg": msg}


def reprocess_one(path: str, name: str, posts: list[dict], date: str) -> dict:
    """한 프로젝트: 받은 조언을 자기 docs에 반영 → 코드가 docs/만 커밋. 결과 dict."""
    material = _material_for(path, posts)
    if not material.strip():
        return {"name": name, "path": path, "skipped": True, "reason": "받은 조언 없음"}
    allowed, disallowed = tools_for("reprocess")
    run_headless(
        prompt=reprocess_docs(name, path, material),
        cwd=path,
        allowed_tools=allowed,
        disallowed_tools=disallowed,
        permission_mode="acceptEdits",   # 파일 저장 자동 승인(코드 밖 쓰기는 애초에 도구가 없음)
        timeout=REPROCESS_TIMEOUT,
        append_system_prompt=REPROCESS_SYSTEM,
    )
    result = _commit_docs(path, date)
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
    logger.info(f"[재가공] {committed}개 프로젝트 docs 커밋(push 안 함)")
    return {"committed": committed, "results": results}
