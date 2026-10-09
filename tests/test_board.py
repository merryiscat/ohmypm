"""게시판 토론 — 응답 파싱·자기 글 제외·반응 중복 방지·단계 시간 배분·설치 멱등."""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.cc import board  # noqa: E402
from src.config.settings import settings  # noqa: E402
from src.db import client as db_client  # noqa: E402


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """임시 SQLite로 바꿔 끼운다 — 스레드 로컬 커넥션도 비워야 새 경로가 먹는다."""
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    db_client._local.conn = None
    db_client.init_db()
    yield
    conn = getattr(db_client._local, "conn", None)
    if conn is not None:
        conn.close()
    db_client._local.conn = None


def test_parse_board_response_keeps_disliked_and_caps_comments():
    out = '여기 결과 {"opened":[1,2],"liked":[2,3],"disliked":[3,9],"comments":[{"post_id":1,"comment":"a"},{"post_id":2,"comment":"b"},{"post_id":2,"comment":"c"}]}'
    opened, liked, disliked, cmts = board._parse_board_response(out, {1, 2, 3})
    assert disliked == {3}                      # 9는 없는 글이라 버림
    assert liked == {2}                         # 3은 좋아요·싫어요 둘 다 → 반대표만
    assert opened == {1, 2, 3}                  # 반응한 글은 연 것으로
    assert len(cmts) == board.MAX_COMMENTS_PER_AGENT


def test_parse_board_response_garbage_is_empty():
    assert board._parse_board_response("응답 없음", {1}) == (set(), set(), set(), [])
    assert board._parse_board_response(None, {1}) == (set(), set(), set(), [])


def test_react_is_recorded_once(tmp_db):
    from src.db import board as board_db

    p = board_db.add_post("alpha", "t", "b", project=r"C:\x\alpha", day="2026-10-09", session_id=7)
    assert board_db.react("beta", "post", p["id"], "like", 7) is True
    assert board_db.react("beta", "post", p["id"], "like", 8) is False   # 다른 회차여도 같은 담당·같은 글은 한 번
    assert board_db.react("gamma", "post", p["id"], "like", 7) is True
    assert board_db.get_post(p["id"])["likes"] == 2
    assert board_db.reacted_ids("beta", "post", {p["id"], 999}) == {p["id"]}


def test_list_posts_since_day_and_session_filters(tmp_db):
    from src.db import board as board_db

    old = board_db.add_post("a", "old", "b", day="2026-09-01")
    new = board_db.add_post("a", "new", "b", day="2026-10-09", session_id=3)
    board_db.add_comment(new["id"], "b", "c", session_id=3)
    recent = board_db.list_posts(since_day="2026-10-01")
    assert [p["id"] for p in recent] == [new["id"]]
    assert [p["id"] for p in board_db.posts_for_session(3)] == [new["id"]]
    assert len(board_db.comments_for_session(3)) == 1
    assert old["id"] not in {p["id"] for p in board_db.posts_for_session(3)}


def test_phase_plan_is_cumulative_and_ends_at_one():
    from src.cc.board_session import PHASE_PLAN

    shares = [s for _, s in PHASE_PLAN]
    assert shares == sorted(shares) and shares[-1] == 1.0
    assert [n for n, _ in PHASE_PLAN] == ["write", "browse", "feedback", "followup"]


def test_scores_roundtrip(tmp_db):
    from src.db import sessions as sessions_db

    s = sessions_db.create_session(10, None)
    sessions_db.upsert_score(s["id"], r"C:\x\alpha", "alpha", posts=1, views=3, post_likes=2, points=23, total=23)
    sessions_db.upsert_score(s["id"], r"C:\x\alpha", "alpha", lesson="짧게 쓰자")
    rows = sessions_db.list_scores(r"C:\x\alpha")
    assert rows[0]["points"] == 23 and rows[0]["lesson"] == "짧게 쓰자"
    assert sessions_db.last_delta(r"C:\x\alpha") == 23
    sessions_db.merge_stats(s["id"], {"posted": 1, "cost_usd": 0.5})
    sessions_db.merge_stats(s["id"], {"posted": 2, "cost_usd": 0.25})
    assert sessions_db.get_session(s["id"])["stats"] == {"posted": 3, "cost_usd": 0.75}


def test_install_is_idempotent_and_reversible(tmp_path):
    from src import install

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "CLAUDE.md").write_bytes("\ufeff# 내 프로젝트\r\n규칙 하나\r\n".encode("utf-8"))   # BOM + CRLF, 끝 개행 있음
    r1 = install.install_project(str(proj))
    assert "ohmypm/" in r1["created"] and "CLAUDE.md" in r1["created"] and "AGENTS.md" in r1["created"]
    assert (proj / "ohmypm" / ".gitignore").read_text(encoding="utf-8") == "*\n"
    claude = (proj / "CLAUDE.md").read_bytes()
    assert claude.startswith("\ufeff".encode("utf-8")) and b"<!-- ohmypm:start -->" in claude and b"\r\n" in claude
    r2 = install.install_project(str(proj))
    assert r2["created"] == [] and "CLAUDE.md" in r2["skipped"]
    r3 = install.uninstall_project(str(proj))
    assert "ohmypm/" in r3["removed"] and not (proj / "ohmypm").exists()
    assert (proj / "CLAUDE.md").read_bytes() == "\ufeff# 내 프로젝트\r\n규칙 하나\r\n".encode("utf-8")
    assert not (proj / "AGENTS.md").exists()   # 블록만 있던 파일은 사라진다


def test_install_skips_self():
    from src import install
    from src.cc.common import REPO_ROOT

    assert install.install_project(str(REPO_ROOT)).get("self") is True


def test_new_tables_exist(tmp_db):
    names = {r["name"] for r in db_client.get_db().execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"board_sessions", "board_reactions", "discussion_scores", "lab_proposals"} <= names
    cols = {r["name"] for r in db_client.get_db().execute("PRAGMA table_info(posts)")}
    assert "session_id" in cols
    assert isinstance(db_client.get_db(), sqlite3.Connection)
    assert Path(settings.db_path).exists()
