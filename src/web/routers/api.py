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
    """수동 스캔 트리거(대시보드 '스캔' 버튼). 빠른 결정론 수집만 — 판정은 별도."""
    from src.scan import run_scan

    return run_scan()


@router.post("/judge")
def trigger_judge() -> dict:
    """수동 판정 트리거(대시보드 '판정' 버튼). 미판정 기한 후보를 에이전트가 가린다.

    LLM 호출이라 느릴 수 있음 — 스캔과 분리해 즉시 피드백을 안 막는다.
    """
    from src.cc.judge import run_judgment

    return run_judgment()
