"""프로젝트 발견 — projects_root 하위 폴더를 순회해 docs 위키가 있는 프로젝트를 등록."""

from pathlib import Path

from loguru import logger

from src.config.settings import settings
from src.db import projects as projects_db


def discover_projects() -> list[dict]:
    """projects_root 하위 1차 폴더 **전부**를 관리 대상으로 upsert.

    발견 조건은 폴더 존재뿐 — 관리 여부는 사용자가 x(제외)로 정한다(2026-09-05 사용자 확정,
    docs 없는 프로젝트야말로 세팅 대상이라 docs 조건을 없앰). 숨김 폴더(.venv 등)와
    사용자 제외 폴더만 건너뛴다. docs 유무는 has_wiki로 기록해 후속 단계가 참고한다.
    """
    root = Path(settings.projects_root)
    found: list[dict] = []
    if not root.is_dir():
        logger.warning(f"[발견] projects_root 없음: {root}")
        return found

    excluded = projects_db.disabled_paths()  # 사용자가 제외한 프로젝트는 다시 안 잡는다
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if str(child) in excluded:
            continue  # 관리 제외됨 (예: 안 쓰는 프로젝트)
        has_wiki = (child / "docs").is_dir()
        projects_db.upsert_project(str(child), child.name, has_wiki)
        found.append({"path": str(child), "name": child.name, "has_wiki": has_wiki})

    logger.info(f"[발견] 프로젝트 {len(found)}개 (위키 있음 {sum(1 for f in found if f['has_wiki'])}개)")
    return found
