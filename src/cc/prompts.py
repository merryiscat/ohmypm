"""에이전트 지시문 로더 — 지시문 본문은 코드가 아니라 `prompts/` 문서 파일에 있다.

2026-09-06 사용자 확정: 지시문을 코드에 하드코딩하지 않는다. 각 프롬프트는
`prompts/<이름>.md` 파일이고, 자리표시자는 `${변수}` 형식(string.Template)이다.

- 본문 템플릿(함수형): **매 호출 파일을 새로 읽는다** → 파일을 고치면 즉시 반영(재시작 불필요)
- 시스템 프롬프트(상수형): 서버 시작 시 한 번 읽는다 → 고치면 서버 재시작 필요
- 이 모듈에는 텍스트가 아니라 조립 로직(빈 값 기본치, 조건부 블록, 게이트 부착)만 남는다
"""

from pathlib import Path
from string import Template

# 프롬프트 문서 폴더 — 저장소 루트/prompts (사용자·에이전트가 직접 읽고 고치는 대상)
PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def load(name: str) -> str:
    """프롬프트 파일 원문. 매 호출 새로 읽는다."""
    return (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


def render(template_id: str, /, **vars: str) -> str:
    """프롬프트 파일의 ${변수}를 채워 완성한다. 모르는 ${}는 그대로 둔다(안전).

    첫 인자는 위치 전용 — 템플릿 변수 이름(name 등)과 충돌하지 않게.
    """
    return Template(load(template_id)).safe_substitute(**vars)


# ── 시스템 프롬프트 (서버 시작 시 로딩 — 수정하면 재시작 필요) ──────────────
GATE = "\n\n" + load("gate")
JUDGE_SYSTEM = load("judge_system")
ROOM_SYSTEM = load("room_system")
PM_SYSTEM = load("pm_system")
MANAGE_SYSTEM = load("manage_system")
FEEDBACK_SYSTEM = load("feedback_system")
FOLLOWUP_SYSTEM = load("followup_system")
BOARD_WRITE_SYSTEM = load("board_write_system")
BOARD_SYSTEM = load("board_system")
REWARD_SYSTEM = load("reward_system")
MANAGER_SYSTEM = load("manager_system")
REPROCESS_SYSTEM = load("reprocess_system")
TIDY_SYSTEM = load("tidy_system")
HARNESS_AUDIT_SYSTEM = load("harness_audit_system")
BASELINE_NOTE = load("baseline_note")
ONBOARDING_SYSTEM = load("onboarding_system")
PM_CHAT_SYSTEM = load("pm_chat_system")
EXPERT_SYSTEM = load("expert_system")
ISSUE_VERIFY_SYSTEM = load("issue_verify_system")

# 1000점 보상 메뉴 (에이전트가 택1) — 데이터라 코드에 남긴다.
# 맨 앞 '모델승급'이 기본 보상(2026-09-07) — 특별한 이유가 없으면 이걸 받는다.
REWARD_MENU = [
    "모델승급",
    "이름", "페르소나", "멘토", "전문가개업", "후배지명", "1일안식", "명예졸업", "대문표창",
]
DEFAULT_REWARD = "모델승급"


# ── 본문 템플릿 (매 호출 파일 재로딩 — 수정 즉시 반영) ─────────────────────
def room_chat(project_name: str, project_path: str, history: str) -> str:
    return render("room_chat", project_name=project_name, project_path=project_path,
                  history=history)


def pm_turn(project_name: str, facts: str, history: str, issues: str = "") -> str:
    return render("pm_turn", project_name=project_name, facts=facts,
                  issues=issues or "(이슈 없음)",
                  history=history or "(아직 없음 — 첫 턴)")


def pm_manage(project_name: str, issue_list: str, transcript: str) -> str:
    return render("pm_manage", project_name=project_name,
                  issue_list=issue_list or "(없음)", transcript=transcript or "(대화 없음)")


def post_feedback(author: str, project_path: str, title: str, body: str, comments: str) -> str:
    return render("post_feedback", author=author, project_path=project_path,
                  title=title, body=body[:400], comments=comments)


def comment_followup(project_name: str, project_path: str, threads: str) -> str:
    return render("comment_followup", project_name=project_name,
                  project_path=project_path, threads=threads)


def daily_agent_answer(project_name: str, project_path: str, question: str, history: str) -> str:
    return render("daily_agent_answer", project_name=project_name, project_path=project_path,
                  question=question, history=history or "(첫 질문)")


def board_write(project_name: str, project_path: str) -> str:
    return render("board_write", project_name=project_name, project_path=project_path)


def board_comment(project_name: str, project_path: str, board_text: str) -> str:
    return render("board_comment", project_name=project_name, project_path=project_path,
                  board_text=board_text)


def reward_choice(name: str, model: str = "", next_model: str = "") -> str:
    """1000점 보상 선택 프롬프트. 모델승급이 기본 보상이라 현재/다음 모델을 같이 알려준다.

    최상위(opus)라 올릴 곳이 없으면 승급 줄을 '이번엔 불가'로 바꿔 다른 보상을 고르게 한다.
    """
    if next_model:
        line = (f"- 모델승급 (기본 보상 — 특별한 이유가 없으면 이걸 골라라): "
                f"네 두뇌를 {model} → {next_model} 로 영구 승급. 앞으로 모든 네 작업이 더 좋은 모델로 돈다")
    else:
        line = (f"- 모델승급: 너는 이미 최상위 모델({model})이라 이번엔 고를 수 없다 "
                f"— 아래 중에서 골라라")
    return render("reward_choice", name=name, model_line=line)


def wish_prompt(name: str) -> str:
    return render("wish_prompt", name=name)


def manager_plan(journal: str, projects_digest: str) -> str:
    return render("manager_plan", journal=journal or "(첫날 — 저널 없음)",
                  projects_digest=projects_digest)


def manager_close(journal: str, results_digest: str, best_text: str = "") -> str:
    best_block = f"\n[오늘의 베스트(게시판 집계) — 표창 대상]\n{best_text}\n" if best_text else ""
    best_rule = (
        " → 맨 끝에 '## 오늘의 표창' 절을 넣어 위 베스트 글·조언을 쓴 담당을 한 줄로 칭찬한다"
        if best_text else ""
    )
    return render("manager_close", journal=journal or "(첫날)", results_digest=results_digest,
                  best_block=best_block, best_rule=best_rule)


def tidy_docs(project_name: str, project_path: str, facts: str) -> str:
    """기록 정리(야간 ①전) — 실제 작업(커밋·작업 중 파일)과 어긋난 문서를 맞추게 한다."""
    return render("tidy_docs", project_name=project_name, project_path=project_path, facts=facts)


def reprocess_docs(project_name: str, project_path: str, material: str) -> str:
    return render("reprocess_docs", project_name=project_name, project_path=project_path,
                  material=material)


def harness_audit_prompt(project_name: str, project_path: str, baseline: str,
                         meta: str = "") -> str:
    meta_block = (
        f"{meta}\n★ 분류가 '외부 클론'·'보관용'이면 저장소 안에 어떤 파일도 만들지 말고 "
        f"리포트만 내라(업스트림 오염·아카이브 불변성 보호).\n\n" if meta else ""
    )
    return render("harness_audit_prompt", project_name=project_name, project_path=project_path,
                  baseline=baseline, meta_block=meta_block) + GATE


def onboarding_review(project_name: str, project_path: str, expert_ref: str = "",
                      meta: str = "") -> str:
    ref_block = (
        f"\n[하네스 전문가 참고 지식 — 권장 조치의 근거로 활용]\n{expert_ref}\n" if expert_ref else ""
    )
    meta_block = f"\n{meta}\n" if meta else ""
    return render("onboarding_review", project_name=project_name, project_path=project_path,
                  ref_block=ref_block, meta_block=meta_block) + GATE


def pm_chat(journal: str, board_brief: str, history: str, message: str) -> str:
    return render("pm_chat", journal=journal or "(아직 없음)", board_brief=board_brief or "(없음)",
                  history=history or "(첫 질문)", message=message)


def expert_collect(topic: str, existing: str) -> str:
    return render("expert_collect", topic=topic,
                  existing=existing or "(아직 비어 있음 — 처음부터 정리)")


def expert_consult(topic: str, wiki: str, question: str) -> str:
    return render("expert_consult", topic=topic,
                  wiki=wiki or "(비어 있음 — 웹으로 조사해 답하라)", question=question)


def summarize_unresolved(project_name: str, items: list[str]) -> str:
    body = "\n".join(f"- {t}" for t in items)
    return render("summarize_unresolved", project_name=project_name, body=body)


def judge_issues(project_name: str, candidates: list[dict], docs_path: str) -> str:
    lines = []
    for c in candidates:
        lines.append(
            f"{c['i']}. [{c['kind_guess']}] \"{c['title']}\"  (출처: {c.get('source', '?')})"
        )
    body = "\n".join(lines)
    return render("judge_issues", project_name=project_name, docs_path=docs_path,
                  body=body) + GATE


def issue_verify(project_name: str, project_path: str, issues: str) -> str:
    """담당이 새 이슈를 실제 코드와 대조해 이미 완결됐는지 확인하는 프롬프트(2026-09-06 신설)."""
    return render("issue_verify", project_name=project_name, project_path=project_path,
                  issues=issues)
