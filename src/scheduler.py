"""APScheduler — 정시 cron(랩실 정기 조사 하나). odin 싱글톤·중복가드 패턴.

2026-10-07 사용자 결정: 자동 스캔(8시)·일간보고(새벽 3시)·아침 텔레그램 발송(7시, 일간보고
요약 전송)을 정시 배치에서 제거. 스캔·일간보고는 대시보드에서 수동 실행만 한다.

5분 주기 heartbeat는 2026-09-09 제거 — 자리만 잡아둔 빈 껍데기(pass)라 하는 일 없이
로그만 어지럽혔다. 주기 작업이 다시 필요해지면 그때 목적에 맞는 주기로 새로 단다.

예약된 안전장치 — '메모리 속 코드가 낡았는지' 자동 확인(2026-09-10 게시판 odin_3.0 조언):
  2026-09-08에 모듈을 고치고 서버를 재시작하지 않아 새벽 배치가 통째로 죽었다. 지금 항체는
  "고쳤으면 그 자리에서 재시작한다"는 사람의 습관뿐이라 언젠가 또 뚫린다. 설계 결론은
  ①서버가 뜰 때 `src/` 트리 파일 내용의 해시를 한 번 찍어두고 ②각 잡의 첫 줄에서 디스크의
  현재 해시와 비교해 다르면 로그·텔레그램으로 알린다. git HEAD 비교로는 이번처럼 커밋 전
  수정을 놓치므로 파일 내용 해시로 간다. 주의 둘 — (가) 비교하는 코드 자체는 **이 파일 최상단
  import**로 둔다(아래 잡들처럼 함수 안에서 부르면 그 장치도 똑같이 낡은 채로 메모리에 남는다),
  (나) 해시 비교는 탐지지 복구가 아니다. 알림만으로는 그날 새벽 보고가 여전히 0건이라,
  '첫 잡이 죽으면 뒤 잡이 전부 죽는' 배치 구조를 단계별로 감싸는 일이 함께 가야 한다.
  착수 시점·조건은 docs/pending.md 참조(상시 서버 경로를 건드리는 변경이라 사용자 확정 후).
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from src.config.settings import settings

scheduler = AsyncIOScheduler()
_running: set[str] = set()  # 중복 실행 가드 (odin _generating 패턴)

# 정시보다 늦게 깨어났을 때 그래도 실행해 주는 유예(초).
# 지정하지 않으면 APScheduler 기본값이 1초라, 정각에 이벤트 루프가 잠깐 바빴다는 이유만으로
# 그 주 잡이 통째로 사라진다(2026-09-23 실측: "missed by 0:00:01.796"). 주 1회 잡에서는
# 1초 지각이 한 주 결손이므로 30분을 둔다.
MISFIRE_GRACE = 1800
_WEEKDAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]   # 로그를 사람이 읽게


async def _run_lab_job() -> None:
    """매주 — 랩실 연구원 3명(모델·디자인·스킬)이 순차 조사해 위키·제안서를 갱신. headless라 to_thread."""
    if "lab_research" in _running:
        return
    _running.add("lab_research")
    try:
        import asyncio

        from src.cc.lab import research_all

        await asyncio.to_thread(research_all)
    except Exception as e:
        logger.error(f"[스케줄러] 랩실 정기 조사 실패: {e}")
    finally:
        _running.discard("lab_research")


def start_scheduler() -> None:
    """서버 startup(lifespan)에서 호출."""
    scheduler.add_job(
        _run_lab_job,
        CronTrigger(day_of_week=settings.expert_collect_weekday, hour=settings.expert_collect_hour, minute=0),
        id="lab_research",
        replace_existing=True,
        misfire_grace_time=MISFIRE_GRACE,
    )
    scheduler.start()
    logger.info(
        f"[스케줄러] 시작 — 랩실 정기 조사 매주 {_WEEKDAY_NAMES[settings.expert_collect_weekday]}요일 "
        f"{settings.expert_collect_hour}:00 (그 밖의 일은 화면에서 수동 실행) · 지각 유예 {MISFIRE_GRACE // 60}분"
    )


def stop_scheduler() -> None:
    """서버 shutdown에서 호출."""
    if scheduler.running:   # SCHEDULER_ENABLED=false면 시작된 적이 없다
        scheduler.shutdown(wait=False)
