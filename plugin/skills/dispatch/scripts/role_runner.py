#!/usr/bin/env python3
"""Own one model process, retaining positive exit evidence after its PTY becomes a shell."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from workflow_core import read_json, require, write_json  # noqa: E402


def process_identity(pid):
    """Return a live process creation identity; never confuse PID reuse with liveness."""
    if not isinstance(pid, int) or pid <= 0:
        return None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        api.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        api.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        handle = api.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            code = wintypes.DWORD()
            if not api.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:
                return None
            times = [wintypes.FILETIME() for _ in range(4)]
            if not api.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
                return None
            return f"{pid}:{times[0].dwHighDateTime}:{times[0].dwLowDateTime}"
        finally:
            api.CloseHandle(handle)
    try:
        stat = Path(f"/proc/{pid}/stat")
        if stat.exists():
            fields = stat.read_text().rsplit(")", 1)[1].split()
            return None if fields[0] == "Z" else f"{pid}:{fields[19]}"
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "lstart="], capture_output=True, text=True
        )
        return (
            f"{pid}:{result.stdout.strip()}"
            if result.returncode == 0 and result.stdout.strip()
            else None
        )
    except OSError:
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", required=True)
    args = parser.parse_args()
    record = read_json(args.record)
    target = record["lifecycle"]
    base = {"token": record["token"], "wrapper_pid": os.getpid()}
    write_json(target, {**base, "status": "starting"})
    try:
        executable = shutil.which(record["argv"][0])
        require(executable, "Model CLI not installed")
        argv = [executable, *record["argv"][1:]]
        if Path(executable).suffix.lower() in (".cmd", ".bat"):
            # Never pass a natural-language prompt through a Windows batch shell — the context is
            # multi-line and quoted, and a .CMD shim mangles it. Resolve the shim to whatever it
            # actually launches instead.
            # ★ 2026-09-23: 이 분기가 claude를 통째로 막고 있었다. Windows에 npm으로 깔면
            #   claude·codex 둘 다 `.CMD` 셈이 되는데, 여기 예외는 codex 하나뿐이라
            #   main(agent=claude) 연결이 "Unsupported batch launcher"로 매번 즉사했다
            #   (odin_3.0 실측: 터미널은 떴고 생명주기 기록만 exited로 남았다).
            #   claude.CMD가 부르는 대상은 node 스크립트가 아니라 **네이티브 claude.exe**라
            #   그 실행 파일을 직접 쓴다 — 배치 셸을 거치지 않는다는 원래 의도 그대로다.
            # 이름은 shim_dir — `base`는 이 함수에서 생명주기 기록의 공통 필드(dict)로 이미
            # 쓰이고 있다. 2026-09-23에 여기를 `base`로 뒀다가 그 dict를 덮어써서
            # `{**base, "status": "running"}`이 TypeError로 죽었다(자식은 이미 떠 있는데
            # 기록만 안 남아 '떴는지 안 떴는지 모르는' 상태가 됐다).
            shim_dir = Path(executable).parent
            native = shim_dir / "node_modules/@anthropic-ai/claude-code/bin/claude.exe"
            entry = shim_dir / "node_modules/@openai/codex/bin/codex.js"
            node = shutil.which("node")
            if record["argv"][0] == "claude" and native.is_file():
                argv = [str(native), *record["argv"][1:]]
            else:
                require(
                    record["argv"][0] == "codex" and entry.is_file() and node,
                    "Unsupported batch launcher; install a native executable"
                    " or supported Codex shim",
                )
                argv = [node, str(entry), *record["argv"][1:]]
        child = subprocess.Popen(argv, cwd=record["project"])
        write_json(
            target,
            {
                **base,
                "status": "running",
                "pid": child.pid,
                "process_identity": process_identity(child.pid),
            },
        )
        code = child.wait()
        write_json(target, {**base, "status": "exited", "pid": child.pid, "exit_code": code})
        return code
    except (OSError, RuntimeError) as exc:
        write_json(target, {**base, "status": "exited", "error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
