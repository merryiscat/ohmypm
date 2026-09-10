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

## 3. 글로벌 스킬 — 킥오프팩 (`~/.claude/skills`)

킥오프 체인·screen-plan·grill·llmwiki 등은 글로벌이라 프로젝트에 안 딸린다:

```powershell
npx skills add merryiscat/kickoff_pack --all -g
```

> 참고: 팩 개발 PC는 글로벌 스킬이 kickoff_pack에 **junction**으로 연결돼 있다.
> 일반 PC는 위 명령으로 설치한다.

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
5. 작업 스케줄러 등록 (로그인 시 `scripts\run_ohmypm.cmd` 자동 실행)

wizard는 대화형이라 **터미널에서 사람이 직접** 실행해야 한다.
수동으로 할 거면 `.env.example`을 `.env`로 복사해 채우고, 스케줄러는
`scripts\register_task.cmd`를 관리자 권한으로 실행한다.

> `.env`에 **모델에 없는 키가 있으면 서버가 아예 안 뜬다**(pydantic-settings가
> `extra_forbidden`으로 거부). `.env.example`은 항상 `src/config/settings.py`와 맞춰 둔다 —
> 2026-09-10에 이미 제거된 `HEARTBEAT_SEC`가 남아 있어 새 PC가 그대로 밟았다.

## 6. 기동 · 확인

```powershell
scripts\run_ohmypm.cmd          # 대시보드 서버 (http://127.0.0.1:8123)
```

`data/ohmypm.db`는 첫 기동에 생성된다. 대시보드에서 발견된 프로젝트 목록이 보이면 성공.
일간보고를 즉시 한 번 돌려보려면 `scripts\run_report_once.cmd`.

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
`GET /api/projects` 200 확인. 5번 wizard는 대화형이라 사람이 직접 돌려야 해 미검증
(`.env`는 손으로 썼다).

## 아직 안 된 것

- **lychee**(링크 점검) — 구현되면 `winget install lycheeverse.lychee` 추가
- **SQLite 초기화 스크립트** — 현재는 첫 기동 시 `src/db/schema.sql`로 자동 생성. 별도 스크립트 불요
