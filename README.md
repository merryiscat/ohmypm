# ohmyPM

모든 로컬 프로젝트를 매일 돌보는 **메타 PM 에이전트**입니다.

프로젝트 환경·하네스 점검, 진행 추적과 일간 보고, 문서·위키 건강 관리를 Claude Code 기반으로
수행하고, 웹 대시보드와 텔레그램으로 알립니다.

## 구성

- **스캔·점검** — `PROJECTS_ROOT` 하위 프로젝트를 발견하고 상태·위키·하네스를 점검합니다.
- **웹 대시보드** — `http://127.0.0.1:8123` (FastAPI + SQLite)
- **일간 보고·알림** — 로컬 스케줄러가 정시에 돌고 텔레그램으로 보냅니다.
- **전문가 에이전트** — 모델 동향 등 주제별 지식 위키를 수집·갱신합니다.

## 설치·실행

Python 3.11+ 와 uv, git, Claude Code CLI(`claude`)가 필요합니다.

```powershell
uv sync
scripts\setup_wizard.cmd     # .env 작성 + 자동 실행 등록 (대화형)
scripts\run_ohmypm.cmd       # 기동 → http://127.0.0.1:8123
```

다른 PC 재현 절차 전체는 [docs/setup.md](docs/setup.md)에 있습니다. PC마다 독립 인스턴스이며
기억(DB·위키 운영 파일)은 공유되지 않습니다.

## 검증

```powershell
uv run pytest
```

- [기획](docs/plan.md)
- [위키 규약](docs/conventions-wiki.md)
