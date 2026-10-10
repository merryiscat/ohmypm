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


def test_notes_assets_and_consult_keep_full_document(env, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.web.routers.api import router

    folder = lab.LAB_DIR / "notes" / "skills"
    folder.mkdir(parents=True)
    body = "# HyperFrames\n\n## 핵심 요약\n" + "조사 내용 " * 1000 + "\n끝까지 읽어야 하는 시험 결과"
    (folder / "hyperframes.md").write_text(body, encoding="utf-8")
    (folder / "hyperframes-showcase.mp4").write_bytes(b"0123456789")
    (folder / "other.mp4").write_bytes(b"unrelated")
    (folder / "hyperframes-secret.txt").write_text("private", encoding="utf-8")
    (lab.LAB_DIR / "skills.md").write_text("최근 위키", encoding="utf-8")

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        note, = client.get("/api/lab/skills/notes").json()
        assert note["title"] == "HyperFrames" and note["body"] == body
        asset, = note["assets"]
        response = client.get(asset["url"], headers={"Range": "bytes=2-5"})
        assert response.status_code == 206 and response.content == b"2345"
        assert response.headers["content-type"] == "video/mp4"
        for name in ["other.mp4", "hyperframes-secret.txt", "missing.mp4"]:
            assert client.get(f"/api/lab/skills/notes/hyperframes/assets/{name}").status_code == 404
        assert client.get("/api/lab/unknown/notes").json() == []
    assert lab.note_file("skills", "../skills.md") is None
    assert lab.note_file("skills", str(folder / "hyperframes.md")) is None
    assert lab.note_file("../skills", "hyperframes.md") is None

    prompts = []
    def answer(prompt, **kwargs):
        prompts.append(prompt)
        return {"result": "답변"}
    monkeypatch.setattr(lab, "run_headless_ex", answer)
    assert lab.consult("skills", "시험 결과 알려줘") == "답변"
    assert "최근 위키" in prompts[0] and body in prompts[0]


NOTE = "# 테스트 주제\n\n2026-10-10 기준\n\n## 핵심 요약\n**결론.**\n\n## 우리 쪽 적용\n제안일 뿐.\n"


def test_request_note_queues_and_writes_note(env, monkeypatch):
    """요청 → 대기열 → 처리하면 정리 문서 파일과 완료 상태. 코드 펜스로 감싸 와도 벗긴다."""
    from src import jobs

    calls = []
    monkeypatch.setattr(jobs, "start", lambda name, target, *a, **k: calls.append(name) or True)
    monkeypatch.setattr(lab, "run_headless_ex",
                        lambda *a, **k: {"result": "```markdown\n" + NOTE + "```", "cost_usd": 1.5, "task": k.get("task")})
    r = lab.request_note("skills", "  CLAUDE.md 설정법!  ", "어디에 무엇을")
    assert r["ok"] and r["request"]["status"] == "queued" and calls == [lab.NOTE_JOB]
    assert lab.request_note("skills", "  ", None)["ok"] is False
    assert lab.request_note("nobody", "x", None)["ok"] is False
    out = lab.process_requests()
    assert out == {"done": 1, "failed": 0}
    row = lab_db.list_requests("skills")[0]
    assert row["status"] == "done" and row["cost_usd"] == 1.5
    f = env["tmp"] / "lab" / "notes" / "skills" / f"{row['note_key']}.md"
    assert f.read_text(encoding="utf-8") == NOTE
    assert row["note_key"].endswith("claude-md-설정법")
    assert [n["key"] for n in lab.research_notes("skills")] == [row["note_key"]]


def test_request_note_bad_output_fails_and_keeps_raw(env, monkeypatch):
    from src import jobs

    monkeypatch.setattr(jobs, "start", lambda *a, **k: True)
    monkeypatch.setattr(lab, "run_headless_ex", lambda *a, **k: {"result": "그냥 답변(제목 없음)", "cost_usd": 0.1})
    lab.request_note("design", "주제", None)
    assert lab.process_requests() == {"done": 0, "failed": 1}
    row = lab_db.list_requests("design")[0]
    assert row["status"] == "failed" and "형식" in row["error"]
    assert list((env["tmp"] / "state").glob("design.note-failed-*.txt"))


def test_requeue_running_on_restart(env, monkeypatch):
    from src import jobs

    started = []
    monkeypatch.setattr(jobs, "start", lambda name, *a, **k: started.append(name) or True)
    lab_db.add_request("models", "끊긴 요청", None)
    assert lab_db.next_queued()["status"] == "running"
    lab.resume_requests()
    assert lab_db.list_requests("models")[0]["status"] == "queued" and started == [lab.NOTE_JOB]


def test_note_key_avoids_existing_files(env):
    d = env["tmp"] / "lab" / "notes" / "models"
    d.mkdir(parents=True)
    (d / "2026-10-10-주제.md").write_text("x", encoding="utf-8")
    assert lab._note_key("2026-10-10", "주제") == "2026-10-10-주제-2"
    assert lab._note_key("2026-10-10", "///") == "2026-10-10-note"
