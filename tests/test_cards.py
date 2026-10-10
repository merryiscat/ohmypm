"""칸반 카드 — PM·담당의 변경 목록 반영, 남의 카드 차단, 채팅 답의 카드 블록 떼기, 완료 시각."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.cc import cards as cc  # noqa: E402
from src.config.settings import settings  # noqa: E402
from src.db import cards as cards_db  # noqa: E402
from src.db import client as db_client  # noqa: E402


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    db_client._local.conn = None
    db_client.init_db()
    yield
    conn = getattr(db_client._local, "conn", None)
    if conn is not None:
        conn.close()
    db_client._local.conn = None


def test_apply_ops_add_move_delete_and_scope():
    n = cc.apply_ops("A", [{"add": "화면 붙이기", "due": "2026-10-20"},
                           {"add": "배포 결정", "status": "needs_user", "due": "내일"}], by="pm")
    assert n == 2
    a1, a2 = cards_db.list_cards("A")
    assert a1["due"] == "2026-10-20" and a2["due"] is None and a2["status"] == "needs_user"
    other = cards_db.add_card("B", "남의 카드")
    n = cc.apply_ops("A", [{"id": a1["id"], "status": "done"}, {"id": other["id"], "status": "done"},
                           {"id": a2["id"], "delete": True}, {"id": a1["id"], "status": "없는칸"}, "쓰레기"], by="agent")
    assert n == 2
    assert cards_db.get_card(a1["id"])["status"] == "done" and cards_db.get_card(a1["id"])["done_at"]
    assert cards_db.get_card(a2["id"]) is None
    assert cards_db.get_card(other["id"])["status"] == "todo"      # 다른 프로젝트 카드는 못 건드린다


def test_duplicate_open_title_not_added_and_done_at_cleared():
    c = cards_db.add_card("A", "같은 일")
    assert cards_db.add_card("A", "같은 일")["id"] == c["id"]
    cards_db.update_card(c["id"], status="done")
    assert cards_db.update_card(c["id"], status="doing")["done_at"] is None


def test_take_block_and_cards_text():
    body, ops = cc.take_block('끝났어.\n\n```cards\n[{"add": "새 일"}]\n```')
    assert body == "끝났어." and ops == [{"add": "새 일"}]
    assert cc.take_block("블록 없음") == ("블록 없음", None)
    cards_db.add_card("A", "늦은 일", due="2000-01-01")
    assert "[지연]" in cc.cards_text("A") and cc.cards_text("Z") == "(카드 없음)"
