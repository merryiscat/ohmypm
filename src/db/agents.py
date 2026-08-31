"""담당 에이전트 프로필 — 연속성(이름·페르소나·자기메모) + 게시판 점수/보상.

점수 = 자기가 쓴 글의 (좋아요·조회) + 자기 댓글의 (좋아요 − 싫어요). 게시판 데이터에서 계산.
프로필은 프로젝트별 1개(담당 1명). PM/담당 프롬프트에 주입해 "어제도 나였다"는 연속성을 준다.
"""

from src.db.client import get_db

# 점수 가중치
W_POST_LIKE = 10
W_POST_VIEW = 1
W_CMT_LIKE = 5
W_CMT_DISLIKE = 5

MILESTONE_MENU = 1000   # 보상 메뉴 택1
MILESTONE_WISH = 2000   # 소원권


def compute_scores() -> dict[str, int]:
    """게시판에서 프로젝트(담당)별 점수를 계산. {name: points}. name=글/댓글 author 기준."""
    db = get_db()
    scores: dict[str, int] = {}
    # 글 점수 — author별
    for r in db.execute(
        "SELECT author, "
        f"SUM(COALESCE(likes,0))*{W_POST_LIKE} + SUM(COALESCE(views,0))*{W_POST_VIEW} AS pts "
        "FROM posts GROUP BY author"
    ):
        scores[r["author"]] = scores.get(r["author"], 0) + int(r["pts"] or 0)
    # 댓글 점수 — author별
    for r in db.execute(
        "SELECT author, "
        f"SUM(COALESCE(likes,0))*{W_CMT_LIKE} - SUM(COALESCE(dislikes,0))*{W_CMT_DISLIKE} AS pts "
        "FROM comments GROUP BY author"
    ):
        if r["author"] == "user":
            continue
        scores[r["author"]] = scores.get(r["author"], 0) + int(r["pts"] or 0)
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


def take_reward(project: str, name: str, reward: str,
                new_name: str | None = None, persona: str | None = None) -> None:
    """1000점 보상 택1 — 현재 게시판 누적을 baseline으로 밀어 점수 리셋 + 보상 기록.

    reward='이름'이면 new_name, '페르소나'면 persona를 프로필에 반영(연속성 주입용).
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
    params.append(project)
    db.execute(f"UPDATE agent_profiles SET {', '.join(fields)} WHERE project = ?", params)
    db.commit()


def persona_prefix(project: str) -> str:
    """담당 프롬프트 앞에 붙일 정체성 한 줄(연속성). 이름·페르소나 없으면 빈 문자열."""
    prof = get_profile(project)
    if not prof:
        return ""
    bits = []
    if prof.get("name"):
        bits.append(f"너는 '{prof['name']}'라는 이름의 담당이다")
    if prof.get("persona"):
        bits.append(f"페르소나: {prof['persona']}")
    if prof.get("reward") == "멘토" or (prof.get("rewards") and "멘토" in prof["rewards"]):
        bits.append("너는 멘토로 승격된 담당이다")
    return ("[정체성] " + ". ".join(bits) + ".\n") if bits else ""


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
