"""llmwiki 파서 — 프로젝트 docs/의 status.md·pending.md에서 이슈를 추출.

★ 형식이 프로젝트마다 다르다(odin `## 날짜 미해결 — 제목` vs ohmyPM `## 미해결` 섹션).
   그래서 여러 패턴을 관대하게 훑는다. 못 맞춰도 죽지 않고 최대한 건진다.
"""

import re
from pathlib import Path

# YYYY-MM-DD 날짜 (기한 추출용)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_wiki(project_path: str) -> list[dict]:
    """docs/status.md(미해결)·pending.md(기한)를 파싱해 이슈 목록 반환."""
    docs = Path(project_path) / "docs"
    out: list[dict] = []

    status = docs / "status.md"
    if status.exists():
        out += _parse_status(status.read_text(encoding="utf-8", errors="replace"))

    pending = docs / "pending.md"
    if pending.exists():
        out += _parse_pending(pending.read_text(encoding="utf-8", errors="replace"))

    return out


def _parse_status(text: str) -> list[dict]:
    """status.md에서 미해결 추출. 3가지 형식 관대 처리:
    - odin식: `## 2026-08-24 미해결 — 제목` (헤더 자체가 이슈)
    - ohmyPM식: `## 미해결` 섹션 아래 `- 항목`
    - 범용: `- [ ]` 미완 체크박스
    """
    out: list[dict] = []
    in_unresolved = False  # ohmyPM식 '미해결' 섹션 안인지
    for line in text.splitlines():
        st = line.strip()
        if st.startswith("#"):
            header = st.lstrip("#").strip()
            before_dash = header.split("—")[0]  # 날짜+상태어 (— 앞부분)
            # "미해결"이되 상태어가 "완료"가 아닐 때만 (odin `날짜 완료 —` 헤더 오탐 제거)
            if "미해결" in header and "완료" not in before_dash:
                if DATE_RE.search(header) or "—" in header:
                    # odin식 — 날짜/대시 붙은 긴 헤더 = 이슈 하나
                    out.append(_issue(header, "status.md"))
                    in_unresolved = False
                else:
                    # ohmyPM식 — 짧은 섹션명, 하위 불릿이 이슈
                    in_unresolved = True
            else:
                in_unresolved = False
            continue
        if st.startswith("- [ ]"):  # 미완 체크박스 (범용)
            t = st[5:].strip()
            if t:
                out.append(_issue(t, "status.md"))
        elif in_unresolved and st.startswith("- ") and not st.startswith("- ["):
            t = st[2:].strip()
            if len(t) > 5:  # 너무 짧은 건 노이즈
                out.append(_issue(t, "status.md"))
    return out


def _parse_pending(text: str) -> list[dict]:
    """pending.md 표에서 날짜(재검토 시점) 있는 행을 기한 이슈로 추출."""
    out: list[dict] = []
    for line in text.splitlines():
        st = line.strip()
        if not st.startswith("|") or "---" in st:
            continue
        m = DATE_RE.search(st)
        if not m:
            continue
        cells = [c.strip() for c in st.strip("|").split("|")]
        if not cells or not cells[0] or "안건" in cells[0]:  # 헤더 행 스킵
            continue
        out.append(
            {"kind": "deadline", "title": cells[0][:200], "due": m.group(0), "source": "pending.md"}
        )
    return out


def _issue(title: str, source: str) -> dict:
    return {"kind": "unresolved", "title": title[:200], "source": source}
