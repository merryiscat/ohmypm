# ohmyPM 다른 PC 세팅 (재현 절차)

> 셸은 **PowerShell** 기준. 2026-10-10 2차 리뉴얼 뒤 기준으로 다시 썼다.

## 전제 — PC마다 독립 인스턴스다

각 PC의 ohmyPM은 그 PC의 로컬 프로젝트만 돌본다. 코드·기획·프롬프트는 git으로 공유되지만 기억은 공유되지 않는다.

| 공유됨 (git) | PC 전용 (gitignore) |
|---|---|
| `src/` · `prompts/` · `docs/`(설계·인터페이스·설치·기획 이력) | `.env` (관리 대상 루트) |
| `CLAUDE.md` · `AGENTS.md` · `skills-lock.json` · `scripts/` | `data/ohmypm.db` (프로젝트·게시판·세션·점수·제안) |
| | `logs/` · `docs/lab/`(연구 위키) · `data/lab/`·`data/model_updates/`(연구 상태) |
| | `.agents/` · `.claude/skills/` (lock으로 재설치) |

스크립트는 자기 위치에서 저장소 경로를 구한다. 절대경로를 커밋하지 않는다.

## 1. 클론·런타임

```powershell
git clone https://github.com/merryiscat/ohmypm.git
cd ohmypm
uv sync
```

- Python 3.11+ 및 uv, git, **Claude Code CLI**(`claude`가 PATH에) — 모든 모델 호출이 `claude -p`다
- Node.js 18+ — 스킬 재설치용(`npx skills experimental_install` → fastapi 스킬)

## 2. 세팅 wizard — `.env` + 로그인 자동 실행 (2단계)

```powershell
scripts\setup_wizard.cmd
```

1. **관리 대상 루트**(`PROJECTS_ROOT`) — 이 PC가 돌볼 프로젝트들의 상위 폴더. 비워 두면 첫 스캔 때
   저장소 위치 기준 기본값(저장소 부모 아래 `projects` 폴더가 있으면 그것, 없으면 부모 폴더)으로 `.env`가 자동 생성된다.
2. 로그인 시 자동 실행 등록 — 시작프로그램 바로가기(`pythonw.exe` + `scripts\run_ohmypm_hidden.py`, 창 없음)

wizard는 대화형이라 터미널에서 사람이 직접 실행한다. 수동으로 하려면 `.env.example`을 `.env`로 복사해 채운다.
`.env`에 모르는 변수가 남아 있어도 기동은 막히지 않는다(설정이 `extra="ignore"`).

## 3. 기동·종료

```powershell
scripts\run_ohmypm.cmd          # 창 + 실시간 로그 (http://127.0.0.1:8123)
scripts\stop_ohmypm.cmd         # 8123 리스닝 프로세스 종료
```

창 없이 띄우려면 `.venv\Scripts\pythonw.exe scripts\run_ohmypm_hidden.py` — 로그는 `logs\server_console.log`.
Claude Code로 이 저장소를 열면 `.claude/hooks/ohmypm-server.ps1`(SessionStart 훅)이 포트가 비어 있을 때만 같은 방식으로 띄운다.

`data/ohmypm.db`는 첫 기동에 생성된다. 첫 화면에서 **스캔(설치)**을 누르면 `PROJECTS_ROOT` 아래 프로젝트가
등록되고 각 프로젝트에 `ohmypm/` 폴더와 지침 블록이 설치된다(ohmyPM 자신은 제외). 두 번째 누르면 전부 '이미 설치'.

정시 배치는 랩실 정기 조사 하나다(`EXPERT_COLLECT_WEEKDAY`/`HOUR`, 기본 월요일 05:00). `SCHEDULER_ENABLED=false`면 그것도 끈다.

## 4. 제거

- 프로젝트에서 ohmyPM 흔적 빼기: 룸의 **설치 제거** — `ohmypm/` 폴더와 CLAUDE.md·AGENTS.md의 블록만 지운다
- 프로젝트를 관리에서 빼기: 사이드바 이름 옆 `x` — DB의 글·대화만 지우고 폴더는 안 건드린다
- 로그인 자동 실행 해제: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\startup_shortcut.ps1 -Remove`

## 5. MCP (각 PC)

Playwright·context7 MCP는 이 저장소에 등록돼 있지 않다 — 쓰려면 각 PC의 Claude Code 설정에서 따로 등록한다.

## 막다른 길 (되풀이 금지)

- `schtasks /create /sc onlogon`은 관리자 권한을 요구한다. 시작프로그램 폴더가 답이다.
- VBS 런처는 최신 Windows 11에서 죽는다. `pythonw.exe`로 창 없이 띄운다.
- `npx skills install`은 `add`로 해석된다 — lock 복원은 `experimental_install`.
