"""프로젝트 담당 에이전트 — 그 프로젝트의 CLAUDE.md·docs를 읽고 룸에서 대화한다.

judge와 같은 headless 통로(`claude -p`)를 읽기 전용으로 재사용한다. 추가 구독·API 불필요.
지금은 '사용자 ↔ 담당 에이전트' 대화용이지만, 계약(방의 최근 대화 → 답 한 줄 추가)을
그대로 두면 나중 'PM ↔ 담당 일간보고'·'담당들끼리 자유채팅'에도 재사용할 수 있다.
"""

import tempfile
import threading
from pathlib import Path

from src.cc.client import run_headless
from src.cc.permissions import tools_for
from src.cc.prompts import ROOM_SYSTEM, room_chat
from src.db import agents as agents_db
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

    일간보고 대화는 daily_report가 룸 피드에도 그대로 기록하므로(2026-09-04),
    최근 대화(history)만 줘도 담당이 밤의 보고 맥락을 이어받는다.
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
        # 사용자가 시키면 그 자리에서 고친다(2026-09-09 확정) — 저장 자동 승인.
        #   Bash가 없어 임의 명령·푸시는 불가. 커밋도 안 한다 — 사용자가 보고 되돌릴 수 있게.
        permission_mode="acceptEdits",
        timeout=CHAT_TIMEOUT,
        append_system_prompt=ROOM_SYSTEM,
        add_dirs=[project_path],      # 대상 폴더 — 읽고, 사용자가 시키면 고친다
        model=agents_db.model_for(project_path),   # 담당별 지정 모델(없으면 기본)
    )
    body = (result or "").strip() or "(지금은 답을 만들지 못했어 — 잠시 후 다시 시도해줘)"
    messages_db.add_message(project_path, AGENT_AUTHOR, body)


# ── 끊긴 답변 되살리기 ────────────────────────────────────────────────────────
# 담당 답변은 서버 프로세스 안의 백그라운드 작업이다. 답을 만드는 3분 사이에 서버가
# 내려가면(재시작·강제종료) 그 작업도 같이 죽고, 방에는 사용자 질문만 남는다.
# 화면은 "마지막 글이 사용자면 답하는 중"으로 그리므로 그 표시가 영영 안 없어진다
# — 2026-09-13 실제 사고: 05:40:11 질문 → 05:40:48 서버 재시작 → 답 없음.
# 그래서 서버가 뜰 때 '답을 기다리다 끊긴 방'을 찾아 한 번씩 다시 부른다.
RESUME_MAX_ROOMS = 5        # 한 번에 되살릴 방 수 상한(뜨자마자 모델 호출이 몰리지 않게)


def dangling_rooms() -> list[dict]:
    """마지막 글이 사용자 질문인 프로젝트 방 목록 — 답을 기다리다 끊긴 방."""
    from src.db import projects as projects_db

    out = []
    for proj in projects_db.list_projects(enabled_only=True):
        msgs = messages_db.list_messages(proj["path"], limit=1)
        if msgs and msgs[-1]["author"] == "user":
            out.append({"path": proj["path"], "name": proj["name"],
                        "asked_at": msgs[-1]["created_at"]})
    return out


def resume_dangling_replies() -> None:
    """끊긴 방들의 답변을 순서대로 다시 부른다. 서버 기동 때 한 번(별도 스레드)."""
    from loguru import logger

    rooms = dangling_rooms()[:RESUME_MAX_ROOMS]
    if not rooms:
        return
    names = ", ".join(r["name"] for r in rooms)
    logger.info(f"[방] 답을 기다리다 끊긴 방 {len(rooms)}개 재개: {names}")

    def _work():
        for r in rooms:
            try:
                reply_in_room(r["path"], r["name"])          # 한 번에 하나씩
                logger.info(f"[방] {r['name']} 답변 재개 완료(질문 {r['asked_at']})")
            except Exception as e:                            # 한 방이 실패해도 나머지는 간다
                logger.warning(f"[방] {r['name']} 답변 재개 실패: {e}")

    threading.Thread(target=_work, daemon=True, name="room-resume").start()
