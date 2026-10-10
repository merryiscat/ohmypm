"""헤드리스 모델 정책(src/cc/models.py) — 2026-09-28 'Fable로 수집기를 돌린' 사고의 항체.

① 미등록 작업은 호출 거부 ② 등급별 모델은 설정이 정한다 ③ 최상위 모델(Fable·Mythos)은 허용 설정
없이는 heavy 등급으로 내린다 ④ run_headless는 항상 --model을 명시하고 task 없이는 못 부른다.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.cc import client, models  # noqa: E402
from src.config.settings import settings  # noqa: E402


def test_unregistered_task_is_rejected():
    with pytest.raises(ValueError, match="미등록"):
        models.resolve_model("brand-new-task")


def test_every_tier_maps_to_configured_model(monkeypatch):
    monkeypatch.setattr(settings, "model_light", "haiku")
    monkeypatch.setattr(settings, "model_standard", "sonnet")
    monkeypatch.setattr(settings, "model_heavy", "opus")
    assert models.resolve_model("board_comment") == "haiku"
    assert models.resolve_model("model_catalog_extract") == "sonnet"
    assert models.resolve_model("model_catalog_profile") == "opus"


def test_override_is_honored_but_frontier_is_downgraded(monkeypatch):
    monkeypatch.setattr(settings, "model_heavy", "opus")
    monkeypatch.setattr(settings, "allow_frontier_headless", False)
    assert models.resolve_model("room_chat", override="sonnet") == "sonnet"
    assert models.resolve_model("room_chat", override="claude-fable-5-1[1m]") == "opus"
    assert models.resolve_model("room_chat", override="mythos") == "opus"


def test_frontier_allowed_only_with_explicit_setting(monkeypatch):
    monkeypatch.setattr(settings, "allow_frontier_headless", True)
    assert models.resolve_model("room_chat", override="claude-fable-5-1") == "claude-fable-5-1"


def test_every_registered_task_has_a_known_tier():
    assert set(models.TASK_TIER.values()) <= {"light", "standard", "heavy"}


def test_all_call_sites_pass_a_registered_task():
    """src/cc 안의 모든 run_headless 호출이 task=를 넘기고, 그 이름이 표에 있다."""
    import re

    root = Path(__file__).resolve().parents[1] / "src" / "cc"
    seen = set()
    for f in root.glob("*.py"):
        if f.name == "client.py":   # 정의·래퍼 자체
            continue
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(r"run_headless(?:_ex)?\(", text):
            if text[max(0, m.start() - 4):m.start()].endswith("def "):
                continue
            i, depth = m.end(), 1
            while depth and i < len(text):
                depth += text[i] == "("
                depth -= text[i] == ")"
                i += 1
            call = text[m.start():i]
            if "def run_headless" in text[m.start() - 200:m.start()] and f.name == "client.py":
                continue
            found = re.search(r'task="([a-z_]+)"', call)
            assert found, f"{f.name}: task 없는 헤드리스 호출: {call[:80]}"
            assert found.group(1) in models.TASK_TIER, f"{f.name}: 미등록 task {found.group(1)}"
            seen.add(found.group(1))
    assert "model_catalog_extract" in seen and "room_chat" in seen


def test_run_headless_always_passes_model_flag(monkeypatch):
    captured = {}

    class R:
        returncode = 0
        stdout = '{"result": "ok", "total_cost_usd": 0.01, "usage": {"output_tokens": 3}, ' \
                 '"modelUsage": {"claude-sonnet-5": {}}}'
        stderr = ""

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return R()

    monkeypatch.setattr(client.subprocess, "run", fake_run)
    monkeypatch.setattr(settings, "model_standard", "sonnet")
    monkeypatch.setattr(settings, "allow_frontier_headless", False)
    meta = client.run_headless_ex("p", ".", [], [], task="room_chat")
    cmd = captured["cmd"]
    assert "--model" in cmd and cmd[cmd.index("--model") + 1] == "sonnet"
    assert cmd[cmd.index("--effort") + 1] == models.TASK_EFFORT["room_chat"]
    assert cmd[cmd.index("--tools") + 1] == ""          # 허용 도구가 없으면 도구를 끈다
    assert meta["result"] == "ok" and meta["model"] == "claude-sonnet-5"
    assert meta["cost_usd"] == 0.01 and meta["output_tokens"] == 3

    with pytest.raises(TypeError):
        client.run_headless("p", ".", [], [])  # task 없이는 못 부른다


def test_every_task_has_a_valid_effort():
    """추론 강도 표는 작업 표와 같은 작업을 모두 갖고, 값은 CLI가 받는 단계 중 하나다."""
    assert set(models.TASK_EFFORT) == set(models.TASK_TIER)
    assert set(models.TASK_EFFORT.values()) <= set(models.EFFORT_LEVELS)
