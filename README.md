# ohmyPM

**내 컴퓨터 안의 모든 프로젝트를 매일 돌봐 주는 PM 에이전트**입니다. 그리고 프로젝트마다 "생각하는 자리"와 "손대는 자리"를 나눠 주는 **작업 구조**를 깔아 줍니다.

- 매일: 프로젝트 폴더를 훑어서 놓친 일·기한·방치·문서 붕괴를 찾아 대시보드와 알림으로 알려 줍니다.
- 프로젝트 시작할 때: 짧은 인터뷰로 기획서를 만들고, 기획·검토·구현이 서로 다른 AI에게 나뉘어 돌아가는 구조를 세팅합니다.

개발자가 아니어도 쓸 수 있게 썼습니다. 명령어는 복사해서 붙여 넣으면 됩니다.

---

## 1. 어떻게 돌아가나 (그림 한 장)

```
[main]  내 원본 폴더            ─ 합치고(머지) 올리기(푸시)만 한다. 일은 안 한다.
   │
   ├─ [pl]  기획 워크스페이스     ─ 터미널 둘이 한 방에 있다
   │     ├─ pl   (GPT 아스트라)   작업 스펙을 쓴다  ← 돈이 드는 자리, 두 번만 켠다
   │     └─ pl2  (Claude 페이블) 스펙을 검토하고, 일을 나눠 주고, 결과를 채점한다
   │
   └─ [T-001, T-002 …] 작업 워크스페이스
         └─ 워커 (Claude 소넷/오퍼스/페이블)  스펙대로만 만든다
```

한 바퀴는 이렇게 돕니다.

1. 내가 main에서 "이거 해 줘"라고 말한다.
2. pl이 **작업 스펙** 한 장을 쓴다. "무엇을, 어디까지, 다 됐다는 건 어떻게 확인하나"가 들어 있다.
3. pl2가 스펙을 **한 번** 검토한다. 고쳐 쓰지 않고 지적만 한다.
4. pl이 지적을 반영해 v2를 낸다. 여기까지가 아스트라를 쓰는 전부다.
5. 내가 승인한다.
6. pl2가 난이도에 맞는 워커를 새 워크스페이스에 띄우고 기다린다.
7. 워커가 끝내면 pl2가 스펙의 완료 기준으로 통과/실패를 매긴다.
8. main이 합치고 올린다.

왜 이렇게 나누나: 서로 다른 회사의 AI가 교차 검토할 때만 품질이 올라가고, 검토를 여러 번 돌리면 오히려 없는 문제를 만들어내며, 검토자가 통째로 다시 쓰면 망가진다는 연구 결과 때문입니다. 근거는 `docs/protocol.md` 맨 아래에 있습니다.

---

## 2. 준비물

| 필요한 것 | 왜 | 확인 방법 |
|---|---|---|
| Windows PC + git | 저장소와 워크스페이스 | 터미널에 `git --version` |
| [Orca](https://github.com/stablyai/orca) | 워크스페이스·터미널을 한 화면에서 굴리는 앱 | 설치 후 `orca --version` |
| Claude Code (Max 플랜) | pl2·워커·main 자리 | `claude --version` |
| Codex CLI + ChatGPT 유료 계정 | pl 자리(GPT 아스트라) | `codex --version` |
| Python 3.11 이상 + uv, Node.js 18 이상 | ohmyPM 자체 실행 | `uv --version`, `node --version` |

Codex는 종량·소액 결제라 **토큰을 아끼는 규칙**이 곳곳에 들어 있습니다. pl은 스펙 쓸 때만 켜고, 조사·대기·검증은 정액제인 Claude가 합니다.

---

## 3. 설치 (10분)

PowerShell을 열고 순서대로 붙여 넣습니다.

**① 저장소 받기**
```powershell
git clone https://github.com/merryiscat/ohmypm.git D:\dev\project\ohmypm
cd D:\dev\project\ohmypm
```
경로는 어디든 됩니다. 아래 명령의 경로만 같이 바꾸세요.

**② Codex 설치와 로그인**
```powershell
npm i -g @openai/codex
codex login          # 브라우저가 열리면 ChatGPT 계정으로 로그인
```
그 다음 `C:\Users\<내이름>\.codex\config.toml` 파일을 만들고 두 줄을 넣습니다.
```toml
model = "gpt-6-astra"
model_reasoning_effort = "high"
```

**③ ohmyPM 플러그인 설치** (킥오프·작업 구조·중계 절차가 전부 이 안에 있습니다)
```powershell
claude plugin marketplace add D:\dev\project\ohmypm\.claude-plugin\marketplace.json
claude plugin install ohmypm@ohmypm-local --scope user -y
claude plugin list        # ohmypm ... enabled 가 보이면 성공
```

**④ ohmyPM 앱 실행 준비** (대시보드·매일 점검이 필요할 때만)
```powershell
uv sync --all-extras
copy .env.example .env    # 열어서 PROJECTS_ROOT=내 프로젝트들이 있는 폴더 로 고친다
```
자세한 실행·자동 기동·다른 PC 재현 절차는 [docs/setup.md](docs/setup.md)에 있습니다.

**⑤ Orca에서 이 폴더 열기** — Orca 앱에서 `D:\dev\project\ohmypm`을 프로젝트로 추가합니다. 열면 대시보드 서버가 자동으로 뜹니다(`http://127.0.0.1:8123`).

---

## 4. 사용법

### 새 프로젝트를 시작할 때 — "킥오프 상담하자"

Orca에서 아무 Claude 터미널을 열고 이렇게 말합니다.

> 킥오프 상담하자

여섯 가지를 물어보고(무엇을·왜, 산출물, 스택, 화면, 외부 연동, 범위) 폴더·git·위키·기획서 초안까지 만들어 줍니다. 끝나면 이어서:

> 작업 구조 세팅하자

프로젝트가 작으면 "안 깔아도 된다"고 말해 줍니다. 깔기로 하면 파일 세트를 넣고 pl 워크스페이스를 열어 줍니다. 레퍼런스 조사나 유즈케이스 발굴은 기본 경로가 아니고, 필요할 때 pl이 요구하면 그때 돌립니다.

### 이미 있는 프로젝트에 붙일 때

그 프로젝트 폴더에서 Claude를 열고:

> pl 구조 붙이자

git이 없는 폴더면 로컬 `git init`부터 합니다. 큰 로그·백업·데이터 폴더는 추적하지 않고 워크스페이스에 링크로 공유하도록 잡아 줍니다.

### 일을 시킬 때 — main에 말한다

원본 폴더(main)의 Claude에게 평소처럼 말합니다.

> 금일 로그 검토해 줘

main은 직접 하지 않고 pl에 "스펙 써라" 한 줄을 넣습니다. 그 뒤로는 위 1절의 바퀴가 돕니다. 중간에 **승인 질문**이 한 번 옵니다(스펙 목표·범위·산출물 두 문장). "네"라고 하면 워커가 뜹니다.

- pl 터미널에 직접 말을 걸지 마세요. 아스트라가 그 자리에서 조사까지 하며 턴을 씁니다. 요청은 main에.
- 매일 반복하는 일(로그 검토 같은 것)은 첫 회만 스펙을 만들고, 다음부터는 pl 없이 pl2가 워커만 다시 띄웁니다.

### 매일 돌보기 — 대시보드

`http://127.0.0.1:8123`에 프로젝트별 현황·이슈·기한·일간보고가 뜹니다. 이 PC는 정시 배치를 꺼 두고(`.env`의 `SCHEDULER_ENABLED=false`) 필요할 때 대시보드에서 수동 실행합니다. 켜면 새벽에 스캔·일간보고가 자동으로 돕니다.

---

## 5. 프로젝트마다 생기는 파일

| 파일 | 하는 일 |
|---|---|
| `docs/roles.md` | 자리·모델·난이도 등급표. 모델을 바꾸면 여기만 고친다 |
| `docs/protocol.md` | 한 바퀴의 절차와 종료 조건, 연구 근거 |
| `docs/tasks/T-NNN-….md` | 작업 스펙. 완료 기준이 "관찰 가능한 문장"이어야 한다 |
| `docs/reviews/T-NNN.review-v1.md` | pl2의 검토서. 지적만, 재작성 없음 |
| `orca.yaml` · `.worktreeinclude` | 워크스페이스에 공유할 폴더와 복사할 비밀 파일 |
| `.githooks/pre-commit` | 기획 브랜치에서 코드 커밋을 막는 가드 |
| `AGENTS.md` · `CLAUDE.md` 블록 | Codex와 Claude가 각자 읽는 역할 규칙(10줄) |

---

## 6. 자주 묻는 것

**Q. pl이 멈춘 것 같아요.**
대부분 자기 몫을 끝내고 대기하는 상태입니다. 화면 아래에 "? 1 question"이 있으면 pl이 나에게 물은 것이니 `alt+↓`로 답하면 됩니다.

**Q. 아스트라 요금이 걱정돼요.**
한 작업당 아스트라는 두 턴(스펙 v1, v2)입니다. 조사·대기·채점은 Claude가 합니다. pl 터미널에 직접 말하지 않는 것이 제일 큰 절약입니다.

**Q. 워커가 옛날 코드 위에서 일했어요.**
워커 워크스페이스는 원격(origin/main) 기준으로 뜹니다. 배정 전에 main이 원격과 맞추고 푸시해야 합니다. 절차에 들어 있습니다.

**Q. 플러그인을 고쳤는데 반영이 안 돼요.**
`plugin/.claude-plugin/plugin.json`의 version을 올린 뒤 `claude plugin update ohmypm@ohmypm-local`. 이미 떠 있는 Claude 세션은 새로 열어야 읽습니다.

---

## 7. 더 읽기

- [docs/plan.md](docs/plan.md) — 왜 만들었나, 무엇을 결정했나
- [docs/setup.md](docs/setup.md) — 다른 PC에서 그대로 재현하는 절차
- [docs/deliverables.md](docs/deliverables.md) — 단계별로 어떤 산출물이 있어야 하는지
- [docs/protocol.md](docs/protocol.md) — 한 바퀴의 규칙과 연구 근거
- `plugin/skills/` — 킥오프·작업 구조·중계 스킬 원문
