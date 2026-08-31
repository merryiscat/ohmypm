"""Claude Code headless 호출 — claude -p subprocess.

도구·스킬·파일접근이 살아있는 Claude Code를 대상 프로젝트(cwd)에서 통째로 실행한다.
화이트리스트(allowed/disallowed)를 CLI 플래그로 강제 = confused-deputy 방지의 물리적 실장.
실패·예외는 None 반환(한 호출 실패가 배치를 안 멈춤 — odin 봇 패턴).
"""

import json
import shutil
import subprocess
from pathlib import Path

from loguru import logger

from src.config.settings import settings

# PreToolUse 훅(인자 레벨 방어 L3) — ohmyPM 안에 둔다(대상 에이전트가 자기 게이트를 못 고치게)
GUARD_HOOK = Path(__file__).resolve().parents[2] / "scripts" / "pretooluse_guard.ps1"


def _resolve_bin() -> str:
    """cc_bin 실행파일 경로 해석. Windows에선 `claude`가 claude.CMD 셈이라
    subprocess가 확장자 없이는 못 찾는다 → shutil.which로 실경로를 잡는다."""
    return shutil.which(settings.cc_bin) or settings.cc_bin


def run_headless(
    prompt: str,
    cwd: str,
    allowed_tools: list[str],
    disallowed_tools: list[str],
    permission_mode: str = "default",
    timeout: int = 300,
    append_system_prompt: str | None = None,
    add_dirs: list[str] | None = None,
) -> str | None:
    """claude -p 실행 → 최종 텍스트(result) 반환. 실패는 None.

    ★ 프롬프트는 argv가 아니라 stdin으로 넘긴다 — Windows claude.CMD→cmd.exe가 특수문자(·→—"[]{})
      투성이 대형 프롬프트를 argv로 받으면 뭉갠다(후보 리스트·경로가 잘려 판정 불가). stdin은 무손실.
    ★ append_system_prompt로 대상 프로젝트 CLAUDE.md의 대화체 지시를 덮어쓴다(구조화 출력 강제).
    ★ 판정(읽기)은 중립 cwd + add_dirs로 대상을 '읽기만' — cwd=대상 프로젝트로 두면 그 프로젝트
      SessionStart 훅이 실행되고 CLAUDE.md 대화체가 JSON 출력을 깨므로. (편집 태스크는 cwd=대상 유지)
    """
    cmd = [
        _resolve_bin(),
        "-p",
        "--output-format",
        "json",
        "--permission-mode",
        permission_mode,
    ]
    if append_system_prompt:
        cmd += ["--append-system-prompt", append_system_prompt]
    for d in add_dirs or []:
        cmd += ["--add-dir", d]
    if allowed_tools:
        cmd += ["--allowedTools", " ".join(allowed_tools)]
    if disallowed_tools:
        cmd += ["--disallowedTools", " ".join(disallowed_tools)]
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            input=prompt,  # 프롬프트는 stdin으로 (argv 뭉갬 회피)
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        if r.returncode != 0:
            # ★ 실패 원인은 stderr가 비고 stdout(JSON)에 담기는 경우가 많다(사용량·속도 한도 등).
            #   둘 다 로깅해야 사후 진단이 된다(2026-09-01 야간 전량 실패를 stderr 빈 값이라 놓침).
            detail = ((r.stderr or "").strip() or (r.stdout or "").strip())[:300]
            logger.warning(f"[headless] 종료코드 {r.returncode}: {detail}")
            return None
        return json.loads(r.stdout).get("result")
    except Exception as e:
        logger.warning(f"[headless] 호출 실패: {e}")
        return None
