"""일일보고 하네스 감사 — 각 프로젝트의 업무환경·하네스를 점검하고 빠진 기본기를 채운다.

온보딩 검토(#3, 읽기전용 진단)의 '쓰기 버전'. 사용자 지시(2026-09-01):
- 모든 프로젝트에 '비개발자 배려' 기본 문장을 CLAUDE.md에 넣는다(없으면 자동 추가).
- 새 프로젝트를 잘 시작·운영할 하네스(파일형: docs·gitignore·README·로컬 스킬)를 자동으로 채운다.

안전 설계(#4 재가공과 동일 계열):
- 에이전트는 Read/Grep/Glob/Write/Edit만(Bash 없음, acceptEdits). npx 서드파티 스킬 설치는 물리적으로
  불가 → 리포트에 '권장'으로만(사용자 글로벌 규칙 '설치는 확인 후'와 충돌 안 함).
- git 커밋은 **코드가 안전 경로 allowlist만** 스코프해서 대신 한다(push 없음 = 로컬에서 되돌리기 가능).
- cwd=대상 프로젝트라 그 프로젝트 규약을 따른다.
"""

import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.cc.client import run_headless
from src.cc.permissions import tools_for
from src.cc.prompts import BASELINE_NOTE, HARNESS_AUDIT_SYSTEM, harness_audit_prompt
from src.cc.room_agent import _neutral_cwd
from src.db import board as board_db

AUDIT_TIMEOUT = 360
AUDIT_CONCURRENCY = 3          # 한도(속도/사용량) 폭주 방지 — 일간보고보다 보수적으로

# 코드가 커밋을 허용하는 경로(그 외 에이전트가 쓴 것은 커밋 안 됨 = 안전 스코프)
COMMIT_ALLOWLIST = ["CLAUDE.md", ".gitignore", "README.md", "docs", ".claude"]


def _git(path: str, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", path, *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )


def _commit_harness(path: str, date: str) -> dict:
    """안전 경로 allowlist만 git 커밋(push 안 함). 변경 없거나 git 아니면 skip."""
    if not (Path(path) / ".git").exists():
        return {"committed": False, "reason": "git 저장소 아님"}
    present = [p for p in COMMIT_ALLOWLIST if (Path(path) / p).exists()]
    if not present:
        return {"committed": False, "reason": "대상 경로 없음"}
    _git(path, "add", *present)
    staged = _git(path, "diff", "--cached", "--name-only", "--", *present).stdout.strip()
    if not staged:
        return {"committed": False, "reason": "변경 없음"}
    msg = f"harness: {date} 환경·하네스 점검 자동 반영 (ohmyPM)"
    c = _git(path, "commit", "-m", msg, "--", *present)
    ok = c.returncode == 0
    if not ok:
        logger.warning(f"[하네스감사] {path} 커밋 실패: {(c.stderr or '')[:160]}")
    return {"committed": ok, "files": staged.splitlines(), "msg": msg}


def audit_one(path: str, name: str, date: str) -> dict:
    """한 프로젝트: 환경·하네스 점검 + 빠진 기본기 파일 반영 → 코드가 안전경로만 커밋. 결과 dict."""
    allowed, disallowed = tools_for("reprocess")   # Read/Grep/Glob/Write/Edit (Bash 없음)
    # ★ 중립 cwd + add_dir로 연다(cwd=대상으로 두면 그 프로젝트의 블로킹 Stop 훅·대화체 CLAUDE.md가
    #   최종 출력을 뭉개고, '할 일 없음'일 때 턴 종료를 막아 타임아웃난다 — bobusang에서 실증).
    #   쓰기는 add_dir 안의 절대경로로 하고, git 커밋은 코드가 git -C로 한다.
    report = run_headless(
        prompt=harness_audit_prompt(name, path, BASELINE_NOTE),
        cwd=_neutral_cwd(),
        add_dirs=[path],
        allowed_tools=allowed,
        disallowed_tools=disallowed,
        permission_mode="acceptEdits",
        timeout=AUDIT_TIMEOUT,
        append_system_prompt=HARNESS_AUDIT_SYSTEM,
    )
    report = (report or "").strip()
    if not report:   # headless 실패(한도 등) — 커밋도 하지 않는다
        return {"name": name, "path": path, "failed": True, "committed": False,
                "report": "(하네스 감사 무응답 — 재시도 필요)"}
    commit = _commit_harness(path, date)
    return {"name": name, "path": path, "failed": False, "report": report, **commit}


def run_harness_audit(paths: list[str] | None = None,
                      concurrency: int = AUDIT_CONCURRENCY, post_board: bool = True) -> dict:
    """전(또는 지정) 프로젝트 하네스 감사. 병렬(보수적) + 각 결과를 게시판 글로(일일보고 표출).

    paths: 지정 시 그 프로젝트만(검증·부분 실행). None이면 위키 있는 전 프로젝트.
    post_board: True면 각 감사 리포트를 게시판 글로 올린다(일일보고 흐름).
    """
    from src.scan.discover import discover_projects

    projects = discover_projects()
    if paths:
        wanted = set(paths)
        projects = [p for p in projects if p["path"] in wanted]
    date = datetime.now().strftime("%Y-%m-%d")

    def worker(p: dict) -> dict:
        try:
            return audit_one(p["path"], p["name"], date)
        except Exception as e:  # 한 프로젝트 실패가 전체를 안 멈춤
            logger.warning(f"[하네스감사] {p['name']} 실패: {e}")
            return {"name": p["name"], "path": p["path"], "failed": True,
                    "committed": False, "report": f"(감사 실패: {e})"}

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        for r in ex.map(worker, projects):
            results.append(r)

    committed = sum(1 for r in results if r.get("committed"))
    ok = [r for r in results if not r.get("failed")]
    logger.info(f"[하네스감사] 완료 {len(ok)}개 · 커밋 {committed}개 · 실패 {len(results) - len(ok)}개")

    if post_board:
        for r in ok:
            first = (r.get("report") or "").splitlines()
            head = next((l for l in first if l.strip() and not l.startswith("#")), "")
            title = f"{r['name']}: 하네스 점검 — {head[:30] or '완료'}"
            board_db.add_post(author=r["name"], title=title,
                              body=r.get("report", ""), project=r.get("path"), day=date)
    return {"date": date, "audited": len(ok), "committed": committed,
            "failed": len(results) - len(ok), "results": results}
