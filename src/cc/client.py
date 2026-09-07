"""Claude Code headless 호출 — claude -p subprocess.

도구·스킬·파일접근이 살아있는 Claude Code를 대상 프로젝트(cwd)에서 통째로 실행한다.
화이트리스트(allowed/disallowed)를 CLI 플래그로 강제 = confused-deputy 방지의 물리적 실장.
실패·예외는 None 반환(한 호출 실패가 배치를 안 멈춤 — odin 봇 패턴).
"""

import json
import re
import shutil
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

from src.config.settings import settings

# PreToolUse 훅(인자 레벨 방어 L3) — ohmyPM 안에 둔다(대상 에이전트가 자기 게이트를 못 고치게)
GUARD_HOOK = Path(__file__).resolve().parents[2] / "scripts" / "pretooluse_guard.ps1"

# ── 사용량 한도 감지 — 429 메시지의 리셋 시각을 붙잡아 야간 배치가 재개 시점을 안다 ──
# 예: "You've hit your session limit · resets 3am (Asia/Seoul)" / "resets 11:40am"
_LIMIT_RESET_AT: float | None = None
_RESET_RE = re.compile(r"resets (\d{1,2})(?::(\d{2}))?\s*(am|pm)", re.IGNORECASE)


def limit_reset_at() -> float | None:
    """마지막으로 감지된 한도 리셋 시각(epoch). 감지 없으면 None."""
    return _LIMIT_RESET_AT


def clear_limit() -> None:
    global _LIMIT_RESET_AT
    _LIMIT_RESET_AT = None


def _capture_limit(text: str) -> None:
    """429 한도 메시지에서 리셋 시각을 파싱해 기억한다(로컬 시간대 = Asia/Seoul 가정)."""
    global _LIMIT_RESET_AT
    if "session limit" not in text and '"api_error_status":429' not in text:
        return
    m = _RESET_RE.search(text)
    if not m:
        return
    hour, minute, ampm = int(m.group(1)), int(m.group(2) or 0), m.group(3).lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    at = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    if at.timestamp() <= time.time():
        at += timedelta(days=1)      # 이미 지난 시각이면 내일의 그 시각
    _LIMIT_RESET_AT = at.timestamp()
    logger.info(f"[한도] 세션 한도 감지 — 리셋 {at:%m-%d %H:%M}")


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
    model: str | None = None,
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
    if model:
        cmd += ["--model", model]   # 담당별 모델(opus/sonnet/haiku). 없으면 구독 기본
    if append_system_prompt:
        # ★ argv로 가는 시스템 프롬프트에서 개행 제거 — Windows claude.CMD→cmd.exe 재파싱이
        #   개행 뒤 인자(--add-dir 등)를 잘라먹는다(09-06 실증: 담당이 폴더를 못 열음).
        #   08-31 '파이프 금지' 함정의 개행 변종. 프롬프트 파일은 여러 줄로 써도 여기서 안전해진다.
        #   원인은 윈도우에서 .cmd 배치 파일을 실행하면 인자가 cmd.exe에 재해석되는 알려진 문제
        #   (Node.js CVE-2024-27980과 같은 뿌리) — 인자를 목록으로 따로 넘겨도 못 막는다.
        #   ⚠ 이 정규화는 '구분용 개행'과 '내용인 개행'을 구별하지 못한다. 지금 argv에 실리는 값은
        #   시스템 프롬프트·도구 이름·폴더 경로뿐이라 안전하지만, 개행이 의미를 갖는 값(여러 줄
        #   커밋 메시지 등)을 argv로 넘기려는 순간 내용이 조용히 뭉개진다 → 그때는 재해석 단계
        #   자체를 피하는 쪽으로(배치 파일 대신 node cli.js 직접 호출 등). docs/pending.md 참조.
        cmd += ["--append-system-prompt", " ".join(append_system_prompt.split())]
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
            full = (r.stdout or "") + (r.stderr or "")
            _capture_limit(full)   # 한도 429면 리셋 시각을 기억 — 야간 배치가 재개에 쓴다
            detail = ((r.stderr or "").strip() or (r.stdout or "").strip())[:300]
            logger.warning(f"[headless] 종료코드 {r.returncode}: {detail}")
            return None
        return json.loads(r.stdout).get("result")
    except Exception as e:
        logger.warning(f"[headless] 호출 실패: {e}")
        return None
