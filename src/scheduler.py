"""APScheduler — 정시 cron(스캔) + heartbeat(감지). odin 싱글톤·중복가드 패턴.

정시 스캔이 미해결·기한을 훑어 알림, heartbeat는 이벤트 감지 골격(상담은 다음 관문).
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from src.config.settings import settings

scheduler = AsyncIOScheduler()
_running: set[str] = set()  # 중복 실행 가드 (odin _generating 패턴)


async def _run_scan_job() -> None:
    """정시 스캔: 전 프로젝트 파싱 → 이슈 적재 → 텔레그램 요약 알림."""
    if "scan" in _running:
        return
    _running.add("scan")
    try:
        from src.scan import run_scan

        result = run_scan()
        from src.bot.telegram_bot import send_telegram

        await send_telegram(
            f"<b>ohmyPM 일일 스캔</b>\n프로젝트 {result['projects']}개 · 이슈 {result['issues']}건 추적 중"
        )
    except Exception as e:
        logger.error(f"[스케줄러] 스캔 실패: {e}")
    finally:
        _running.discard("scan")


async def _heartbeat_job() -> None:
    """heartbeat: 기한 임박·신규 이슈 감지 골격. 상담(케이스4)·화이트리스트 자율은 다음 관문."""
    try:
        # MVP: 감지 골격만. 정시 스캔 알림이 첫 관문의 핵심.
        pass
    except Exception as e:
        logger.error(f"[스케줄러] heartbeat 실패: {e}")


def start_scheduler() -> None:
    """서버 startup(lifespan)에서 호출."""
    scheduler.add_job(
        _run_scan_job,
        CronTrigger(hour=settings.scan_hour, minute=0),
        id="daily_scan",
        replace_existing=True,
    )
    scheduler.add_job(
        _heartbeat_job,
        IntervalTrigger(seconds=settings.heartbeat_sec),
        id="heartbeat",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"[스케줄러] 시작 — 스캔 매일 {settings.scan_hour}:00, heartbeat {settings.heartbeat_sec}초"
    )


def stop_scheduler() -> None:
    """서버 shutdown에서 호출."""
    scheduler.shutdown(wait=False)
