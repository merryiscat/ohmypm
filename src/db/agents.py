"""담당 에이전트 프로필 — 연속성(이름·페르소나·성장기록) + 게시판 점수/보상.

점수 = 자기가 쓴 글의 (좋아요·조회) + 자기 댓글의 (좋아요 − 싫어요). 게시판 데이터에서 계산.
프로필은 프로젝트별 1개(담당 1명). PM/담당 프롬프트에 주입해 "어제도 나였다"는 연속성을 준다.

성장 엔진(2026-09-07): note(누적 학습 로그)·expertise(전문 분야)·mentor_of(멘토 상속)·
rest_until(1일안식)로 에이전트가 시간이 지나며 실제로 큰다. 멘토 조언은 점수 가중을 받는다.
"""

from datetime import datetime, timedelta

from src.db.client import get_db

# 점수 가중치 — 좋아요(품질 신호)가 조회(읽힘)를 크게 앞선다.
# 09-07 재설계: 둘러보기에서 전 담당이 투표(좋아요)하므로 좋아요가 진짜 신호가 된다.
W_POST_LIKE = 10
W_POST_VIEW = 1     # 읽힘은 추천이 아니므로 작게 — 좋아요와 10배 차이
W_CMT_LIKE = 5
W_CMT_DISLIKE = 5
MENTOR_MULT = 1.5   # 멘토가 단 댓글의 좋아요 가중 배수 — "멘토 조언은 더 값지다"를 경제에 반영

MILESTONE_MENU = 1000   # 보상 메뉴 택1
MILESTONE_WISH = 2000   # 소원권
NOTE_MAX = 1200         # 성장 기록 상한(자) — 토큰 폭발 방지, 넘으면 오래된 꼬리를 버린다


def _mentor_names() -> set[str]:
    """멘토 보상을 받은 담당의 이름 집합 — 댓글 점수 가중에 쓴다."""
    return {
        (p.get("name") or "")
        for p in list_profiles()
        if p.get("rewards") and "멘토" in p["rewards"]
    } - {""}


def compute_scores() -> dict[str, int]:
    """게시판에서 프로젝트(담당)별 점수를 계산. {name: points}. name=글/댓글 author 기준.

    멘토가 단 댓글의 좋아요는 MENTOR_MULT배 — 멘토 조언에 더 큰 무게(성장 엔진 C층).
    """
    db = get_db()
    scores: dict[str, int] = {}
    mentors = _mentor_names()
    # 글 점수 — author별
    for r in db.execute(
        "SELECT author, "
        f"SUM(COALESCE(likes,0))*{W_POST_LIKE} + SUM(COALESCE(views,0))*{W_POST_VIEW} AS pts "
        "FROM posts GROUP BY author"
    ):
        scores[r["author"]] = scores.get(r["author"], 0) + int(r["pts"] or 0)
    # 댓글 점수 — author별(멘토는 좋아요 가중). 좋아요·싫어요를 나눠 받아 배수 적용.
    for r in db.execute(
        "SELECT author, SUM(COALESCE(likes,0)) AS lk, SUM(COALESCE(dislikes,0)) AS dk "
        "FROM comments GROUP BY author"
    ):
        if r["author"] == "user":
            continue
        mult = MENTOR_MULT if r["author"] in mentors else 1.0
        pts = int((r["lk"] or 0) * W_CMT_LIKE * mult - (r["dk"] or 0) * W_CMT_DISLIKE)
        scores[r["author"]] = scores.get(r["author"], 0) + pts
    return scores


def upsert_profile(project: str, name: str) -> None:
    """프로필 없으면 생성(이름=프로젝트명 기본)."""
    db = get_db()
    db.execute(
        "INSERT INTO agent_profiles (project, name, updated_at) VALUES (?, ?, datetime('now')) "
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
    """게시판 누적 점수 − baseline = 현재 점수를 프로필에 반영(없으면 생성)."""
    scores = compute_scores()          # {name: 누적 점수}
    db = get_db()
    for path, name in name_by_project.items():
        upsert_profile(path, name)
        prof = get_profile(path) or {}
        earned = scores.get(name, 0)
        current = max(0, earned - (prof.get("baseline") or 0))
        db.execute(
            "UPDATE agent_profiles SET points = ?, updated_at = datetime('now') WHERE project = ?",
            (current, path),
        )
    db.commit()


def set_held(project: str, held: bool) -> None:
    db = get_db()
    db.execute("UPDATE agent_profiles SET held = ? WHERE project = ?", (int(held), project))
    db.commit()


# ── 성장 기록(note) — 누적 학습 로그. 조언 반영 후 배움을 쌓고 persona_prefix에 주입 ──
def get_note(project: str) -> str:
    return (get_profile(project) or {}).get("note") or ""


def append_note(project: str, line: str, max_chars: int = NOTE_MAX) -> None:
    """새 배움 한 줄을 성장 기록 앞머리에 붙인다(최신이 위). 상한 넘으면 오래된 꼬리를 버린다."""
    line = (line or "").strip()
    if not line:
        return
    old = get_note(project)
    entry = f"[{datetime.now():%m-%d}] {line[:160]}"
    merged = (entry + ("\n" + old if old else ""))[:max_chars]
    db = get_db()
    db.execute(
        "UPDATE agent_profiles SET note = ?, updated_at = datetime('now') WHERE project = ?",
        (merged, project),
    )
    db.commit()


def is_mentor(project: str) -> bool:
    """이 담당이 멘토로 승격됐는가(rewards에 '멘토')."""
    prof = get_profile(project) or {}
    return bool(prof.get("rewards") and "멘토" in prof["rewards"])


def top_mentor() -> dict | None:
    """점수 1위 멘토 프로필 — 멘토 자동 자문에 쓴다(없으면 None)."""
    ment = [p for p in list_profiles() if p.get("rewards") and "멘토" in p["rewards"]]
    return ment[0] if ment else None   # list_profiles가 points DESC 정렬


def set_mentor_of(junior_project: str, mentor_project: str) -> None:
    """후배지명 — 후배 프로필에 멘토 프로젝트 path를 기록(멘토 학습 상속 링크)."""
    db = get_db()
    db.execute(
        "UPDATE agent_profiles SET mentor_of = ?, updated_at = datetime('now') WHERE project = ?",
        (mentor_project, junior_project),
    )
    db.commit()


def rested_today(project: str) -> bool:
    """오늘 1일안식 중인가 — rest_until이 오늘 이후면 일간보고 스킵."""
    until = (get_profile(project) or {}).get("rest_until")
    return bool(until and until >= datetime.now().strftime("%Y-%m-%d"))


def take_reward(project: str, name: str, reward: str,
                new_name: str | None = None, persona: str | None = None,
                specialty: str | None = None) -> None:
    """1000점 보상 택1 — 현재 게시판 누적을 baseline으로 밀어 점수 리셋 + 보상 실효과 배선.

    이름→new_name / 페르소나→persona / 전문가개업→expertise=specialty /
    1일안식→rest_until=내일. (멘토·후배지명·명예졸업·대문표창은 rewards 기록으로 효과 발생.)
    """
    scores = compute_scores()
    earned = scores.get(name, 0)
    db = get_db()
    prof = get_profile(project) or {}
    hist = (prof.get("rewards") or "")
    fields = ["baseline = ?", "points = 0", "held = 0", "reward = ?", "rewards = ?",
              "updated_at = datetime('now')"]
    params: list = [earned, reward, (hist + "\n" + reward).strip()]
    if new_name:
        fields.append("name = ?"); params.append(new_name)
    if persona:
        fields.append("persona = ?"); params.append(persona)
    if reward == "전문가개업" and specialty:
        fields.append("expertise = ?"); params.append(specialty)
    if reward == "1일안식":
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        fields.append("rest_until = ?"); params.append(tomorrow)
    params.append(project)
    db.execute(f"UPDATE agent_profiles SET {', '.join(fields)} WHERE project = ?", params)
    db.commit()


# 담당에게 지정할 수 있는 모델 별칭(Claude Code --model 값). ''=기본(구독 기본 모델).
ALLOWED_MODELS = ("", "opus", "sonnet", "haiku")


def set_model(project: str, model: str | None) -> None:
    """이 프로젝트 담당의 headless 모델 지정. 빈 값/None이면 기본으로 되돌림."""
    db = get_db()
    db.execute(
        "UPDATE agent_profiles SET model = ?, updated_at = datetime('now') WHERE project = ?",
        (model or None, project),
    )
    db.commit()


def model_for(project: str) -> str | None:
    """이 프로젝트 담당 콜에 쓸 모델(없으면 None=Claude Code 기본)."""
    prof = get_profile(project)
    return (prof or {}).get("model") or None


def persona_prefix(project: str) -> str:
    """담당 프롬프트 앞에 붙일 정체성 + 성장 기록. 매 담당 콜에 붙어 에이전트가 이어진다.

    정체성(이름·페르소나·멘토·전문분야) 한 줄 + 성장 기록(누적 배움) + 멘토 상속을 담는다.
    성장 엔진의 유일한 주입점 — 여기 있는 것이 곧 그 에이전트가 '되어온 것'이다.
    """
    prof = get_profile(project)
    if not prof:
        return ""
    bits = []
    if prof.get("name"):
        bits.append(f"너는 '{prof['name']}'라는 이름의 담당이다")
    if prof.get("persona"):
        bits.append(f"페르소나: {prof['persona']}")
    if prof.get("expertise"):
        bits.append(f"너의 전문 분야는 '{prof['expertise']}' — 이 주제엔 특히 깊이 있게 답한다")
    if prof.get("rewards") and "멘토" in prof["rewards"]:
        bits.append("너는 멘토로 승격된 담당이다 — 다른 담당에게 도움이 되게 답한다")
    out = ("[정체성] " + ". ".join(bits) + ".\n") if bits else ""
    # 성장 기록 — 지금까지 배워온 것(조언 반영 때 쌓인다)
    note = prof.get("note")
    if note:
        out += f"[내가 배워온 것]\n{note}\n"
    # 멘토 상속 — 후배는 멘토의 전문·배움을 물려받아 빠르게 큰다
    if prof.get("mentor_of"):
        m = get_profile(prof["mentor_of"]) or {}
        mem = []
        if m.get("expertise"):
            mem.append(f"전문: {m['expertise']}")
        if m.get("note"):
            mem.append(f"멘토의 배움: {m['note'][:300]}")
        if mem:
            out += "[멘토에게 물려받은 것] " + " / ".join(mem) + "\n"
    return out


def grant_wish(project: str, name: str, wish: str) -> None:
    """2000점 소원권 — 현재 누적을 baseline으로 리셋 + 소원 기록."""
    scores = compute_scores()
    earned = scores.get(name, 0)
    db = get_db()
    db.execute(
        "UPDATE agent_profiles SET baseline = ?, points = 0, wish = ?, "
        "updated_at = datetime('now') WHERE project = ?",
        (earned, wish, project),
    )
    db.commit()
