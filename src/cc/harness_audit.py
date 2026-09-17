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
from src.db import messages as messages_db
from src.proc import NO_WINDOW

AUDIT_TIMEOUT = 360
AUDIT_CONCURRENCY = 3          # 한도(속도/사용량) 폭주 방지 — 일간보고보다 보수적으로

# 코드가 커밋을 허용하는 경로(그 외 에이전트가 쓴 것은 커밋 안 됨 = 안전 스코프)
COMMIT_ALLOWLIST = ["CLAUDE.md", ".gitignore", "README.md", "docs", ".claude"]

# 처음 세팅 시 .gitignore에 넣는 docs 차단 줄(2026-09-14 사용자 지시 — odin-3.0에서 작업 보드·
# 보류 대장이 공개 저장소에 올라간 뒤 뒤늦게 뺐다). ohmyPM은 docs를 로컬 파일로 직접 읽으므로 연동 무관.
DOCS_IGNORE_BLOCK = (
    "# 위키(docs/) — 작업 보드·보류 대장 등 내부 기록이라 로컬 전용(ohmyPM은 로컬 파일을 직접 읽는다)\n"
    "/docs/\n"
)


def _git(path: str, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", path, *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
        creationflags=NO_WINDOW,
    )


def _is_first_setup(path: str) -> bool:
    """계약 파일(status.md·pending.md)이 아직 없음 = 골격 생성 전 = 처음 세팅."""
    docs = Path(path) / "docs"
    return not ((docs / "status.md").exists() and (docs / "pending.md").exists())


def _ensure_docs_ignored(path: str) -> dict:
    """처음 세팅 때 .gitignore에 docs 차단을 코드가 결정론으로 넣는다(에이전트 재량에 안 맡김).

    이미 막혀 있으면 손대지 않는다. 이미 git이 추적 중인 docs 파일은 .gitignore로 안 빠지므로
    (추적 해제 = 다음 push에 원격에서 사라짐 → 사용자 결정) 목록만 돌려줘 리포트에 올린다.
    """
    if not (Path(path) / ".git").exists():
        return {"added": False, "tracked": []}
    tracked = [f for f in _git(path, "ls-files", "--", "docs").stdout.splitlines() if f.strip()]
    # 존재하지 않는 경로도 패턴으로 판정된다 — docs/·/docs/·docs 등 어떤 표기든 한 번에 확인
    if _git(path, "check-ignore", "-q", "--no-index", "docs/status.md").returncode == 0:
        return {"added": False, "tracked": tracked}
    gi = Path(path) / ".gitignore"
    text = ""
    if gi.exists():   # newline="" — 읽을 때 CRLF를 LF로 바꾸면 기존 줄바꿈 형식이 통째로 뒤바뀐다
        with open(gi, encoding="utf-8", errors="replace", newline="") as f:
            text = f.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    if text and not text.endswith(("\n", "\r")):
        text += nl
    text += (nl if text else "") + DOCS_IGNORE_BLOCK.replace("\n", nl)
    with open(gi, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return {"added": True, "tracked": tracked}


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
    # ★ 커밋 pathspec은 allowlist 경로가 아니라 '실제 스테이징된 파일'로 준다 — allowlist에 있으나
    #   git 미추적인 경로(.claude 등)를 pathspec에 넣으면 'did not match'로 커밋 전체가 실패한다
    #   (Ts_skin_maker에서 .claude 미추적으로 실패 실증, 2026-09-01).
    staged_files = staged.splitlines()
    msg = f"harness: {date} 환경·하네스 점검 자동 반영 (ohmyPM)"
    c = _git(path, "commit", "-m", msg, "--", *staged_files)
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
    from src.cc.onboarding import meta_block

    # 처음 세팅이면 에이전트가 docs를 만들기 **전에** .gitignore부터 막는다(커밋에 섞이지 않게)
    docs_ignore = _ensure_docs_ignored(path) if _is_first_setup(path) else None

    report = run_headless(
        prompt=harness_audit_prompt(name, path, BASELINE_NOTE, meta_block(path)),
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
    if docs_ignore and (docs_ignore["added"] or docs_ignore["tracked"]):
        notes = []
        if docs_ignore["added"]:
            notes.append("- .gitignore에 `/docs/` 추가 — 위키는 로컬 전용(ohmyPM 코드가 처음 세팅 때 자동 반영)")
        if docs_ignore["tracked"]:
            files = ", ".join(docs_ignore["tracked"][:10])
            notes.append(f"- ⚠ 이미 git이 추적 중인 docs 파일이 있어 .gitignore만으로는 안 빠짐: {files}"
                         " — 빼려면 `git rm -r --cached docs` 후 커밋(푸시 시 원격에서 사라짐, 사용자 결정)")
        report += "\n\n## docs 로컬 전용 처리\n" + "\n".join(notes)
    commit = _commit_harness(path, date)
    return {"name": name, "path": path, "failed": False, "report": report, **commit}


def run_harness_audit(paths: list[str] | None = None,
                      concurrency: int = AUDIT_CONCURRENCY) -> dict:
    """전(또는 지정) 프로젝트 하네스 감사. 병렬(보수적) + 리포트는 담당 방에 PM 메시지로.

    paths: 지정 시 그 프로젝트만(검증·부분 실행·골격 생성 승인). None이면 전 프로젝트.
    게시판에는 올리지 않는다 — 게시판은 담당 창작 글 전용(2026-09-06 재설계).
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

    for r in ok:
        messages_db.add_message(r["path"], "pm", "[골격 생성 리포트]\n\n" + (r.get("report") or ""))
    return {"date": date, "audited": len(ok), "committed": committed,
            "failed": len(results) - len(ok), "results": results}
