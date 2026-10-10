"""환경 세팅 — 수집·제안 검증·적용·되돌리기·서버 재시작 정리.

임시 프로젝트와 임시 SQLite만 쓰고, 모델(run_headless_ex)은 가짜로 바꾼다. 실제 프로젝트·실제 모델은 안 쓴다.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import env_setup as es  # noqa: E402
from src.cc import env_setup as cc_env  # noqa: E402
from src.config.settings import settings  # noqa: E402
from src.db import client as db_client  # noqa: E402
from src.db import env_setup as env_db  # noqa: E402
from src.db import projects as projects_db  # noqa: E402

CLAUDE = "# 프로젝트\n\n규칙 하나\n"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    db_client._local.conn = None
    db_client.init_db()
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "CLAUDE.md").write_text(CLAUDE, encoding="utf-8", newline="")
    projects_db.upsert_project(str(proj), "proj", False)
    yield proj
    conn = getattr(db_client._local, "conn", None)
    if conn is not None:
        conn.close()
    db_client._local.conn = None


def fake_model(items, calls=None):
    def run(*args, **kw):
        if calls is not None:
            calls.append((args, kw))
        body = items if isinstance(items, str) else json.dumps({"items": items}, ensure_ascii=False)
        return {"result": body, "model": "opus", "cost_usd": 0.5, "output_tokens": 100, "task": kw.get("task")}
    return run


def item(**kw):
    base = {"id": "item-1", "kind": "claude_md", "title": "응답 언어", "why": "한국어로 답하게 합니다.",
            "target": "CLAUDE.md", "op": "append", "before": None, "after": "\n응답은 한국어로 한다.\n",
            "material": None, "experimental": False}
    base.update(kw)
    return base


def propose(monkeypatch, proj, items, calls=None):
    monkeypatch.setattr(cc_env, "run_headless_ex", fake_model(items, calls))
    run_id = env_db.create_run(str(proj.resolve()))
    cc_env.run_env_setup(run_id)
    return run_id, env_db.get_run(run_id), env_db.list_items(run_id)


def make_link(link: Path, target: Path):
    try:
        os.symlink(target, link, target_is_directory=target.is_dir())
        return
    except (OSError, NotImplementedError):
        pass
    try:
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    except Exception:
        pytest.skip("연결 경로를 만들 수 없는 환경")


# ── 수집 ─────────────────────────────────────────────────────────────────────
def test_collect_snapshot_facts_and_limits(env, monkeypatch):
    (env / "package.json").write_text(json.dumps({"scripts": {"test": "vitest", "build": "vite build"}}), encoding="utf-8")
    (env / "src").mkdir()
    (env / "src" / "App.tsx").write_text("x", encoding="utf-8")
    (env / "src" / "a.css").write_text("x", encoding="utf-8")
    (env / "tests").mkdir()
    (env / "docs").mkdir()
    for i in range(3):
        (env / "docs" / f"d{i}.md").write_text("x", encoding="utf-8")
    big = "가" * 30
    (env / "AGENTS.md").write_text(big, encoding="utf-8")
    monkeypatch.setattr(es, "MAX_INSTRUCTION_CHARS", 10)
    monkeypatch.setattr(es, "MAX_DOCS", 2)
    s = es.collect_snapshot(str(env))
    assert "package.json" in s["manifests"]
    assert s["frontend_counts"] == {".tsx": 1, ".css": 1}
    assert "tests" in s["test_dirs"]
    assert {"command": "npm run test", "source": "package.json", "location": "scripts.test",
            "script": "vitest"} in s["commands"]
    assert s["docs"][:2] == ["docs/d0.md", "docs/d1.md"] and s["docs"][-1] == "(이후 생략)"
    a = s["instructions"]["AGENTS.md"]
    assert a["truncated"] and len(a["text"]) == 10
    assert a["sha256"] == sha((env / "AGENTS.md").read_bytes())          # 해시는 원본 전체 바이트
    assert s["targets"][".claude/settings.json"]["exists"] is False
    assert not (env / "ohmypm").exists()                                   # 수집은 아무것도 만들지 않는다
    assert any("잘랐다" in w for w in s["warnings"]) and any("앞 10자" in w for w in s["warnings"])


def test_collect_excludes_dependencies_and_external_links(env, tmp_path):
    (env / "node_modules" / "x").mkdir(parents=True)
    (env / "node_modules" / "x" / "a.js").write_text("x", encoding="utf-8")
    (env / ".venv").mkdir()
    (env / ".venv" / "b.html").write_text("x", encoding="utf-8")
    (env / "ohmypm").mkdir()
    (env / "ohmypm" / "c.css").write_text("x", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.html").write_text("x", encoding="utf-8")
    make_link(env / "linked", outside)
    s = es.collect_snapshot(str(env))
    assert s["frontend_counts"] == {}


def test_collect_settings_errors_and_env_ignore(env):
    (env / ".claude").mkdir()
    (env / ".claude" / "settings.json").write_text("{깨짐", encoding="utf-8")
    (env / ".claude" / "settings.local.json").write_text(json.dumps(
        {"permissions": {"allow": ["Bash(ls:*)"]}, "hooks": {"Stop": [{"x": 1}, {"y": 2}]}, "env": {"KEY": "비밀"}}),
        encoding="utf-8")
    (env / ".env").write_text("SECRET=1", encoding="utf-8")
    s = es.collect_snapshot(str(env))
    broken = s["settings_summary"][".claude/settings.json"]
    assert broken["exists"] and broken["valid_json"] is False               # 깨진 설정 ≠ 없는 설정
    local = s["settings_summary"][".claude/settings.local.json"]
    assert local["hooks"] == {"Stop": 2} and "비밀" not in json.dumps(s, ensure_ascii=False)
    assert s["env_ignored"]["value"] == "unknown"                           # git 저장소가 아님
    subprocess.run(["git", "init", "-q"], cwd=env, check=True)
    (env / ".gitignore").write_text(".env\n", encoding="utf-8")
    assert es.collect_snapshot(str(env))["env_ignored"]["value"] == "yes"
    (env / ".gitignore").write_text("# .env 는 올리지 말 것\n", encoding="utf-8")   # 글자만 있고 규칙은 아님
    assert es.collect_snapshot(str(env))["env_ignored"]["value"] == "no"


# ── 제안 ─────────────────────────────────────────────────────────────────────
def test_propose_calls_model_once_read_only(env, monkeypatch):
    calls = []
    _, run, items = propose(monkeypatch, env, [item()], calls)
    assert len(calls) == 1 and run["status"] == "proposed" and len(items) == 1
    args, kw = calls[0]
    assert kw["task"] == "env_setup" and kw["add_dirs"] == [str(env.resolve())]
    assert kw["cwd"] == cc_env.neutral_cwd() and "plugin_dirs" not in kw
    assert set(kw["allowed_tools"]) == {"Read", "Grep", "Glob"}
    assert kw["append_system_prompt"] == cc_env.ENV_SETUP_SYSTEM
    assert run["model"] == "opus" and run["cost_usd"] == 0.5


@pytest.mark.parametrize("resp,ok", [
    (json.dumps({"items": []}), True),
    ("JSON이 아닌 답", False),
    (json.dumps({"items": "x"}), False),
    (json.dumps({"items": [item(), item()]}), False),                     # 식별자 겹침
    (json.dumps({"items": [item(id=f"i{n}", target="AGENTS.md", kind="doc") for n in range(9)]}), False),
    (json.dumps({"items": [item(title=123)]}), False),
    (json.dumps({"items": [item(op="replace", before=None)]}), False),
    (json.dumps({"items": [item(before="x")]}), False),                   # append인데 before
    (json.dumps({"items": [item(why="좋아요 \U0001F600")]}), False),        # 이모지
])
def test_proposal_json_validation(env, monkeypatch, resp, ok):
    _, run, items = propose(monkeypatch, env, resp)
    assert (run["status"] == "proposed") is ok
    if not ok:
        assert run["error"] and items == []


@pytest.mark.parametrize("target", ["/etc/x", "C:/Windows/x", "C:x", "\\\\srv\\share\\CLAUDE.md", "../CLAUDE.md",
                                    "a/../../CLAUDE.md", "CLAUDE.md:stream", "CLAUDE.md.", "docs//x.md",
                                    ".claude/settings.local.json"])
def test_proposal_rejects_unsafe_targets(env, monkeypatch, target):
    _, run, _ = propose(monkeypatch, env, [item(kind="doc", target=target)])
    assert run["status"] == "failed"


def test_proposal_rejects_wrong_writable_target_and_linked_path(env, monkeypatch, tmp_path):
    _, run, _ = propose(monkeypatch, env, [item(target="README.md")])        # claude_md인데 다른 파일
    assert run["status"] == "failed"
    outside = tmp_path / "out"
    outside.mkdir()
    make_link(env / "lnk", outside)
    _, run, _ = propose(monkeypatch, env, [item(kind="doc", target="lnk/x.md")])
    assert run["status"] == "failed"


def test_material_policy_and_skill_display_only(env, monkeypatch):
    calls = []
    run_id, run, items = propose(monkeypatch, env, [
        item(id="s1", kind="skill", target=".claude/skills/web-review/SKILL.md", op="create",
             material="skills/web-review/", experimental=False),
        item(id="d1", kind="doc", target="DESIGN.md", op="create", material="templates/DESIGN.md")], calls)
    assert run["status"] == "proposed"
    by = {json.loads(i["proposal_json"])["id"]: i for i in items}
    s1 = json.loads(by["s1"]["proposal_json"])
    assert s1["experimental"] is True and "install_guide" in s1 and not by["s1"]["applicable"]   # 코드가 정함
    assert not by["d1"]["applicable"]
    with pytest.raises(es.EnvSetupError):
        es.apply_run(run_id, [by["s1"]["id"]])
    assert not (env / ".claude").exists() and not (env / "DESIGN.md").exists()
    _, run, _ = propose(monkeypatch, env, [item(id="s2", kind="skill", target=".claude/skills/x/SKILL.md",
                                                 op="create", material="skills/unknown/")])
    assert run["status"] == "failed"                                         # kit 밖 재료
    _, run, _ = propose(monkeypatch, env, [item(id="s3", kind="skill", target=".claude/skills/x/SKILL.md",
                                                 op="create", material=None)])
    assert run["status"] == "failed"


def test_settings_only_adds_deny_rules(env, monkeypatch):
    base = {"permissions": {"allow": ["Read"], "deny": ["Bash(rm:*)"]}, "model": "sonnet"}
    (env / ".claude").mkdir()
    (env / ".claude" / "settings.json").write_text(json.dumps(base), encoding="utf-8")
    old = json.dumps(base)
    good = json.dumps({"permissions": {"allow": ["Read"], "deny": ["Bash(rm:*)", "Read(./.env)"]}, "model": "sonnet"})
    assert es._settings_deny_only(old, good) is None
    assert es._settings_deny_only(old, json.dumps({"permissions": {"allow": ["Read", "Bash"], "deny": ["Bash(rm:*)", "X"]},
                                                   "model": "sonnet"}))           # 허용 확대
    assert es._settings_deny_only(old, json.dumps({"permissions": {"allow": ["Read"], "deny": ["X"]}, "model": "sonnet"}))
    assert es._settings_deny_only(old, json.dumps({**json.loads(good), "hooks": {"Stop": []}}))
    assert es._settings_deny_only(old, "{깨진")
    run_id, run, items = propose(monkeypatch, env, [item(kind="settings", target=".claude/settings.json",
                                                         op="replace", before='"deny": ["Bash(rm:*)"]',
                                                         after='"deny": ["Bash(rm:*)", "Read(./.env)"]')])
    r = es.apply_run(run_id, [items[0]["id"]])
    assert r["counts"]["applied"] == 1
    assert json.loads((env / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"]["deny"] == \
        ["Bash(rm:*)", "Read(./.env)"]
    # 허용을 넓히는 replace는 적용 단계에서 건너뛴다
    (env / ".claude" / "settings.json").write_text(old, encoding="utf-8")
    run_id, run, items = propose(monkeypatch, env, [item(kind="settings", target=".claude/settings.json",
                                                         op="replace", before='"allow": ["Read"]',
                                                         after='"allow": ["Read", "Bash"]')])
    r = es.apply_run(run_id, [items[0]["id"]])
    assert r["counts"]["applied"] == 0 and (env / ".claude" / "settings.json").read_text(encoding="utf-8") == old


# ── 적용 ─────────────────────────────────────────────────────────────────────
def test_unapproved_items_leave_files_unchanged(env, monkeypatch):
    (env / "AGENTS.md").write_text("에이전트\n", encoding="utf-8")
    before = (env / "AGENTS.md").read_bytes()
    run_id, _, items = propose(monkeypatch, env, [item(), item(id="item-2", kind="agents_md", target="AGENTS.md")])
    r = es.apply_run(run_id, [items[0]["id"]])
    assert (env / "AGENTS.md").read_bytes() == before
    st = {i["proposal_id"]: i["status"] for i in r["items"]}
    assert st == {"item-1": "applied", "item-2": "rejected"} and r["counts"]["rejected"] == 1


@pytest.mark.parametrize("change", ["modify", "delete", "create"])
def test_changed_source_is_skipped(env, monkeypatch, change):
    if change == "create":
        (env / "CLAUDE.md").unlink()
        run_id, _, items = propose(monkeypatch, env, [item(op="create", after="새 지침\n")])
        (env / "CLAUDE.md").write_text("사용자가 먼저 만듦\n", encoding="utf-8")
    else:
        run_id, _, items = propose(monkeypatch, env, [item()])
        if change == "modify":
            (env / "CLAUDE.md").write_text(CLAUDE + "사용자 수정\n", encoding="utf-8")
        else:
            (env / "CLAUDE.md").unlink()
    snapshot = (env / "CLAUDE.md").read_bytes() if (env / "CLAUDE.md").exists() else None
    r = es.apply_run(run_id, [items[0]["id"]])
    assert r["items"][0]["status"] == "skipped" and "바뀌어" in r["items"][0]["reason"]
    assert ((env / "CLAUDE.md").read_bytes() if (env / "CLAUDE.md").exists() else None) == snapshot


@pytest.mark.parametrize("text", ["규칙 둘\n", "규칙 하나\n규칙 하나\n"])
def test_replace_requires_one_exact_match(env, monkeypatch, text):
    (env / "CLAUDE.md").write_text("# p\n" + text, encoding="utf-8")
    run_id, _, items = propose(monkeypatch, env, [item(op="replace", before="규칙 하나", after="규칙 1")])
    r = es.apply_run(run_id, [items[0]["id"]])
    assert r["items"][0]["status"] == "skipped" and (env / "CLAUDE.md").read_text(encoding="utf-8") == "# p\n" + text


def test_preserves_crlf_bom_and_unmodified_text(env, monkeypatch):
    raw = "\ufeff# 제목\r\n규칙 하나\r\n끝\r\n".encode("utf-8")
    (env / "CLAUDE.md").write_bytes(raw)
    run_id, _, items = propose(monkeypatch, env, [item(op="replace", before="규칙 하나\n", after="규칙 1\n")])
    es.apply_run(run_id, [items[0]["id"]])
    assert (env / "CLAUDE.md").read_bytes() == "\ufeff# 제목\r\n규칙 1\r\n끝\r\n".encode("utf-8")
    (env / "CLAUDE.md").write_bytes(raw)
    run_id, _, items = propose(monkeypatch, env, [item(after="\n추가 줄\n")])
    es.apply_run(run_id, [items[0]["id"]])
    assert (env / "CLAUDE.md").read_bytes() == raw + "\r\n추가 줄\r\n".encode("utf-8")


def test_preserves_marked_blocks_and_imports(env, monkeypatch):
    block = "<!-- ohmypm:start -->\n## ohmyPM\n- 블록 내용\n<!-- ohmypm:end -->\n"
    (env / "CLAUDE.md").write_text("@AGENTS.md\n# p\n" + block, encoding="utf-8")
    cases = [item(op="replace", before="- 블록 내용", after="- 바꿈"),                  # 블록 안
             item(op="replace", before="# p\n<!-- ohmypm:start -->", after="# q\n"),   # 경계에 걸침
             item(op="replace", before="@AGENTS.md\n", after="")]                       # 불러오기 삭제
    for c in cases:
        orig = (env / "CLAUDE.md").read_bytes()
        run_id, run, items = propose(monkeypatch, env, [c])
        r = es.apply_run(run_id, [items[0]["id"]])
        assert r["items"][0]["status"] == "skipped", c
        assert (env / "CLAUDE.md").read_bytes() == orig
    # 내용 있는 AGENTS.md만 있는데 @AGENTS.md 없이 CLAUDE.md를 새로 만들면 적용 불가로 표시
    (env / "CLAUDE.md").unlink()
    (env / "AGENTS.md").write_text("에이전트 규칙\n", encoding="utf-8")
    _, _, items = propose(monkeypatch, env, [item(op="create", after="# 새 지침\n")])
    assert not items[0]["applicable"] and "@AGENTS.md" in items[0]["reason"]


def test_duplicate_target_is_rejected(env, monkeypatch):
    _, run, _ = propose(monkeypatch, env, [item(), item(id="item-2", target="claude.md")])
    assert run["status"] == "failed" and "같은 파일" in run["error"]


def test_backup_failure_prevents_write(env, monkeypatch):
    run_id, _, items = propose(monkeypatch, env, [item()])
    before = (env / "CLAUDE.md").read_bytes()

    def boom(data, dest):
        raise OSError("디스크 가득")
    monkeypatch.setattr(es, "_backup", boom)
    r = es.apply_run(run_id, [items[0]["id"]])
    assert r["counts"]["failed"] == 1 and (env / "CLAUDE.md").read_bytes() == before
    assert r["run"]["status"] == "failed"


def test_apply_then_revert_restores_bytes(env, monkeypatch):
    (env / "other.txt").write_text("관계없음", encoding="utf-8")
    before = (env / "CLAUDE.md").read_bytes()
    (env / "AGENTS.md").unlink(missing_ok=True)
    run_id, _, items = propose(monkeypatch, env, [item(), item(id="item-2", kind="agents_md", target="AGENTS.md",
                                                              op="create", after="# 에이전트\n")])
    r = es.apply_run(run_id, [i["id"] for i in items])
    assert r["run"]["status"] == "applied" and (env / "AGENTS.md").exists()
    backup = Path(r["run"]["backup_dir"])
    assert backup.is_relative_to(env / "ohmypm" / "setup-backup") and (backup / "CLAUDE.md").read_bytes() == before
    assert (env / "ohmypm" / ".gitignore").read_text(encoding="utf-8") == "*\n"
    r2 = es.revert_run(run_id)
    assert r2["run"]["status"] == "reverted" and r2["counts"]["reverted"] == 2
    assert (env / "CLAUDE.md").read_bytes() == before and not (env / "AGENTS.md").exists()
    assert (env / "other.txt").read_text(encoding="utf-8") == "관계없음" and backup.exists()   # 백업은 남긴다


def test_revert_preserves_later_user_changes(env, monkeypatch):
    run1, _, items1 = propose(monkeypatch, env, [item()])
    es.apply_run(run1, [items1[0]["id"]])
    run2, _, items2 = propose(monkeypatch, env, [item(after="\n둘째 실행\n")])
    es.apply_run(run2, [items2[0]["id"]])
    now = (env / "CLAUDE.md").read_bytes()
    r = es.revert_run(run1)                                     # 오래된 실행 — 뒤 실행이 파일을 바꿨다
    assert r["counts"]["reverted"] == 0 and r["counts"]["skipped"] == 1
    assert "충돌" in r["items"][0]["reason"] and (env / "CLAUDE.md").read_bytes() == now
    (env / "CLAUDE.md").write_text("사용자가 손댐\n", encoding="utf-8")
    r = es.revert_run(run2)
    assert r["counts"]["reverted"] == 0 and (env / "CLAUDE.md").read_text(encoding="utf-8") == "사용자가 손댐\n"


def test_apply_and_revert_are_idempotent(env, monkeypatch):
    run_id, _, items = propose(monkeypatch, env, [item()])
    es.apply_run(run_id, [items[0]["id"]])
    once = (env / "CLAUDE.md").read_bytes()
    with pytest.raises(es.EnvSetupError) as e:
        es.apply_run(run_id, [items[0]["id"]])
    assert e.value.code == 409 and (env / "CLAUDE.md").read_bytes() == once
    es.revert_run(run_id)
    (env / "CLAUDE.md").write_text("되돌린 뒤 새로 씀\n", encoding="utf-8")
    with pytest.raises(es.EnvSetupError):
        es.revert_run(run_id)
    assert (env / "CLAUDE.md").read_text(encoding="utf-8") == "되돌린 뒤 새로 씀\n"


def test_self_project_rejected(env):
    from src.cc.common import REPO_ROOT

    projects_db.upsert_project(str(REPO_ROOT), "ohmyPM", True)
    for p in (str(REPO_ROOT), str(REPO_ROOT / "src" / "..")):
        with pytest.raises(es.EnvSetupError, match="자기 자신"):
            es.collect_snapshot(p)
        with pytest.raises(es.EnvSetupError, match="자기 자신"):
            cc_env.start(p)
    rid = env_db.create_run(str(REPO_ROOT))
    env_db.update_run(rid, status="applied")
    with pytest.raises(es.EnvSetupError, match="자기 자신"):
        es.revert_run(rid)


def test_existing_database_initialization(env):
    from src.db.client import get_db

    db = get_db()
    db.execute("INSERT INTO lab_requests (researcher, topic) VALUES ('skills', '남겨야 할 행')")
    db.commit()
    db_client.init_db()
    db_client.init_db()
    assert db.execute("SELECT topic FROM lab_requests").fetchone()["topic"] == "남겨야 할 행"
    names = {r["name"] for r in db.execute("SELECT name FROM sqlite_master")}
    assert {"env_setup_runs", "env_setup_items", "idx_env_setup_runs_project", "idx_env_setup_items_run"} <= names


def test_interrupted_run_recovery(env, monkeypatch):
    calls = []
    monkeypatch.setattr(cc_env, "run_headless_ex", fake_model([item()], calls))
    queued = env_db.create_run(str(env.resolve()))
    # 적용 도중 꺼진 실행: 항목 하나는 써졌고(계획 해시와 같음), 하나는 아직
    run_id, _, items = propose(monkeypatch, env, [item(), item(id="item-2", kind="agents_md", target="AGENTS.md",
                                                              op="create", after="# a\n")])
    calls.clear()
    env_db.update_run(run_id, status="applying")
    new = CLAUDE + "써진 내용\n"
    (env / "CLAUDE.md").write_text(new, encoding="utf-8", newline="")
    env_db.update_item(items[0]["id"], status="approved", approved_at="t", planned_hash=sha(new.encode("utf-8")))
    env_db.update_item(items[1]["id"], status="approved", approved_at="t", planned_hash="x")
    before_files = {p.name: p.read_bytes() for p in env.iterdir() if p.is_file()}
    es.recover_on_startup()
    assert env_db.get_run(queued)["status"] == "failed" and calls == []          # 모델 재호출 없음
    st = {i["proposal_id"]: i["status"] for i in env_db.list_items(run_id)}
    assert st == {"item-1": "applied", "item-2": "skipped"}
    assert env_db.get_run(run_id)["status"] == "partial" and "서버가 꺼져" in env_db.get_run(run_id)["error"]
    assert {p.name: p.read_bytes() for p in env.iterdir() if p.is_file()} == before_files   # 파일 자동 변경 없음


def test_uninstall_preserves_setup_backups(env, monkeypatch):
    from src import install

    install.install_project(str(env))
    run_id, _, items = propose(monkeypatch, env, [item(after="\n추가\n")])
    es.apply_run(run_id, [items[0]["id"]])
    r = install.uninstall_project(str(env))
    assert r.get("blocked") and (env / "ohmypm" / "setup-backup").is_dir()


def test_settings_summary_redacts_secrets(env):
    (env / ".claude").mkdir(exist_ok=True)
    rules = ["Bash(export SUPABASE_ACCESS_TOKEN=sbp_v0_aaaaaaaaaaaaaaaaaaaaaaaa)",
             "Bash(curl -H \"Authorization: Bearer abcdefghijklmnop\" x)",
             "Bash(OPENAI_API_KEY=sk-proj-abcdefgh12345678 node x)", "Bash(npm run test:*)"]
    (env / ".claude" / "settings.local.json").write_text(json.dumps({"permissions": {"allow": rules}}), encoding="utf-8")
    s = es.collect_snapshot(str(env))
    text = json.dumps(s, ensure_ascii=False)
    assert "sbp_v0_a" not in text and "abcdefghijklmnop" not in text and "sk-proj" not in text
    allow = s["settings_summary"][".claude/settings.local.json"]["permissions"]["allow"]
    assert allow[0] == f"Bash(export SUPABASE_ACCESS_TOKEN={es.REDACTED})" and allow[3] == "Bash(npm run test:*)"


def test_material_item_without_target_gets_code_chosen_target(env, monkeypatch):
    _, run, items = propose(monkeypatch, env, [item(id="s1", kind="skill", target=None, op="create", after=None,
                                                     material="skills/web-review/")])
    assert run["status"] == "proposed" and items[0]["target"] == ".claude/skills/web-review/SKILL.md"
    assert not items[0]["applicable"]
