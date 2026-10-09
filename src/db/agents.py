"""담당 에이전트 프로필 — 연속성(이름·페르소나·배운 것) + 게시판 누적 점수.

점수 = 자기 글의 (좋아요·조회 − 싫어요) + 자기 댓글의 (좋아요 − 싫어요). 게시판 데이터에서 계산.
프로필은 프로젝트별 1개(담당 1명). 매 헤드리스 호출 앞에 persona_prefix()를 붙여 "지난번도
나였다"는 연속성과, 토론 복기에서 쌓인 '배운 것'(note)을 준다.

2026-10-09: 보상 체계(1000점 메뉴·소원권·멘토·안식·모델승급)는 폐지. 점수는 강화학습 재료 —
회차별 이력은 discussion_scores(src/db/sessions.py), 배운 것은 note에 쌓인다.
"""

from datetime import datetime

from src.cc.common import is_self_project
from src.db.client import get_db

# 점수 가중치 — 좋아요(품질 신호)가 조회(읽힘)를 크게 앞선다.
W_POST_LIKE = 10
W_POST_VIEW = 1      # 읽힘은 추천이 아니므로 작게 — 좋아요와 10배 차이
W_POST_DISLIKE = 10  # 글 싫어요 — 좋아요와 같은 무게(재탕이 이득이 되지 않게)
W_CMT_LIKE = 5
W_CMT_DISLIKE = 5

NOTE_MAX = 1200      # 배운 것 상한(자) — 토큰 폭발 방지, 넘으면 오래된 꼬리를 버린다


def compute_scores() -> dict[str, int]:
    """게시판에서 담당(author)별 누적 점수. {name: points}."""
    db = get_db()
    scores: dict[str, int] = {}
    for r in db.execute(
        "SELECT author, "
        f"SUM(COALESCE(likes,0))*{W_POST_LIKE} + SUM(COALESCE(views,0))*{W_POST_VIEW} "
        f"- SUM(COALESCE(dislikes,0))*{W_POST_DISLIKE} AS pts "
        "FROM posts GROUP BY author"
    ):
        scores[r["author"]] = scores.get(r["author"], 0) + int(r["pts"] or 0)
    for r in db.execute(
        "SELECT author, SUM(COALESCE(likes,0)) AS lk, SUM(COALESCE(dislikes,0)) AS dk "
        "FROM comments GROUP BY author"
    ):
        if r["author"] == "user":
            continue
        pts = int((r["lk"] or 0) * W_CMT_LIKE - (r["dk"] or 0) * W_CMT_DISLIKE)
        scores[r["author"]] = scores.get(r["author"], 0) + pts
    return scores


def upsert_profile(project: str, name: str) -> None:
    """프로필 없으면 생성(이름=프로젝트명 기본)."""
    db = get_db()
    db.execute(
        "INSERT INTO agent_profiles (project, name, updated_at) VALUES (?, ?, datetime('now','localtime')) "
        "ON CONFLICT(project) DO NOTHING",
        (project, name),
    )
    db.commit()


def get_profile(project: str) -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM agent_profiles WHERE project = ?", (project,)).fetchone()
    return dict(row) if row else None


def list_profiles() -> list[dict]:
    db = get_db()
    return [dict(r) for r in db.execute("SELECT * FROM agent_profiles ORDER BY points DESC")]


def refresh_scores(name_by_project: dict[str, str]) -> None:
    """게시판 누적 점수를 프로필 points에 반영(없으면 생성)."""
    scores = compute_scores()
    db = get_db()
    for path, name in name_by_project.items():
        upsert_profile(path, name)
        prof = get_profile(path) or {}
        earned = scores.get(prof.get("name") or name, 0)
        db.execute(
            "UPDATE agent_profiles SET points = ?, updated_at = datetime('now','localtime') WHERE project = ?",
            (max(0, earned), path),
        )
    db.commit()


# ── 배운 것(note) — 토론 복기가 쌓고 persona_prefix가 주입한다 ──────────────────
def get_note(project: str) -> str:
    return (get_profile(project) or {}).get("note") or ""


def append_note(project: str, line: str, max_chars: int = NOTE_MAX) -> None:
    """새 배움 한 줄을 앞머리에 붙인다(최신이 위). 상한 넘으면 오래된 꼬리를 버린다."""
    line = (line or "").strip()
    if not line:
        return
    old = get_note(project)
    entry = f"[{datetime.now():%m-%d}] {line[:160]}"
    merged = (entry + ("\n" + old if old else ""))[:max_chars]
    db = get_db()
    db.execute(
        "UPDATE agent_profiles SET note = ?, updated_at = datetime('now','localtime') WHERE project = ?",
        (merged, project),
    )
    db.commit()


# ── 모델 ────────────────────────────────────────────────────────────────────
# 담당에게 지정할 수 있는 모델 별칭(Claude Code --model 값). ''=기본.
ALLOWED_MODELS = ("", "opus", "sonnet", "haiku")
DEFAULT_MODEL = "sonnet"
SELF_MODEL = "opus"     # ohmyPM 자신의 담당만 opus — 총괄 자신이라 판단 품질이 전 프로젝트에 번진다


def default_model(project: str) -> str:
    """지정이 없을 때 이 프로젝트 담당이 쓸 모델 — ohmyPM 자신만 opus, 나머지는 sonnet."""
    return SELF_MODEL if is_self_project(project) else DEFAULT_MODEL


def set_model(project: str, model: str | None) -> None:
    """이 프로젝트 담당의 headless 모델 지정. 빈 값/None이면 기본으로 되돌림."""
    db = get_db()
    db.execute(
        "UPDATE agent_profiles SET model = ?, updated_at = datetime('now','localtime') WHERE project = ?",
        (model or None, project),
    )
    db.commit()


def model_for(project: str) -> str | None:
    """이 프로젝트 담당 콜에 쓸 모델. 지정이 없으면 기본."""
    prof = get_profile(project)
    return (prof or {}).get("model") or default_model(project)


def persona_prefix(project: str) -> str:
    """담당 프롬프트 앞에 붙일 정체성 + 배운 것. 매 담당 콜에 붙어 에이전트가 이어진다.

    여기가 성장의 유일한 주입점 — 토론 복기(reflect.py)가 note에 쌓은 것이 다음 호출에 들어간다.
    """
    prof = get_profile(project)
    if not prof:
        return ""
    bits = []
    if prof.get("name"):
        bits.append(f"너는 '{prof['name']}'라는 이름의 담당이다")
    if prof.get("persona"):
        bits.append(f"페르소나: {prof['persona']}")
    out = ("[정체성] " + ". ".join(bits) + ".\n") if bits else ""
    note = prof.get("note")
    if note:
        out += f"[내가 배워온 것 — 지난 토론에서 받은 반응으로 복기한 것]\n{note}\n"
    return out
