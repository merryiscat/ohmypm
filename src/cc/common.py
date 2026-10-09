"""여러 모듈이 같이 쓰는 작은 헬퍼 — 중립 작업 폴더, 도구 커밋 판정, JSON 추출, 자기 자신 판정.

2026-10-09 2차 리뉴얼 때 신설. 그전엔 같은 함수가 room_agent·expert·daily_report에 세 벌씩 있었다.
"""

import json
import os
import re
import tempfile
from pathlib import Path

# 저장소 루트(ohmyPM 자신) — 파일 위치에서 구하므로 PC마다 경로가 달라도 맞는다
REPO_ROOT = Path(__file__).resolve().parents[2]

# 담당 에이전트는 중립 cwd에서 돈다(대상 프로젝트의 SessionStart 훅·CLAUDE.md 대화체 격리).
# 대상 폴더는 --add-dir로만 열어 준다. 프로세스당 한 번 만들어 재사용.
_NEUTRAL_CWD: str | None = None


def neutral_cwd() -> str:
    """헤드리스 호출에 쓰는 빈 임시 폴더 경로. 없으면 만든다."""
    global _NEUTRAL_CWD
    if _NEUTRAL_CWD is None or not Path(_NEUTRAL_CWD).exists():
        _NEUTRAL_CWD = tempfile.mkdtemp(prefix="ohmypm_room_")
    return _NEUTRAL_CWD


# 활동 신호에서 제외할 커밋 — 제목에 이 말이 들어간 커밋은 도구가 만든 것으로 본다(대소문자 무시).
#   ohmypm             : ohmyPM이 남기는 커밋
#   kickoff-workspaces : 옛 작업 구조 배포(2026-09)가 대상 프로젝트에 남긴 커밋
TOOL_COMMIT_MARKS = ("ohmypm", "kickoff-workspaces")


def tool_commit(subject: str) -> bool:
    """커밋 제목이 도구가 만든 것인지 — 대소문자를 구분하지 않고 표식을 찾는다."""
    low = (subject or "").lower()
    return any(mark in low for mark in TOOL_COMMIT_MARKS)


_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)   # 응답에서 첫 JSON 객체
_ARR_RE = re.compile(r"\[.*\]", re.DOTALL)   # 응답에서 첫 JSON 배열


def parse_json_object(text: str | None) -> dict | None:
    """모델 응답 텍스트에서 JSON 객체 하나를 뽑는다. 없거나 깨졌으면 None."""
    if not text:
        return None
    m = _OBJ_RE.search(text)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return d if isinstance(d, dict) else None


def parse_json_array(text: str | None) -> list | None:
    """모델 응답 텍스트에서 JSON 배열 하나를 뽑는다. 없거나 깨졌으면 None."""
    if not text:
        return None
    m = _ARR_RE.search(text)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return d if isinstance(d, list) else None


def is_self_project(path: str) -> bool:
    """이 경로가 ohmyPM 자기 자신인가 — 관리 대상 루트 안에 ohmyPM이 들어 있을 때 제외용."""
    if not path:
        return False
    return os.path.normcase(os.path.normpath(path)) == os.path.normcase(str(REPO_ROOT))
