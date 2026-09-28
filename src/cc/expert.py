"""전문가 에이전트 — ohmyPM에 상주하며 웹으로 최신 지식을 모아 docs/experts/ 위키로 관리하고,
PM(지휘자)·사용자의 질문에 답한다. PM은 오케스트라: 프로젝트 담당 + 사내 전문가를 조율한다.

지식 위키 파일 쓰기는 **코드**가 한다(에이전트는 읽기+웹만, 텍스트로 반환) — 자율 쓰기 최소화.
"""

import tempfile
from pathlib import Path

from loguru import logger

from src.cc.client import run_headless
from src.cc.permissions import tools_for
from src.cc.prompts import EXPERT_SYSTEM, expert_collect, expert_consult
from src.db import messages as messages_db

ROOT = Path(__file__).resolve().parents[2]      # ohmyPM 루트
EXPERT_TIMEOUT = 300                            # 웹 조사라 넉넉히

# 사내 전문가 명부 — 도메인별 상주 전문가. 새 도메인은 여기 한 줄 추가하면 명부·수집·자문에 반영된다.
EXPERTS: dict[str, dict] = {
    "harness": {
        "name": "하네스 엔지니어링 전문가",
        "topic": "AI 에이전트 하네스 엔지니어링 — 프롬프트·스킬·MCP·훅·권한 설계, "
                 "특히 Claude Code 기반 에이전트 구성 모범사례",
    },
    "llm-apps": {
        "name": "LLM 앱 개발 전문가",
        "topic": "LLM 애플리케이션 개발 — 프롬프트 엔지니어링, RAG, 평가(eval)·벤치마크, "
                 "에이전트 설계 패턴, 모델·비용 선택과 최신 모델 동향",
    },
    "product": {
        "name": "프로덕트 PM 전문가",
        "topic": "1인·소규모 개발 프로덕트 매니지먼트 — 우선순위 판단, 스코프 관리, "
                 "출시(ship) 판단, 사용자 피드백 루프, 작게 자주 내보내는 전략",
    },
    "design": {
        "name": "화면 디자인 전문가",
        "topic": "바이브 코딩 화면 디자인 — AI 도구로 UI를 만들 때의 시각 디자인 원칙과 워크플로, "
                 "타이포그래피·컬러·레이아웃·간격 기본기, 레퍼런스 수집·활용법, 그리고 **AI 특유의 "
                 "티 나는 디자인을 피하는 구체적 기법**(획일적 보라 그라데이션·카드 남발·기본 "
                 "템플릿 룩·과한 장식을 벗어나 사람 손맛 나는 화면 만들기)",
    },
    # 모델 동향 — 웹 자율 조사가 아니라 공식 출처 4개를 코드가 직접 수집(model_catalog.py).
    # "웹으로 지식 수집" 버튼도 이 도메인에선 그 수집기를 대신 부른다(T-007 r2).
    "models": {
        "name": "모델 동향 전문가",
        "topic": "Claude·Codex 공식 문서 기반 최신 모델·하네스 변화 추적 — 발표/릴리스 문서에서 "
                 "실제 달라진 점만 근거 링크와 함께 정리하고 하네스(프롬프트·추론설정·컨텍스트관리·"
                 "도구사용)에 대한 적용 제안을 asserted/inferred로 구분한다",
    },
}

MODELS_DOMAIN = "models"

_NEUTRAL: str | None = None


def _neutral() -> str:
    global _NEUTRAL
    if _NEUTRAL is None or not Path(_NEUTRAL).exists():
        _NEUTRAL = tempfile.mkdtemp(prefix="ohmypm_expert_")
    return _NEUTRAL


def wiki_path(domain: str) -> Path:
    return ROOT / "docs" / "experts" / f"{domain}.md"


def read_wiki(domain: str) -> str:
    p = wiki_path(domain)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def expert_room(domain: str) -> str:
    return f"expert::{domain}"


def _model_trend_brief() -> str:
    """모델동향(models) 위키 요약 — 다른 전문가 수집/자문 입력에 주입(T-007 C7).

    상태가 아직 없으면 빈 문자열 → 기존 프롬프트가 그대로 나가 기존 기능이 안 깨진다.
    """
    try:
        from src.cc.model_catalog import trend_brief

        return trend_brief()
    except Exception as e:  # 모델동향 쪽 오류가 다른 전문가 수집/자문을 막지 않는다
        logger.warning(f"[전문가] 모델동향 요약 주입 실패(무시): {e}")
        return ""


def _with_trend_brief(domain: str, existing: str) -> str:
    if domain == MODELS_DOMAIN:
        return existing
    brief = _model_trend_brief()
    if not brief:
        return existing
    block = f"[최신 모델 동향 요약]\n{brief}"
    return f"{block}\n\n{existing}" if existing else block


def collect_knowledge(domain: str) -> dict:
    """전문가가 웹으로 최신 지식을 조사해 위키를 갱신(코드가 파일 기록)."""
    e = EXPERTS.get(domain)
    if not e:
        return {"ok": False, "error": "unknown expert"}
    allowed, disallowed = tools_for("expert")
    out = run_headless(
        prompt=expert_collect(e["topic"], _with_trend_brief(domain, read_wiki(domain))),
        cwd=_neutral(),
        allowed_tools=allowed, disallowed_tools=disallowed,
        timeout=EXPERT_TIMEOUT, append_system_prompt=EXPERT_SYSTEM,
    )
    body = (out or "").strip()
    if not body:
        logger.warning(f"[전문가] {domain} 수집 실패(빈 응답)")
        return {"ok": False, "error": "empty"}
    p = wiki_path(domain)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    logger.info(f"[전문가] {domain} 위키 갱신 {len(body)}자")
    return {"ok": True, "chars": len(body)}


def consult(domain: str, question: str) -> str:
    """전문가 답변 텍스트를 동기로 반환(DB 기록 없음). PM 흐름이 자동 자문할 때 쓴다."""
    e = EXPERTS.get(domain)
    if not e:
        return ""
    allowed, disallowed = tools_for("expert")
    out = run_headless(
        prompt=expert_consult(e["topic"], _with_trend_brief(domain, read_wiki(domain)), question),
        cwd=_neutral(),
        allowed_tools=allowed, disallowed_tools=disallowed,
        timeout=EXPERT_TIMEOUT, append_system_prompt=EXPERT_SYSTEM,
    )
    return (out or "").strip()


def ask_expert(domain: str, question: str) -> None:
    """질문에 전문가가 위키(+웹)로 답해 expert 방에 남긴다. (사용자 질문은 API가 먼저 방에 기록)"""
    if domain not in EXPERTS:
        return
    answer = consult(domain, question)
    messages_db.add_message(expert_room(domain), domain, answer or "(답변을 만들지 못했어)")


# ── 담당 전문가(전문가개업 보상으로 승격) — 사내 명부에 가상 도메인으로 노출 ──
# 고정 상수 EXPERTS는 안 건드리고, expertise 있는 담당을 agent::{path} 도메인으로 얇게 잇는다.
def list_agent_experts() -> list[dict]:
    """전문가개업 보상을 받은 담당들 — {domain: 'agent::{path}', name, topic:expertise}."""
    from src.db import agents as agents_db

    out = []
    for prof in agents_db.list_profiles():
        if prof.get("expertise"):
            out.append({
                "domain": f"agent::{prof['project']}",
                "name": prof.get("name") or prof["project"],
                "topic": prof["expertise"],
            })
    return out


def consult_agent_expert(project_path: str, question: str) -> str:
    """담당 전문가에게 자문 — 그 프로젝트를 열고 expertise+성장기록을 근거로 답한다."""
    from src.cc.prompts import expert_consult
    from src.cc.room_agent import _neutral_cwd
    from src.db import agents as agents_db

    prof = agents_db.get_profile(project_path) or {}
    topic = prof.get("expertise") or ""
    if not topic:
        return ""
    allowed, disallowed = tools_for("expert")
    wiki = f"전문 분야: {topic}\n" + (f"쌓아온 배움:\n{prof.get('note')}" if prof.get("note") else "")
    return (run_headless(
        prompt=expert_consult(topic, wiki, question),
        cwd=_neutral_cwd(),
        allowed_tools=allowed, disallowed_tools=disallowed,
        timeout=EXPERT_TIMEOUT, append_system_prompt=EXPERT_SYSTEM,
        add_dirs=[project_path], model=agents_db.model_for(project_path),
    ) or "").strip()


def collect_all() -> dict:
    """전 도메인 위키를 순차 수집·갱신(정기 cron용). 갱신 도메인 수 반환.

    모델 동향(models)을 먼저 코드 수집기로 갱신한 다음 나머지 도메인을 수집해, 같은 실행에서
    harness·llm-apps 등이 최신 모델 동향 요약을 참조하게 한다(T-007 C7).
    """
    updated = 0
    try:
        from src.cc.model_catalog import collect_all_sources

        if collect_all_sources().get("ok"):
            updated += 1
    except Exception as e:
        logger.warning(f"[전문가] 모델동향 정기수집 실패: {e}")
    domains = [d for d in EXPERTS if d != MODELS_DOMAIN]
    for domain in domains:
        try:
            if collect_knowledge(domain).get("ok"):
                updated += 1
        except Exception as e:  # 한 도메인 실패가 나머지를 안 멈춤
            logger.warning(f"[전문가] {domain} 정기수집 실패: {e}")
    total = len(domains) + 1
    logger.info(f"[전문가] 정기수집 — {updated}/{total} 도메인 갱신")
    return {"updated": updated, "total": total}
