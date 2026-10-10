"""헤드리스 모델 정책 — 작업(task)마다 등급(light/standard/heavy)을 정하고, 등급별 모델은
.env가 정한다.

2026-09-28 사고: `run_headless`가 model 없이 불리면 Claude CLI의 개인 기본 모델을 썼다. 이 PC의
기본이 Fable 5.1이라 모델 동향 수집(정형 JSON 추출 + 프로필) 40여 회가 전부 Fable로 돌았다.
사용자 결정: "작업 수준·난이도에 따른 모델 매칭은 필수". 항체 세 가지 —
  ① 모든 호출은 등록된 task 이름을 내야 한다(미등록 task는 호출 거부 — 새 호출부는 표에 먼저 등록).
  ② 호출은 항상 `--model`을 명시한다(개인 기본값에 기대지 않는다).
  ③ Fable·Mythos 같은 최상위 모델은 `ALLOW_FRONTIER_HEADLESS=true`가 아니면 heavy로 내리고 경고한다.
  ④ 추론 강도(--effort)도 작업마다 명시한다(2026-10-10). 안 정하면 이 PC 개인 설정이나 모델 기본값을
     따르는데, 모델을 개인 기본값에 맡겼다가 난 09-28 사고와 같은 빈틈이다(랩실 정리 문서
     docs/lab/notes/models/harness-per-model.md). 강도가 높을수록 품질이 오르고 한도(세션)도 더 쓴다.
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
    "weekly_pm": "standard",          # 주간 점검 — PM이 담당에게 묻는 질문·중간 요약(JSON)
    "weekly_agent": "standard",       # 주간 점검 — 담당이 자기 폴더를 읽고 답(담당별 지정 모델 우선)
    "env_setup": "heavy",             # 환경 세팅 — 스냅샷을 보고 작은 변경안(JSON)을 낸다
    "weekly_review": "standard",      # 주간 변경 리뷰 — 이번 주 커밋을 Ponytail 리뷰로(읽기 전용)
    # 랩실(연구소)
    "expert_consult": "standard",     # 연구원 자문
    "lab_research": "standard",       # 웹 조사형 연구원(디자인·스킬)의 수집·제안
    "lab_proposal": "standard",       # 모델 연구원의 제안서
    "lab_note": "heavy",              # 조사 요청 → 정리 문서 한 편(웹 조사 + 종합 글쓰기)
    "model_catalog_extract": "standard",   # 공식 문서 diff → 정형 JSON 추출
    "model_catalog_profile": "heavy",      # 모델별 상세 프로필 종합
}

# 작업 → 추론 강도(low/medium/high/xhigh/max). TASK_TIER와 같은 작업이 모두 있어야 한다(테스트가 확인).
# 출발점: 짧고 정형인 일 low, 대화·조사·추출 medium, 종합 글쓰기 high. 바꿀 땐 호출 로그의 세션 값으로 비교한다.
TASK_EFFORT: dict[str, str] = {
    "board_write": "medium",
    "board_comment": "low",
    "board_feedback": "low",
    "board_followup": "low",
    "board_reflect": "low",
    "room_chat": "medium",
    "weekly_report": "high",          # 주간 종합 — 전 프로젝트 대화를 한 장으로
    "weekly_pm": "medium",
    "weekly_agent": "medium",
    "weekly_review": "medium",
    "env_setup": "high",
    "expert_consult": "medium",
    "lab_research": "medium",
    "lab_proposal": "medium",
    "lab_note": "medium",
    "model_catalog_extract": "medium",     # 정확도가 중요한 추출 — low는 비교 확인 뒤에만
    "model_catalog_profile": "high",
}
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")


def resolve_effort(task: str) -> str:
    """호출에 쓸 추론 강도. 표에 없으면 medium(새 작업은 TASK_TIER와 함께 여기에도 등록)."""
    return TASK_EFFORT.get(task, "medium")


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
