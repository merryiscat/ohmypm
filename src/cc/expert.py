"""전문가 에이전트 — ohmyPM에 상주하는 사내 전문가 명부와 자문 창구.

2026-09-28 사용자 결정(R-010): 웹 자율 조사형 전문가(하네스·LLM 앱·프로덕트·디자인)는
한 번도 수집되지 않아 명부에서 뺐다. 남은 것은 **모델 동향 전문가(벤더별 탭)** — 공식 문서를
코드가 직접 수집하고 모델별 상세를 정리한다(`src/cc/model_catalog.py`). 자문은 그 위키를 1차
근거로 답한다.
지식 위키 파일 쓰기는 **코드**가 한다(에이전트는 읽기+웹만, 텍스트로 반환).
"""

import tempfile
from pathlib import Path

from loguru import logger

from src.cc.client import run_headless
from src.cc.model_catalog import MODEL_DOMAINS, VENDORS, collect_vendor
from src.cc.permissions import tools_for
from src.cc.prompts import EXPERT_SYSTEM, expert_consult
from src.db import messages as messages_db

ROOT = Path(__file__).resolve().parents[2]      # ohmyPM 루트
EXPERT_TIMEOUT = 300                            # 웹 조사라 넉넉히

# 사내 전문가 명부 — 벤더별 모델 동향 탭. 새 벤더는 model_catalog.VENDORS에 추가하면 여기 자동 반영.
EXPERTS: dict[str, dict] = {
    meta["domain"]: {"name": meta["name"], "topic": meta["topic"], "vendor": vendor}
    for vendor, meta in VENDORS.items()
}

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


def collect_knowledge(domain: str) -> dict:
    """전문가 지식 수집. 모델 동향 탭은 그 벤더의 공식 출처를 코드 수집기가 받는다."""
    if domain not in EXPERTS:
        return {"ok": False, "error": "unknown expert"}
    vendor = MODEL_DOMAINS.get(domain)
    if vendor:
        return collect_vendor(vendor)
    return {"ok": False, "error": "no collector"}


def consult(domain: str, question: str) -> str:
    """전문가 답변 텍스트를 동기로 반환(DB 기록 없음). PM 흐름이 자동 자문할 때 쓴다."""
    e = EXPERTS.get(domain)
    if not e:
        return ""
    allowed, disallowed = tools_for("expert")
    out = run_headless(task="expert_consult",
        prompt=expert_consult(e["topic"], read_wiki(domain), question),
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
# 고정 명부 EXPERTS는 안 건드리고, expertise 있는 담당을 agent::{path} 도메인으로 얇게 잇는다.
def collect_all() -> dict:
    """전 벤더 모델 동향을 순차 수집·갱신(정기 cron용). 갱신 벤더 수 반환."""
    updated = 0
    for domain in EXPERTS:
        try:
            if collect_knowledge(domain).get("ok"):
                updated += 1
        except Exception as e:  # 한 벤더 실패가 나머지를 안 멈춤
            logger.warning(f"[전문가] {domain} 정기수집 실패: {e}")
    logger.info(f"[전문가] 정기수집 — {updated}/{len(EXPERTS)} 벤더 갱신")
    return {"updated": updated, "total": len(EXPERTS)}
