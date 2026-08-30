"""프로젝트 담당 에이전트 — 그 프로젝트의 CLAUDE.md·docs를 읽고 룸에서 대화한다.

judge와 같은 headless 통로(`claude -p`)를 읽기 전용으로 재사용한다. 추가 구독·API 불필요.
지금은 '사용자 ↔ 담당 에이전트' 대화용이지만, 계약(방의 최근 대화 → 답 한 줄 추가)을
그대로 두면 나중 'PM ↔ 담당 일간보고'·'담당들끼리 자유채팅'에도 재사용할 수 있다.
"""

import tempfile
from pathlib import Path

from src.cc.client import run_headless
from src.cc.permissions import tools_for
from src.cc.prompts import ROOM_SYSTEM, room_chat
from src.db import messages as messages_db

AGENT_AUTHOR = "agent"      # 담당 에이전트 발화의 author (화면에서 왼쪽 버블)
CHAT_TIMEOUT = 180          # 콜드스타트 + 파일 탐색 여유
HISTORY_LIMIT = 20          # 프롬프트에 넣을 최근 대화 줄 수

# 담당 에이전트는 중립 cwd에서 돈다(대상 SessionStart 훅·CLAUDE.md 대화체 격리).
# 대상 폴더는 --add-dir로 '읽기만' 열어준다. 프로세스당 한 번 만들어 재사용.
_NEUTRAL_CWD: str | None = None


def _neutral_cwd() -> str:
    global _NEUTRAL_CWD
    if _NEUTRAL_CWD is None or not Path(_NEUTRAL_CWD).exists():
        _NEUTRAL_CWD = tempfile.mkdtemp(prefix="ohmypm_room_")
    return _NEUTRAL_CWD


def reply_in_room(project_path: str, name: str) -> None:
    """방(room=project_path)의 최근 대화를 담당 에이전트가 읽고, 답 한 줄을 방에 남긴다.

    실패해도 방에 안내 메시지를 남겨 '조용한 실패'를 피한다(놓침0 원칙).
    백그라운드에서 호출된다 — HTTP 응답을 막지 않는다.
    """
    history = messages_db.list_messages(project_path, limit=HISTORY_LIMIT)
    hist_txt = "\n".join(f"{m['author']}: {m['body']}" for m in history)
    prompt = room_chat(name, project_path, hist_txt)
    allowed, disallowed = tools_for("room_chat")
    result = run_headless(
        prompt=prompt,
        cwd=_neutral_cwd(),           # 중립 cwd — 대상 훅·CLAUDE.md 격리
        allowed_tools=allowed,
        disallowed_tools=disallowed,
        permission_mode="default",
        timeout=CHAT_TIMEOUT,
        append_system_prompt=ROOM_SYSTEM,
        add_dirs=[project_path],      # 대상 CLAUDE.md·docs를 읽기 허용
    )
    body = (result or "").strip() or "(지금은 답을 만들지 못했어 — 잠시 후 다시 시도해줘)"
    messages_db.add_message(project_path, AGENT_AUTHOR, body)
