"""환경 세팅 API — 실행 범위·승인 검사, 작업 접수·이력. 라우터만 붙인 TestClient로 본다."""

import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.cc import env_setup as cc_env  # noqa: E402
from tests.test_env_setup import env, fake_model, item, propose  # noqa: E402,F401


@pytest.fixture
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.web.routers.api import router

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c


def test_env_setup_api_scope_and_approval(env, monkeypatch, client):
    run1, _, items1 = propose(monkeypatch, env, [item(), item(id="d1", kind="doc", target="DESIGN.md",
                                                              op="create", material="templates/DESIGN.md")])
    run2, _, items2 = propose(monkeypatch, env, [item()])
    assert client.post(f"/api/env-setup/{run1}/apply", json={"item_ids": [items2[0]["id"]]}).status_code == 422
    display = next(i for i in items1 if not i["applicable"])
    assert client.post(f"/api/env-setup/{run1}/apply", json={"item_ids": [display["id"]]}).status_code == 422
    assert client.post(f"/api/env-setup/{run1}/apply", json={"item_ids": []}).status_code == 422
    assert client.post("/api/env-setup/9999/apply", json={"item_ids": [1]}).status_code == 404
    applicable = next(i for i in items1 if i["applicable"])
    r = client.post(f"/api/env-setup/{run1}/apply", json={"item_ids": [applicable["id"]], "after": "몰래 바꾼 내용"})
    assert r.status_code == 200 and r.json()["counts"]["applied"] == 1
    assert "몰래" not in (env / "CLAUDE.md").read_text(encoding="utf-8")
    assert client.post(f"/api/env-setup/{run1}/apply", json={"item_ids": [applicable["id"]]}).status_code == 409
    assert client.post(f"/api/env-setup/{run2}/revert").status_code == 409            # 적용 안 한 실행
    d = client.get(f"/api/env-setup/{run1}").json()
    assert d["run"]["status"] == "applied" and d["run"]["has_backup"]
    shown = {i["proposal_id"]: i for i in d["items"]}
    assert shown["d1"]["experimental"] is True and shown["d1"]["applicable"] is False
    assert "snapshot_json" not in d["run"] and "raw_response" not in d["run"]


def test_env_setup_api_jobs_and_history(env, monkeypatch, client):
    monkeypatch.setattr(cc_env, "run_headless_ex", fake_model([item()]))
    r = client.post("/api/env-setup/run", json={"path": str(env)})
    assert r.status_code == 200 and r.json()["job"].startswith("env-setup-")
    body = r.json()
    for _ in range(100):
        st = client.get(f"/api/jobs/{body['job']}").json()
        if not st["running"]:
            break
        time.sleep(0.05)
    assert st["ok"] is True
    hist = client.get("/api/env-setup", params={"project": str(env)}).json()
    assert hist["available"] and hist["runs"][0]["id"] == body["run_id"] and hist["runs"][0]["status"] == "proposed"
    # 진행 중인 실행이 있으면 같은 프로젝트는 다시 받지 않는다
    from src.db import env_setup as env_db

    env_db.update_run(body["run_id"], status="running")
    assert client.post("/api/env-setup/run", json={"path": str(env)}).status_code == 409
    assert client.post("/api/env-setup/run", json={"path": str(env / "없음")}).status_code == 404
    other = env.parent / "unregistered"
    other.mkdir()
    assert client.post("/api/env-setup/run", json={"path": str(other)}).status_code == 404
    assert client.get("/api/env-setup", params={"project": str(other)}).json()["available"] is False
    assert json.loads(json.dumps(hist))   # 응답은 JSON으로 직렬화 가능
