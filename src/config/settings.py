"""
환경 변수 설정 — .env 파일에서 로드 (pydantic-settings로 타입 안전하게).
예: from src.config.settings import settings
"""

import sys
from pathlib import Path

from loguru import logger
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수를 파이썬 객체로 매핑."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # 대소문자 구분 안 함
        # 모르는 변수는 무시한다 — 설정을 없앤 뒤(예: 텔레그램) 다른 PC의 옛 .env가 기동을 막지 않게
        extra="ignore",
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
    # False면 서버가 cron을 아예 걸지 않는다. 2026-10-07 사용자 결정으로 자동 스캔(8시)과
    # 새벽 일간보고 배치는 제거됨 — 정시 배치는 전문가수집(주 1회)만 남았고,
    # 스캔·일간보고는 대시보드에서 수동 실행한다.
    scheduler_enabled: bool = True
    # 담당을 부를지 말지 정하는 '사람의 작업이 있었나' 판정 창(시간 단위).
    # 매일 돌던 시절엔 24였다 — 주 1회로 바뀌면서 168시간(7일)으로 넓혔다.
    # 2026-10-07 이후 주간보고는 수동 실행이므로 '마지막 실행 이후'를 넉넉히 덮도록 넓게 유지할 것.
    activity_window_hours: int = 168
    # 전문가 위키 정기 수집 — 매주 지정 요일·시각(웹 조사라 자주 돌릴 필요 없음)
    expert_collect_weekday: int = 0   # 0=월요일 … 6=일요일
    expert_collect_hour: int = 5      # 새벽

    # --- 시스템 ---
    log_level: str = "INFO"
    expose_dev_tools: bool = False  # True면 FastAPI /docs 노출 (개발용)


# 전역 설정 인스턴스
settings = Settings()

# ohmyPM 저장소 루트 — 이 파일(src/config/settings.py)에서 두 단계 위 폴더.
# .env를 어디에 만들지 정할 때 쓴다 (경로 하드코딩 금지 원칙).
REPO_ROOT = Path(__file__).resolve().parents[2]


def ensure_env() -> bool:
    """.env가 없으면 기본값으로 만들어 준다. 새로 만들었으면 True를 돌려준다.

    배경(2026-10-07 사용자 결정): .env가 없으면 스캔이 아무 경고 화면 없이
    "프로젝트 0개"로 끝나는 사고가 있었다. 그래서 스캔이 시작될 때마다 이 함수가
    먼저 .env가 있는지 확인하고, 없으면 ohmyPM 저장소 위치를 기준으로 기본
    .env를 만들어 바로 쓸 수 있게 한다.

    기본 관리 루트(PROJECTS_ROOT)를 정하는 방법:
    - ohmyPM 저장소의 부모 폴더 아래에 'projects' 폴더가 있으면 그것을 쓴다
      (이 PC의 실제 배치: orca/ohmypm 옆에 orca/projects가 있다).
    - 없으면 부모 폴더 자체를 쓴다.
    """
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        return False  # 이미 있으면 손대지 않는다

    # 기본 관리 루트 결정
    parent = REPO_ROOT.parent
    candidate = parent / "projects"
    default_root = candidate if candidate.is_dir() else parent

    # .env.example을 바탕으로 내용을 만든다 — PROJECTS_ROOT 줄만 기본값으로 채우고
    # 나머지 항목(모델 등급, 스케줄 등)은 예시 그대로 둔다.
    example = REPO_ROOT / ".env.example"
    if example.exists():
        lines = example.read_text(encoding="utf-8").splitlines()
        content = "\n".join(
            f"PROJECTS_ROOT={default_root}" if line.startswith("PROJECTS_ROOT=") else line
            for line in lines
        ) + "\n"
    else:
        content = f"PROJECTS_ROOT={default_root}\n"

    env_path.write_text(content, encoding="utf-8")
    # 이미 떠 있는 서버에도 바로 반영한다 — .env 파일은 프로그램 시작 때 한 번만
    # 읽히므로, 파일만 만들면 재시작 전까지 설정이 빈 값 그대로 남기 때문이다.
    settings.projects_root = str(default_root)
    logger.warning(f"[설정] .env가 없어 기본값으로 새로 생성 — 관리 루트: {default_root}")
    return True

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
