"""PM 온보딩 검토 — 프로젝트의 초기 세팅·하네스(스킬·MCP·설정)를 read-only로 점검.

담당 에이전트 통로(중립 cwd + --add-dir로 대상 폴더 열기, 읽기 전용)를 그대로 재사용한다.
결과 리포트는 그 프로젝트의 담당 방(room=path)에 'pm' 메시지로 남겨 화면 채팅에서 본다.
"""

from loguru import logger

from src.cc.client import run_headless
from src.cc.permissions import tools_for
from src.cc.prompts import ONBOARDING_SYSTEM, onboarding_review
from src.cc.room_agent import _neutral_cwd
from src.db import messages as messages_db

ONBOARD_TIMEOUT = 240


def review_project(path: str, name: str) -> str:
    """프로젝트 온보딩을 진단하고 리포트를 담당 방에 PM 메시지로 남긴다. 리포트 반환."""
    allowed, disallowed = tools_for("daily_agent")   # Read/Grep/Glob 읽기 전용
    out = run_headless(
        prompt=onboarding_review(name, path),
        cwd=_neutral_cwd(),
        allowed_tools=allowed,
        disallowed_tools=disallowed,
        timeout=ONBOARD_TIMEOUT,
        append_system_prompt=ONBOARDING_SYSTEM,
        add_dirs=[path],
    )
    report = (out or "").strip() or "(온보딩 검토 응답 없음)"
    messages_db.add_message(path, "pm", "[온보딩 검토]\n\n" + report)
    logger.info(f"[온보딩] {name} 검토 완료 {len(report)}자")
    return report
