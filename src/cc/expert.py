"""모델 동향 전문가(벤더별 탭) — 랩실 '모델 연구원'의 수집 엔진.

공식 문서를 코드가 직접 수집하고 모델별 상세를 정리한다(`src/cc/model_catalog.py`). 위키는
docs/lab/models-<vendor>.md. 2026-10-09부터 화면·스케줄은 src/cc/lab.py가 맡고, 이 모듈은
명부(EXPERTS)·수집(collect_all)·자문(consult)만 제공한다. 위키 파일 쓰기는 코드가 한다.
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
    return ROOT / "docs" / "lab" / f"{domain}.md"     # 랩실 위키 폴더(런타임 산출물, git 미추적)


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
