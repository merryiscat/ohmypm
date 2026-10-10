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


def _fake(result, pm=None, agent="화면은 다 붙였고 막힌 건 없다."):
    """task별로 다른 응답 — 종합(weekly_report)·PM 턴(weekly_pm)·담당 답(weekly_agent).
    pm 기본값: 첫 턴엔 묻고, 둘째 턴엔 끝낸다."""
    calls = {"pm": 0}

    def run(*args, **kw):
        task = kw.get("task")
        if task == "weekly_pm":
            calls["pm"] += 1
            if pm is not None:
                out = pm
            elif calls["pm"] % 2 == 1:
                out = json.dumps({"ask": "화면은 끝났나?", "done": False, "summary": "화면 작업이 있었다."}, ensure_ascii=False)
            else:
                out = json.dumps({"ask": None, "done": True, "summary": "화면을 마쳤다.",
                                  "cards": [{"add": "배포 날짜 정하기", "status": "needs_user"}]}, ensure_ascii=False)
        elif task == "weekly_agent":
            out = agent
        else:
            out = result
        return {"result": out, "model": "sonnet", "cost_usd": 0.1, "output_tokens": 10, "task": task}
    return run


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
    # 전체 방엔 원문, alpha 방엔 점검 대화만(몫은 없음)
    assert messages_db.list_messages(wr._room(r["date"]))[-1]["body"].startswith("이번 주는")
    authors = [m["author"] for m in messages_db.list_messages(wr._room(r["date"], str(env["a"])))]
    assert "ohmyPM" not in authors
    assert not (env["a"] / "ohmypm" / "weekly.md").exists()


def test_weekly_no_result(env, monkeypatch):
    monkeypatch.setattr(wr, "run_headless_ex", _fake(None, pm=""))
    r = wr.run_weekly_report()
    assert r["ok"] is False and messages_db.list_rooms_like("weekly::") == [wr._room(r["date"], str(env["a"]))]
    # PM이 실패해도 방에 한 줄 남긴다(조용한 실패 금지)
    assert "실패" in messages_db.list_messages(wr._room(r["date"], str(env["a"])))[0]["body"]


def test_weekly_conversation_stored_and_fed(env, monkeypatch):
    """활동 있는 프로젝트만 PM↔담당 대화가 방에 쌓이고, 몫이 맨 끝, 룸 맥락으로도 읽힌다."""
    data = {"headline": "h", "projects": [{"name": "alpha", "summary": "몫"}], "quiet": ["beta"]}
    seen = {}
    fake = _fake(json.dumps(data, ensure_ascii=False))

    def spy(*args, **kw):
        if kw.get("task") == "weekly_report":
            seen["prompt"] = args[0]
        return fake(*args, **kw)
    monkeypatch.setattr(wr, "run_headless_ex", spy)
    r = wr.run_weekly_report()
    msgs = messages_db.list_messages(wr._room(r["date"], str(env["a"])))
    assert [m["author"] for m in msgs] == ["pm", "agent", "pm", "ohmyPM"]
    assert "담당에게: 화면은 끝났나?" in msgs[0]["body"]
    assert "칸반 1건 정리" in msgs[2]["body"]
    from src.db import cards as cards_db
    assert [c["title"] for c in cards_db.list_cards(str(env["a"]))] == ["배포 날짜 정하기"]
    assert "[PM과 담당의 점검 대화]" in seen["prompt"] and "막힌 건 없다" in seen["prompt"]
    assert messages_db.list_messages(wr._room(r["date"], str(env["b"]))) == []   # 조용한 프로젝트는 대화 없음
    ctx = wr.latest_conversation(str(env["a"]))
    assert r["date"] in ctx and "나(담당)" in ctx and wr.latest_conversation(str(env["b"])) == ""


def test_weekly_partial_run_merges_into_existing_report(env, monkeypatch):
    """한 프로젝트만 돌리면 그날 보고에 끼워 넣고, 조용했던 목록에서 빼며, 한 줄은 그대로 둔다."""
    date = "2026-10-10"
    messages_db.add_message(wr._room(date), "ohmyPM",
                            "# 주간보고 2026-10-10\n\n**이번 주 한 줄** — 원래 한 줄\n\n## gamma\n감마 몫\n\n"
                            "**조용했던 프로젝트** — alpha, beta\n")
    data = {"headline": "새 한 줄", "projects": [{"name": "alpha", "summary": "알파 몫"}], "quiet": []}
    calls = []
    fake = _fake(json.dumps(data, ensure_ascii=False))

    def spy(*args, **kw):
        calls.append(kw.get("task"))
        return fake(*args, **kw)
    monkeypatch.setattr(wr, "run_headless_ex", spy)
    r = wr.run_weekly_report(paths=[str(env["a"])], date=date)
    assert r["ok"] and r["projects"] == 1
    body = messages_db.list_messages(wr._room(date))[-1]["body"]
    assert "원래 한 줄" in body and "새 한 줄" not in body
    assert body.index("## gamma") < body.index("## alpha") < body.index("**조용했던 프로젝트** — beta")
    assert "알파 몫" in body and "alpha," not in body
    # 같은 프로젝트를 또 돌리면 절을 바꾼다(두 번 들어가지 않는다)
    data["projects"][0]["summary"] = "알파 다시"
    monkeypatch.setattr(wr, "run_headless_ex", _fake(json.dumps(data, ensure_ascii=False)))
    wr.run_weekly_report(paths=[str(env["a"])], date=date)
    body = messages_db.list_messages(wr._room(date))[-1]["body"]
    assert body.count("## alpha") == 1 and "알파 다시" in body and "알파 몫" not in body


def test_merge_report_drops_quiet_line_when_empty():
    out = wr._merge_report("# t\n\n**조용했던 프로젝트** — alpha\n", [("alpha", "몫")])
    assert "조용했던" not in out and "## alpha\n몫" in out


def test_weekly_review_stored_and_fed(env, monkeypatch):
    """커밋 있는 프로젝트만 이번 주 diff를 Ponytail 리뷰로 — 플러그인은 그 호출에만, 방엔 'review', 종합에도 실린다."""
    data = {"headline": "h", "projects": [{"name": "alpha", "summary": "몫"}], "quiet": ["beta"]}
    seen = {"review_calls": []}
    fake = _fake(json.dumps(data, ensure_ascii=False))

    def spy(*args, **kw):
        if kw.get("task") == "weekly_review":
            seen["review_calls"].append(kw)
            return {"result": "이번 주 변경: 화면 추가.\n꼭 고칠 것\n1. **포커스가 튕김** `app.js:10`",
                    "model": "sonnet", "cost_usd": 0.1, "output_tokens": 10, "task": "weekly_review"}
        if kw.get("task") == "weekly_report":
            seen["prompt"] = args[0]
        return fake(*args, **kw)
    monkeypatch.setattr(wr, "run_headless_ex", spy)
    monkeypatch.setattr(wr, "_ponytail_dir", lambda: "/plugins/ponytail")
    monkeypatch.setattr(wr, "_week_diff", lambda path, days: "=== 커밋 abc 10-05 화면 추가\n+x")
    r = wr.run_weekly_report()
    assert len(seen["review_calls"]) == 1                                   # beta는 커밋이 없어 리뷰 없음
    call = seen["review_calls"][0]
    assert call["plugin_dirs"] == ["/plugins/ponytail"] and call["add_dirs"] == [str(env["a"])]
    assert set(call["allowed_tools"]) == {"Read", "Grep", "Glob"}          # 읽기 전용
    authors = [m["author"] for m in messages_db.list_messages(wr._room(r["date"], str(env["a"])))]
    assert authors == ["pm", "agent", "pm", "review", "ohmyPM"]
    assert "[이번 주 변경 리뷰]" in seen["prompt"] and "포커스가 튕김" in seen["prompt"]


def test_weekly_review_skipped_without_plugin(env, monkeypatch):
    data = {"headline": "h", "projects": [{"name": "alpha", "summary": "몫"}], "quiet": []}
    monkeypatch.setattr(wr, "run_headless_ex", _fake(json.dumps(data, ensure_ascii=False)))
    monkeypatch.setattr(wr, "_ponytail_dir", lambda: None)
    r = wr.run_weekly_report()
    authors = [m["author"] for m in messages_db.list_messages(wr._room(r["date"], str(env["a"])))]
    assert "review" not in authors and r["ok"]
