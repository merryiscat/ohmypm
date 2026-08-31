"""포트 실행 관리(2단계) — 등록 포트의 서버 start/stop.

안전 원칙(이 프로젝트 관통: 화이트리스트·게이트, confused-deputy 방지):
- start: **등록된 start_cmd만** 실행한다(화이트리스트). 임의 명령을 받지 않는다.
- stop: 등록 포트를 지금 점유한 **그 PID만** 강제 종료한다(임의 PID kill 금지).
  종료는 되돌리기 어려운 행동(미저장 유실) → 실제 확인 게이트는 화면(대상 PID·프로세스명 표시
  + 확인창)에서 받는다. 여기 백엔드는 확인된 요청만 수행한다.
"""

import subprocess
from pathlib import Path

from loguru import logger

from src.db import ports as ports_db
from src.portscan import listening_ports

# Windows: 부모(서버)와 분리해 띄운다 — 서버가 죽어도 살아 있게
_DETACHED = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def start_port(port_id: int) -> dict:
    """등록된 start_cmd를 그 프로젝트 폴더에서 실행(화이트리스트). 이미 떠 있으면 skip."""
    reg = ports_db.get_port(port_id)
    if not reg:
        return {"ok": False, "reason": "등록되지 않은 포트"}
    if reg["port"] in listening_ports():
        return {"ok": False, "reason": "이미 실행 중"}
    cmd = (reg.get("start_cmd") or "").strip()
    if not cmd:
        return {"ok": False, "reason": "start_cmd 미등록 — 포트 등록 시 실행 명령을 넣어야 켤 수 있음"}
    cwd = reg["project"]
    if not Path(cwd).exists():
        return {"ok": False, "reason": "프로젝트 폴더 없음"}
    try:
        subprocess.Popen(          # noqa: S602 — start_cmd는 사용자 등록 화이트리스트
            cmd, shell=True, cwd=cwd, creationflags=_DETACHED,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.warning(f"[포트] start 실패({cmd[:40]}): {e}")
        return {"ok": False, "reason": f"실행 실패: {e}"}
    logger.info(f"[포트] start {reg['port']} ← {cmd[:60]}")
    return {"ok": True, "started": cmd}


def stop_port(port_id: int) -> dict:
    """등록 포트를 지금 점유한 PID만 강제 종료(/T로 자식까지). 화면 확인 게이트를 거친 뒤 호출된다."""
    reg = ports_db.get_port(port_id)
    if not reg:
        return {"ok": False, "reason": "등록되지 않은 포트"}
    info = listening_ports().get(reg["port"])
    if not info:
        return {"ok": False, "reason": "실행 중이 아님"}
    pid = info["pid"]
    try:
        r = subprocess.run(
            ["taskkill", "/PID", str(pid), "/F", "/T"],
            capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace",
        )
    except Exception as e:
        logger.warning(f"[포트] stop 실패(pid {pid}): {e}")
        return {"ok": False, "reason": f"종료 실패: {e}"}
    if r.returncode != 0:
        return {"ok": False, "reason": (r.stderr or r.stdout or "종료 실패").strip()[:160]}
    logger.info(f"[포트] stop {reg['port']} → PID {pid}({info.get('proc')}) 종료")
    return {"ok": True, "killed": pid, "proc": info.get("proc")}
