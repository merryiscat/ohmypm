"""모델 동향 전문가 — 벤더(Claude·Codex)별로 공식 문서를 코드가 직접 수집해
`docs/experts/models-<vendor>.md` 위키를 유지한다(T-007 r2 → R-010 벤더 분리·모델별 상세).

구조(2026-09-28 사용자 결정):
- 탭(도메인)은 벤더별 하나: `models-claude`, `models-codex`. 각 벤더는 자기 출처만 수집하고
  자기 상태(`data/model_updates/<vendor>/`)·자기 위키를 갖는다.
- 위키는 **모델별 절**로 정리한다. 절마다 개요·스펙·잘 쓰는 법·하네스 조정·주의·변화 이력.
  라인업 전체에 걸친 정책은 '라인업 공통' 절.
- 모델과 무관한 플랫폼·API·SDK·앱 기능 변경은 수집하지 않는다(프롬프트 규칙 + 코드 검증).

흐름: 코드가 httpx로 원문 수집 → 정규화 본문 sha256으로 fetched/applied 분리 → 이전 반영본과
절 단위(해시) 비교 → 바뀐 절만 24,000자 청크로 LLM(claude -p, 도구 없음)에 → 변경 항목 JSON 검증 →
바뀐 모델마다 프로필 LLM 1회(원문 발췌 + 누적 변경 기록 → 상세 프로필 JSON) → 코드가 위키를
원자적으로 재생성. 어느 단계든 실패하면 마지막 정상 위키가 남는다.
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

from src.cc.client import run_headless_ex
from src.cc.permissions import NEVER_ALLOW
from src.cc.prompts import model_catalog_update, model_profile
from src.config.settings import settings

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "model_updates"          # git 미추적(.gitignore의 data/) — 로컬 전용
LOCK_NAME = ".lock"
LOCK_STALE_SECONDS = 600                            # 죽은 프로세스가 쥔 잠금으로 보고 회수

USER_AGENT = "ohmyPM-model-catalog/1.1 (+local; contact via project owner)"
CHUNK_LIMIT = 24000                                 # LLM 1회 입력 최대 글자수(벤더별 분할)
MODEL_CATALOG_TIMEOUT = 300
FIRST_RUN_WINDOW_DAYS = 90
RECENT_PER_MODEL = 12                               # 모델별 변화 이력 보존 수(초과분은 한 줄 요약)
OVERVIEW_EXCERPT_LIMIT = 6000                       # 프로필 입력에 넣는 원문 발췌 상한
COMMON_MODEL = "라인업 공통"

# ── 벤더(탭) — 각 벤더는 자기 출처·상태·위키를 갖는다. 새 벤더는 여기 한 항목 + SOURCES 추가 ──
VENDORS: dict[str, dict] = {
    "claude": {
        "domain": "models-claude",
        "name": "Claude 모델 동향",
        "topic": "Anthropic Claude 모델 라인업 — 공식 모델 문서·릴리스 노트에서 모델별로 "
                 "무엇이 바뀌었고, 어떻게 써야 잘 쓰며, 하네스(프롬프트·추론 설정·컨텍스트·도구)를 "
                 "어떻게 바꿔야 하는지",
        "sources": ["claude-models", "claude-releases"],
        "overview_source": "claude-models",
    },
    "codex": {
        "domain": "models-codex",
        "name": "Codex 모델 동향",
        "topic": "OpenAI Codex 모델(GPT-6 Sol·Luna·Astra 등) — 공식 모델 문서·changelog에서 "
                 "모델별로 무엇이 바뀌었고, 어떻게 써야 잘 쓰며, 하네스(config.toml·추론 노력·"
                 "프롬프트)를 어떻게 바꿔야 하는지",
        "sources": ["codex-models", "codex-changelog"],
        "overview_source": "codex-models",
    },
}

# 공식 출처 — 2026-09-28 검증: httpx + 명시 User-Agent + follow_redirects로 전부 200.
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

MODEL_DOMAINS: dict[str, str] = {v["domain"]: k for k, v in VENDORS.items()}   # domain → vendor


def tracked_models(vendor: str) -> list[str]:
    """이 벤더에서 위키에 담는 모델(.env MODEL_TRACK_<VENDOR>, 공식 표기 그대로). 2026-09-28 사용자:
    "실제 사용할 모델만 — 옛날 모델 필요 없다". 목록 밖 모델의 변경은 추적 모델에 영향을 줄 때만
    그 추적 모델 항목으로 들어온다(프롬프트 규칙) — 그 외는 코드가 버린다."""
    raw = {"claude": settings.model_track_claude,
           "codex": settings.model_track_codex}.get(vendor, "")
    return [m.strip() for m in raw.split(",") if m.strip()]


def _is_tracked(vendor: str, model: str) -> bool:
    return model == COMMON_MODEL or model in tracked_models(vendor)

_HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
_ISO_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}
_MONTHS.update({k[:3]: v for k, v in list(_MONTHS.items())})
_TEXT_DATE_RE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})\b",
    re.IGNORECASE)
REQUIRED_FIELDS = {"name", "model", "diff", "impact_type", "source_url"}
VALID_IMPACT_TYPES = {"asserted", "inferred", "none"}
PROFILE_SPEC_KEYS = ("api_id", "pricing", "context", "reasoning", "cutoff", "availability",
                     "retirement")
PROFILE_SPEC_LABELS = {
    "api_id": "API ID·별칭", "pricing": "가격", "context": "컨텍스트·출력",
    "reasoning": "추론 설정",
    "cutoff": "지식 컷오프", "availability": "제공 범위", "retirement": "은퇴·대체",
}

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


def vendor_of_source(key: str) -> str:
    return SOURCES[key]["vendor"]


def vendor_dir(vendor: str) -> Path:
    return DATA_DIR / vendor


def state_path(vendor: str) -> Path:
    return vendor_dir(vendor) / "state.json"


def _applied_path(key: str) -> Path:
    return vendor_dir(vendor_of_source(key)) / f"{key}.applied.txt"


# ── 잠금·원자적 쓰기 — CLI/API/collect_all이 같은 로컬 잠금으로 직렬화(동시 실행 안전) ──────
@contextlib.contextmanager
def _locked(timeout: float = 60.0):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lock = DATA_DIR / LOCK_NAME
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except FileNotFoundError:
                continue  # 그 사이 다른 쪽이 풀었다 — 재시도
            if age > LOCK_STALE_SECONDS:
                with contextlib.suppress(FileNotFoundError):
                    lock.unlink()
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError("model_catalog: 잠금 대기 초과")
            time.sleep(0.2)
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            lock.unlink()


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


# ── 벤더 상태(state.json) — 소스별 확인/반영, 변경 기록(모델별), 프로필(모델별) ──────────────
def _load_state(vendor: str) -> dict:
    p = state_path(vendor)
    data = {}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    data.setdefault("vendor", vendor)
    data.setdefault("sources", {})
    data.setdefault("changes", [])
    data.setdefault("applied_batches", [])
    data.setdefault("history", {})        # model → [한 줄 요약] (RECENT_PER_MODEL 초과분)
    data.setdefault("profiles", {})       # model → 프로필(JSON) + updated_at + entry_count
    data.setdefault("generation", 0)
    return data


def _save_state(state: dict) -> None:
    state["generation"] = state.get("generation", 0) + 1
    _atomic_write(state_path(state["vendor"]), json.dumps(state, ensure_ascii=False, indent=2))


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


def _parse_date(text: str) -> date | None:
    """'2026-09-24'와 'September 24, 2026' 둘 다 읽는다(릴리스 노트는 영문 월 이름을 쓴다)."""
    m = _ISO_DATE_RE.search(text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = _TEXT_DATE_RE.search(text)
    if m:
        month = _MONTHS.get(m.group(1).lower()[:3])
        try:
            return date(int(m.group(3)), month, int(m.group(2))) if month else None
        except ValueError:
            return None
    return None


def _filter_recent(sections: list[tuple[str, str]], cutoff: date) -> list[tuple[str, str]]:
    """첫 수집 기준선 — 날짜 찍힌 절 중 cutoff보다 오래된 과거 이력은 신규 출시로 취급 안 함.
    직전 절의 날짜가 이어지는 하위 절(날짜 없는 ###)은 그 날짜를 물려받는다."""
    out = []
    current: date | None = None
    for title, body in sections:
        d = _parse_date(title) or _parse_date(body[:200])
        if d:
            current = d
        if current and current < cutoff:
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


# ── LLM 응답 검증 — 구조/필수 필드/출처 링크/모델 이름. 하나라도 어긋나면 배치 전체를 거부 ──
def _as_str_list(value) -> list[str] | None:
    if value is None:
        return []
    if not isinstance(value, list):
        return None
    return [str(v).strip() for v in value if str(v).strip()]


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
        model = str(item.get("model") or "").strip()
        diff = str(item.get("diff") or "").strip()
        source_url = str(item.get("source_url") or "")
        impact_type = item.get("impact_type")
        if not name or not model or not diff or not source_url.startswith("https://"):
            return None
        if impact_type not in VALID_IMPACT_TYPES:
            return None
        tips = _as_str_list(item.get("usage_tips"))
        harness = _as_str_list(item.get("harness_changes"))
        if tips is None or harness is None:
            return None
        out.append({
            "name": name,
            "model": model,
            "announced_date": item.get("announced_date") or None,
            "confirmed_date": str(item.get("confirmed_date") or _today()),
            "diff": diff,
            "usage_tips": tips,
            "harness_changes": harness,
            "impact_type": impact_type,
            "source_url": source_url,
        })
    return out


def _parse_profile(raw: str | None) -> dict | None:
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict) or not str(data.get("overview") or "").strip():
        return None
    spec_in = data.get("spec") or {}
    if not isinstance(spec_in, dict):
        return None
    spec = {k: (str(spec_in[k]).strip() if spec_in.get(k) else None) for k in PROFILE_SPEC_KEYS}
    lists = {}
    for key in ("usage_tips", "harness_changes", "suggestions", "gotchas", "sources"):
        val = _as_str_list(data.get(key))
        if val is None:
            return None
        lists[key] = val
    lists["sources"] = [s for s in lists["sources"] if s.startswith("https://")]
    return {"overview": str(data["overview"]).strip(), "spec": spec, **lists}


# ── 병합·정리 — 배치 id로 중복 반영 방지, 모델별 최근 N건 유지 + 초과분은 한 줄 이력 ──────
def _apply_changes(state: dict, source_key: str, changes: list[dict],
                   applied_hash: str) -> set[str]:
    """반영하고, 새 항목이 들어간 모델 이름 집합을 돌려준다(프로필 재생성 대상)."""
    batch_id = _hash(f"{source_key}:{applied_hash}")
    if batch_id in state["applied_batches"]:
        return set()  # 이미 반영된 배치 — 재실행/복구에서 중복 삽입 방지
    state["applied_batches"].append(batch_id)
    state["applied_batches"] = state["applied_batches"][-200:]
    now = _now_iso()
    existing_ids = {c["id"] for c in state["changes"]}
    touched: set[str] = set()
    for ch in changes:
        entry = dict(ch)
        entry["id"] = _hash(f"{source_key}:{ch['model']}:{ch['name']}:{ch['diff']}")
        if entry["id"] in existing_ids:
            continue
        entry["source"] = source_key
        entry["batch"] = batch_id
        entry["applied_at"] = now
        state["changes"].insert(0, entry)
        existing_ids.add(entry["id"])
        touched.add(entry["model"])
    _rollup(state)
    return touched


def _rollup(state: dict, keep: int = RECENT_PER_MODEL) -> None:
    """모델별로 최근 keep건만 changes에 남기고, 넘치는 건 history[model]에 한 줄로."""
    per_model: dict[str, int] = {}
    kept: list[dict] = []
    for c in state["changes"]:
        n = per_model.get(c["model"], 0)
        if n < keep:
            kept.append(c)
            per_model[c["model"]] = n + 1
        else:
            line = (f"- {c['name']} ({c.get('confirmed_date', '?')}) — {c['diff'][:120]} "
                    f"[출처]({c['source_url']})")
            bucket = state["history"].setdefault(c["model"], [])
            if line not in bucket:
                bucket.append(line)
    state["changes"] = kept


def _models_in(state: dict) -> list[str]:
    """위키 절 순서 — 추적 목록(.env) 순서대로, 기록·프로필이 있는 모델만. '라인업 공통'은 맨 뒤."""
    present = ({c["model"] for c in state["changes"]} | set(state["profiles"])
               | set(state["history"]))
    order = [m for m in tracked_models(state["vendor"]) if m in present]
    if COMMON_MODEL in present:
        order.append(COMMON_MODEL)
    return order


# ── 프로필 — 모델별 상세(개요·스펙·잘 쓰는 법·하네스 조정·주의)를 LLM이 쓰고 코드가 검증 ──────
def _overview_excerpt(vendor: str, model: str) -> str:
    """모델 개요 문서(반영본)에서 그 모델을 언급하는 절만 발췌 — 프로필 입력."""
    key = VENDORS[vendor].get("overview_source")
    if not key:
        return ""
    p = _applied_path(key)
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    if model == COMMON_MODEL:
        return text[:OVERVIEW_EXCERPT_LIMIT]
    needle = model.lower()
    short = needle.split()[-1] if " " in needle else needle
    parts = []
    for _title, body in _split_sections(text):
        low = body.lower()
        if needle in low or short in low:
            parts.append(body)
    joined = "\n\n".join(parts) if parts else text[:OVERVIEW_EXCERPT_LIMIT]
    return joined[:OVERVIEW_EXCERPT_LIMIT]


def _entries_text(state: dict, model: str) -> str:
    lines = []
    for c in state["changes"]:
        if c["model"] != model:
            continue
        lines.append(f"### {c['name']} (확인 {c.get('confirmed_date', '?')}, "
                     f"발표 {c.get('announced_date') or '미확인'})")
        lines.append(f"달라진 점: {c['diff']}")
        for t in c.get("usage_tips", []):
            lines.append(f"팁: {t}")
        for h in c.get("harness_changes", []):
            lines.append(f"하네스: {h}")
        lines.append(f"출처: {c['source_url']}")
        lines.append("")
    for line in state["history"].get(model, [])[:20]:
        lines.append(f"(이전) {line}")
    return "\n".join(lines).strip() or "(기록 없음)"


def _refresh_profiles(state: dict, models: set[str]) -> dict:
    """바뀐 모델의 프로필을 LLM으로 다시 쓴다. 실패한 모델은 이전 프로필을 유지(없으면 비움)."""
    vendor = state["vendor"]
    result = {"ok": 0, "failed": [], "cost_usd": 0.0, "model": None}
    for model in sorted(models):
        meta = run_headless_ex(
            prompt=model_profile(VENDORS[vendor]["name"], model,
                                 _entries_text(state, model), _overview_excerpt(vendor, model)),
            cwd=_neutral_cwd(), allowed_tools=[], disallowed_tools=NEVER_ALLOW,
            timeout=MODEL_CATALOG_TIMEOUT, task="model_catalog_profile",
        )
        raw = meta["result"]
        result["cost_usd"] += meta["cost_usd"]
        result["model"] = meta["model"]
        prof = _parse_profile(raw)
        if prof is None:
            _atomic_write(vendor_dir(vendor) / f"profile-failed-{_hash(model)[:8]}.txt",
                          f"{model}\n\n{raw or '(빈 응답)'}")
            result["failed"].append(model)
            logger.warning(f"[모델동향:{vendor}] '{model}' 프로필 생성 실패 — 이전 프로필 유지")
            continue
        prof["updated_at"] = _now_iso()
        prof["entry_count"] = sum(1 for c in state["changes"] if c["model"] == model)
        prof["llm_model"], prof["cost_usd"] = meta["model"], round(meta["cost_usd"], 4)
        state["profiles"][model] = prof
        result["ok"] += 1
    return result


def _stale_profiles(state: dict) -> set[str]:
    """변경 기록은 있는데 프로필이 없거나, 기록 수가 달라진 모델."""
    counts: dict[str, int] = {}
    for c in state["changes"]:
        counts[c["model"]] = counts.get(c["model"], 0) + 1
    return {m for m, n in counts.items()
            if _is_tracked(state["vendor"], m)
            and (m not in state["profiles"] or state["profiles"][m].get("entry_count") != n)}


# ── 위키 렌더 — docs/experts/models-<vendor>.md 전체를 state에서 재생성해 원자적으로 교체 ──────
def _render_wiki(state: dict) -> str:
    vendor = state["vendor"]
    meta = VENDORS[vendor]
    lines = [f"# {meta['name']}", "",
             "공식 문서에서 코드가 수집하고 LLM이 정리한 모델별 동향 위키. "
             f"마지막 갱신 세대 {state.get('generation', 0)}.",
             f"추적 모델: {', '.join(tracked_models(vendor))} (.env MODEL_TRACK_*). "
             "각 모델 절: 개요 → 스펙 → 잘 쓰는 법 → 하네스 조정 → 우리 판단(제안) → 주의 → "
             "변화 이력. "
             "[asserted]=공식 문서가 직접 말함, [inferred]/(제안)=우리 판단.", ""]
    models = _models_in(state)
    if not models:
        lines += ["(아직 수집된 모델 변화 없음)", ""]
    for model in models:
        prof = state["profiles"].get(model)
        lines.append(f"## {model}")
        if prof:
            lines.append(prof["overview"])
            spec_lines = [f"- **{PROFILE_SPEC_LABELS[k]}**: {prof['spec'][k]}"
                          for k in PROFILE_SPEC_KEYS if prof["spec"].get(k)]
            if spec_lines:
                lines += ["", "### 스펙"] + spec_lines
            if prof["usage_tips"]:
                lines += ["", "### 잘 쓰는 법"] + [f"- {t}" for t in prof["usage_tips"]]
            if prof["harness_changes"]:
                lines += ["", "### 하네스 조정"] + [f"- {h}" for h in prof["harness_changes"]]
            if prof.get("suggestions"):
                lines += ["", "### 우리 판단(제안)"] + [f"- {g}" for g in prof["suggestions"]]
            if prof["gotchas"]:
                lines += ["", "### 주의"] + [f"- {g}" for g in prof["gotchas"]]
            lines.append("")
            srcs = " · ".join(f"[{s}]({s})" for s in prof["sources"])
            cost = (f" · {prof['llm_model']} ${prof['cost_usd']:.2f}"
                    if prof.get("llm_model") else "")
            lines.append(f"프로필 갱신: {prof.get('updated_at', '?')}{cost}" +
                         (f" · 근거: {srcs}" if srcs else ""))
        else:
            lines.append("(상세 프로필 미생성 — 다음 수집에서 다시 시도)")
        entries = [c for c in state["changes"] if c["model"] == model]
        if entries:
            lines += ["", "### 변화 이력"]
            for c in entries:
                tag = {"asserted": "[asserted]", "inferred": "[inferred]",
                       "none": ""}[c["impact_type"]]
                lines.append(f"- **{c['name']}** ({c.get('confirmed_date', '?')}) {tag} — "
                             f"{c['diff']} [출처]({c['source_url']})")
                for t in c.get("usage_tips", []):
                    lines.append(f"  - 팁: {t}")
                for h in c.get("harness_changes", []):
                    lines.append(f"  - 하네스: {h}")
        hist = state["history"].get(model)
        if hist:
            lines += ["", "### 이전 변화(요약)"] + hist
        lines.append("")

    lines.append("## 출처·확인 상태")
    for key in meta["sources"]:
        src = state["sources"].get(key, {"url": SOURCES[key]["url"]})
        lines.append(f"- **{key}** — [{src.get('url')}]({src.get('url')})")
        checked = src.get("last_checked_at") or "없음"
        status = src.get("last_status") or "미수집"
        lines.append(f"  - 최종 확인: {checked} ({status})")
        lines.append(f"  - 최종 반영: {src.get('applied_at') or '없음'}")
        if src.get("last_llm_model"):
            lines.append(f"  - 최근 추출 LLM: {src['last_llm_model']} "
                         f"(${src.get('last_llm_cost_usd', 0):.2f})")
        if src.get("last_error"):
            lines.append(f"  - 마지막 오류: {src['last_error']}")
    prof_cost = sum(p.get("cost_usd", 0) for p in state["profiles"].values())
    prof_models = sorted({p["llm_model"] for p in state["profiles"].values() if p.get("llm_model")})
    if state["profiles"]:
        lines.append(f"- 모델 프로필 {len(state['profiles'])}개 — "
                     f"LLM {', '.join(prof_models) or '?'} · 누적 ${prof_cost:.2f}")
    return "\n".join(lines) + "\n"


def _write_wiki_from_state(state: dict) -> None:
    from src.cc.expert import wiki_path

    _atomic_write(wiki_path(VENDORS[state["vendor"]]["domain"]), _render_wiki(state))


def trend_brief(limit: int = 3) -> str:
    """다른 프롬프트에 주입할 벤더별 최근 변화 요약 + 확인 시각. 상태 없으면 빈 문자열."""
    blocks = []
    for vendor, meta in VENDORS.items():
        state = _load_state(vendor)
        checked = [s.get("last_checked_at") for s in state["sources"].values()
                   if s.get("last_checked_at")]
        if not checked:
            continue
        lines = [f"{meta['name']} (확인 {max(checked)})"]
        for c in state["changes"][:limit]:
            lines.append(f"- {c['model']} / {c['name']} ({c.get('confirmed_date', '?')}): "
                         f"{c['diff'][:80]}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


# ── 수집 진입점 ──────────────────────────────────────────────────────────────────────
def _fail(state: dict, srec: dict, status: str, error: str, key: str, code: str) -> dict:
    srec["last_status"], srec["last_error"] = status, error
    _save_state(state)
    _write_wiki_from_state(state)
    logger.warning(f"[모델동향] {key} {error}")
    return {"ok": False, "error": code}


def collect_source(key: str, fetch_only: bool = False, profiles: bool = True) -> dict:
    """소스 하나를 받아 diff 있으면 LLM으로 반영하고, 바뀐 모델의 프로필을 갱신한다."""
    src = SOURCES.get(key)
    if not src:
        return {"ok": False, "error": "unknown source"}
    vendor = src["vendor"]
    with _locked():
        state = _load_state(vendor)
        srec = state["sources"].setdefault(key, {"url": src["url"]})
        now = _now_iso()
        srec["requested_url"] = src["url"]
        srec["last_checked_at"] = now

        fetched = _fetch(src["url"])
        if not fetched["ok"]:
            return _fail(state, srec, "error", fetched["error"], key, fetched["error"])
        srec["final_url"] = fetched["final_url"]

        if src["format"] == "html":
            extracted = _extract_html_body(fetched["body"])
            if not extracted["ok"]:
                return _fail(state, srec, "error", "본문 추출 실패(main/article 없음)", key,
                             "extract_failed")
            body = extracted["text"]
        else:
            body = fetched["body"]

        body = _normalize(body)
        if not body:
            return _fail(state, srec, "error", "빈 본문", key, "empty_body")

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
        all_changes: list[dict] = []
        dropped = 0
        llm_calls = 0
        llm_cost = 0.0
        llm_model = None
        for chunk in chunks:
            llm_calls += 1
            meta = run_headless_ex(
                prompt=model_catalog_update(VENDORS[vendor]["name"], key, srec["final_url"],
                                             window_note, chunk, tracked_models(vendor)),
                cwd=_neutral_cwd(), allowed_tools=[], disallowed_tools=NEVER_ALLOW,
                timeout=MODEL_CATALOG_TIMEOUT, task="model_catalog_extract",
            )
            raw = meta["result"]
            llm_cost += meta["cost_usd"]
            llm_model = meta["model"]
            srec["last_llm_model"], srec["last_llm_cost_usd"] = llm_model, round(llm_cost, 4)
            parsed = _parse_llm_changes(raw)
            if parsed is None:
                # 실패 원문을 남겨 다음에 원인을 볼 수 있게(형식 위반인지, 빈 응답인지)
                _atomic_write(vendor_dir(vendor) / f"{key}.llm-failed.txt", raw or "(빈 응답)")
                srec["last_status"], srec["last_error"] = "llm_failed", "LLM 응답 검증 실패"
                _save_state(state)
                _write_wiki_from_state(state)
                logger.warning(f"[모델동향] {key} LLM 반영 실패 — 기존 위키 보존, 다음에 재시도")
                return {"ok": False, "error": "llm_failed", "changed": True}
            kept = [c for c in parsed if _is_tracked(vendor, c["model"])]
            dropped += len(parsed) - len(kept)   # 추적 목록 밖 모델(옛 모델 등)은 버린다
            all_changes.extend(kept)

        touched = _apply_changes(state, key, all_changes, fetched_hash)
        srec["applied_hash"], srec["applied_at"] = fetched_hash, now
        _atomic_write(applied_path, body)
        _save_state(state)
        _write_wiki_from_state(state)

        prof = {"ok": 0, "failed": [], "cost_usd": 0.0, "model": None}
        if profiles and touched:
            prof = _refresh_profiles(state, touched)
            llm_calls += len(touched)
            _save_state(state)
            _write_wiki_from_state(state)
        total_cost = round(llm_cost + prof["cost_usd"], 4)
        logger.info(f"[모델동향] {key} 반영 — 변경 {len(all_changes)}건, "
                    f"모델 {len(touched)}개 프로필, LLM 호출 {llm_calls}회, "
                    f"추출={llm_model} 프로필={prof['model']} 비용=${total_cost:.4f}")
        return {"ok": True, "changed": True, "llm_called": llm_calls > 0,
                "changes": len(all_changes), "dropped": dropped, "models": sorted(touched),
                "profiles_failed": prof["failed"], "llm_model": llm_model,
                "profile_model": prof["model"], "cost_usd": total_cost}


def refresh_profiles(vendor: str, models: set[str] | None = None) -> dict:
    """프로필만 다시 쓴다(수집 없이). models가 None이면 기록 수와 어긋난(stale) 모델만."""
    with _locked():
        state = _load_state(vendor)
        targets = models if models is not None else _stale_profiles(state)
        if not targets:
            return {"ok": True, "updated": 0, "failed": []}
        result = _refresh_profiles(state, targets)
        _save_state(state)
        _write_wiki_from_state(state)
        return {"ok": not result["failed"], "updated": result["ok"], "failed": result["failed"]}


def collect_vendor(vendor: str, fetch_only: bool = False) -> dict:
    """벤더 하나의 출처를 순차 수집. 한 소스 실패가 나머지를 막지 않는다."""
    meta = VENDORS.get(vendor)
    if not meta:
        return {"ok": False, "error": "unknown vendor"}
    results = {}
    for key in meta["sources"]:
        try:
            results[key] = collect_source(key, fetch_only=fetch_only)
        except Exception as e:  # 한 소스 예외가 배치를 안 멈춘다
            logger.warning(f"[모델동향] {key} 처리 중 예외: {e}")
            results[key] = {"ok": False, "error": str(e)}
    if not fetch_only:
        try:
            stale = refresh_profiles(vendor)      # 이전 실행에서 프로필이 실패한 모델 재시도
            if stale.get("updated"):
                results["profiles"] = stale
        except Exception as e:
            logger.warning(f"[모델동향:{vendor}] 프로필 재시도 실패: {e}")
    ok = all(r.get("ok") for k, r in results.items() if k != "profiles")
    return {"ok": ok, "sources": results}


def collect_all_sources(fetch_only: bool = False) -> dict:
    """전 벤더 순차 수집(정기 cron·CLI용)."""
    results = {v: collect_vendor(v, fetch_only=fetch_only) for v in VENDORS}
    return {"ok": all(r["ok"] for r in results.values()), "vendors": results}
