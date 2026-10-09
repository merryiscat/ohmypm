# ohmyPM

로컬 프로젝트들을 돌보는 프로젝트 관리 도구(FastAPI + SQLite + Claude Code 헤드리스). 구조는 `docs/design.md`,
API는 `docs/interfaces.md`, 설치는 `docs/setup.md`. 기획 이력은 `docs/plan.md`.

## 작업 규칙

- 모델 호출은 `run_headless(_ex)`에 **task 이름을 글자 그대로** 넘긴다 — `src/cc/models.py` TASK_TIER에 먼저 등록.
  권한은 `src/cc/permissions.py`. 라우트에서 직접 부르지 않고 `src/jobs.py`나 스레드로.
- 지시문은 코드가 아니라 `prompts/*.md`(`${변수}`). 시스템 프롬프트(`*_system.md`)는 서버 재시작 때 읽힌다.
- 다른 프로젝트의 파일은 `src/install.py`가 만드는 `ohmypm/` 폴더와 표식 블록만 건드린다. 커밋하지 않는다.
- 확인은 `uv run pytest` + 서버 재기동(`scripts\stop_ohmypm.cmd` → `.venv\Scripts\pythonw.exe scripts\run_ohmypm_hidden.py`) + 화면.
