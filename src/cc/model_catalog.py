"""모델 동향 전문가(domain=models) — Claude·Codex 공식 문서를 코드가 직접 수집해
`docs/experts/models.md` 위키를 유지한다(T-007 r2).

전문가 에이전트(`src/cc/expert.py`)의 일반 도메인은 **에이전트가** WebSearch/WebFetch로
조사하지만, 이 모듈은 4개 고정 공식 출처를 **코드가 httpx로 직접** 받는다(공식 문서 확인
검증, 2026-09-28 PL 기록 — 기본 urllib은 Claude 문서에서 403). LLM은 마지막 반영본과
달라진 절만 받아 구조화 JSON으로 요약한다(텍스트만 반환 — 파일 접근·웹 도구 없음). 코드가
JSON 구조·필수 필드·출처 링크를 검증한 뒤 임시 파일 + 원자적 교체로 위키를 쓴다 — 실패하면
마지막 정상 위키가 그대로 남는다.

수집 비교용 원문·상태는 git 미추적 로컬 `data/model_updates/`에만 남고,
공개 위키(docs/experts/)에는 요약·출처 링크만 나간다.
"""

import contextlib
import hashlib
import json
import os
import re
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

import httpx
from loguru import logger

from src.cc.client import run_headless
from src.cc.permissions import NEVER_ALLOW
from src.cc.prompts import model_catalog_update

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "model_updates"          # git 미추적(.gitignore의 data/) — 로컬 전용
STATE_PATH = DATA_DIR / "state.json"
LOCK_PATH = DATA_DIR / ".lock"
LOCK_STALE_SECONDS = 600                            # 죽은 프로세스가 쥔 잠금으로 보고 회수

MODELS_DOMAIN = "models"                            # 전문가 명부 도메인 키(docs/experts/models.md)
USER_AGENT = "ohmyPM-model-catalog/1.0 (+local; contact via project owner)"
CHUNK_LIMIT = 24000                                 # LLM 1회 입력 최대 글자수(벤더별 분할)
MODEL_CATALOG_TIMEOUT = 300
FIRST_RUN_WINDOW_DAYS = 90
RECENT_CHANGES_KEEP = 20

# 공식 출처 4개 — 2026-09-28 PL 검증: httpx + 명시 User-Agent + follow_redirects로 Claude 두 문서와
# Codex HTML changelog가 200, Codex models.md는 markdown. changelog는 `.md`가 아니라 HTML 본문 추출.
SOURCES: dict[str, dict] = {
    "claude-models": {
        "url": "https://platform.claude.com/docs/en/models/overview.md",
        "format": "markdown",
        "vendor": "claude",
    },
    "claude-releases": {
        "url": "https://platform.claude.com/docs/en/release-notes/overview.md",
        "format": "markdown",
        "vendor": "claude",
    },
    "codex-models": {
        "url": "https://learn.chatgpt.com/docs/models.md",
        "format": "markdown",
        "vendor": "codex",
    },
    "codex-changelog": {
        "url": "https://learn.chatgpt.com/docs/changelog",
        "format": "html",
        "vendor": "codex",
    },
}

_HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
REQUIRED_FIELDS = {"name", "confirmed_date", "diff", "impact", "impact_type", "source_url"}
VALID_IMPACT_TYPES = {"asserted", "inferred", "none"}

_NEUTRAL_DIR: str | None = None


def _neutral_cwd() -> str:
    """LLM 호출용 중립 cwd — 대상 프로젝트 CLAUDE.md/훅이 안 걸리게(expert.py와 같은 패턴)."""
    global _NEUTRAL_DIR
    if _NEUTRAL_DIR is None or not Path(_NEUTRAL_DIR).exists():
        _NEUTRAL_DIR = tempfile.mkdtemp(prefix="ohmypm_modelcat_")
    return _NEUTRAL_DIR


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today() -> str:
    return date.today().isoformat()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── 잠금·원자적 쓰기 — CLI/API/collect_all이 같은 로컬 잠금으로 직렬화(동시 실행 안전) ──────
@contextlib.contextmanager
def _locked(timeout: float = 60.0):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                age = time.time() - LOCK_PATH.stat().st_mtime
            except FileNotFoundError:
                continue  # 그 사이 다른 쪽이 풀었다 — 재시도
            if age > LOCK_STALE_SECONDS:
                with contextlib.suppress(FileNotFoundError):
                    LOCK_PATH.unlink()
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError("model_catalog: 잠금 대기 초과")
            time.sleep(0.2)
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            LOCK_PATH.unlink()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=path.suffix or ".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


# ── 상태(state.json) — 소스별 확인/반영 시각·해시, 최근 변화, 월별 요약 ─────────────────
def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}
    data.setdefault("sources", {})
    data.setdefault("changes", [])
    data.setdefault("applied_batches", [])
    data.setdefault("monthly_summary", {})
    data.setdefault("generation", 0)
    return data


def _save_state(state: dict) -> None:
    state["generation"] = state.get("generation", 0) + 1
    _atomic_write(STATE_PATH, json.dumps(state, ensure_ascii=False, indent=2))


def _applied_path(key: str) -> Path:
    return DATA_DIR / f"{key}.applied.txt"


# ── 수집(httpx) — 벤더 markdown은 그대로, HTML은 본문만 추출(script/style/nav 제외) ──────
def _fetch(url: str) -> dict:
    """{"ok", "status", "final_url", "body", "error"}. 실패는 ok=False + error 문자열."""
    try:
        with httpx.Client(follow_redirects=True, timeout=30.0,
                           headers={"User-Agent": USER_AGENT}) as client:
            r = client.get(url)
        if r.status_code != 200:
            return {"ok": False, "status": r.status_code, "final_url": str(r.url),
                     "body": "", "error": f"http {r.status_code}"}
        return {"ok": True, "status": 200, "final_url": str(r.url), "body": r.text, "error": None}
    except httpx.HTTPError as e:
        return {"ok": False, "status": None, "final_url": url, "body": "", "error": str(e)}


class _MainExtractor(HTMLParser):
    """<main>/<article> 본문 텍스트 + 링크만 추출. script/style/nav는 제외."""

    SKIP_TAGS = {"script", "style", "nav"}
    CONTAINER_TAGS = {"main", "article"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.container_depth = 0
        self.found_container = False
        self.chunks: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.title: str | None = None
        self._title_capture = False
        self._link_href: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._title_capture = True
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if tag in self.CONTAINER_TAGS:
            self.container_depth += 1
            self.found_container = True
        if self.container_depth > 0 and tag == "a":
            self._link_href = dict(attrs).get("href")
            self._link_text = []

    def handle_endtag(self, tag):
        if tag == "title":
            self._title_capture = False
        if tag in self.SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1
            return
        if tag in self.CONTAINER_TAGS and self.container_depth > 0:
            self.container_depth -= 1
        if tag == "a" and self._link_href is not None:
            text = "".join(self._link_text).strip()
            if text:
                self.links.append((text, self._link_href))
            self._link_href = None
            self._link_text = []

    def handle_data(self, data):
        if self._title_capture and self.title is None:
            self.title = data.strip()
        if self.skip_depth > 0:
            return
        if self.container_depth > 0:
            if self._link_href is not None:
                self._link_text.append(data)
            text = data.strip()
            if text:
                self.chunks.append(text)


def _extract_html_body(html_text: str) -> dict:
    """{"ok", "text", "title", "links"}. main/article 없거나 본문이 비면 ok=False(수집 실패)."""
    parser = _MainExtractor()
    try:
        parser.feed(html_text)
    except Exception:
        return {"ok": False, "text": "", "title": None, "links": []}
    if not parser.found_container or not parser.chunks:
        return {"ok": False, "text": "", "title": parser.title, "links": []}
    return {"ok": True, "text": "\n".join(parser.chunks), "title": parser.title,
             "links": parser.links}


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    out: list[str] = []
    blank = 0
    for line in text.split("\n"):
        line = line.rstrip()
        if line == "":
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        out.append(line)
    return "\n".join(out).strip()


# ── 절 분할·diff — 날짜/절 경계에서 나눠 LLM 입력을 24,000자 이하로 쪼갠다 ────────────────
def _split_sections(text: str) -> list[tuple[str, str]]:
    text = text.strip()
    if not text:
        return []
    matches = list(_HEADER_RE.finditer(text))
    if matches:
        sections = []
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections.append((m.group(2).strip(), text[start:end].strip()))
        return sections
    # 헤더가 없는 본문(예: HTML에서 추출한 평문) — 빈 줄 경계로 문단 단위 분할
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    return [(b.splitlines()[0][:80], b) for b in blocks]


def _changed_sections(applied_text: str, fetched_text: str) -> list[tuple[str, str]]:
    """이전 반영본에 없던(해시로 식별) 절만 — 재배치만 된 절은 변경으로 안 친다."""
    applied_hashes = {_hash(body) for _, body in _split_sections(applied_text)}
    return [(title, body) for title, body in _split_sections(fetched_text)
            if _hash(body) not in applied_hashes]


def _filter_recent(sections: list[tuple[str, str]], cutoff: date) -> list[tuple[str, str]]:
    """첫 수집 기준선 — 날짜 찍힌 절 중 90일보다 오래된 과거 이력은 신규 출시로 취급 안 함."""
    out = []
    for title, body in sections:
        m = _DATE_RE.search(title) or _DATE_RE.search(body[:200])
        if m:
            try:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                d = None
            if d and d < cutoff:
                continue
        out.append((title, body))
    return out


def _chunk_sections(sections: list[tuple[str, str]]) -> list[str]:
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for _title, body in sections:
        text = body
        if len(text) > CHUNK_LIMIT:
            text = text[: CHUNK_LIMIT - 20] + "\n…(길이 제한으로 생략)"
        add_len = len(text) + 2
        if cur and cur_len + add_len > CHUNK_LIMIT:
            chunks.append("\n\n".join(cur))
            cur, cur_len = [], 0
        cur.append(text)
        cur_len += add_len
    if cur:
        chunks.append("\n\n".join(cur))
    return chunks


def _related_index() -> str:
    """실제 존재하는 harness/llm-apps 위키 제목만 LLM에 후보로 준다(지어낸 링크 방지)."""
    from src.cc.expert import wiki_path

    lines = []
    for domain in ("harness", "llm-apps"):
        p = wiki_path(domain)
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        for h in re.findall(r"^#{1,6}\s+(.*)$", text, re.MULTILINE):
            lines.append(f"{domain}: {h.strip()}")
    return "\n".join(lines)


# ── LLM 응답 검증 — 구조/필수 필드/출처 링크. 하나라도 어긋나면 배치 전체를 거부(기존 위키 보존) ──
def _parse_llm_changes(raw: str | None) -> list[dict] | None:
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, list):
        return None
    out = []
    for item in data:
        if not isinstance(item, dict) or not REQUIRED_FIELDS.issubset(item.keys()):
            return None
        name = str(item.get("name") or "").strip()
        diff = str(item.get("diff") or "").strip()
        source_url = str(item.get("source_url") or "")
        impact_type = item.get("impact_type")
        if not name or not diff or not source_url.startswith("https://"):
            return None
        if impact_type not in VALID_IMPACT_TYPES:
            return None
        related = item.get("related") or []
        if not isinstance(related, list):
            return None
        out.append({
            "name": name,
            "announced_date": item.get("announced_date") or None,
            "confirmed_date": str(item.get("confirmed_date") or _today()),
            "diff": diff,
            "impact": str(item.get("impact") or "").strip(),
            "impact_type": impact_type,
            "source_url": source_url,
            "related": [str(r) for r in related],
        })
    return out


# ── 병합·정리 — 배치 id로 중복 반영 방지(중단 뒤 복구 안전), 최근 20건 유지 + 월별 요약 ──────
def _apply_changes(state: dict, source_key: str, changes: list[dict], applied_hash: str) -> None:
    batch_id = _hash(f"{source_key}:{applied_hash}")
    if batch_id in state["applied_batches"]:
        return  # 이미 반영된 배치 — 재실행/복구에서 중복 삽입 방지
    state["applied_batches"].append(batch_id)
    state["applied_batches"] = state["applied_batches"][-200:]
    now = _now_iso()
    existing_ids = {c["id"] for c in state["changes"]}
    for ch in changes:
        entry = dict(ch)
        entry["id"] = _hash(f"{source_key}:{ch['name']}:{ch['diff']}")
        if entry["id"] in existing_ids:
            continue
        entry["source"] = source_key
        entry["batch"] = batch_id
        entry["applied_at"] = now
        state["changes"].insert(0, entry)
        existing_ids.add(entry["id"])
    _rollup(state)


def _rollup(state: dict, keep: int = RECENT_CHANGES_KEEP) -> None:
    changes = state["changes"]
    if len(changes) <= keep:
        return
    overflow, state["changes"] = changes[keep:], changes[:keep]
    monthly = state.setdefault("monthly_summary", {})
    for c in overflow:
        month = (c.get("confirmed_date") or "")[:7] or "미확인"
        confirmed = c.get("confirmed_date", "?")
        line = f"- {c['name']} ({confirmed}) — {c['diff'][:120]} [출처]({c['source_url']})"
        bucket = monthly.setdefault(month, [])
        if line not in bucket:
            bucket.append(line)


# ── 위키 렌더 — docs/experts/models.md 전체를 state에서 재생성해 원자적으로 교체 ──────────
def _render_wiki(state: dict) -> str:
    lines = ["# 모델 동향 전문가", "", f"<!-- generation: {state.get('generation', 0)} -->", "",
              "## 최근 변화", ""]
    if not state["changes"]:
        lines.append("(아직 수집된 변경 없음)")
    impact_tags = {"asserted": "[asserted]", "inferred": "[inferred]", "none": "[해당 없음]"}
    for c in state["changes"]:
        confirmed = c.get("confirmed_date", "?")
        lines.append(f"### {c['name']} ({confirmed})")
        lines.append(f"- 발표일: {c.get('announced_date') or '미확인'} · 확인일: {confirmed}")
        lines.append(f"- 달라진 점: {c['diff']}")
        lines.append(f"- 적용 영향 {impact_tags[c['impact_type']]}: {c['impact']}")
        lines.append(f"- 출처: [{c['source_url']}]({c['source_url']})")
        if c.get("related"):
            lines.append("- 관련 지식: " + ", ".join(c["related"]))
        lines.append("")

    if state.get("monthly_summary"):
        lines.append("## 지난 변화(월별 요약)")
        for month in sorted(state["monthly_summary"], reverse=True):
            lines.append(f"### {month}")
            lines.extend(state["monthly_summary"][month])
            lines.append("")

    lines.append("## 하네스에서 검토할 점")
    reviewable = [c for c in state["changes"]
                  if c["impact_type"] in ("asserted", "inferred") and c["impact"]]
    if reviewable:
        for c in reviewable[:10]:
            lines.append(f"- {c['name']}: {c['impact']}")
    else:
        lines.append("(공식 문서에 하네스 변경 설명이 있는 항목 없음)")
    lines.append("")

    lines.append("## 관련 지식")
    related_all = sorted({r for c in state["changes"] for r in c.get("related", [])})
    if related_all:
        lines.extend(f"- {r}" for r in related_all)
    else:
        lines.append("(연결된 기존 위키 항목 없음)")
    lines.append("")

    lines.append("## 출처·확인 상태")
    for key, src in state["sources"].items():
        lines.append(f"- **{key}** — [{src.get('url')}]({src.get('url')})")
        checked = src.get("last_checked_at") or "없음"
        status = src.get("last_status") or "미수집"
        lines.append(f"  - 최종 확인: {checked} ({status})")
        lines.append(f"  - 최종 반영: {src.get('applied_at') or '없음'}")
        if src.get("last_error"):
            lines.append(f"  - 마지막 오류: {src['last_error']}")
    return "\n".join(lines) + "\n"


def _write_wiki_from_state(state: dict) -> None:
    from src.cc.expert import wiki_path

    _atomic_write(wiki_path(MODELS_DOMAIN), _render_wiki(state))


def trend_brief(limit: int = 5) -> str:
    """다른 전문가(harness·llm-apps)의 수집/자문 입력에 주입할 요약 + 확인 시각.

    위키/상태가 아직 없으면 빈 문자열(기존 기능 그대로 동작 — C7).
    """
    state = _load_state()
    checked = [s.get("last_checked_at") for s in state["sources"].values()
               if s.get("last_checked_at")]
    if not checked:
        return ""
    lines = [f"확인 시각: {max(checked)}"]
    for c in state.get("changes", [])[:limit]:
        lines.append(f"- {c['name']} ({c.get('confirmed_date', '?')}): {c['diff'][:80]}")
    return "\n".join(lines)


# ── 수집 진입점 ──────────────────────────────────────────────────────────────────────
def collect_source(key: str, fetch_only: bool = False) -> dict:
    """소스 하나를 받아 diff 있으면 LLM으로 반영. 실패해도 다른 소스 수집을 막지 않는다."""
    src = SOURCES.get(key)
    if not src:
        return {"ok": False, "error": "unknown source"}
    with _locked():
        state = _load_state()
        srec = state["sources"].setdefault(key, {"url": src["url"]})
        now = _now_iso()
        srec["requested_url"] = src["url"]
        srec["last_checked_at"] = now

        fetched = _fetch(src["url"])
        if not fetched["ok"]:
            srec["last_status"], srec["last_error"] = "error", fetched["error"]
            _save_state(state)
            _write_wiki_from_state(state)
            logger.warning(f"[모델동향] {key} 수집 실패: {fetched['error']}")
            return {"ok": False, "error": fetched["error"]}

        srec["final_url"] = fetched["final_url"]

        if src["format"] == "html":
            extracted = _extract_html_body(fetched["body"])
            if not extracted["ok"]:
                srec["last_status"] = "error"
                srec["last_error"] = "본문 추출 실패(main/article 없음)"
                _save_state(state)
                _write_wiki_from_state(state)
                logger.warning(f"[모델동향] {key} 본문 추출 실패")
                return {"ok": False, "error": "extract_failed"}
            body = extracted["text"]
        else:
            body = fetched["body"]

        body = _normalize(body)
        if not body:
            srec["last_status"], srec["last_error"] = "error", "빈 본문"
            _save_state(state)
            _write_wiki_from_state(state)
            return {"ok": False, "error": "empty_body"}

        srec["last_status"], srec["last_error"] = "ok", None
        fetched_hash = _hash(body)
        srec["fetched_hash"], srec["fetched_at"] = fetched_hash, now

        applied_path = _applied_path(key)
        applied_body = applied_path.read_text(encoding="utf-8") if applied_path.exists() else ""
        applied_hash = srec.get("applied_hash")

        if fetched_hash == applied_hash:
            _save_state(state)
            _write_wiki_from_state(state)
            return {"ok": True, "changed": False, "llm_called": False}

        if fetch_only:
            _save_state(state)
            _write_wiki_from_state(state)
            return {"ok": True, "changed": True, "llm_called": False, "pending": True}

        first_run = not applied_path.exists()
        if first_run:
            window_note = ("이 소스의 첫 수집이다 — 최근 90일 안의 절만 새 출시로 다루고, "
                            "그보다 오래된 과거 이력이나 날짜 없는 현재 소개는 각 항목을 "
                            "'현재 공개된 상태'로만 담백하게 정리하라(새 출시로 과장 금지).")
            cutoff = date.today() - timedelta(days=FIRST_RUN_WINDOW_DAYS)
            sections = _filter_recent(_split_sections(body), cutoff)
        else:
            window_note = "이전에 반영한 버전과 비교했을 때 새로 생기거나 바뀐 절이다."
            sections = _changed_sections(applied_body, body)

        chunks = _chunk_sections(sections) if sections else []
        related_index = _related_index()
        all_changes: list[dict] = []
        llm_calls = 0
        failed = False
        for chunk in chunks:
            llm_calls += 1
            raw = run_headless(
                prompt=model_catalog_update(src["vendor"], key, srec["final_url"], window_note,
                                             related_index, chunk),
                cwd=_neutral_cwd(), allowed_tools=[], disallowed_tools=NEVER_ALLOW,
                timeout=MODEL_CATALOG_TIMEOUT,
            )
            parsed = _parse_llm_changes(raw)
            if parsed is None:
                failed = True
                break
            all_changes.extend(parsed)

        if failed:
            srec["last_status"], srec["last_error"] = "llm_failed", "LLM 응답 검증 실패"
            _save_state(state)
            _write_wiki_from_state(state)
            logger.warning(f"[모델동향] {key} LLM 반영 실패 — 기존 위키 보존, 다음 실행에서 재시도")
            return {"ok": False, "error": "llm_failed", "changed": True}

        _apply_changes(state, key, all_changes, fetched_hash)
        srec["applied_hash"], srec["applied_at"] = fetched_hash, now
        _atomic_write(applied_path, body)
        _save_state(state)
        _write_wiki_from_state(state)
        logger.info(f"[모델동향] {key} 반영 — 변경 {len(all_changes)}건, LLM 호출 {llm_calls}회")
        return {"ok": True, "changed": True, "llm_called": llm_calls > 0,
                "changes": len(all_changes)}


def collect_all_sources(fetch_only: bool = False) -> dict:
    """4개 공식 출처 순차 수집. 한 소스 실패가 나머지를 막지 않는다."""
    results = {}
    for key in SOURCES:
        try:
            results[key] = collect_source(key, fetch_only=fetch_only)
        except Exception as e:  # 한 소스 예외가 배치를 안 멈춘다
            logger.warning(f"[모델동향] {key} 처리 중 예외: {e}")
            results[key] = {"ok": False, "error": str(e)}
    ok = all(r.get("ok") for r in results.values())
    return {"ok": ok, "sources": results}
