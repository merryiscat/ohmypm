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

# 사내 전문가 명부 — 첫 전문가: 하네스/에이전트 엔지니어링
EXPERTS: dict[str, dict] = {
    "harness": {
        "name": "하네스 엔지니어링 전문가",
        "topic": "AI 에이전트 하네스 엔지니어링 — 프롬프트·스킬·MCP·훅·권한 설계, "
                 "특히 Claude Code 기반 에이전트 구성 모범사례",
    },
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
    """전문가가 웹으로 최신 지식을 조사해 위키를 갱신(코드가 파일 기록)."""
    e = EXPERTS.get(domain)
    if not e:
        return {"ok": False, "error": "unknown expert"}
    allowed, disallowed = tools_for("expert")
    out = run_headless(
        prompt=expert_collect(e["topic"], read_wiki(domain)),
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


def ask_expert(domain: str, question: str) -> None:
    """질문에 전문가가 위키(+웹)로 답해 expert 방에 남긴다. (사용자 질문은 API가 먼저 방에 기록)"""
    e = EXPERTS.get(domain)
    if not e:
        return
    allowed, disallowed = tools_for("expert")
    out = run_headless(
        prompt=expert_consult(e["topic"], read_wiki(domain), question),
        cwd=_neutral(),
        allowed_tools=allowed, disallowed_tools=disallowed,
        timeout=EXPERT_TIMEOUT, append_system_prompt=EXPERT_SYSTEM,
    )
    messages_db.add_message(expert_room(domain), domain, (out or "(답변을 만들지 못했어)").strip())
