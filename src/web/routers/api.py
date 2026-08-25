"""대시보드 데이터 API (JSON). 화면 JS가 이걸 fetch해 카드를 그린다."""

from fastapi import APIRouter

from src.db import issues as issues_db
from src.db import projects as projects_db

router = APIRouter(prefix="/api")


@router.get("/projects")
def get_projects() -> list[dict]:
    """관리 대상 프로젝트 목록."""
    return projects_db.list_projects()


@router.get("/issues")
def get_issues(status: str | None = None) -> list[dict]:
    """이슈 목록(선택: 상태 필터). 기한 임박순."""
    return issues_db.list_issues(status)


@router.post("/scan")
def trigger_scan() -> dict:
    """수동 스캔 트리거(대시보드 '스캔' 버튼)."""
    from src.scan import run_scan

    return run_scan()
