"""보상 처리 — 1000점 달성 담당에게 '보상 택1(받고 리셋) vs 참고 2000 소원권'을 스스로 고르게 한다.

에이전트가 headless로 선택 → 코드가 프로필에 반영(take_reward/grant_wish, 점수 리셋).
2000점이면 소원권. 야간 흐름 끝이나 수동 트리거로 돈다.
"""

import json
import re

from loguru import logger

from src.cc.client import run_headless
from src.cc.permissions import tools_for
from src.cc.prompts import REWARD_MENU, REWARD_SYSTEM, reward_choice, wish_prompt
from src.cc.room_agent import _neutral_cwd
from src.db import agents as agents_db
from src.db import projects as projects_db

_OBJ = re.compile(r"\{.*\}", re.DOTALL)
REWARD_TIMEOUT = 120


def _ask(prompt: str) -> dict:
    allowed, disallowed = tools_for("daily_pm")   # 읽기 전용
    r = run_headless(
        prompt=prompt, cwd=_neutral_cwd(),
        allowed_tools=allowed, disallowed_tools=disallowed,
        timeout=REWARD_TIMEOUT, append_system_prompt=REWARD_SYSTEM,
    )
    if not r:
        return {}
    m = _OBJ.search(r)
    if not m:
        return {}
    try:
        d = json.loads(m.group(0))
        return d if isinstance(d, dict) else {}
    except json.JSONDecodeError:
        return {}


def run_rewards() -> dict:
    """전 담당 점수 재계산 → 2000↑ 소원권, 1000↑(미보류) 보상 선택. 처리 건수 반환."""
    projs = projects_db.list_projects(enabled_only=True)
    name_by = {p["path"]: p["name"] for p in projs}
    agents_db.refresh_scores(name_by)

    granted = 0
    for p in projs:
        prof = agents_db.get_profile(p["path"]) or {}
        pts = prof.get("points", 0) or 0
        name = prof.get("name") or p["name"]
        if pts >= agents_db.MILESTONE_WISH:
            d = _ask(wish_prompt(name))
            wish = (d.get("wish") or "").strip()
            if wish:
                agents_db.grant_wish(p["path"], name, wish)
                logger.info(f"[보상] {name} 소원권: {wish[:40]}")
                granted += 1
        elif pts >= agents_db.MILESTONE_MENU and not prof.get("held"):
            d = _ask(reward_choice(name))
            choice = d.get("choice")
            if choice == "take" and d.get("reward") in REWARD_MENU:
                agents_db.take_reward(
                    p["path"], name, d["reward"],
                    new_name=(d.get("new_name") or "").strip() or None,
                    persona=(d.get("persona") or "").strip() or None,
                )
                logger.info(f"[보상] {name} → {d['reward']}")
                granted += 1
            else:
                agents_db.set_held(p["path"], True)   # 참고 2000 향해
                logger.info(f"[보상] {name} 보류(2000 향해)")
    return {"granted": granted}
