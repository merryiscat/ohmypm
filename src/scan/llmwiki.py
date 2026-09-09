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


def _parse_pending(text: str) -> list[dict]:
    """pending.md 표에서 날짜(재검토 시점) 있는 행을 기한 후보로 추출.

    ★ 여기서 뽑는 건 '후보'다 — 표 행의 날짜가 마감일인지 보류일인지, 조건인지는
       판정 에이전트(cc/judge)가 소스를 열어 가린다. 다만 이미 버린 안건(취소선·미채택)은
       판정할 것도 없으니 값싸게 선거른다(에이전트 호출·화면 노이즈 절감).

    ★ 알려진 오탐 원인(2026-09-10 게시판 kickoff_pack 왕복) — 아래 DATE_RE는 **행 전체**에서
       날짜를 찾는다. 그래서 '재검토 시점' 칸이 아니라 보류 이유 칸의 등재일이나 배경 링크의
       로그 날짜(예: `[log 09-08]`가 아니라 `2026-08-17` 같은 표기)까지 마감일로 둔갑한다.
       실제로 두 프로젝트에서 '기한 초과'가 잘못 떴다(한 곳은 등재일, 다른 곳은 조건 대기 3건).
       고칠 방향은 '칸을 알아보고 재검토 시점 칸의 날짜만 쓰기'다 — 표 머리글에 '재검토'가
       있으면 그 칸 번호를 기억했다가 그 칸만 보고, 없으면 지금처럼 행 전체를 본다.
       지금 안 고치는 이유: 이 함수의 결과가 25개 프로젝트 기한 목록을 그대로 바꾸므로
       야간 배치가 걸린 날 즉흥으로 손대지 않는다 → docs/pending.md에 안건으로 등재.
    """
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
        title = cells[0]
        # 선거름 ①: 안건 칸이 취소선(~~...~~) = 이미 해소/폐기
        if title.startswith("~~") or "~~" in title:
            continue
        # 선거름 ②: 행 어디든 '미채택/제외/폐기…' = 버린 안건
        if any(mk in st for mk in DEAD_MARKERS):
            continue
        out.append(
            {"kind": "deadline", "title": title[:200], "due": m.group(0), "source": "pending.md"}
        )
    return out


def _issue(title: str, source: str) -> dict:
    return {"kind": "unresolved", "title": title[:200], "source": source}
