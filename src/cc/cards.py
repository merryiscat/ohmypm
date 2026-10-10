"""칸반 카드 반영 — PM(주간보고)과 담당(채팅)이 내놓은 카드 변경 목록을 DB에 적용한다.

모델은 DB를 직접 못 만진다. 대신 정해진 모양의 JSON 목록을 내놓고, 코드가 검사해서 반영한다.
  {"add": "제목", "status": "todo", "due": "2026-10-20", "note": "한 줄 설명"}   새 카드
  {"id": 12, "status": "done"}                                                 칸 옮기기(due·note·title도 가능)
  {"id": 12, "delete": true}                                                   잘못 만든 카드 지우기
다른 프로젝트의 카드 id는 무시한다(남의 판을 건드리지 못하게).
"""

import re
from datetime import date

from src.db import cards as cards_db

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# 담당 채팅 답에서 카드 변경 블록을 찾는다: ```cards [...] ```
_BLOCK_RE = re.compile(r"```cards\s*(\[.*?\])\s*```", re.DOTALL)


def cards_text(project: str, done_limit: int = 5) -> str:
    """프롬프트에 넣을 지금 카드 목록. 완료는 최근 몇 장만."""
    today = date.today().isoformat()
    rows = cards_db.list_cards(project)
    done = [c for c in rows if c["status"] == "done"][-done_limit:]
    live = [c for c in rows if c["status"] != "done"]
    names = dict(cards_db.STATUSES)
    lines = []
    for c in live + done:
        late = " [지연]" if c["due"] and c["due"] < today and c["status"] != "done" else ""
        due = f", 기한 {c['due']}" if c["due"] else ""
        note = f" — {c['note']}" if c.get("note") else ""
        lines.append(f"[{c['id']}] ({names.get(c['status'], c['status'])}{due}){late} {c['title']}{note}")
    return "\n".join(lines) or "(카드 없음)"


def _clean_due(v) -> str | None:
    return v if isinstance(v, str) and _DATE_RE.match(v) else None


def apply_ops(project: str, ops, by: str) -> int:
    """변경 목록 적용. 실제로 반영한 건수를 돌려준다. 모양이 틀린 항목은 조용히 건너뛴다."""
    if not isinstance(ops, list):
        return 0
    mine = {c["id"] for c in cards_db.list_cards(project)}
    n = 0
    for op in ops:
        if not isinstance(op, dict):
            continue
        if isinstance(op.get("add"), str) and op["add"].strip():
            cards_db.add_card(project, op["add"].strip()[:200], status=op.get("status") or "todo",
                              note=(op.get("note") or None), due=_clean_due(op.get("due")), created_by=by)
            n += 1
            continue
        try:
            cid = int(op.get("id"))
        except (TypeError, ValueError):
            continue
        if cid not in mine:
            continue
        if op.get("delete") is True:
            n += cards_db.delete_card(cid)
            continue
        fields = {k: op[k] for k in ("title", "note", "status") if isinstance(op.get(k), str) and op[k].strip()}
        if "due" in op:
            fields["due"] = _clean_due(op.get("due"))
        if fields and cards_db.update_card(cid, **fields):
            n += 1
    return n


def take_block(text: str) -> tuple[str, list | None]:
    """담당 답에서 ```cards [...]``` 블록을 떼어 낸다 → (블록을 뺀 본문, 변경 목록 또는 None)."""
    import json

    m = _BLOCK_RE.search(text or "")
    if not m:
        return text, None
    try:
        ops = json.loads(m.group(1))
    except json.JSONDecodeError:
        ops = None
    return (text[:m.start()] + text[m.end():]).strip(), ops if isinstance(ops, list) else None
