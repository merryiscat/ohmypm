# ohmyPM 다른 PC 세팅 (재현 절차)

> 이 저장소를 새 PC에서 세팅하는 절차. 셸은 **PowerShell** 기준(상위 CLAUDE.md).

## 전제 — PC마다 **독립 인스턴스**다 (2026-09-10 사용자 확정)

각 PC의 ohmyPM은 **그 PC의 로컬 프로젝트만** 돌보는 별개의 PM이다. 코드·기획·규약은
git으로 공유되지만 **기억은 공유되지 않는다**:

| 공유됨 (git) | PC 전용 (gitignore) |
|---|---|
| `src/` · `prompts/` · `docs/` 기획·규약 | `.env` (관리 대상 루트·토큰) |
| `CLAUDE.md` · `skills-lock.json` | `data/ohmypm.db` (프로젝트·이슈·게시판·일간보고) |
| `scripts/` (경로 무관하게 동작) | `logs/` · `docs/status.md` · `log.md` · `mistakes.md` · `pending.md` |
| | `.agents/` · `.claude/skills/` (lock으로 재설치) |

따라서 새 PC는 **보드가 백지인 새 PM**으로 출발한다. 이전 PC의 이슈·게시판을 이어받고
싶다면 그건 다른 설계(상태 공유)이고, 지금 구조가 아니다 — [plan.md](plan.md)의
"SQLite 로컬 = 서버 없음" 결정 재검토가 선행돼야 한다.

**하드코딩 금지 규칙**: 스크립트는 자기 위치(`%~dp0` / `BASH_SOURCE`)에서 저장소 경로를
구한다. `C:\Users\<누구>\...` 같은 절대경로를 커밋하지 않는다 — 2026-09-10에 정확히 이것
때문에 두 번째 PC에서 아무것도 안 돌았다.

---

## 1. 클론

```powershell
git clone https://github.com/merryiscat/ohmypm.git
cd ohmypm
```

저장소는 어디에 둬도 된다(`D:\dev\project\ohmypm` 등). 스크립트가 경로를 가정하지 않는다.

## 2. 런타임

- **Python 3.11+ 및 uv** — 소스 실행 (상위 CLAUDE.md: `uv` 우선)
- **Node.js 18+** — npx 스킬 설치용
- **git** · **Claude Code CLI**(`claude`가 PATH에 있어야 함 — 판단·작업을 headless로 호출)

```powershell
uv sync
```

## 3. 하네스 플러그인 — 이 저장소의 `plugin/` (2026-09-17, kickoff_pack 대체)

킥오프(interview → workspaces)·선택 스킬(refsweep·usecases)·llmwiki는 **이 저장소 안의 Claude Code 플러그인**이다.
클론이 곧 마켓플레이스라 별도 다운로드가 없다:

```powershell
claude plugin marketplace add D:\dev\project\ohmypm\.claude-plugin\marketplace.json   # 클론 경로에 맞춘다
claude plugin install ohmypm@ohmypm-local --scope user -y
claude plugin list                                                                # 설치된 버전과 enabled 확인
```

2.0 작업 환경(T-006)은 **프로젝트 파일을 바꾸지 않고** 외부에 등록한다. 실행기·절차·템플릿은
`%LOCALAPPDATA%\ohmypm\runtimes\<내용 해시>`(`--home`·`OHMYPM_HOME`으로 변경)에 불변 설치되고,
프로필·원문·route·승인·질문·증거는 그 프로젝트의 `.git/ohmypm/`에 남는다. 커밋할 것이 없다:
```powershell
python plugin/skills/kickoff-workspaces/scripts/ws_upgrade.py <프로젝트경로> --dry-run
python plugin/skills/kickoff-workspaces/scripts/ws_upgrade.py <프로젝트경로> [--profiles <roles.json>]
python <runtime.path>\scripts\environment_cli.py --project <프로젝트경로> doctor
python <runtime.path>\scripts\environment_cli.py --project <프로젝트경로> role-connect --role main
```

`runtime.path`는 등록 결과 JSON의 `config.runtime.path`다. 역할·모델·approval은 `--profiles`의 JSON
(`{"roles":{"main":…,"pl":…,"work":…}}`)으로 정하며 생략하면 플러그인 템플릿 기본값이다.
명령·복구는 `plugin/skills/dispatch/references/runtime.md`, 절차는 `plugin/skills/kickoff-workspaces/PROTOCOL.md`.
`.git/ohmypm/`은 clone으로 복구되지 않으므로 `environment_cli.py export`로 따로 백업한다.

기존 1.0 설치본(`docs/protocol.md`·`.ohmypm/bin/` 등)이 있는 프로젝트는 등록 뒤 `migration-plan`으로
파일별 remove/edit/keep/conflict 표를 받아 검토하고, 그 digest로 `migration-apply`한다. 적용 결과는 작업 트리 변경으로만
남으며 stage·commit·push하지 않는다 — 정리 커밋은 사용자가 별도로 검토한다. 활성 1.0 작업이 있으면 적용되지 않는다.
2026-09-22 기준 ohmypm 자체만 전환했다. odin-3.0·log_moniteoling 전환은 별도 요청이다(pending 참조).

스킬은 `ohmypm:kickoff-interview`처럼 이름공간이 붙는다. `plugin/`을 고쳤으면 plugin.json의 version을 올리고 `claude plugin update ohmypm@ohmypm-local` — 버전이 같으면 갱신하지 않는다.
플러그인 갱신 뒤 프로젝트에서 `ws_upgrade.py`를 다시 실행하면 새 runtime이 설치되고 **다음 작업부터** 쓰인다. 진행 중 작업은 고정 runtime을 계속 쓴다.

> screen-plan·grill 등 범용 글로벌 스킬과 Orca 동봉 스킬(orca-cli·orchestration·computer-use, `~/.agents/skills` + junction)은 플러그인 밖이다.
> 구 kickoff_pack(`npx skills add merryiscat/kickoff_pack`)은 더 쓰지 않는다 — kickoff-harness는 폐기됐고 나머지는 여기로 옮겼다.

## 4. 프로젝트 로컬 스킬 재설치 (skills-lock.json 기반)

```powershell
npx skills experimental_install
```

→ `fastapi` 스킬이 `.agents/skills`에 재설치된다(스킬 코드는 gitignore, **lock으로 재현** = npm lock 패턴).

> 명령 이름 주의: lock 복원은 `add`/`install`이 아니라 **`experimental_install`**이다
> (2026-09-10 실측 — `npx skills install`은 `add`로 해석돼 "Missing required argument: source"로 죽는다).

## 5. 세팅 wizard — `.env` + 부팅 자동실행

```powershell
scripts\setup_wizard.cmd
```

5단계로 묻는다:

1. **관리 대상 루트**(`PROJECTS_ROOT`) — 이 PC가 돌볼 프로젝트들의 상위 폴더. **PC마다 다르다.**
   기본값이 없으므로 비워두면 프로젝트 발견이 경고 후 아무것도 안 잡는다
2. 텔레그램 봇 토큰 (BotFather) — 비우면 알림만 조용히 건너뛰고 시스템은 정상 동작
3. chat_id
4. 발송 테스트
5. 로그인 시 자동 실행 등록 (시작프로그램 바로가기 → 창 없이 기동)

wizard는 대화형이라 **터미널에서 사람이 직접** 실행해야 한다.
수동으로 할 거면 `.env.example`을 `.env`로 복사해 채우고, 자동 실행은 아래 §6.

> `.env`에 **모델에 없는 키가 있으면 서버가 아예 안 뜬다**(pydantic-settings가
> `extra_forbidden`으로 거부). `.env.example`은 항상 `src/config/settings.py`와 맞춰 둔다 —
> 2026-09-10에 이미 제거된 `HEARTBEAT_SEC`가 남아 있어 새 PC가 그대로 밟았다.

## 6. 기동 · 자동 실행 · 종료

```powershell
scripts\run_ohmypm.cmd          # 창 + 실시간 로그로 기동 (http://127.0.0.1:8123)
scripts\stop_ohmypm.cmd         # 종료 (8123 리스닝 프로세스를 잡아 끈다)
```

`data/ohmypm.db`는 첫 기동에 생성된다. 프로젝트 발견은 기동이 아니라 **스캔**에서 일어난다 —
새 PC는 대시보드 '스캔' 버튼(`POST /api/scan`)을 한 번 눌러 목록이 보이면 성공.

**정시 배치를 안 쓰는 PC**: `.env`에 `SCHEDULER_ENABLED=false`. 폴더로만 관리하는 프로젝트가 많거나
인터넷이 제한적인 PC용 — cron(스캔·일간보고·게시판·전문가수집)을 걸지 않고 대시보드/API로만 돌린다.
일간보고를 즉시 한 번 돌려보려면 `scripts\run_report_once.cmd`.

**로그인 시 자동 실행**(창 없이):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\startup_shortcut.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\startup_shortcut.ps1 -Remove   # 해제
```

시작프로그램 폴더에 `ohmyPM.lnk`를 만든다. 대상은 `.venv\Scripts\pythonw.exe`
(GUI 서브시스템 = 콘솔 창이 아예 없음) + `scripts\run_ohmypm_hidden.py`.
창이 없으니 로그는 `logs\server_console.log`로 간다.

**오르카에서 이 방을 열면 자동 기동**(2026-09-16 사용자 확정, 이 PC 기본):
`.claude/hooks/ohmypm-server.ps1`을 SessionStart 훅으로 걸어 뒀다(`.claude/settings.json`).
127.0.0.1:8123을 누가 듣고 있으면 아무것도 안 하고, 비어 있으면 위 자동 실행과 같은 방식
(`pythonw` + `run_ohmypm_hidden.py`)으로 띄운 뒤 포트가 잡힐 때까지 최대 8초 기다렸다 보고한다.
Orca 자동화(`orca automations`)는 스케줄 트리거뿐이라 '앱 실행 시'로는 못 건다.
로그인 자동 실행과 같이 쓸 필요는 없다 — 둘 중 하나면 충분하다(중복 기동은 포트 확인으로 막힌다).

> **막다른 길 둘 (2026-09-10 실측, 되풀이 금지)**
> - `schtasks /create /sc onlogon`은 **관리자 권한**을 요구한다(액세스 거부). 시작프로그램
>   폴더는 사용자 자기 것이라 승격이 필요 없다. `scripts\register_task.cmd`는 관리자로
>   돌릴 때를 위한 대안으로만 남겨 둔다.
> - **VBS 런처는 쓰지 마라.** 최신 Windows 11(10.0.26200)에서 Windows Script Host가
>   `WScript.Echo` 한 줄에도 "메모리 리소스가 부족" 오류로 죽는다. VBScript가 기능 분리된
>   탓이다. 단 `WScript.Shell` **COM 객체**는 멀쩡해서 .lnk 생성에는 쓸 수 있다
>   (깨진 건 `wscript.exe` 실행기뿐).

## 7. MCP 승인 (각 PC)

Playwright·context7 MCP는 프로젝트에 등록돼 있으나 각 PC에서 승인 필요:

```powershell
claude   # 실행 후 pending MCP(playwright·context7) 승인
```

## 8. 위키 운영 파일 (선택)

`docs/status.md` · `log.md` · `mistakes.md` · `pending.md`는 git에 없다. 이 PC에서 처음
작업할 때 새로 만든다(빈 파일이어도 됨) — 규약은 [conventions-wiki.md](conventions-wiki.md).

---

## 검증 (2026-09-10, `D:\dev\project\ohmypm`)

1~4·6번을 이 PC에서 실제로 돌려 확인했다 — `uv sync` → `.env` 작성 →
`npx skills experimental_install`(fastapi 1개) → `scripts\run_ohmypm.cmd`.
`data/ohmypm.db` 자동 생성, `PROJECTS_ROOT=D:\dev\project` 하위 **8개 프로젝트 발견**,
`GET /api/projects` 200 확인.

6번 자동 실행도 실측했다 — `startup_shortcut.ps1`로 등록 후 바로가기를 직접 실행해
창 없이 기동(`pythonw`) + HTTP 200 확인.

5번 wizard는 대화형(TTY 필요)이라 **텔레그램 3단계와 등록 실행은 미검증**이다. 다만
wizard가 쓰는 경로 산출은 따로 확인했다 — cwd를 `C:\`로 두고도 `REPO_ROOT`가 저장소로
잡히고, `ENV_FILE`이 저장소의 `.env`, `write_env` 2회에 1줄(멱등). `.env`는 손으로 썼다.

## 아직 안 된 것

- **lychee**(링크 점검) — 구현되면 `winget install lycheeverse.lychee` 추가
- **SQLite 초기화 스크립트** — 현재는 첫 기동 시 `src/db/schema.sql`로 자동 생성. 별도 스크립트 불요
