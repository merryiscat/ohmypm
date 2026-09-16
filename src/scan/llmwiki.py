"""llmwiki 파서 — 프로젝트 docs/의 status.md·pending.md에서 이슈를 추출.

★ 형식이 프로젝트마다 다르다(odin `## 날짜 미해결 — 제목` vs ohmyPM `## 미해결` 섹션).
   그래서 여러 패턴을 관대하게 훑는다. 못 맞춰도 죽지 않고 최대한 건진다.
"""

import re
from pathlib import Path

# YYYY-MM-DD 날짜 (기한 추출용)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

# 이미 버린 안건 표시 — 이런 행은 판정 에이전트에 넘길 것도 없이 값싸게 선거른다.
# (취소선은 별도로 처리. '취소/철회' 같은 애매한 말은 오작동 우려로 제외 — 나머지는 에이전트가 가림.)
DEAD_MARKERS = ("미채택", "제외", "폐기", "불채택")


def parse_wiki(project_path: str) -> list[dict]:
    """docs/status.md(미해결)·pending.md(기한)를 파싱해 이슈 목록 반환 + 인덱스 미등재 점검."""
    docs = Path(project_path) / "docs"
    out: list[dict] = []

    out += _check_index(docs)

    status = docs / "status.md"
    if status.exists():
        out += _parse_status(status.read_text(encoding="utf-8", errors="replace"))

    pending = docs / "pending.md"
    if pending.exists():
        out += _parse_pending(pending.read_text(encoding="utf-8", errors="replace"))

    return out


def _check_index(docs: Path) -> list[dict]:
    """docs/index.md에 등재 안 된 문서를 찾아 이슈로 낸다 (2026-09-08 사용자 확정).

    위키 규약은 "새 페이지는 index.md에 한 줄 등재"인데 지키는지 확인하는 장치가 없어
    조용히 새는 문서가 쌓였다(09-08 실측: 위키 19개 중 6개에서 8건). 파일 목록과
    index.md 문자열 비교라 **모델 호출이 필요 없다** — 스캔의 결정론 원칙 그대로.

    자동으로 고치지 않고 발견만 한다 — 한 줄 설명은 사람이나 담당이 써야 제 역할을 한다.
    """
    index = docs / "index.md"
    if not index.exists():
        return []      # 위키 없는 프로젝트는 대상 아님(골격 생성은 온보딩이 맡는다)
    text = index.read_text(encoding="utf-8", errors="replace")
    out = []
    for f in sorted(docs.glob("*.md")):
        if f.name == "index.md" or f.name in text:
            continue   # 링크 문법을 안 따져도 파일명이 본문에 있으면 등재로 본다(오탐 억제)
        out.append({"kind": "format", "title": f"위키 인덱스 미등재 — docs/{f.name}",
                    "source": "index.md"})
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


# 마감일 칸에서 날짜 옆에 붙어도 되는 '역할 낱말' — 사람이 표만 봐도 그 날짜가 무슨 날인지 알게 하는 장치.
# 이 낱말을 떼어낸 나머지가 날짜 하나뿐일 때만 기한으로 읽는다(conventions-wiki '2026-09-15에 무엇을 만들지').
ROLE_WORDS = ("재검토", "마감", "까지", "D-")


def _deadline_col(header_cells: list[str]) -> int | None:
    """표 머리글에서 기한 칸 번호를 찾는다 — '마감일' 우선, 없으면 '재검토'가 든 칸, 둘 다 없으면 None."""
    for i, c in enumerate(header_cells):
        if "마감일" in c:
            return i
    for i, c in enumerate(header_cells):
        if "재검토" in c:
            return i
    return None


def _condition_col(header_cells: list[str]) -> int | None:
    """표 머리글에서 '조건' 칸 번호 — 마감일 칸을 나눈 새 형식에서 조건 대기 안건을 읽는다."""
    for i, c in enumerate(header_cells):
        if c.strip() == "조건" or c.startswith("조건"):
            return i
    return None


def _single_date(cell: str) -> str | None:
    """칸 값에서 역할 낱말을 떼어낸 나머지가 **날짜 하나뿐**이면 그 날짜, 아니면 None.

    '2026-09-20', '2026-09-20 마감', '**2026-09-20까지**' → 날짜.
    '조건: 야간 배치가 2026-08-17 로그처럼 또 죽으면' → None (인용 날짜는 언제나 문장 속에 있다).
    """
    s = cell.replace("*", " ")
    for w in ROLE_WORDS:
        s = s.replace(w, " ")
    dates = DATE_RE.findall(s)
    if len(dates) != 1:
        return None
    rest = s.replace(dates[0], " ").strip(" :·—-()[]`")
    return dates[0] if not rest else None


def _parse_pending(text: str) -> list[dict]:
    """pending.md 표에서 기한(마감일) 후보와 조건 대기 안건을 추출.

    2026-09-17 칸 인식으로 전환(설계는 09-14 확정, conventions-wiki '2026-09-15에 무엇을 만들지'):
      ① 표 머리글(구분선 `|---|` 바로 윗줄)에서 기한 칸을 찾는다 — '마감일' 우선, 없으면 '재검토'
      ② 그 칸 값에서 역할 낱말(재검토·마감·까지·D-)을 뗀 나머지가 날짜 하나뿐일 때만 kind="deadline"
      ③ 날짜 말고 다른 글자가 남거나 날짜가 없으면(조건 문장) kind="conditional", due 없음 —
         칸반의 '조건 대기'로 들어가고 기한 목록에는 오르지 않는다
      ④ 기한 칸이 없는 옛 표(다른 프로젝트)는 종전대로 행 전체에서 날짜를 찾아 후보로 올린다 —
         이 경우만 판정 에이전트(cc/judge)가 마감/조건을 가른다(모델 호출)

    그전엔 행 전체에서 날짜를 찾아 등재일·배경 링크 날짜까지 마감으로 둔갑했고(실제 오탐 2건),
    판정 에이전트가 모델 호출로 사후에 갈라내고 있었다 — 원인을 두고 증상만 막는 구조.

    이미 버린 안건(취소선·미채택)은 종전대로 값싸게 선거른다.
    """
    out: list[dict] = []
    lines = text.splitlines()
    col: int | None = None          # 현재 표의 기한 칸 번호(표마다 구분선에서 다시 잡는다)
    ccol: int | None = None         # '조건' 칸 번호(새 형식에만 있다)
    for idx, line in enumerate(lines):
        st = line.strip()
        if not st.startswith("|"):
            continue
        if "---" in st:             # 구분선 — 바로 윗줄이 머리글
            prev = lines[idx - 1].strip() if idx else ""
            hdr = [c.strip() for c in prev.strip("|").split("|")]
            col, ccol = _deadline_col(hdr), _condition_col(hdr)
            continue
        cells = [c.strip() for c in st.strip("|").split("|")]
        if not cells or not cells[0] or "안건" in cells[0]:  # 머리글 행 스킵
            continue
        title = cells[0]
        # 선거름 ①: 안건 칸이 취소선(~~...~~) = 이미 해소/폐기
        if title.startswith("~~") or "~~" in title:
            continue
        # 선거름 ②: 행 어디든 '미채택/제외/폐기…' = 버린 안건
        if any(mk in st for mk in DEAD_MARKERS):
            continue
        if col is None:
            # 옛 표(기한 칸 없음) — 종전 방식: 행 전체 날짜 → 후보, 판정 에이전트가 가린다
            m = DATE_RE.search(st)
            if m:
                out.append({"kind": "deadline", "title": title[:200], "due": m.group(0),
                            "source": "pending.md"})
            continue
        cell = cells[col] if col < len(cells) else ""
        cond = cells[ccol] if ccol is not None and ccol < len(cells) else ""
        due = _single_date(cell)
        if due:
            out.append({"kind": "deadline", "title": title[:200], "due": due, "source": "pending.md"})
        elif cell or cond:
            # 기한 칸에 날짜 아닌 글자가 남았거나(옛 형식의 조건 문장), 조건 칸이 차 있으면 조건 대기
            out.append({"kind": "conditional", "title": title[:200], "due": None,
                        "source": "pending.md", "status": "deferred"})
        # 둘 다 비어 있으면 기한도 조건도 없는 안건 — 후보로 올리지 않는다
    return out


def _issue(title: str, source: str) -> dict:
    return {"kind": "unresolved", "title": title[:200], "source": source}
