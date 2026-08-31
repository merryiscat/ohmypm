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
        # 결정론 수집 뒤 판정 에이전트가 후보의 오탐을 가린다(기한만 — 첫 관문).
        from src.cc.judge import run_judgment

        judged = run_judgment()
        from src.bot.telegram_bot import send_telegram

        await send_telegram(
            f"<b>ohmyPM 일일 스캔</b>\n프로젝트 {result['projects']}개 · 이슈 {result['issues']}건 추적 중"
            f"\n판정: 기한 후보 {judged['candidates']}건 중 {judged['applied']}건 정리"
        )
    except Exception as e:
        logger.error(f"[스케줄러] 스캔 실패: {e}")
    finally:
        _running.discard("scan")


async def _run_nightly_job() -> None:
    """매일 01:00 — 멀티에이전트 일간보고(→03시) + 담당 자유대화(→04시).

    headless가 몇 분~시간 걸리므로 to_thread로 돌려 이벤트 루프를 막지 않는다.
    """
    if "nightly" in _running:
        return
    _running.add("nightly")
    try:
        import asyncio

        from src.cc.daily_report import run_nightly

        await asyncio.to_thread(run_nightly)
    except Exception as e:
        logger.error(f"[스케줄러] 일간보고 실패: {e}")
    finally:
        _running.discard("nightly")


async def _run_telegram_job() -> None:
    """매일 07:00 — 새벽에 생성해 저장해 둔 일간보고 요약을 텔레그램으로 발송."""
    try:
        import asyncio

        from src.cc.daily_report import send_daily_telegram

        await asyncio.to_thread(send_daily_telegram)
    except Exception as e:
        logger.error(f"[스케줄러] 텔레그램 발송 실패: {e}")


async def _run_expert_collect_job() -> None:
    """매주 — 전 도메인 전문가 위키를 웹으로 최신화(정기 수집). headless라 to_thread."""
    if "expert_collect" in _running:
        return
    _running.add("expert_collect")
    try:
        import asyncio

        from src.cc.expert import collect_all

        await asyncio.to_thread(collect_all)
    except Exception as e:
        logger.error(f"[스케줄러] 전문가 정기수집 실패: {e}")
    finally:
        _running.discard("expert_collect")


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
        _run_nightly_job,
        CronTrigger(hour=settings.daily_report_hour, minute=0),
        id="daily_report",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_telegram_job,
        CronTrigger(hour=settings.telegram_hour, minute=0),
        id="daily_telegram",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_expert_collect_job,
        CronTrigger(day_of_week=settings.expert_collect_weekday, hour=settings.expert_collect_hour, minute=0),
        id="expert_collect",
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
        f"[스케줄러] 시작 — 스캔 {settings.scan_hour}:00, 일간보고 {settings.daily_report_hour}:00, "
        f"텔레그램 {settings.telegram_hour}:00, 전문가수집 매주 {settings.expert_collect_weekday}요일 "
        f"{settings.expert_collect_hour}:00, heartbeat {settings.heartbeat_sec}초"
    )


def stop_scheduler() -> None:
    """서버 shutdown에서 호출."""
    scheduler.shutdown(wait=False)
