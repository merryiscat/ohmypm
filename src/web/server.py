"""FastAPI 대시보드 서버. odin lifespan 패턴 차용 — 인증·RBAC·no-cache 미들웨어는 제거(로컬 단독).

실행: uv run uvicorn src.web.server:app --port 8000
★ 단일 워커 전제(APScheduler 중복 방지) — --workers 늘리지 말 것.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from src.config.settings import settings
from src.db.client import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작: DB 보장 + 필수 설정 점검 + 스케줄러 기동
    init_db()
    # ★ 필수 설정이 비면 배치가 '실패'가 아니라 '할 일 0건'으로 조용히 끝난다(2026-09-12 사고).
    #   기동할 때 한 번 크게 찍어, 코드 업데이트로 새 설정이 생긴 걸 그 자리에서 알아채게 한다.
    from pathlib import Path as _P

    if not settings.projects_root:
        logger.error("[설정] PROJECTS_ROOT 비어 있음 — .env에 관리 대상 루트를 넣어야 "
                     "프로젝트 발견·일간보고·게시판이 전부 0건으로 돈다 "
                     "(scripts/setup_wizard.cmd 실행 또는 .env 직접 편집)")
    elif not _P(settings.projects_root).is_dir():
        logger.error(f"[설정] PROJECTS_ROOT 경로가 없다: {settings.projects_root}")
    from src.scheduler import start_scheduler, stop_scheduler

    if settings.scheduler_enabled:
        start_scheduler()
    else:
        logger.warning("[스케줄러] SCHEDULER_ENABLED=false — 정시 배치 없음(수동 실행만)")
    # 서버가 내려갈 때 죽어버린 담당 답변을 되살린다 — 안 하면 화면의 "답하는 중…"이 영영 안 없어진다
    # (2026-09-13 사고: 질문 37초 뒤 서버 재시작으로 답변 작업이 같이 죽었다).
    from src.cc.room_agent import resume_dangling_replies

    resume_dangling_replies()
    yield
    # 종료: 스케줄러 정리
    stop_scheduler()


app = FastAPI(
    title="ohmyPM",
    lifespan=lifespan,
    docs_url="/docs" if settings.expose_dev_tools else None,
    redoc_url=None,
)

from src.web.routers import api, pages  # noqa: E402 (app 정의 후 import)

app.include_router(api.router)
app.include_router(pages.router)
