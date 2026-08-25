"""FastAPI 대시보드 서버. odin lifespan 패턴 차용 — 인증·RBAC·no-cache 미들웨어는 제거(로컬 단독).

실행: uv run uvicorn src.web.server:app --port 8000
★ 단일 워커 전제(APScheduler 중복 방지) — --workers 늘리지 말 것.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config.settings import settings
from src.db.client import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작: DB 보장 + 스케줄러 기동
    init_db()
    from src.scheduler import start_scheduler, stop_scheduler

    start_scheduler()
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
