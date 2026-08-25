"""자율 행동 로그 (케이스 15). 각 자율 행동을 git 커밋 SHA와 함께 남겨 되돌릴 수 있게."""

from src.db.client import get_db


def log_action(
    project: str,
    action: str,
    commit_sha: str | None = None,
    reason: str | None = None,
) -> None:
    """자율로 한 일 기록. commit_sha가 롤백 단위."""
    db = get_db()
    db.execute(
        "INSERT INTO autolog (project, action, commit_sha, reason) VALUES (?, ?, ?, ?)",
        (project, action, commit_sha, reason),
    )
    db.commit()


def list_actions(limit: int = 100) -> list[dict]:
    """최근 자율 행동 내역 (최신순)."""
    db = get_db()
    return [
        dict(row)
        for row in db.execute(
            "SELECT * FROM autolog ORDER BY created_at DESC LIMIT ?", (limit,)
        )
    ]
