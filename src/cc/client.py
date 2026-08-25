"""Claude Code headless 호출 — claude -p subprocess.

도구·스킬·파일접근이 살아있는 Claude Code를 대상 프로젝트(cwd)에서 통째로 실행한다.
화이트리스트(allowed/disallowed)를 CLI 플래그로 강제 = confused-deputy 방지의 물리적 실장.
실패·예외는 None 반환(한 호출 실패가 배치를 안 멈춤 — odin 봇 패턴).
"""

import json
import subprocess
from pathlib import Path

from loguru import logger

from src.config.settings import settings

# PreToolUse 훅(인자 레벨 방어 L3) — ohmyPM 안에 둔다(대상 에이전트가 자기 게이트를 못 고치게)
GUARD_HOOK = Path(__file__).resolve().parents[2] / "scripts" / "pretooluse_guard.ps1"


def run_headless(
    prompt: str,
    cwd: str,
    allowed_tools: list[str],
    disallowed_tools: list[str],
    permission_mode: str = "default",
    timeout: int = 300,
) -> str | None:
    """대상 프로젝트에서 claude -p 실행 → 최종 텍스트(result) 반환. 실패는 None."""
    cmd = [
        settings.cc_bin,
        "-p",
        prompt,
        "--output-format",
        "json",
        "--permission-mode",
        permission_mode,
    ]
    if allowed_tools:
        cmd += ["--allowedTools", " ".join(allowed_tools)]
    if disallowed_tools:
        cmd += ["--disallowedTools", " ".join(disallowed_tools)]
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        if r.returncode != 0:
            logger.warning(f"[headless] 종료코드 {r.returncode}: {(r.stderr or '')[:200]}")
            return None
        return json.loads(r.stdout).get("result")
    except Exception as e:
        logger.warning(f"[headless] 호출 실패: {e}")
        return None
