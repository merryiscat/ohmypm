"""ohmyPM 대시보드 서버 — 창 없이 기동(로그인 자동실행용).

`pythonw.exe`로 실행한다. GUI 서브시스템이라 콘솔 창이 아예 안 생긴다.
(예전엔 VBS 런처를 썼는데 2026-09-10 확인 — 최신 Windows 11에서 Windows Script Host가
"메모리 리소스가 부족" 오류로 죽는다. VBScript가 기능 분리되며 못 믿을 경로가 됐다.)

**pythonw에는 stdout·stderr가 없다(None).** uvicorn·loguru가 거기 쓰려다 죽으므로,
무엇을 import하기 **전에** 로그 파일로 돌려놓는다. 창으로 보고 싶으면 run_ohmypm.cmd를 쓴다.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # 저장소 위치는 이 파일에서 구한다(하드코딩 금지)
os.chdir(ROOT)                                  # db_path·logs가 저장소 기준 상대경로다
sys.path.insert(0, str(ROOT))

(ROOT / "logs").mkdir(exist_ok=True)
_console = open(ROOT / "logs" / "server_console.log", "a", buffering=1,
                encoding="utf-8", errors="replace")
sys.stdout = sys.stderr = _console

import uvicorn  # noqa: E402 (stdout/stderr를 돌려놓은 뒤에 import해야 한다)

uvicorn.run("src.web.server:app", host="127.0.0.1", port=8123)
