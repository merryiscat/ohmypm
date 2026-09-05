"""PM 온보딩 검토 — 프로젝트의 초기 세팅·하네스(스킬·MCP·설정)를 read-only로 점검.

담당 에이전트 통로(중립 cwd + --add-dir로 대상 폴더 열기, 읽기 전용)를 그대로 재사용한다.
결과 리포트는 그 프로젝트의 담당 방(room=path)에 'pm' 메시지로 남겨 화면 채팅에서 본다.

신규 편입 프로젝트의 첫 관문(2026-09-06 사용자 확정): 파일을 만들기 전에 PM이 하네스
전문가 자문을 끼고 **검토 리포트만** 낸다. 골격 생성(쓰기)은 사용자가 승인할 때만.
분류(내 프로젝트/외부 클론/보관용)·시크릿 추적 같은 결정론 판정 재료는 에이전트가 아니라
**코드가 공급**한다(전문가 자문 P0 — 정책은 모델 출력이 아니다).
"""

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from loguru import logger

from src.cc.client import run_headless
from src.cc.permissions import tools_for
from src.cc.prompts import ONBOARDING_SYSTEM, onboarding_review
from src.cc.room_agent import _neutral_cwd
from src.db import messages as messages_db

ONBOARD_TIMEOUT = 240
OWNER_MARK = "merryiscat"        # 이 문자열이 origin에 있으면 내 저장소
ARCHIVE_AFTER_DAYS = 365         # 마지막 커밋이 이보다 오래되면 보관용 추정(전문가 권고 기준)
SECRET_GLOBS = (".env", ".env.*", "*.pem", "*.key", "*credentials*", "*secret*")


def _git(path: str, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=15)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def project_meta(path: str) -> dict:
    """저장소 메타 + 결정론 분류. 에이전트 판정에 재료로 주입한다.

    분류: mine(내 프로젝트) / external(외부 클론 — origin이 내 소유 아님) /
    archive(보관용 — 마지막 커밋 1년 이상 전) / non-git(git 아님).
    tracked_secrets: git이 추적 중인 시크릿 의심 파일(.gitignore로는 이미 늦은 것들).
    """
    if not (Path(path) / ".git").exists():
        return {"cls": "non-git", "origin": None, "last_commit": None, "tracked_secrets": []}
    origin = _git(path, "config", "--get", "remote.origin.url") or None
    last = _git(path, "log", "-1", "--format=%ci") or None
    tracked = []
    for g in SECRET_GLOBS:
        tracked += [f for f in _git(path, "ls-files", "--", g, f"**/{g}").splitlines() if f]
    upstream = _git(path, "config", "--get", "remote.upstream.url") or None
    cls = "mine"
    if origin and OWNER_MARK not in origin.lower():
        cls = "external"
    elif upstream:
        cls = "external"   # 내 계정 포크라도 upstream 리모트가 있으면 외부 코드 계열로 취급
    elif last:
        try:
            dt = datetime.strptime(last[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - dt > timedelta(days=ARCHIVE_AFTER_DAYS):
                cls = "archive"
        except ValueError:
            pass
    return {"cls": cls, "origin": origin, "last_commit": last, "tracked_secrets": sorted(set(tracked))}


CLS_LABEL = {"mine": "내 프로젝트", "external": "외부 클론(origin이 내 소유 아님)",
             "archive": "보관용 추정(마지막 커밋 1년 이상 전)", "non-git": "git 저장소 아님"}


def meta_block(path: str) -> str:
    """코드가 뽑은 메타를 프롬프트 주입용 텍스트로."""
    m = project_meta(path)
    secrets = "\n".join(f"  - {f}" for f in m["tracked_secrets"]) or "  (없음)"
    return (
        f"[저장소 메타 — 코드가 결정론으로 판정한 값, 이 분류를 따르라]\n"
        f"- 분류: {CLS_LABEL[m['cls']]}\n"
        f"- origin: {m['origin'] or '(없음 — 로컬 전용)'}\n"
        f"- 마지막 커밋: {m['last_commit'] or '(없음)'}\n"
        f"- git 추적 중인 시크릿 의심 파일(.gitignore로는 이미 늦음 — 발견 시 최우선 경고):\n{secrets}"
    )


def _harness_ref() -> str:
    """하네스 전문가 위키를 온보딩 근거로 자동 주입(자동 자문). 위키 앞부분만 발췌."""
    from src.cc import expert as ex

    return ex.read_wiki("harness")[:3500]


def review_project(path: str, name: str, post_board: bool = False) -> str:
    """프로젝트 온보딩을 진단하고 리포트를 담당 방에 PM 메시지로 남긴다. 리포트 반환.

    하네스 전문가 위키를 자동 자문하고, 코드가 뽑은 저장소 분류·시크릿 메타를 주입한다.
    post_board=True면 게시판에도 글로 올린다(야간 신규 편입 검토 표출용).
    """
    allowed, disallowed = tools_for("daily_agent")   # Read/Grep/Glob 읽기 전용
    out = run_headless(
        prompt=onboarding_review(name, path, _harness_ref(), meta_block(path)),
        cwd=_neutral_cwd(),
        allowed_tools=allowed,
        disallowed_tools=disallowed,
        timeout=ONBOARD_TIMEOUT,
        append_system_prompt=ONBOARDING_SYSTEM,
        add_dirs=[path],
    )
    report = (out or "").strip() or "(온보딩 검토 응답 없음)"
    messages_db.add_message(path, "pm", "[온보딩 검토]\n\n" + report)
    if post_board and out:
        from src.db import board as board_db

        board_db.add_post(author=name, title="신규 편입 검토 — 골격 생성은 승인 대기",
                          body=report, project=path, day=datetime.now().strftime("%Y-%m-%d"))
    logger.info(f"[온보딩] {name} 검토 완료 {len(report)}자")
    return report
