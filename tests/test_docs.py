"""플러그인 운영 문서 린트 — 규칙이 이유·대신·출처와 함께 이동하는지 기계로 지킨다.

2026-09-23 사고: kickoff-workspaces/SKILL.md의 "훅은 수정하지 않는다" 한 문장을 "훅을 쓸 수
없다"로 읽고 설계했다. 원 결정(T-006)에는 이유와 대안이 있었으나 파생 문서에는 결론만 옮겨졌다.
전수 조사: 세션에 직접 주입되는 entry.md는 규칙 ~30개 중 이유 0, 접수 진입점 dispatch/SKILL.md는
~25개 중 0 — 가장 자주 읽히는 문서일수록 이유가 없었다. conventions "반복 실패는 지침이 아니라
스크립트·린트로 승격"에 따라 이 테스트가 그 장치다.

원본은 PROTOCOL.md 하나. 항목 문법:
    - [P-nn] **제목** — 규칙 한 문장 (2칸 들여쓴 줄로 이어 쓸 수 있다)
      이유: … 또는 이유(inferred): …     (필수 — 추론이면 지어내지 말고 inferred로 표시)
      대신: …                              (규칙 문장에 금지 패턴이 있으면 필수)
      예외: …                              (선택)
      출처: T-006 §5 (2026-09-22) …        (필수, 인라인 자립형 — 링크·docs/ 경로·URL 금지:
                                            이 파일은 23개 프로젝트의 런타임으로 복사되고
                                            거기엔 docs/tasks/가 없다)
    필드는 4칸 들여쓴 이어쓰기 1줄까지(필드당 최대 2줄) — 퇴적 방지.
    폐기: "## 폐기된 규칙" 절에만  - [P-nn] 폐기 YYYY-MM-DD — 이유. 대체: [P-mm] 또는 없음
    번호는 부여 순서대로, 재사용 금지, live ∪ 묘비가 01..N으로 이어진다(지우면 구멍이 나서 실패).
파생 문서(CITING)는 규칙을 재서술하지 않고 [P-nn]을 인용한다. 금지문인데 인용이 없으면 실패.
예외 표기는 <!-- rule-lint: skip: 이유 --> (같은 줄 또는 바로 윗줄), 전체 예산 8개.
미탐(알고 둔 것): 긍정형 제한("…만 한다")은 안 잡는다 — 이번 사고의 원인 부류(금지문)에 집중한다.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugin/skills"
REGISTRY = SKILLS / "kickoff-workspaces/PROTOCOL.md"
CITING = [
    SKILLS / p
    for p in (
        "dispatch/SKILL.md",
        "dispatch/references/entry.md",
        "dispatch/references/runtime.md",
        "kickoff-workspaces/SKILL.md",
        "kickoff-workspaces/templates/task.md",
        "kickoff-workspaces/templates/review.md",
    )
]
ENTRY = SKILLS / "dispatch/references/entry.md"
TASK_TEMPLATE = SKILLS / "kickoff-workspaces/templates/task.md"
REVIEW_TEMPLATE = SKILLS / "kickoff-workspaces/templates/review.md"

ITEM = re.compile(r"^- \[P-(\d{2})\] \*\*[^*]+\*\* — \S")
TOMB = re.compile(r"^- \[P-(\d{2})\] 폐기 \d{4}-\d{2}-\d{2} — \S")
FIELD = re.compile(r"^  (이유|이유\(inferred\)|대신|예외|출처): \S")
ANY_FIELD = re.compile(r"^  ([^\s:]+): ")
CONT = re.compile(r"^    \S")
RULE_CONT = re.compile(r"^  \S")
CITE = re.compile(r"\[P-(\d{2})\]")
PROHIBIT = re.compile(
    r"않는다|안 된다|금지|말 것|하지 마|없다\.|(?<![\w-])(never|do not|don't|must not|only)\b",
    re.IGNORECASE,
)
SOURCE_OK = re.compile(r"\d{4}-\d{2}-\d{2}|T-\d{3}")
NOT_INLINE = re.compile(r"\]\(|docs/|https?://")
SKIP = re.compile(r"<!-- rule-lint: skip: \S[^>]* -->")
TOMB_SECTION = "## 폐기된 규칙"
SKIP_BUDGET = 8
ENTRY_MAX_LINES = 40


def read(path):
    return path.read_text(encoding="utf-8").splitlines()


def parse_registry():
    """PROTOCOL.md → (live 항목 목록, 묘비 목록, 오류 목록). 오류는 '파일:줄 — 트리거 — 조치'."""
    lines = read(REGISTRY)
    live, tombs, errors = [], [], []
    in_tomb = False
    item = None

    def close():
        if item is not None:
            live.append(item)

    for no, line in enumerate(lines, 1):
        where = f"{REGISTRY.name}:{no}"
        if line.startswith("## "):
            close()
            item = None
            in_tomb = line.strip() == TOMB_SECTION
            continue
        if in_tomb:
            if not line.strip():
                continue
            m = TOMB.match(line)
            if m:
                tombs.append({"id": int(m.group(1)), "line": no, "text": line})
            else:
                errors.append(
                    f"{where} — 폐기 절에 묘비 형식이 아닌 줄 — "
                    "`- [P-nn] 폐기 YYYY-MM-DD — 이유. 대체: [P-mm]|없음`으로 적는다"
                )
            continue
        m = ITEM.match(line)
        if m:
            close()
            item = {"id": int(m.group(1)), "line": no, "rule": line, "fields": {}, "order": []}
            continue
        if line.startswith("- [P-"):
            close()
            item = None
            errors.append(f"{where} — 항목 머리 형식 오류 — `- [P-nn] **제목** — 규칙` (em dash)로 적는다")
            continue
        if item is None:
            continue
        fm = FIELD.match(line)
        if fm:
            name = fm.group(1)
            if name in item["fields"]:
                errors.append(f"{where} — 필드 '{name}' 중복 — 한 항목에 한 번만")
            item["fields"][name] = [line]
            item["order"].append(name)
            continue
        am = ANY_FIELD.match(line)
        if am:
            errors.append(
                f"{where} — 알 수 없는 필드 '{am.group(1)}' — 이유/이유(inferred)/대신/예외/출처만"
            )
            continue
        if CONT.match(line) and item["order"]:
            item["fields"][item["order"][-1]].append(line)
            continue
        if RULE_CONT.match(line) and not item["order"]:
            item["rule"] += " " + line.strip()
            continue
        if line.strip():
            errors.append(
                f"{where} — 항목 안에 해석할 수 없는 줄 — 규칙 이어쓰기는 2칸, 필드 이어쓰기는 4칸 들여쓴다"
            )
    close()
    return live, tombs, errors


def strip_markup(lines):
    """코드 펜스와 YAML 프론트매터 밖의 줄만 (번호, 내용)으로."""
    out, fence, front = [], False, False
    for no, line in enumerate(lines, 1):
        if no == 1 and line.strip() == "---":
            front = True
            continue
        if front:
            if line.strip() == "---":
                front = False
            continue
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        out.append((no, line))
    return out


class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.live, self.tombs, self.errors = parse_registry()

    def test_registry_parses(self):
        self.assertFalse(self.errors, "\n".join(self.errors))
        self.assertTrue(self.live, f"{REGISTRY.name} — 규칙 항목이 하나도 없다 — [P-nn] 문법으로 적는다")

    def test_registry_grammar(self):
        problems = []
        for it in self.live:
            where = f"{REGISTRY.name}:{it['line']} [P-{it['id']:02d}]"
            f = it["fields"]
            if "이유" not in f and "이유(inferred)" not in f:
                problems.append(
                    f"{where} — 이유 없음 — `이유:` 또는 `이유(inferred):`를 붙인다. 지어내지 않는다"
                )
            if "출처" not in f:
                problems.append(f"{where} — 출처 없음 — `출처: T-xxx §n (YYYY-MM-DD)` 형태로 붙인다")
            for name, body in f.items():
                if len(body) > 2:
                    problems.append(
                        f"{where} — 필드 '{name}'이 {len(body)}줄 — 최대 2줄, 길면 결정 기록으로 보낸다"
                    )
        self.assertFalse(problems, "\n".join(problems))

    def test_prohibitions_state_alternative(self):
        problems = [
            f"{REGISTRY.name}:{it['line']} [P-{it['id']:02d}] — 금지문인데 `대신:` 없음 — 무엇을 하면 되는지를 적는다"
            for it in self.live
            if PROHIBIT.search(it["rule"]) and "대신" not in it["fields"]
        ]
        self.assertFalse(problems, "\n".join(problems))

    def test_sources_are_inline(self):
        problems = []
        for it in self.live:
            src = " ".join(it["fields"].get("출처", []))
            where = f"{REGISTRY.name}:{it['line']} [P-{it['id']:02d}]"
            if src and not SOURCE_OK.search(src):
                problems.append(f"{where} — 출처에 날짜(YYYY-MM-DD)나 T-xxx가 없음 — 자립형으로 적는다")
            if NOT_INLINE.search(src):
                problems.append(
                    f"{where} — 출처에 링크/docs/ 경로/URL — 배포 대상엔 docs/가 없다, 인라인으로 적는다"
                )
        self.assertFalse(problems, "\n".join(problems))

    def test_ids_unique_and_contiguous(self):
        ids = [it["id"] for it in self.live] + [t["id"] for t in self.tombs]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        self.assertFalse(dup, f"{REGISTRY.name} — ID 중복 {dup} — 번호는 재사용하지 않는다")
        expected = set(range(1, len(ids) + 1))
        missing = sorted(expected - set(ids))
        extra = sorted(set(ids) - expected)
        self.assertFalse(
            missing or extra,
            f"{REGISTRY.name} — ID가 01..{len(ids):02d}로 이어지지 않음 (빠짐 {missing}, 범위 밖 {extra}) — "
            "삭제 대신 폐기 절에 묘비를 남긴다",
        )

    def test_tombstones_only_in_their_section(self):
        in_tomb = False
        problems = []
        for no, line in enumerate(read(REGISTRY), 1):
            if line.startswith("## "):
                in_tomb = line.strip() == TOMB_SECTION
                continue
            if not in_tomb and line.startswith("- [P-") and " 폐기 " in line:
                problems.append(f"{REGISTRY.name}:{no} — 묘비가 폐기 절 밖에 있음 — `{TOMB_SECTION}` 아래로 옮긴다")
        self.assertFalse(problems, "\n".join(problems))


class CitationTest(unittest.TestCase):
    def setUp(self):
        self.live, self.tombs, _ = parse_registry()
        self.live_ids = {it["id"] for it in self.live}
        self.tomb_ids = {t["id"] for t in self.tombs}

    def test_citations_resolve(self):
        problems = []
        for path in sorted(SKILLS.rglob("*.md")):
            rel = path.relative_to(ROOT)
            for no, line in enumerate(read(path), 1):
                body = re.sub(r"^- \[P-\d{2}\]", "", line)  # 항목·묘비 자신의 머리 ID는 인용이 아니다
                for m in CITE.finditer(body):
                    pid = int(m.group(1))
                    if pid in self.tomb_ids:
                        problems.append(f"{rel}:{no} — 폐기된 [P-{pid:02d}] 인용 — 묘비의 `대체:`를 따라 바꾼다")
                    elif pid not in self.live_ids:
                        problems.append(f"{rel}:{no} — 없는 [P-{pid:02d}] 인용 — PROTOCOL.md에 먼저 등록한다")
        self.assertFalse(problems, "\n".join(problems))

    def test_prohibition_lines_cite_rule(self):
        problems = []
        for path in CITING:
            rel = path.relative_to(ROOT)
            prev = ""
            for no, line in strip_markup(read(path)):
                if (
                    PROHIBIT.search(line)
                    and not CITE.search(line)
                    and not SKIP.search(line)
                    and not SKIP.search(prev)
                ):
                    problems.append(
                        f"{rel}:{no} — 금지문에 [P-nn] 인용 없음 — PROTOCOL.md의 항목을 인용하거나 "
                        "규칙이면 거기 등록한다; 도구 사실이면 `<!-- rule-lint: skip: 이유 -->`"
                    )
                prev = line
        self.assertFalse(problems, "\n".join(problems))

    def test_skip_budget(self):
        skips, bad = [], []
        for path in CITING:
            rel = path.relative_to(ROOT)
            for no, line in enumerate(read(path), 1):
                if "rule-lint: skip" in line:
                    if SKIP.search(line):
                        skips.append(f"{rel}:{no}")
                    else:
                        bad.append(f"{rel}:{no} — skip에 이유 없음 — `<!-- rule-lint: skip: 이유 -->`")
        self.assertFalse(bad, "\n".join(bad))
        self.assertLessEqual(
            len(skips),
            SKIP_BUDGET,
            f"skip {len(skips)}개 > 예산 {SKIP_BUDGET} — 규칙이면 PROTOCOL.md로 올린다:\n" + "\n".join(skips),
        )


class ShapeTest(unittest.TestCase):
    def test_entry_budget(self):
        lines = read(ENTRY)
        self.assertLessEqual(
            len(lines),
            ENTRY_MAX_LINES,
            f"{ENTRY.name} {len(lines)}줄 > {ENTRY_MAX_LINES} — 이유는 PROTOCOL.md에, 여기엔 규칙과 [P-nn]만",
        )
        self.assertIn("Session entry contract", lines[0])

    def test_templates_carry_promotion(self):
        task = TASK_TEMPLATE.read_text(encoding="utf-8")
        review = REVIEW_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn(
            "## 상시 규칙으로 남는 결정",
            task,
            f"{TASK_TEMPLATE.name} — 결정→규칙 승격 절이 없다 — 이유 없는 규칙이 파생 문서로 새는 구멍",
        )
        self.assertIn("승격 규칙", review, f"{REVIEW_TEMPLATE.name} — pl 판정에 승격 규칙 기준이 없다")


if __name__ == "__main__":
    unittest.main()
