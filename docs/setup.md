# ohmyPM 다른 PC 세팅 (재현 절차)

> 이 저장소를 새 PC에서 세팅하는 절차. 환경은 **두 층**이다 —
> ① `git clone`으로 딸려오는 프로젝트 로컬, ② 각 PC에 따로 세팅해야 하는 글로벌·런타임·시크릿.
> 셸은 **PowerShell** 기준(상위 CLAUDE.md).

## 1. 클론 (① 프로젝트 로컬)

```powershell
git clone https://github.com/merryiscat/ohmypm.git
cd ohmypm
```

clone으로 오는 것: `docs/`(기획·레퍼런스·유즈케이스·규약) · `CLAUDE.md` · `skills-lock.json` · `.gitignore`.
**안 오는 것**: 스킬 코드(재설치)·시크릿(.env)·위키 운영 파일(status/log/mistakes/pending — 로컬 전용).

## 2. 글로벌 스킬 — 킥오프팩 (② `~/.claude/skills`)

킥오프 체인·screen-plan·grill·llmwiki 등은 글로벌이라 프로젝트에 안 딸린다:

```powershell
npx skills add merryiscat/kickoff_pack --all -g
```

> 참고: 이 개발 PC는 팩 개발자 모드라 글로벌 스킬이 kickoff_pack에 **junction**으로 연결돼 있다.
> 일반 PC는 위 명령으로 설치하면 된다.

## 3. 프로젝트 로컬 스킬 재설치 (skills-lock.json 기반)

```powershell
npx skills install
```

→ `fastapi` 스킬이 `.agents/skills`에 재설치된다(스킬 코드는 gitignore, **lock으로 재현** = npm lock 패턴).

## 4. 런타임

- **Node.js 18+** — npx 스킬 설치용
- **Python 3.11+ 및 uv** — 소스 실행 (상위 CLAUDE.md: `uv` 우선)
- **git**
- **lychee** (링크 점검, 구현 시) — `winget install lycheeverse.lychee` (또는 scoop/choco)

## 5. MCP 승인 (② 각 PC)

Playwright·context7 MCP는 프로젝트에 등록돼 있으나 각 PC에서 승인 필요 — 화면 구현·검수 단계에서:

```powershell
claude   # 실행 후 pending MCP(playwright·context7) 승인
```

## 6. 시크릿 (`.env` — 절대 커밋 안 함)

**구현 단계에서 확정.** 텔레그램 봇 토큰 등. `.env.example`(생기면)을 복사해 채운다.

---

## TODO (구현 후 이 문서 갱신)

- 런타임 의존성 확정 (`pyproject.toml`/`requirements`) → 3·4번 구체화
- `.env.example` 작성 (텔레그램 토큰·관리 대상 경로 등)
- 실행 스케줄 등록 절차 (Windows scheduled tasks / cron + heartbeat) + `.cmd` 동봉
- SQLite 초기화 스크립트
- (선택) `setup.cmd` 반자동 세팅 스크립트 — clone에 안 딸리는 ②~⑥을 순서대로
