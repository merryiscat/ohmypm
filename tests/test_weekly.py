"""주간보고 — JSON 응답을 프로젝트별로 나눠 방과 ohmypm/weekly.md에 쓰고, 깨진 JSON은 전체 방에만 남긴다."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.cc import weekly_report as wr  # noqa: E402
from src.config.settings import settings  # noqa: E402
from src.db import client as db_client  # noqa: E402
from src.db import messages as messages_db  # noqa: E402


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    db_client._local.conn = None
    db_client.init_db()
    a = tmp_path / "alpha"; a.mkdir(); (a / "ohmypm").mkdir()
    (a / "ohmypm" / "state.md").write_text("# 지금 상태\n\n화면 붙이는 중\n", encoding="utf-8")
    b = tmp_path / "beta"; b.mkdir()                       # 미설치
    monkeypatch.setattr(wr, "collect_weekly_commits", lambda days=7: [
        {"path": str(a), "name": "alpha", "commits": ["10-05 화면 추가"], "state": "화면 붙이는 중"},
        {"path": str(b), "name": "beta", "commits": [], "state": ""},
    ])
    yield {"a": a, "b": b}
    conn = getattr(db_client._local, "conn", None)
    if conn is not None:
        conn.close()
    db_client._local.conn = None


def _fake(result):
    return lambda *args, **kw: {"result": result, "model": "sonnet", "cost_usd": 0.1, "output_tokens": 10, "task": kw.get("task")}


def test_weekly_splits_per_project_and_writes_file(env, monkeypatch):
    data = {"headline": "조용한 주", "projects": [{"name": "alpha", "summary": "화면을 붙였다."}], "quiet": ["beta"]}
    monkeypatch.setattr(wr, "run_headless_ex", _fake(json.dumps(data, ensure_ascii=False)))
    r = wr.run_weekly_report()
    assert r["ok"] and r["written"] == ["alpha"] and r["not_written"] == []
    rooms = messages_db.list_rooms_like("weekly::")
    assert len(rooms) == 2 and any(room.endswith(str(env["a"])) for room in rooms)
    overall = messages_db.list_messages(wr._room(r["date"]))[-1]["body"]
    assert "조용한 주" in overall and "beta" in overall
    md = (env["a"] / "ohmypm" / "weekly.md").read_text(encoding="utf-8")
    assert md.startswith("# 주간보고") and f"## {r['date']}" in md and "화면을 붙였다." in md
    # 두 번째 실행은 맨 위에 쌓인다
    data["projects"][0]["summary"] = "두 번째 주"
    monkeypatch.setattr(wr, "run_headless_ex", _fake(json.dumps(data, ensure_ascii=False)))
    wr.run_weekly_report()
    md2 = (env["a"] / "ohmypm" / "weekly.md").read_text(encoding="utf-8")
    assert md2.index("두 번째 주") < md2.index("화면을 붙였다.")
    listed = wr.list_reports()
    assert listed[0]["projects"][0]["written"] is True


def test_weekly_broken_json_keeps_raw(env, monkeypatch):
    monkeypatch.setattr(wr, "run_headless_ex", _fake("이번 주는 이러저러했다 (JSON 아님)"))
    r = wr.run_weekly_report()
    assert r["ok"] and r["written"] == []
    rooms = messages_db.list_rooms_like("weekly::")
    assert rooms == [wr._room(r["date"])]
    assert not (env["a"] / "ohmypm" / "weekly.md").exists()


def test_weekly_no_result(env, monkeypatch):
    monkeypatch.setattr(wr, "run_headless_ex", _fake(None))
    r = wr.run_weekly_report()
    assert r["ok"] is False and messages_db.list_rooms_like("weekly::") == []
