"""백그라운드 작업 레지스트리 — 주간보고·랩실 조사처럼 몇 분 걸리는 일을 스레드로 돌리고 상태를 기억한다.

FastAPI 라우트에서 헤드리스 호출을 직접 부르면 응답이 막히므로, 여기로 넘기고 화면은 상태를 폴링한다.
같은 이름의 작업은 하나만 돈다(중복 가드). 결과는 메모리에만 남는다 — 서버가 재시작되면 사라지고,
영속해야 할 결과(보고 본문 등)는 각 작업이 DB·파일에 직접 쓴다.
"""

import threading
from datetime import datetime

from loguru import logger

_LOCK = threading.Lock()
_JOBS: dict[str, dict] = {}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def start(name: str, target, *args, **kwargs) -> bool:
    """작업을 스레드로 시작한다. 같은 이름이 돌고 있으면 False(시작 안 함)."""
    with _LOCK:
        cur = _JOBS.get(name)
        if cur and cur.get("running") and cur["thread"].is_alive():
            return False
        state = {"name": name, "running": True, "started_at": _now(), "finished_at": None,
                 "ok": None, "error": None, "result": None}

        def _run():
            try:
                res = target(*args, **kwargs)
                state["result"] = res if isinstance(res, (dict, list, str, int, float)) or res is None else str(res)
                state["ok"] = True
            except Exception as e:  # 작업 실패는 상태에 남기고 서버는 계속
                logger.exception(f"[작업] {name} 실패: {e}")
                state["ok"] = False
                state["error"] = str(e)[:300]
            finally:
                state["running"] = False
                state["finished_at"] = _now()

        t = threading.Thread(target=_run, daemon=True, name=f"job-{name}")
        state["thread"] = t
        _JOBS[name] = state
        t.start()
        return True


def is_running(name: str) -> bool:
    cur = _JOBS.get(name)
    return bool(cur and cur.get("running") and cur["thread"].is_alive())


def status(name: str) -> dict:
    """화면에 줄 상태 — 스레드 객체는 뺀다. 한 번도 안 돌았으면 running=False만."""
    cur = _JOBS.get(name)
    if not cur:
        return {"name": name, "running": False}
    out = {k: v for k, v in cur.items() if k != "thread"}
    out["running"] = is_running(name)
    return out
