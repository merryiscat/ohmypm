"""로컬 LISTEN 포트 실시간 스캔 (Windows, 새 의존성 없이) + 프로세스 명령줄로 프로젝트 매칭.

2026-10-09 교체. 옛 방식(PowerShell Get-NetTCPConnection + 포트마다 Get-Process)은 2초 넘게 걸리고
프로세스 이름 화이트리스트(python·node…)에 든 것만 감지했다. 지금은
  netstat -ano -p TCP (0.05초)  →  포트→PID
  Get-CimInstance Win32_Process (0.2초, 한 번)  →  PID→이름·명령줄
명령줄에 든 절대경로로 어느 프로젝트의 포트인지 맞춘다(예: ...\\project\\state\\dashboard\\server.py → state).
읽기 전용. 실패는 빈 dict(흐름 안 막음). Windows가 아니면 빈 dict.
"""

import json
import os
import shutil
import subprocess
import sys

from loguru import logger

from src.proc import NO_WINDOW

# 운영체제 서비스 — 감지 목록에서 뺀다(사용자 프로젝트일 리 없는 것들)
SYSTEM_PROCS = {"system", "idle", "svchost", "services", "lsass", "wininit", "winlogon", "csrss",
                "smss", "spoolsv", "dns", "dhcp", "natsvc", "jhi_service"}
TIMEOUT = 10

# PowerShell 한 줄 — 출력 인코딩을 UTF-8로 강제(한글 경로가 깨지지 않게)하고 JSON으로 받는다
_PS_PROCS = (
    "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
    "Get-CimInstance Win32_Process | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
)


def _parse_netstat(text: str) -> dict[int, int]:
    """netstat -ano 출력에서 LISTENING 행만 → {port: pid}. IPv4·IPv6 모두, 포트당 첫 PID."""
    out: dict[int, int] = {}
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP" or parts[3].upper() != "LISTENING":
            continue
        local = parts[1]
        try:
            port = int(local.rsplit(":", 1)[1])
            pid = int(parts[4])
        except (ValueError, IndexError):
            continue
        out.setdefault(port, pid)
    return out


def _parse_procs(json_text: str) -> dict[int, tuple[str, str]]:
    """ConvertTo-Json 결과 → {pid: (이름(.exe 뗌), 명령줄)}. 단일 객체·배열 모두 처리."""
    try:
        data = json.loads(json_text or "null")
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):
        data = [data]
    out: dict[int, tuple[str, str]] = {}
    for row in data or []:
        if not isinstance(row, dict):
            continue
        try:
            pid = int(row.get("ProcessId"))
        except (TypeError, ValueError):
            continue
        name = (row.get("Name") or "")
        if name.lower().endswith(".exe"):
            name = name[:-4]
        out[pid] = (name, row.get("CommandLine") or "")
    return out


def match_project(cmdline: str, candidates: list[str]) -> str | None:
    """명령줄에 들어 있는 프로젝트 경로를 찾는다(대소문자 무시, 경로 구분자까지 맞아야 함). 여러 개면 가장 긴 경로."""
    if not cmdline:
        return None
    low = os.path.normcase(cmdline)
    best: str | None = None
    for cand in candidates:
        c = os.path.normcase(os.path.normpath(cand))
        if not c:
            continue
        hit = any((c + sep) in low for sep in (os.sep, "/", '"', "'")) or low.endswith(c)
        if hit and (best is None or len(c) > len(os.path.normcase(best))):
            best = cand
    return best


def _netstat() -> dict[int, int]:
    exe = shutil.which("netstat") or "netstat"
    r = subprocess.run([exe, "-ano", "-p", "TCP"], capture_output=True, text=True, timeout=TIMEOUT,
                       encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    return _parse_netstat(r.stdout)


def _processes() -> dict[int, tuple[str, str]]:
    ps = shutil.which("powershell") or "powershell"
    r = subprocess.run([ps, "-NoProfile", "-Command", _PS_PROCS], capture_output=True, text=True,
                       timeout=TIMEOUT, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    return _parse_procs(r.stdout)


def listening_ports(candidates: list[str] | None = None) -> dict[int, dict]:
    """{port: {'pid', 'proc', 'cmdline', 'project'}} — 지금 LISTEN 중인 포트. 실패는 빈 dict.

    candidates: 매칭에 쓸 프로젝트 경로 목록(없으면 projects 표 + ohmyPM 자신).
    """
    if sys.platform != "win32":
        return {}
    try:
        ports = _netstat()
    except Exception as e:
        logger.warning(f"[포트스캔] netstat 실패: {e}")
        return {}
    try:
        procs = _processes()
    except Exception as e:
        logger.warning(f"[포트스캔] 프로세스 목록 실패: {e}")
        procs = {}
    if candidates is None:
        candidates = _default_candidates()
    out: dict[int, dict] = {}
    for port, pid in ports.items():
        name, cmd = procs.get(pid, ("", ""))
        out[port] = {"pid": pid, "proc": name, "cmdline": cmd, "project": match_project(cmd, candidates)}
    return out


def _default_candidates() -> list[str]:
    from src.cc.common import REPO_ROOT
    from src.db import projects as projects_db

    try:
        paths = [p["path"] for p in projects_db.list_projects(enabled_only=False)]
    except Exception:
        paths = []
    return [*paths, str(REPO_ROOT)]
