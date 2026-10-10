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
    """프롬프트 파일의 ${변수}를 채워 완성한다. 모르는 ${}는 그대로 둔다(안전)."""
    return Template(load(template_id)).safe_substitute(**vars)


# ── 시스템 프롬프트 (서버 시작 시 로딩 — 수정하면 재시작 필요) ──────────────
GATE = "\n\n" + load("gate")
ROOM_SYSTEM = load("room_system")
FEEDBACK_SYSTEM = load("feedback_system")
FOLLOWUP_SYSTEM = load("followup_system")
BOARD_WRITE_SYSTEM = load("board_write_system")
BOARD_SYSTEM = load("board_system")
EXPERT_SYSTEM = load("expert_system")


# ── 본문 템플릿 (매 호출 파일 재로딩 — 수정 즉시 반영) ─────────────────────
def room_chat(project_name: str, project_path: str, history: str, weekly: str = "",
              cards: str = "") -> str:
    return render("room_chat", project_name=project_name, project_path=project_path,
                  history=history, weekly=weekly or "(아직 없음)", cards=cards or "(카드 없음)")


def post_feedback(author: str, project_path: str, title: str, body: str, comments: str) -> str:
    return render("post_feedback", author=author, project_path=project_path,
                  title=title, body=body[:400], comments=comments)


def comment_followup(project_name: str, project_path: str, threads: str) -> str:
    return render("comment_followup", project_name=project_name,
                  project_path=project_path, threads=threads)


def board_write(project_name: str, project_path: str, past_posts: str = "") -> str:
    """글쓰기 프롬프트. past_posts = 이 담당이 전에 올린 글 목록(재탕 방지용 기억)."""
    return render("board_write", project_name=project_name, project_path=project_path,
                  past_posts=past_posts or "(아직 올린 글이 없다 — 첫 글이다)")


def board_comment(project_name: str, project_path: str, board_text: str) -> str:
    return render("board_comment", project_name=project_name, project_path=project_path,
                  board_text=board_text)


def expert_consult(topic: str, wiki: str, question: str) -> str:
    return render("expert_consult", topic=topic,
                  wiki=wiki or "(비어 있음 — 웹으로 조사해 답하라)", question=question)


def model_catalog_update(vendor_name: str, source_key: str, source_url: str, window_note: str,
                         diff_text: str, tracked_models: list[str]) -> str:
    """모델 동향 소스의 달라진 절 → 추적 모델별 변경 JSON 생성 프롬프트.

    LLM은 텍스트만 반환(도구 없음) — 코드가 JSON 구조·필수 필드·모델 이름·출처 링크를 검증한다.
    """
    return render("model_catalog_update", vendor_name=vendor_name, source_key=source_key,
                  source_url=source_url, window_note=window_note, diff_text=diff_text,
                  tracked_models="\n".join(f"- {m}" for m in tracked_models)) + GATE


def model_profile(vendor_name: str, model: str, entries_text: str, overview_text: str) -> str:
    """모델 하나의 상세 프로필(개요·스펙·잘 쓰는 법·하네스 조정·주의) JSON 생성 프롬프트."""
    return render("model_profile", vendor_name=vendor_name, model=model,
                  entries_text=entries_text or "(기록 없음)",
                  overview_text=overview_text or "(공식 문서 발췌 없음)") + GATE
