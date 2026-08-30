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
    projects_root: str = r"C:\Users\minhy\project"

    # --- 로컬 저장 ---
    db_path: str = "data/ohmypm.db"  # SQLite 파일 경로

    # --- Claude Code headless ---
    # 판단·작업을 claude -p 로 호출할 때 쓰는 실행 파일. PATH에 있으면 "claude"
    cc_bin: str = "claude"

    # --- 스케줄 ---
    scan_hour: int = 8       # 매일 정시 스캔 시각(24시간)
    heartbeat_sec: int = 300  # 이슈 감지 heartbeat 주기(초)
    # 일간보고(멀티에이전트) — 01:00 시작, 보고 소프트마감 03:00, 게시판 토론 마감 04:00
    daily_report_hour: int = 1
    daily_soft_deadline_hour: int = 3
    discussion_until_hour: int = 4
    telegram_hour: int = 7   # 일간보고 요약 텔레그램 발송 시각(생성은 새벽, 발송은 아침)

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
logger.add(sys.stderr, level=settings.log_level)
logger.add(
    "logs/ohmypm_{time:YYYY-MM-DD}.log",
    rotation="00:00",     # 매일 자정 새 파일
    retention="30 days",  # 30일 보관
    level="INFO",
    encoding="utf-8",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {name}:{function}:{line} | {message}",
)
