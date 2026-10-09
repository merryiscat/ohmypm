"""헤드리스 모델 정책 — 작업(task)마다 등급(light/standard/heavy)을 정하고, 등급별 모델은
.env가 정한다.

2026-09-28 사고: `run_headless`가 model 없이 불리면 Claude CLI의 개인 기본 모델을 썼다. 이 PC의
기본이 Fable 5.1이라 모델 동향 수집(정형 JSON 추출 + 프로필) 40여 회가 전부 Fable로 돌았다.
사용자 결정: "작업 수준·난이도에 따른 모델 매칭은 필수". 항체 세 가지 —
  ① 모든 호출은 등록된 task 이름을 내야 한다(미등록 task는 호출 거부 — 새 호출부는 표에 먼저 등록).
  ② 호출은 항상 `--model`을 명시한다(개인 기본값에 기대지 않는다).
  ③ Fable·Mythos 같은 최상위 모델은 `ALLOW_FRONTIER_HEADLESS=true`가 아니면 heavy로 내리고 경고한다.
"""

from loguru import logger

from src.config.settings import settings

# 작업 → 등급. 새 헤드리스 호출부는 여기 한 줄 추가가 먼저다.
TASK_TIER: dict[str, str] = {
    # 게시판 토론 — 담당별 지정 모델이 있으면 그것이 우선한다
    "board_write": "standard",
    "board_comment": "light",
    "board_feedback": "light",
    "board_followup": "light",
    "board_reflect": "light",         # 토론 끝 복기 — 받은 반응에서 배운 것 한두 줄
    # 담당 룸 대화
    "room_chat": "standard",
    # 주간보고 — 커밋 팩트를 종합해 한 장 보고(종합 글쓰기라 heavy)
    "weekly_report": "heavy",
    # 랩실(연구소)
    "expert_consult": "standard",     # 연구원 자문
    "lab_research": "standard",       # 웹 조사형 연구원(디자인·스킬)의 수집·제안
    "lab_proposal": "standard",       # 모델 연구원의 제안서
    "model_catalog_extract": "standard",   # 공식 문서 diff → 정형 JSON 추출
    "model_catalog_profile": "heavy",      # 모델별 상세 프로필 종합
}

# 헤드리스 기본 금지 모델(부분 문자열 매칭). 대화 세션에서 쓰는 것과 배치에서 쓰는 것은 다르다.
FRONTIER_MARKERS = ("fable", "mythos")


def tier_model(tier: str) -> str:
    return {"light": settings.model_light, "standard": settings.model_standard,
            "heavy": settings.model_heavy}[tier]


def is_frontier(model: str | None) -> bool:
    m = (model or "").lower()
    return any(k in m for k in FRONTIER_MARKERS)


def resolve_model(task: str, override: str | None = None) -> str:
    """호출에 쓸 모델을 정한다. override(담당별 지정 등)가 있으면 그것, 없으면 task 등급의 모델.
    최상위 모델은 허용 설정 없이는 heavy 등급으로 내린다. 미등록 task는 예외(호출부 등록 강제)."""
    if task not in TASK_TIER:
        raise ValueError(f"미등록 헤드리스 작업 '{task}' — src/cc/models.py TASK_TIER에 먼저 등록")
    model = override or tier_model(TASK_TIER[task])
    if is_frontier(model) and not settings.allow_frontier_headless:
        fallback = tier_model("heavy")
        logger.warning(f"[모델정책] task={task} 모델 '{model}'은 헤드리스 기본 금지 → "
                       f"'{fallback}'로 내림 (허용하려면 ALLOW_FRONTIER_HEADLESS=true)")
        model = fallback
    return model
