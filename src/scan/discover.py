"""프로젝트 발견 — projects_root 하위 폴더를 순회해 docs 위키가 있는 프로젝트를 등록."""

from pathlib import Path

from loguru import logger

from src.config.settings import settings
from src.db import projects as projects_db


def discover_projects() -> list[dict]:
    """projects_root 하위 1차 폴더 중 docs/ 있는 것을 관리 대상으로 upsert.

    MVP: docs 위키 있는 것만 등록(없는 건 케이스 14 온보딩 대상).
    숨김 폴더(.venv 등)는 제외.
    """
    root = Path(settings.projects_root)
    found: list[dict] = []
    if not root.is_dir():
        logger.warning(f"[발견] projects_root 없음: {root}")
        return found

    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        has_wiki = (child / "docs").is_dir()
        if not has_wiki:
            continue  # MVP는 위키 있는 것만
        projects_db.upsert_project(str(child), child.name, has_wiki)
        found.append({"path": str(child), "name": child.name, "has_wiki": has_wiki})

    logger.info(f"[발견] 위키 있는 프로젝트 {len(found)}개")
    return found
