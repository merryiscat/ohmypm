"""APScheduler — 정시 cron(스캔·일간보고·텔레그램·전문가수집). odin 싱글톤·중복가드 패턴.

5분 주기 heartbeat는 2026-09-09 제거 — 자리만 잡아둔 빈 껍데기(pass)라 하는 일 없이
로그만 어지럽혔다. 주기 작업이 다시 필요해지면 그때 목적에 맞는 주기로 새로 단다.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
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
        import asyncio

        from src.scan import run_scan

        result = run_scan()
        # ①완결 검증(2026-09-06 사용자 확정) — 담당이 새 이슈를 실제 코드와 대조,
        #   문서만 낡고 끝난 일은 완료 처리. ②그다음 판정 에이전트가 남은 후보의 오탐을 가린다.
        #   둘 다 headless(느림)라 to_thread — 이벤트 루프(대시보드 응답)를 안 막는다.
        from src.cc.issue_verify import run_issue_verification
        from src.cc.judge import run_judgment

        verified = await asyncio.to_thread(run_issue_verification)
        judged = await asyncio.to_thread(run_judgment)
        from src.bot.telegram_bot import send_telegram

        await send_telegram(
            f"<b>ohmyPM 일일 스캔</b>\n프로젝트 {result['projects']}개 · 이슈 {result['issues']}건 추적 중"
            f"\n완결 확인: {verified['checked']}건 대조 · {verified['resolved']}건 완료 처리"
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
    scheduler.start()
    logger.info(
        f"[스케줄러] 시작 — 스캔 {settings.scan_hour}:00, 일간보고 {settings.daily_report_hour}:00, "
        f"텔레그램 {settings.telegram_hour}:00, 전문가수집 매주 {settings.expert_collect_weekday}요일 "
        f"{settings.expert_collect_hour}:00"
    )


def stop_scheduler() -> None:
    """서버 shutdown에서 호출."""
    scheduler.shutdown(wait=False)
