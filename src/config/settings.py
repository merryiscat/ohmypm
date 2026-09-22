"""
환경 변수 설정 — .env 파일에서 로드 (pydantic-settings로 타입 안전하게).
예: from src.config.settings import settings
"""

import sys

from loguru import logger
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수를 파이썬 객체로 매핑."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # 대소문자 구분 안 함
    )

    # --- 관리 대상 ---
    # 이 폴더 하위의 프로젝트들을 매일 돌본다
    # PC마다 다르므로 기본값을 두지 않는다 — .env의 PROJECTS_ROOT로 각 PC가 정한다
    # (setup_wizard가 물어본다). 비어 있으면 프로젝트 발견이 경고 후 건너뛴다.
    projects_root: str = ""

    # --- 로컬 저장 ---
    db_path: str = "data/ohmypm.db"  # SQLite 파일 경로

    # --- Claude Code headless ---
    # 판단·작업을 claude -p 로 호출할 때 쓰는 실행 파일. PATH에 있으면 "claude"
    cc_bin: str = "claude"

    # --- 스케줄 ---
    # False면 서버가 cron을 아예 걸지 않는다 — 스캔·일간보고·게시판은 대시보드/API로 수동 실행.
    # 폴더로만 관리하는 프로젝트가 많고 인터넷이 제한적인 PC용(2026-09-15 사용자 확정)
    scheduler_enabled: bool = True
    # ★ 2026-09-23 사용자 확정 — 매일 08시 스캔 잡을 **끈다**(종전 기본 켬).
    #   이유: 주간 배치가 자기 안에서 스캔을 돈다(daily_report.run_nightly). 배치가 주 1회가 된
    #   이상 매일 스캔은 그 사이 화면 숫자를 최신으로 두는 것뿐인데, 그 대가로 24개 프로젝트에
    #   모델을 부르며 매일 18분을 썼다(이 잡은 비용 집계도 안 됐다). 화면은 '스캔'·'판정' 버튼으로
    #   그 자리에서 최신화할 수 있다(/api/scan, /api/judge).
    #   되살리려면 .env에 SCAN_ENABLED=true — 스캔 코드도 버튼도 그대로 남아 있다.
    scan_enabled: bool = False
    scan_hour: int = 8       # 스캔 잡을 다시 켤 때 쓰는 시각(24시간)
    # 주간보고(멀티에이전트) — 03:00 시작(사용량 리셋 직후, 01시는 리셋 전이라 한도로 전량실패했음
    # 2026-09-01), 보고 소프트마감 05:00, 게시판 토론 마감 06:00
    daily_report_hour: int = 3
    # ★ 2026-09-23 사용자 확정 — 매일 새벽에서 **매주 토요일 새벽**으로 바꿨다.
    #   0=월요일 … 6=일요일. 이 값을 바꾸면 바로 아래 activity_window_hours도 같이 봐야 한다:
    #   활동 판정 창이 배치 주기보다 좁으면 그 사이에 한 작업을 통째로 못 보고 넘어간다.
    #   놓쳤을 때(PC가 꺼져 있었다면) 따라잡기는 하지 않는다 — 그 주는 건너뛴다(사용자 확정).
    daily_report_weekday: int = 5
    # 담당을 부를지 말지 정하는 '사람의 작업이 있었나' 판정 창(시간 단위).
    # 매일 돌던 시절엔 24였다 — 주 1회로 바뀌면서 168시간(7일)으로 넓혔다.
    # 이게 좁으면 토큰은 아끼지만 놓침이 생긴다. 배치 주기와 같거나 넓게 유지할 것.
    activity_window_hours: int = 168
    daily_soft_deadline_hour: int = 5
    discussion_until_hour: int = 6
    telegram_hour: int = 7   # 일간보고 요약 텔레그램 발송 시각(생성은 새벽, 발송은 아침)
    # 게시판 경로(기록 정리·글쓰기·둘러보기·반응·대대댓글·조언 반영·보상)를 돌리는 요일 —
    # 2026-09-17 사용자 확정: 기본 끄고 주 1회. 쉼표로 여러 요일("2,6"), 빈 값이면 절대 안 돈다.
    # ★ 2026-09-23 일요일(6) → 토요일(5). 게시판은 야간 배치 **안에서** 도는 경로라,
    #   배치가 토요일에만 도는데 요일이 일요일이면 영영 안 돈다(사용자 확정: 같이 돌린다).
    #   0=월요일 … 6=일요일 — daily_report_weekday와 같은 값으로 두어야 한다.
    board_weekdays: str = "5"
    # 전문가 위키 정기 수집 — 매주 지정 요일·시각(웹 조사라 자주 돌릴 필요 없음)
    expert_collect_weekday: int = 0   # 0=월요일 … 6=일요일
    expert_collect_hour: int = 5      # 새벽(일간보고 흐름과 겹치지 않게)

    # --- 텔레그램 (비우면 알림 no-op) ---
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # --- 시스템 ---
    log_level: str = "INFO"
    expose_dev_tools: bool = False  # True면 FastAPI /docs 노출 (개발용)


# 전역 설정 인스턴스
settings = Settings()

# 로깅 설정 (loguru) — 콘솔 + logs/ 일별 파일
logger.remove()
# pythonw(창 없는 실행)에는 stderr가 없다(None) — 그대로 넘기면 loguru가 죽는다.
# 파일 싱크는 아래에서 따로 붙으므로 콘솔 싱크만 건너뛰면 된다.
if sys.stderr is not None:
    logger.add(sys.stderr, level=settings.log_level)
logger.add(
    "logs/ohmypm_{time:YYYY-MM-DD}.log",
    rotation="00:00",     # 매일 자정 새 파일
    retention="30 days",  # 30일 보관
    level="INFO",
    encoding="utf-8",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {name}:{function}:{line} | {message}",
)
