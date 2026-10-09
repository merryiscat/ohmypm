"""토론 세션 러너 — "토론 시작" 버튼 한 번에 게시판 4단계를 마감 시각까지 순서대로 돌린다.

흐름: start(minutes) → DB에 세션 행 → 스레드에서 _run:
  글쓰기(35%) → 둘러보기·댓글(35%) → 글쓴이 반응(15%) → 대대댓글(15%) → 복기(reflect, 마감 밖)
단계 예산은 누적 비율로 계산한다 — 앞 단계가 일찍 끝나면 남은 시간은 뒤 단계로 흐른다.
중지(stop): DB 상태 'stopping' + Event. 이미 도는 헤드리스 호출은 끝까지 가고 새 호출만 안 뜬다.
서버 재시작: 돌던 세션은 'stopped'로 닫고 점수 집계만 결정론으로 남긴다(자동 재개 없음 — 비용 통제).
"""

import threading
import time
from datetime import datetime

from loguru import logger

from src.cc import board, reflect
from src.config.settings import settings
from src.db import sessions as sessions_db

ALLOWED_MINUTES = (10, 30, 60)
# 단계별 시간 몫(누적) — write 35%, browse 35%, feedback 15%, followup 15%
PHASE_PLAN = (("write", 0.35), ("browse", 0.70), ("feedback", 0.85), ("followup", 1.00))

_LOCK = threading.Lock()
_THREADS: dict[int, threading.Thread] = {}
_STOP_EVENTS: dict[int, threading.Event] = {}


def start(minutes: int, paths: list[str] | None = None) -> dict:
    """세션을 시작한다. 반환 {ok, session} 또는 {ok: False, error}."""
    if minutes not in ALLOWED_MINUTES or minutes > settings.board_max_minutes:
        return {"ok": False, "error": f"토론 시간은 {', '.join(map(str, ALLOWED_MINUTES))}분 중 하나(상한 {settings.board_max_minutes}분)"}
    with _LOCK:
        for s in sessions_db.active_sessions():
            t = _THREADS.get(s["id"])
            if t and t.is_alive():
                return {"ok": False, "error": f"토론 #{s['id']}이 아직 진행 중입니다"}
            # 행만 남고 스레드가 없다 = 서버 재시작 등으로 끊긴 것 → 닫는다
            sessions_db.set_status(s["id"], "stopped", error="스레드 없음(서버 재시작으로 끊김)", finished=True)
        sess = sessions_db.create_session(minutes, paths)
        stop = threading.Event()
        _STOP_EVENTS[sess["id"]] = stop
        t = threading.Thread(target=_run, args=(sess["id"], stop), daemon=True, name=f"board-session-{sess['id']}")
        _THREADS[sess["id"]] = t
        t.start()
    logger.info(f"[토론] 세션 #{sess['id']} 시작 — {minutes}분, 대상 {len(paths) if paths else '전체'}")
    return {"ok": True, "session": current()}


def stop() -> dict:
    """진행 중인 세션에 중지 신호를 보낸다."""
    active = sessions_db.active_sessions()
    if not active:
        return {"ok": False, "error": "진행 중인 토론이 없습니다"}
    s = active[0]
    sessions_db.set_status(s["id"], "stopping")
    ev = _STOP_EVENTS.get(s["id"])
    if ev:
        ev.set()
    logger.info(f"[토론] 세션 #{s['id']} 중지 요청")
    return {"ok": True, "session": current()}


def current() -> dict | None:
    """최근 세션 + 남은 시간(초) + 스레드 생존 여부. 세션이 하나도 없으면 None."""
    s = sessions_db.latest_session()
    if not s:
        return None
    try:
        deadline = datetime.strptime(s["deadline_at"], "%Y-%m-%d %H:%M:%S").timestamp()
    except (TypeError, ValueError):
        deadline = time.time()
    s["remaining_sec"] = max(0, int(deadline - time.time())) if s["status"] in sessions_db.ACTIVE_STATUSES else 0
    t = _THREADS.get(s["id"])
    s["alive"] = bool(t and t.is_alive())
    return s


def _run(session_id: int, stop_ev: threading.Event) -> None:
    sess = sessions_db.get_session(session_id)
    start_ts = time.time()
    total = sess["minutes"] * 60
    paths = sess.get("paths")
    try:
        for phase, share in PHASE_PLAN:
            if stop_ev.is_set():
                break
            deadline = start_ts + total * share
            if time.time() > deadline:
                continue                   # 앞 단계가 시간을 다 썼으면 이 단계는 건너뛴다
            sessions_db.set_phase(session_id, phase)
            fn = {"write": board.run_board_posts, "browse": board.run_board_discussion,
                  "feedback": board.run_post_feedback, "followup": board.run_reply_followup}[phase]
            res = fn(paths=paths, deadline_ts=deadline, stop=stop_ev, session_id=session_id)
            sessions_db.merge_stats(session_id, {k: v for k, v in res.items() if k != "note"})
            logger.info(f"[토론] #{session_id} {phase} 끝 — {res}")
        if stop_ev.is_set():
            # 중지: 복기는 하지 않지만 점수 집계는 남긴다(결정론, 비용 0)
            reflect.record_scores(session_id)
            sessions_db.set_status(session_id, "stopped", finished=True)
            logger.info(f"[토론] #{session_id} 중지됨")
            return
        sessions_db.set_phase(session_id, "reflect")
        res = reflect.run(session_id, stop_ev)
        sessions_db.merge_stats(session_id, res)
        sessions_db.set_status(session_id, "done", finished=True)
        logger.info(f"[토론] #{session_id} 끝 — 복기 {res.get('reflected', 0)}명")
    except Exception as e:
        logger.exception(f"[토론] #{session_id} 실패: {e}")
        sessions_db.set_status(session_id, "failed", error=str(e)[:300], finished=True)
    finally:
        _STOP_EVENTS.pop(session_id, None)


def recover_on_startup() -> None:
    """서버가 뜰 때 — 돌다 끊긴 세션을 닫는다. 자동 재개는 하지 않는다."""
    for s in sessions_db.active_sessions():
        try:
            reflect.record_scores(s["id"])
        except Exception as e:
            logger.warning(f"[토론] #{s['id']} 점수 집계 실패(복구 중): {e}")
        sessions_db.set_status(s["id"], "stopped", error="서버 재시작으로 중단", finished=True)
        logger.info(f"[토론] 세션 #{s['id']} — 서버 재시작으로 중단 처리")
