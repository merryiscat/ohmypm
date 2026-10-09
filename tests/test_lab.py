"""랩실 — 연구원 명부, 웹 조사 결과 파싱·위키 기록·제안 저장(중복 skip, 미설치는 파일 기록 안 함)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.cc import expert, lab  # noqa: E402
from src.config.settings import settings  # noqa: E402
from src.db import client as db_client  # noqa: E402
from src.db import lab as lab_db  # noqa: E402
from src.db import projects as projects_db  # noqa: E402


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    db_client._local.conn = None
    db_client.init_db()
    monkeypatch.setattr(lab, "LAB_DIR", tmp_path / "lab")
    monkeypatch.setattr(lab, "STATE_DIR", tmp_path / "state")
    a = tmp_path / "alpha"; a.mkdir(); (a / "ohmypm").mkdir()
    b = tmp_path / "beta"; b.mkdir()
    projects_db.upsert_project(str(a), "alpha", True)
    projects_db.upsert_project(str(b), "beta", False)
    yield {"a": a, "b": b, "tmp": tmp_path}
    conn = getattr(db_client._local, "conn", None)
    if conn is not None:
        conn.close()
    db_client._local.conn = None


def test_researchers_fixed_and_models_matches_expert_registry():
    assert list(lab.RESEARCHERS) == ["models", "design", "skills"]
    assert lab.RESEARCHERS["models"]["domains"] == list(expert.EXPERTS)
    assert all(r["mode"] in ("catalog", "web") for r in lab.RESEARCHERS.values())


def test_web_research_writes_wiki_and_proposals(env, monkeypatch):
    data = {
        "findings": [
            {"title": "토큰 기반 다크모드", "summary": "색을 토큰으로 두면 테마가 쉽다.", "source_url": "https://example.com/a", "date": "2026-10"},
            {"title": "출처 없는 것", "summary": "버려야 함", "source_url": "javascript:alert(1)"},
        ],
        "proposals": [
            {"title": "alpha에 디자인 토큰 도입", "body": "무엇·왜·어디·첫 걸음", "target_project": "alpha", "source_url": "https://example.com/a"},
            {"title": "beta 접근성 점검", "body": "...", "target_project": "beta", "source_url": None},
            {"title": "전체 공통 폰트 정리", "body": "...", "target_project": None, "source_url": "https://example.com/c"},
        ],
    }
    monkeypatch.setattr(lab, "run_headless_ex", lambda *a, **k: {"result": json.dumps(data, ensure_ascii=False), "cost_usd": 0.2, "model": "sonnet"})
    r = lab.research("design")
    assert r["ok"] and r["findings"] == 1 and r["proposals"] == 3 and r["written"] == 1
    wiki = (env["tmp"] / "lab" / "design.md").read_text(encoding="utf-8")
    assert "토큰 기반 다크모드" in wiki and "출처 없는 것" not in wiki
    assert (env["a"] / "ohmypm" / "proposals.md").exists()
    assert not (env["b"] / "ohmypm").exists()
    rows = lab_db.list_proposals(project=str(env["a"]))
    assert {x["title"] for x in rows} == {"alpha에 디자인 토큰 도입", "전체 공통 폰트 정리"}   # beta 것은 안 보임
    assert next(x for x in rows if x["title"].startswith("alpha"))["written"] == 1
    # 같은 제목은 60일 안에 다시 안 들어간다
    r2 = lab.research("design")
    assert r2["proposals"] == 0 and r2["dup"] == 3
    assert lab.list_researchers()[1]["last_ok"] is True


def test_web_research_bad_json_keeps_raw_and_fails(env, monkeypatch):
    monkeypatch.setattr(lab, "run_headless_ex", lambda *a, **k: {"result": "그냥 글", "cost_usd": 0, "model": "sonnet"})
    r = lab.research("skills")
    assert r["ok"] is False
    assert (env["tmp"] / "state" / "skills.llm-failed.txt").read_text(encoding="utf-8") == "그냥 글"
    assert not (env["tmp"] / "lab" / "skills.md").exists()


def test_proposal_status(env):
    row = lab_db.add_proposal("skills", "t", "b", None, None)
    assert lab_db.set_status(row["id"], "done") and not lab_db.set_status(row["id"], "weird")
    assert lab_db.list_proposals(researcher="skills")[0]["status"] == "done"
