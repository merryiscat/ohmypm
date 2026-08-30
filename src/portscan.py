"""로컬 LISTEN 포트 실시간 스캔 (Windows 네이티브, 새 의존성 없이).

PowerShell `Get-NetTCPConnection`으로 지금 열려 있는(LISTEN) 포트→PID→프로세스명을 뽑는다.
읽기 전용 — 포트 관리 '표시·충돌 감지'용. 실패는 빈 dict(흐름 안 막음).
"""

import shutil
import subprocess

from loguru import logger

# 포트별 (PID·프로세스명) 한 줄씩 탭 구분으로 뱉는 PowerShell 한 줄
_PS = (
    "Get-NetTCPConnection -State Listen | "
    "Select-Object -Unique LocalPort,OwningProcess | ForEach-Object { "
    "try { $n=(Get-Process -Id $_.OwningProcess -ErrorAction Stop).ProcessName } catch { $n='' }; "
    "\"$($_.LocalPort)`t$($_.OwningProcess)`t$n\" }"
)


def listening_ports() -> dict[int, dict]:
    """{port: {'pid': int, 'proc': str}} — 지금 LISTEN 중인 포트 맵. 실패는 빈 dict."""
    ps = shutil.which("powershell") or "powershell"
    try:
        r = subprocess.run(
            [ps, "-NoProfile", "-Command", _PS],
            capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace",
        )
    except Exception as e:
        logger.warning(f"[포트스캔] 실패: {e}")
        return {}
    out: dict[int, dict] = {}
    for line in (r.stdout or "").splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        try:
            port = int(parts[0]); pid = int(parts[1])
        except ValueError:
            continue
        out[port] = {"pid": pid, "proc": parts[2] if len(parts) > 2 else ""}
    return out
