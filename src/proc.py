"""자식 프로세스 생성 플래그 — 창 없이 실행되는 서버에서 콘솔 창이 튀지 않게.

2026-09-10에 자동실행을 `pythonw.exe`(콘솔 없는 GUI 서브시스템)로 바꾸면서 드러난 문제:
**부모에 콘솔이 없으면 자식 콘솔 앱(powershell·git·claude)이 각자 새 콘솔 창을 할당한다.**
대시보드가 `/api/ports`를 폴링할 때마다 powershell 창이 깜빡이는 걸로 나타났다
(예전 `run_ohmypm.cmd`는 콘솔이 있어 자식이 물려받았기 때문에 조용했다).

그래서 이 프로젝트의 subprocess 호출은 전부 `creationflags=NO_WINDOW`를 붙인다.
"""

import os
import subprocess

# Windows에서만 있는 플래그. 다른 OS에선 0(플래그 없음)이라 그대로 넘겨도 안전하다.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
