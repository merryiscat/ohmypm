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
    # 작업 등급별 모델(2026-09-28 사용자 결정: 작업 수준·난이도에 따른 모델 매칭은 필수).
    # 모든 헤드리스 호출은 src/cc/models.py의 작업→등급 표를 거쳐 --model을 명시한다 —
    # 개인 CLI 기본 모델(이 PC는 Fable)에 조용히 기대지 않는다. 사고: 수집기가 모델을 안 정해
    # 정형 JSON 추출 40여 회를 Fable로 돌렸다(한 호출 $0.36).
    model_light: str = "haiku"      # 분류·반응·택1 같은 짧고 정형인 일
    model_standard: str = "sonnet"  # 요약·검토·대화·정형 추출
    model_heavy: str = "opus"       # 종합·설계 수준의 글쓰기
    # Fable·Mythos 같은 최상위 모델은 헤드리스에서 기본 금지 — 명시적으로 켜야만 쓴다
    allow_frontier_headless: bool = False
    # 모델 동향 위키가 추적하는 모델(쉼표 구분, 공식 문서 표기 그대로). 2026-09-28 사용자 결정:
    # "실제 사용할 모델만 — 옛날 모델 필요 없다". 목록 밖 모델의 변경은 추적 모델에 영향을 줄 때만
    # (대체·마이그레이션) 그 추적 모델 항목으로 적고, 아니면 버린다.
    model_track_claude: str = ("Claude Fable 5.1,Claude Opus 5.5,Claude Opus 5,Claude Sonnet 5,"
                               "Claude Haiku 4.5")
    model_track_codex: str = "GPT-6 Astra,GPT-6 Sol,GPT-6 Luna"

    # --- 스케줄 ---
    # False면 서버가 cron을 아예 걸지 않는다 — 스캔·일간보고·게시판은 대시보드/API로 수동 실행.
    # 폴더로만 관리하는 프로젝트가 많고 인터넷이 제한적인 PC용(2026-09-15 사용자 확정)
    scheduler_enabled: bool = True
    scan_hour: int = 8       # 매일 정시 스캔 시각(24시간)
    # 일간보고(멀티에이전트) — 03:00 시작(사용량 리셋 직후, 01시는 리셋 전이라 한도로 전량실패했음
    # 2026-09-01), 보고 소프트마감 05:00, 게시판 토론 마감 06:00
    daily_report_hour: int = 3
    daily_soft_deadline_hour: int = 5
    discussion_until_hour: int = 6
    telegram_hour: int = 7   # 일간보고 요약 텔레그램 발송 시각(생성은 새벽, 발송은 아침)
    # 게시판 경로(기록 정리·글쓰기·둘러보기·반응·대대댓글·조언 반영·보상)를 돌리는 요일 —
    # 2026-09-17 사용자 확정: 기본 끄고 주 1회. 감지·알림(스캔·판정·일간보고·텔레그램)은 매일.
    # 쉼표로 여러 요일("2,6"), 빈 값이면 절대 안 돈다. 0=월요일 … 6=일요일
    board_weekdays: str = "6"
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
