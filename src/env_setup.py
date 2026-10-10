"""환경 세팅 — 관리 프로젝트의 처음 환경(CLAUDE.md·AGENTS.md·.claude 설정)을 손보는 기능의 '코드' 쪽.

흐름: ① collect_snapshot — 프로젝트를 코드로만 조사(모델 호출 없음, 대상 프로젝트에 아무것도 만들지 않음)
      ② (src/cc/env_setup.py가 모델을 한 번 불러 변경안을 받는다)
      ③ validate_proposal — 변경안을 코드가 검사하고, 무엇을 '쓸 수 있는지'(applicable)·'시험 전'인지 코드가 정한다
      ④ apply_run — 사용자가 화면에서 승인한 항목만, 원본을 백업한 뒤 쓴다
      ⑤ revert_run — 그 실행이 실제로 쓴 파일만 백업으로 되돌린다

지키는 것(CLAUDE.md의 '환경 세팅 예외'):
  - 보여 주고, 승인한 것만, 백업한 뒤에만 쓴다. 커밋하지 않는다. 스킬·플러그인 설치 명령을 실행하지 않는다.
  - 1차에서 실제로 쓰는 대상은 루트 CLAUDE.md, 루트 AGENTS.md, .claude/settings.json(거부 규칙 추가만) 셋뿐.
    스킬·문서·'시험 전' 재료는 보여 주기만 한다(2026-10-11 사용자 결정).
  - ohmyPM 표식 블록(<!-- ohmypm:start -->~end)과 @AGENTS.md 불러오기 구조는 건드리지 않는다.
  - 사용자 범위(~/.claude)와 .env 본문은 읽지 않는다. 연결 경로(심볼릭 링크·정션)는 따라가지 않는다.
  - 기준 시점은 수집 때다 — 그 뒤 파일이 바뀌면 그 항목은 쓰지 않고 '파일이 바뀌어 건너뜀'으로 남긴다.
"""

import copy
import hashlib
import json
import os
import re
import subprocess
import threading
import tomllib
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.cc.common import REPO_ROOT, is_self_project
from src.db import env_setup as db
from src.install import _IMPORT_AGENTS_RE, BLOCK_END, BLOCK_START, OHMYPM_DIR, _read, _write
from src.proc import NO_WINDOW

# ── 상한(잘림은 숨기지 않고 스냅샷 warnings·truncated에 남긴다) ─────────────────
MAX_INSTRUCTION_CHARS = 20_000   # 지침 파일 하나를 모델에 넘기는 최대 글자 수(해시는 원본 전체로)
MAX_DOCS = 500                   # docs/ 파일 목록 최대 개수
MAX_WALK_FILES = 50_000          # 화면 파일 수를 세며 훑는 최대 파일 수
MAX_ITEMS = 8                    # 제안 항목 최대 개수 — 한 번에 크게 바꾸지 않는다
MAX_SCRIPTS = 30                 # package.json scripts에서 모으는 최대 개수
MAX_TEXT_FIELD = 20_000          # 제안의 before/after 최대 길이
GIT_TIMEOUT = 15

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__"}   # 어느 깊이에서든 건너뛴다
FRONTEND_EXTS = (".html", ".css", ".js", ".jsx", ".tsx", ".vue", ".svelte")
TEST_DIR_NAMES = {"tests", "test", "__tests__", "spec"}
MANIFESTS = ("pyproject.toml", "uv.lock", "requirements.txt", "setup.py", "package.json", "pnpm-lock.yaml",
             "package-lock.json", "yarn.lock", "bun.lockb", "Cargo.toml", "go.mod", "pubspec.yaml",
             "Gemfile", "composer.json")

# 종류 → 실제로 쓸 수 있는 유일한 대상(1차). 나머지 종류(skill·doc)는 보여 주기만 한다.
WRITABLE = {"claude_md": "CLAUDE.md", "agents_md": "AGENTS.md", "settings": ".claude/settings.json"}
KINDS = ("claude_md", "agents_md", "settings", "skill", "doc")
OPS = ("create", "append", "replace")
READ_ONLY_SETTINGS = ".claude/settings.local.json"
BACKUP_DIR = "setup-backup"
KIT_README = REPO_ROOT / "kit" / "README.md"

SKIP_MARK = "건너뜀 — "    # 이유 앞머리: 안전하게 쓰지 않은 것
FAIL_MARK = "실패 — "      # 이유 앞머리: 쓰려다 실패한 것(화면에서 건너뜀과 구분)

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿⌀-⏿]")

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


class EnvSetupError(Exception):
    """화면에 보여 줄 이유 + HTTP 코드(404 없음, 409 상태 충돌, 422 잘못된 입력)."""

    def __init__(self, message: str, code: int = 422):
        super().__init__(message)
        self.code = code


class ProposalError(Exception):
    """모델 제안이 계약을 어겼다 — 실행을 실패로 남기고 아무것도 적용 가능하게 만들지 않는다."""


# ── 작은 도구들 ──────────────────────────────────────────────────────────────
def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _norm(p) -> str:
    return os.path.normcase(os.path.normpath(str(p)))


def _is_link(p: Path) -> bool:
    """심볼릭 링크나 윈도우 정션 — 프로젝트 밖으로 이어질 수 있어 따라가지 않는다."""
    try:
        return p.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(p))
    except OSError:
        return True


def _lock(project: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(_norm(project), threading.Lock())


def project_key(root: Path) -> str:
    """작업 이름에 쓰는 프로젝트 키 — 정규화한 경로의 해시(같은 프로젝트는 늘 같고, 다른 프로젝트는 다르다)."""
    return hashlib.sha1(_norm(root).encode("utf-8")).hexdigest()[:12]


def resolve_project(path: str) -> Path:
    """요청 경로를 실제 폴더로 풀고(.. 와 연결 경로까지) 관리 대상인지·자기 자신이 아닌지 확인한다."""
    if not path or not str(path).strip():
        raise EnvSetupError("프로젝트 경로가 비었습니다", 422)
    try:
        root = Path(path).resolve(strict=True)
    except (OSError, RuntimeError):
        raise EnvSetupError("프로젝트 폴더가 없습니다", 404)
    if not root.is_dir():
        raise EnvSetupError("프로젝트 폴더가 없습니다", 404)
    if is_self_project(str(root)):
        raise EnvSetupError("ohmyPM 자기 자신은 환경 세팅 대상이 아닙니다", 422)
    from src.db import projects as projects_db

    registered = set()
    for p in projects_db.list_projects(enabled_only=True):
        try:
            registered.add(_norm(Path(p["path"]).resolve()))
        except (OSError, RuntimeError):
            continue
    if _norm(root) not in registered:
        raise EnvSetupError("관리 대상으로 등록된(켜진) 프로젝트가 아닙니다", 404)
    return root


def safe_target(root: Path, target: str) -> str:
    """제안의 대상 경로를 검사해 'a/b' 꼴 상대경로로 돌려준다. 위험하면 ProposalError.

    거부: 빈 값, 절대경로(/·\\ 시작), 드라이브(C:), UNC(\\\\서버), ':'(대체 데이터 스트림),
    '..'·'.'·빈 조각, 끝이 점·공백인 조각(윈도우가 몰래 떼어 냄), 연결 경로, 프로젝트 밖으로 풀리는 경로."""
    t = (target or "").strip()
    if not t or len(t) > 200 or "\x00" in t:
        raise ProposalError(f"대상 경로가 비었거나 너무 깁니다: {target!r}")
    if t.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", t) or ":" in t:
        raise ProposalError(f"대상은 프로젝트 기준 상대경로만 됩니다: {target!r}")
    parts = re.split(r"[\\/]", t)
    if any(p in ("", ".", "..") or p != p.rstrip(". ") for p in parts):
        raise ProposalError(f"허용하지 않는 경로 조각이 있습니다: {target!r}")
    cur = root
    for p in parts:
        cur = cur / p
        if _is_link(cur):
            raise ProposalError(f"연결 경로(심볼릭 링크·정션)는 대상이 될 수 없습니다: {target!r}")
    try:
        cur.resolve(strict=False).relative_to(root.resolve())
    except ValueError:
        raise ProposalError(f"프로젝트 밖으로 이어지는 경로입니다: {target!r}")
    return "/".join(parts)


def _protected_ranges(text: str) -> tuple[list[list[int]], bool]:
    """표식 블록의 [시작, 끝) 글자 위치들. 표식이 짝을 이루지 않으면 ([], False)."""
    starts = [m.start() for m in re.finditer(re.escape(BLOCK_START), text)]
    ends = [m.end() for m in re.finditer(re.escape(BLOCK_END), text)]
    if len(starts) != len(ends):
        return [], False
    ranges, prev = [], -1
    for s, e in zip(starts, ends):
        if not (prev <= s < e):
            return [], False
        ranges.append([s, e])
        prev = e
    return ranges, True


def _blocks(text: str) -> list[str] | None:
    ranges, ok = _protected_ranges(text)
    return [text[s:e] for s, e in ranges] if ok else None


def _nl_of(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _adapt(s: str, nl: str) -> str:
    """새로 넣는 문장의 줄바꿈만 대상 파일 방식에 맞춘다(기존 원문은 건드리지 않는다)."""
    s = s.replace("\r\n", "\n")
    return s.replace("\n", nl) if nl != "\n" else s


def _file_state(path: Path) -> dict:
    """대상 파일의 수집 시점 상태 — 없음/읽기 실패/해시를 구분한다(읽기 실패를 '없음'으로 저장하지 않는다)."""
    if _is_link(path):
        return {"exists": True, "readable": False, "sha256": None, "error": "연결 경로라 읽지 않음"}
    if not path.exists():
        return {"exists": False, "readable": True, "sha256": None, "error": None}
    try:
        data = path.read_bytes()
    except OSError as e:
        return {"exists": True, "readable": False, "sha256": None, "error": f"읽기 실패: {e}"}
    return {"exists": True, "readable": True, "sha256": _sha(data), "error": None, "_bytes": data}


# ── ① 수집 ───────────────────────────────────────────────────────────────────
def _walk(root: Path, warnings: list[str]) -> tuple[dict, list[str], list[str]]:
    counts = {e: 0 for e in FRONTEND_EXTS}
    test_dirs: list[str] = []
    docs: list[str] = []
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        rel = here.relative_to(root)
        keep = []
        for d in sorted(dirnames):
            full = here / d
            if d in SKIP_DIRS or (rel == Path(".") and d == OHMYPM_DIR) or _is_link(full):
                continue
            keep.append(d)
            if d.lower() in TEST_DIR_NAMES and len(rel.parts) < 3:
                test_dirs.append((rel / d).as_posix())
        dirnames[:] = keep
        for f in sorted(filenames):
            seen += 1
            if seen > MAX_WALK_FILES:
                warnings.append(f"파일이 {MAX_WALK_FILES:,}개를 넘어 화면 파일 수·문서 목록을 그 앞까지만 셌다")
                return counts, test_dirs, docs
            full = here / f
            if _is_link(full):
                continue
            ext = full.suffix.lower()
            if ext in counts:
                counts[ext] += 1
            if rel.parts[:1] == ("docs",):
                if len(docs) < MAX_DOCS:
                    docs.append((rel / f).as_posix())
                elif len(docs) == MAX_DOCS:
                    docs.append("(이후 생략)")
                    warnings.append(f"docs/ 파일이 {MAX_DOCS}개를 넘어 목록을 잘랐다")
    return counts, test_dirs, docs


def _commands(root: Path, warnings: list[str]) -> list[dict]:
    """설정 파일에 실제로 적힌 실행·검증 명령과 그 근거. 명령은 실행하지 않는다."""
    out: list[dict] = []
    pj = root / "package.json"
    if pj.is_file() and not _is_link(pj):
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            warnings.append(f"package.json을 읽지 못함: {e}")
        else:
            runner = "pnpm run" if (root / "pnpm-lock.yaml").exists() else \
                "yarn run" if (root / "yarn.lock").exists() else "npm run"
            scripts = data.get("scripts") if isinstance(data, dict) else None
            if isinstance(scripts, dict):
                for k, v in list(scripts.items())[:MAX_SCRIPTS]:
                    if isinstance(v, str):
                        out.append({"command": f"{runner} {k}", "source": "package.json",
                                    "location": f"scripts.{k}", "script": v[:300]})
    pp = root / "pyproject.toml"
    if pp.is_file() and not _is_link(pp):
        try:
            data = tomllib.loads(pp.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            warnings.append(f"pyproject.toml을 읽지 못함: {e}")
        else:
            if isinstance(data.get("tool", {}).get("pytest", {}).get("ini_options"), dict):
                cmd = "uv run pytest" if (root / "uv.lock").exists() else "pytest"
                out.append({"command": cmd, "source": "pyproject.toml", "location": "tool.pytest.ini_options"})
            scripts = data.get("project", {}).get("scripts")
            if isinstance(scripts, dict):
                for k in list(scripts)[:MAX_SCRIPTS]:
                    out.append({"command": k, "source": "pyproject.toml", "location": f"project.scripts.{k}"})
    return out


# 권한 규칙 문자열에는 사용자가 허용한 명령이 통째로 남는다 — 예: 'Bash(TOKEN=sbp_... npx ...)'.
# 2026-10-11 runmagotchi 첫 시험에서 Supabase 토큰이 이 경로로 모델 입력에 실렸다. 모델에 넘기기 전에 가린다.
REDACTED = "(비밀값 가림)"
_BEARER_RE = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}")
_ASSIGN_RE = re.compile(r"(?i)\b([A-Z0-9_]*(?:TOKEN|KEY|SECRET|PASSWORD|PASSWD|PWD)[A-Z0-9_]*)\s*[=:]\s*"
                        r"(?!\(비밀값)(\"[^\"]*\"|'[^']*'|[^\s)]+)")
_TOKEN_RES = [
    re.compile(r"\b(?:sbp|sk|pk|rk|ghp|gho|ghu|ghs|ghr|github_pat|glpat|xox[abpr])[-_][A-Za-z0-9_\-]{8,}"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{4,}"),      # JWT
    re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"),                                                  # 길고 무작위한 문자열
]


def redact(s: str) -> str:
    """비밀값처럼 보이는 부분을 가린다. 변수 이름(KEY=)은 남기고 값만 가린다."""
    s = _BEARER_RE.sub(lambda m: f"{m.group(1)}{REDACTED}", s)
    s = _ASSIGN_RE.sub(lambda m: f"{m.group(1)}={REDACTED}", s)
    for rx in _TOKEN_RES:
        s = rx.sub(REDACTED, s)
    return s


def _settings_summary(path: Path, warnings: list[str]) -> dict:
    """설정 파일에서 권한·훅 모양만 뽑는다. 그 밖의 값(환경 변수 등)은 모델에 넘기지 않는다."""
    info: dict = {"exists": False, "valid_json": None, "error": None, "permissions": {}, "hooks": {}}
    if _is_link(path):
        info.update(exists=True, error="연결 경로라 읽지 않음")
        return info
    if not path.exists():
        return info
    info["exists"] = True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        info.update(valid_json=False, error=f"JSON으로 읽지 못함: {e}")
        warnings.append(f"{path.name}이 올바른 JSON이 아님 — 없는 설정으로 취급하지 않음")
        return info
    if not isinstance(data, dict):
        info.update(valid_json=False, error="JSON 객체가 아님")
        return info
    info["valid_json"] = True
    perms = data.get("permissions")
    if isinstance(perms, dict):
        for key in ("allow", "deny", "ask"):
            rules = perms.get(key)
            if isinstance(rules, list):
                info["permissions"][key] = [redact(str(r))[:200] for r in rules[:50]]
        if isinstance(perms.get("defaultMode"), str):
            info["permissions"]["defaultMode"] = perms["defaultMode"]
    hooks = data.get("hooks")
    if isinstance(hooks, dict):
        info["hooks"] = {str(ev): (len(v) if isinstance(v, list) else 1) for ev, v in hooks.items()}
    return info


def _env_ignored(root: Path) -> dict:
    """.env가 Git에서 빠지는지 — 문자열 포함이 아니라 git check-ignore로 판단. 못 하면 unknown."""
    if not (root / ".git").exists():
        return {"value": "unknown", "evidence": ".git이 없어 Git 무시 규칙을 판단하지 않음"}
    try:
        r = subprocess.run(["git", "check-ignore", "-v", ".env"], cwd=root, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as e:
        return {"value": "unknown", "evidence": f"git check-ignore 실행 실패: {e}"}
    if r.returncode == 0:
        return {"value": "yes", "evidence": f"git check-ignore: {r.stdout.strip()}"}
    if r.returncode == 1:
        return {"value": "no", "evidence": "git check-ignore: .env가 무시 규칙에 걸리지 않음"}
    return {"value": "unknown", "evidence": f"git check-ignore 오류: {(r.stderr or '').strip()[:200]}"}


def collect_snapshot(project_path: str) -> dict:
    """프로젝트 하나의 스냅샷(제안의 기준 시점). 대상 프로젝트에 파일·폴더를 만들지 않는다."""
    root = resolve_project(project_path)
    warnings: list[str] = []
    manifests = [m for m in MANIFESTS if (root / m).is_file() and not _is_link(root / m)]
    counts, test_dirs, docs = _walk(root, warnings)

    targets: dict[str, dict] = {}
    instructions: dict[str, dict] = {}
    for rel in WRITABLE.values():
        st = _file_state(root / rel)
        data = st.pop("_bytes", None)
        targets[rel] = st
        if rel.endswith(".md"):
            info = {"exists": st["exists"], "sha256": st["sha256"], "text": "", "truncated": False,
                    "protected_ranges": [], "markers_ok": True, "error": st["error"]}
            if data is not None:
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    info["error"] = "UTF-8이 아님"
                    targets[rel]["readable"] = False
                    targets[rel]["error"] = "UTF-8이 아님"
                    warnings.append(f"{rel}가 UTF-8이 아니라 읽지 못함")
                else:
                    ranges, ok = _protected_ranges(text)
                    info.update(text=text[:MAX_INSTRUCTION_CHARS], truncated=len(text) > MAX_INSTRUCTION_CHARS,
                                protected_ranges=ranges, markers_ok=ok, chars=len(text))
                    if info["truncated"]:
                        warnings.append(f"{rel}가 길어 앞 {MAX_INSTRUCTION_CHARS:,}자만 넘김(해시는 전체 기준)")
                    if not ok:
                        warnings.append(f"{rel}의 ohmyPM 표식이 짝을 이루지 않음")
            elif st["error"]:
                warnings.append(f"{rel}: {st['error']}")
            instructions[rel] = info

    claude = instructions["CLAUDE.md"]
    agents = instructions["AGENTS.md"]
    imports_agents = bool(claude["text"] and _IMPORT_AGENTS_RE.search(claude["text"]))
    agents_body = re.sub(re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END), "", agents["text"], flags=re.S)

    skills_dir = root / ".claude" / "skills"
    skills = sorted(p.name for p in skills_dir.iterdir() if p.is_dir() and not _is_link(p)) \
        if skills_dir.is_dir() and not _is_link(skills_dir) else []

    return {
        "project": str(root),
        "captured_at": db.now(),
        "manifests": manifests,
        "frontend_counts": {k: v for k, v in counts.items() if v},
        "test_dirs": test_dirs,
        "commands": _commands(root, warnings),
        "docs": docs,
        "instructions": instructions,
        "imports_agents": imports_agents,
        "agents_has_content": bool(agents_body.strip()),
        "targets": targets,
        "settings_summary": {
            ".claude/settings.json": _settings_summary(root / ".claude" / "settings.json", warnings),
            READ_ONLY_SETTINGS: _settings_summary(root / ".claude" / "settings.local.json", warnings),
        },
        "skills": skills,
        "env_ignored": _env_ignored(root),
        "warnings": warnings,
    }


# ── 재료 표(kit/README.md) ─────────────────────────────────────────────────────
def load_materials(path: Path = KIT_README) -> list[dict]:
    """kit/README.md 표에서 재료 목록을 읽는다. 상태가 '검증됨'으로 시작하지 않으면 모두 시험 전(experimental)."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        m = re.match(r"`([^`]+)`", cells[0]) if cells else None
        if not m or len(cells) < 3:
            continue
        name = m.group(1).strip()
        status = cells[-1]
        out.append({"name": name, "kind": "skill" if name.startswith("skills/") else "doc",
                    "status": status, "experimental": not status.startswith("검증됨"),
                    "summary": cells[0][:300], "for": cells[1][:200]})
    return out


def install_guide(material: dict) -> str:
    """스킬 재료의 설치 안내 — 코드가 만든 고정 문장(모델이 낸 명령은 쓰지 않는다). 보여 주기만 한다."""
    base = material["name"].rstrip("/").split("/")[-1]
    return (f"ohmyPM 저장소의 kit/{material['name'].rstrip('/')}/ 폴더를 이 프로젝트의 .claude/skills/{base}/ 로 "
            "복사하면 설치됩니다. ohmyPM은 복사하지 않습니다 — 원하면 직접 하세요.")


# ── ③ 제안 검증 ───────────────────────────────────────────────────────────────
def _settings_deny_only(old_text: str | None, new_text: str) -> str | None:
    """설정 변경이 '기존 permissions.deny에 거부 규칙을 더하는 것'뿐인지. 아니면 이유 문자열."""
    try:
        new = json.loads(new_text)
        old = json.loads(old_text) if old_text else {}
    except ValueError as e:
        return f"결과가 올바른 JSON이 아님: {e}"
    if not isinstance(new, dict) or not isinstance(old, dict):
        return "설정은 JSON 객체여야 함"
    op, np_ = old.get("permissions", {}), new.get("permissions", {})
    if not isinstance(op, dict) or not isinstance(np_, dict):
        return "permissions가 객체가 아님"
    od, nd = op.get("deny", []), np_.get("deny", [])
    if not isinstance(od, list) or not isinstance(nd, list) or not all(isinstance(x, str) for x in nd):
        return "permissions.deny는 문자열 목록이어야 함"
    if any(x not in nd for x in od):
        return "기존 거부 규칙을 지우는 변경은 허용하지 않음"
    if not [x for x in nd if x not in od]:
        return "추가된 거부 규칙이 없음"
    o2, n2 = copy.deepcopy(old), copy.deepcopy(new)
    o2.setdefault("permissions", {}).pop("deny", None)
    n2.setdefault("permissions", {}).pop("deny", None)
    if o2 != n2:
        return "거부 규칙 추가 말고 다른 설정(허용 권한·훅 등)까지 바꾸는 변경은 허용하지 않음"
    return None


def _check_text(field: str, value, limit: int, required: bool = True) -> str | None:
    if value is None:
        if required:
            raise ProposalError(f"{field}가 없음")
        return None
    if not isinstance(value, str) or (required and not value.strip()) or len(value) > limit:
        raise ProposalError(f"{field}의 형식·길이가 맞지 않음")
    return value


def validate_proposal(data, snapshot: dict, materials: list[dict]) -> list[dict]:
    """모델 응답(dict)을 검사해 저장할 항목 목록으로 만든다. 계약 위반이면 ProposalError(실행 실패).

    무엇을 쓸 수 있는지(applicable)·시험 전인지(experimental)는 모델이 아니라 코드가 정한다."""
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ProposalError("응답에 items 목록이 없음")
    raw = data["items"]
    if len(raw) > MAX_ITEMS:
        raise ProposalError(f"제안이 {len(raw)}개 — 최대 {MAX_ITEMS}개")
    root = Path(snapshot["project"])
    mats = {m["name"]: m for m in materials}
    seen_ids, seen_targets = set(), set()
    out = []
    for it in raw:
        if not isinstance(it, dict):
            raise ProposalError("항목이 객체가 아님")
        pid = it.get("id")
        if not isinstance(pid, str) or not _ID_RE.match(pid) or pid in seen_ids:
            raise ProposalError(f"항목 식별자가 없거나 형식이 틀렸거나 겹침: {pid!r}")
        seen_ids.add(pid)
        kind, op = it.get("kind"), it.get("op")
        if kind not in KINDS:
            raise ProposalError(f"{pid}: 모르는 종류 {kind!r}")
        if op not in OPS:
            raise ProposalError(f"{pid}: 모르는 작업 {op!r}")
        title = _check_text(f"{pid}.title", it.get("title"), 120)
        why = _check_text(f"{pid}.why", it.get("why"), 1000)
        after = _check_text(f"{pid}.after", it.get("after"), MAX_TEXT_FIELD, required=False) or ""
        if op == "replace":
            before = _check_text(f"{pid}.before", it.get("before"), MAX_TEXT_FIELD)
        else:
            if it.get("before") is not None:
                raise ProposalError(f"{pid}: replace가 아니면 before는 null이어야 함")
            before = None
        if any(_EMOJI_RE.search(s or "") for s in (title, why, after)):
            raise ProposalError(f"{pid}: 이모지·장식 기호가 들어 있음")
        material_name = it.get("material")
        if material_name is not None and (not isinstance(material_name, str) or material_name not in mats):
            raise ProposalError(f"{pid}: kit/에 없는 재료 {material_name!r}")
        mat = mats.get(material_name) if material_name else None

        raw_target = it.get("target")
        if raw_target is None and kind in ("skill", "doc") and mat:
            # 보여 주기만 하는 재료 항목은 대상이 비어도 받는다 — 놓일 자리를 코드가 정한다(2026-10-11 첫 시험)
            base = mat["name"].rstrip("/").split("/")[-1]
            raw_target = f".claude/skills/{base}/SKILL.md" if kind == "skill" else base
        target = safe_target(root, raw_target)
        if target.casefold() == READ_ONLY_SETTINGS.casefold():
            raise ProposalError(f"{pid}: {READ_ONLY_SETTINGS}는 읽기 전용")
        if kind in WRITABLE:
            canon = WRITABLE[kind]
            if target.casefold() != canon.casefold():
                raise ProposalError(f"{pid}: {kind}의 대상은 {canon}뿐 — {target!r}")
            target = canon
            if target.casefold() in seen_targets:
                raise ProposalError(f"{pid}: 같은 파일({target})을 바꾸는 항목이 둘 이상")
            seen_targets.add(target.casefold())
            if kind == "settings":
                if op == "append":
                    raise ProposalError(f"{pid}: 설정은 append로 바꿀 수 없음")
                if op == "create":
                    why_bad = _settings_deny_only(None, after)
                    if why_bad:
                        raise ProposalError(f"{pid}: {why_bad}")
        elif kind == "skill" and mat is None:
            raise ProposalError(f"{pid}: 스킬은 kit/ 재료만 제시할 수 있음")

        experimental = bool(mat and mat["experimental"])
        prop = {"id": pid, "kind": kind, "title": title, "why": why, "target": target, "op": op,
                "before": before, "after": after, "material": material_name, "experimental": experimental}
        if kind == "skill" and mat:
            prop["install_guide"] = install_guide(mat)

        rec = {"proposal": prop, "target": target, "applicable": False, "reason": None,
               "existed_before": None, "source_hash": None}
        if kind not in WRITABLE:
            rec["reason"] = "스킬은 보여 주기만 합니다 — 설치는 직접 하세요" if kind == "skill" else \
                "문서 항목은 1차에서 보여 주기만 합니다"
        elif experimental:
            rec["reason"] = "시험 전 재료라 적용하지 않습니다(보여 주기만)"
        else:
            st = snapshot["targets"][target]
            rec["existed_before"] = st["exists"]
            rec["source_hash"] = st["sha256"]
            info = snapshot["instructions"].get(target, {})
            if not st["readable"]:
                rec["reason"] = f"수집 때 파일을 읽지 못해 적용하지 않습니다({st['error']})"
            elif op == "create" and st["exists"]:
                rec["reason"] = "이미 있는 파일이라 새로 만들 수 없습니다"
            elif op != "create" and not st["exists"]:
                rec["reason"] = "없는 파일이라 덧붙이거나 바꿀 수 없습니다"
            elif target.endswith(".md") and not info.get("markers_ok", True):
                rec["reason"] = "ohmyPM 표식이 짝을 이루지 않아 적용하지 않습니다"
            elif (target == "CLAUDE.md" and op == "create" and snapshot.get("agents_has_content")
                  and not _IMPORT_AGENTS_RE.search(after)):
                rec["reason"] = "내용 있는 AGENTS.md를 가리게 됩니다 — 새 CLAUDE.md에 @AGENTS.md 줄이 빠져 있음"
            else:
                rec["applicable"] = True
        out.append(rec)
    return out


# ── 변경 계획(적용할 최종 원문 만들기) ─────────────────────────────────────────
def plan_text(prop: dict, current: str | None) -> tuple[str | None, str | None]:
    """(새 원문, None) 또는 (None, 건너뛸 이유). 기존 원문은 정규화하지 않는다."""
    op, after = prop["op"], prop.get("after") or ""
    if op == "create":
        if current is not None:
            return None, "이미 있는 파일이라 새로 만들지 않음"
        new = after
    elif current is None:
        return None, "파일이 없어 덧붙이거나 바꿀 수 없음"
    elif op == "append":
        nl = _nl_of(current)
        add = _adapt(after, nl)
        if current and not current.endswith(("\n", "\r")) and not add.startswith(("\n", "\r")):
            add = nl + add
        new = current + add
    else:   # replace — before가 원문에 정확히 한 번 있을 때만
        nl = _nl_of(current)
        before = _adapt(prop["before"], nl) if nl == "\r\n" and "\r\n" not in prop["before"] else prop["before"]
        n = current.count(before)
        if n != 1:
            return None, f"바꿀 원문(before)이 {'없음' if n == 0 else f'{n}번 나옴'} — 정확히 한 번일 때만 바꿈"
        i = current.index(before)
        ranges, ok = _protected_ranges(current)
        if not ok:
            return None, "ohmyPM 표식이 짝을 이루지 않음"
        if any(i < e and s < i + len(before) for s, e in ranges):
            return None, "ohmyPM 표식 블록과 겹치는 변경"
        new = current[:i] + _adapt(after, nl) + current[i + len(before):]
    if current is not None and prop["target"].endswith(".md"):
        if _blocks(current) != _blocks(new):
            return None, "ohmyPM 표식 블록이 바뀌는 변경"
        if prop["target"] == "CLAUDE.md" and _IMPORT_AGENTS_RE.search(current) and not _IMPORT_AGENTS_RE.search(new):
            return None, "@AGENTS.md 불러오기 줄이 사라지는 변경"
    if prop["target"] == WRITABLE["settings"]:
        why_bad = _settings_deny_only(current, new)
        if why_bad:
            return None, why_bad
    return new, None


def _backup(data: bytes, dest: Path) -> None:
    """원본 바이트를 그대로 복사하고 다시 읽어 확인한다. 실패하면 예외(그 항목은 쓰지 않는다)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    if _sha(dest.read_bytes()) != _sha(data):
        raise OSError("백업 파일 확인 해시가 다름")


def _atomic_write(path: Path, text: str, tag: str) -> None:
    """같은 폴더의 임시 파일에 쓴 뒤 바꿔 끼운다 — 파일이 반만 써지는 일을 줄인다(_write = newline 보존)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.ohmypm-tmp-{tag}")
    _write(tmp, text)
    os.replace(tmp, path)


def _current(path: Path) -> tuple[bytes | None, str | None]:
    data = path.read_bytes() if path.exists() else None
    return data, (_sha(data) if data is not None else None)


def _prepare_backup_dir(root: Path, run_id: int) -> Path:
    """백업 폴더를 만들고 Git에서 빠지는지 확인한다. 확인 못 하면 409로 멈춘다(관리 폴더 .gitignore는 덮어쓰지 않음)."""
    od = root / OHMYPM_DIR
    if _is_link(od):
        raise EnvSetupError("ohmypm 폴더가 연결 경로라 백업하지 않습니다", 409)
    od.mkdir(exist_ok=True)
    gi = od / ".gitignore"
    if not gi.exists():
        _write(gi, "*\n")          # 미설치 프로젝트: 백업이 git에 안 올라가게 하는 최소 파일만
    bd = od / BACKUP_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-r{run_id}"
    bd.mkdir(parents=True, exist_ok=False)
    if (root / ".git").exists():
        rel = (bd / "probe").relative_to(root).as_posix()
        try:
            r = subprocess.run(["git", "check-ignore", "-q", rel], cwd=root, capture_output=True,
                               timeout=GIT_TIMEOUT, creationflags=NO_WINDOW)
            ignored = r.returncode == 0
        except (OSError, subprocess.SubprocessError):
            ignored = False
        if not ignored:
            bd.rmdir()
            raise EnvSetupError("백업 폴더가 Git에서 빠지는지 확인하지 못해 적용을 멈췄습니다"
                                f"({OHMYPM_DIR}/.gitignore를 확인하세요)", 409)
    return bd


# ── ④ 적용 ───────────────────────────────────────────────────────────────────
def _counts(items: list[dict], kinds: tuple[str, ...]) -> dict:
    c = {k: 0 for k in kinds}
    for it in items:
        st, why = it["status"], it.get("reason") or ""
        if st in c and st != "skipped":
            c[st] += 1
        elif why.startswith(FAIL_MARK) and "failed" in c:
            c["failed"] += 1
        elif (st == "skipped" or why.startswith(SKIP_MARK)) and "skipped" in c:
            c["skipped"] += 1
    return c


def apply_run(run_id: int, item_ids: list[int]) -> dict:
    """승인한 항목만 적용한다. 반환 {run, items, counts}. 이 실행을 다시 적용하지 않는다(상태 전이로 막음)."""
    run = db.get_run(run_id)
    if not run:
        raise EnvSetupError("없는 실행입니다", 404)
    root = resolve_project(run["project"])
    if not isinstance(item_ids, list) or not item_ids or not all(isinstance(i, int) for i in item_ids):
        raise EnvSetupError("적용할 항목을 하나 이상 고르세요", 422)
    items = db.list_items(run_id)
    by_id = {it["id"]: it for it in items}
    for i in item_ids:
        if i not in by_id:
            raise EnvSetupError(f"이 실행의 항목이 아닙니다: {i}", 422)
        if not by_id[i]["applicable"]:
            raise EnvSetupError(f"보여 주기만 하는 항목은 적용할 수 없습니다: {i}", 422)
    with _lock(str(root)):
        other = db.active_run(run["project"])
        if other and other["id"] != run_id:
            raise EnvSetupError("이 프로젝트에서 다른 환경 세팅 작업이 진행 중입니다", 409)
        if run["status"] != "proposed":
            raise EnvSetupError("이미 적용했거나 적용할 수 없는 상태의 실행입니다 — 새 제안을 만드세요", 409)
        backup_dir = _prepare_backup_dir(root, run_id)     # 실패하면 상태를 바꾸기 전에 멈춘다
        if not db.transition(run_id, ("proposed",), "applying", backup_dir=str(backup_dir)):
            raise EnvSetupError("다른 요청이 먼저 이 실행을 바꿨습니다", 409)
        t = db.now()
        for it in items:
            if it["applicable"] and it["status"] == "proposed":
                if it["id"] in item_ids:
                    db.update_item(it["id"], status="approved", approved_at=t)
                else:
                    db.update_item(it["id"], status="rejected")
        for it in db.list_items(run_id):
            if it["status"] == "approved":
                _apply_one(root, run_id, backup_dir, it)
        return _finish_apply(run_id)


def _apply_one(root: Path, run_id: int, backup_dir: Path, it: dict) -> None:
    prop = json.loads(it["proposal_json"])

    def skip(why: str, mark: str = SKIP_MARK):
        db.update_item(it["id"], status="skipped", reason=mark + why)

    try:
        full = root / safe_target(root, it["target"])
        data, h = _current(full)
        if h != it["source_hash"]:
            return skip("파일이 바뀌어 건너뜀(제안 뒤에 수정·삭제·생성됨)")
        try:
            text = data.decode("utf-8") if data is not None else None
        except UnicodeDecodeError:
            return skip("UTF-8이 아니라 건너뜀")
        new, why = plan_text(prop, text)
        if why:
            return skip(why)
        planned = new.encode("utf-8")
        backup_path = None
        if data is not None:
            dest = backup_dir / Path(*it["target"].split("/"))
            try:
                _backup(data, dest)
            except OSError as e:
                return skip(f"백업 실패라 쓰지 않음: {e}", FAIL_MARK)
            backup_path = str(dest)
        db.update_item(it["id"], planned_hash=_sha(planned), backup_path=backup_path)   # 쓰기 전에 기록
        if _current(full)[1] != h:                                                         # 쓰기 직전 재확인
            return skip("파일이 바뀌어 건너뜀(쓰기 직전 확인)")
        _atomic_write(full, new, f"r{run_id}")
        if _current(full)[1] != _sha(planned):
            return skip("쓴 뒤 확인한 내용이 계획과 다름", FAIL_MARK)
        db.update_item(it["id"], status="applied", applied_hash=_sha(planned), applied_at=db.now(), reason=None)
    except ProposalError as e:
        skip(str(e))
    except Exception as e:                          # 한 항목 실패가 다른 항목을 막지 않는다
        logger.warning(f"[환경 세팅] 실행 {run_id} 항목 {it['id']} 적용 실패: {e}")
        skip(f"쓰기 실패: {e}", FAIL_MARK)


def _finish_apply(run_id: int, note: str | None = None) -> dict:
    items = db.list_items(run_id)
    approved = [i for i in items if i["approved_at"]]
    applied = [i for i in approved if i["status"] == "applied"]
    if approved and len(applied) == len(approved):
        status, err = "applied", None
    elif applied:
        status, err = "partial", "승인한 항목 중 일부만 적용했습니다"
    else:
        status, err = "failed", "승인한 항목을 하나도 적용하지 못했습니다"
    if note:
        err = f"{note}{' — ' + err if err else ''}"
    db.update_run(run_id, status=status, error=err, applied_at=db.now() if applied else None)
    return {"run": db.get_run(run_id), "items": items,
            "counts": _counts(items, ("applied", "skipped", "failed", "rejected"))}


# ── ⑤ 되돌리기 ───────────────────────────────────────────────────────────────
def revert_run(run_id: int) -> dict:
    """그 실행이 실제로 쓴(applied) 파일만 되살린다. 적용 뒤 사용자가 고친 파일은 덮어쓰지 않는다(충돌로 남김)."""
    run = db.get_run(run_id)
    if not run:
        raise EnvSetupError("없는 실행입니다", 404)
    root = resolve_project(run["project"])
    with _lock(str(root)):
        before_status = run["status"]
        if before_status not in ("applied", "partial") or not any(
                i["status"] == "applied" for i in db.list_items(run_id)):
            raise EnvSetupError("되돌릴 적용 항목이 없습니다", 409)
        other = db.active_run(run["project"])
        if other and other["id"] != run_id:
            raise EnvSetupError("이 프로젝트에서 다른 환경 세팅 작업이 진행 중입니다", 409)
        if not db.transition(run_id, ("applied", "partial"), "reverting"):
            raise EnvSetupError("다른 요청이 먼저 이 실행을 바꿨습니다", 409)
        for it in db.list_items(run_id):
            if it["status"] == "applied":
                _revert_one(root, run_id, it)
        return _finish_revert(run_id, before_status)


def _revert_one(root: Path, run_id: int, it: dict) -> None:
    try:
        full = root / safe_target(root, it["target"])
        _, h = _current(full)
        if h != it["applied_hash"]:
            db.update_item(it["id"], reason=SKIP_MARK + "되돌리기 충돌 — 적용 뒤 파일이 바뀌어 덮어쓰지 않음")
            return
        if it["existed_before"]:
            bp = Path(it["backup_path"] or "")
            if not it["backup_path"] or not bp.is_file():
                db.update_item(it["id"], reason=FAIL_MARK + "백업 파일이 없어 되돌리지 못함")
                return
            data = bp.read_bytes()
            if _sha(data) != it["source_hash"]:
                db.update_item(it["id"], reason=FAIL_MARK + "백업 파일 해시가 원본과 달라 되돌리지 않음")
                return
            tmp = full.with_name(f"{full.name}.ohmypm-tmp-revert{run_id}")
            tmp.write_bytes(data)
            os.replace(tmp, full)
            if _current(full)[1] != it["source_hash"]:
                db.update_item(it["id"], reason=FAIL_MARK + "되살린 뒤 확인 해시가 다름")
                return
        else:
            full.unlink()                 # 새로 만든 파일 하나만 — 폴더는 지우지 않는다
        db.update_item(it["id"], status="reverted", reverted_at=db.now(), reason=None)
    except Exception as e:
        logger.warning(f"[환경 세팅] 실행 {run_id} 항목 {it['id']} 되돌리기 실패: {e}")
        db.update_item(it["id"], reason=FAIL_MARK + f"되돌리기 실패: {e}")


def _finish_revert(run_id: int, before_status: str, note: str | None = None) -> dict:
    items = db.list_items(run_id)
    still = [i for i in items if i["status"] == "applied"]
    reverted = [i for i in items if i["status"] == "reverted"]
    if reverted and not still:
        status, err = "reverted", None
    elif reverted:
        status, err = "partial", "일부만 되돌렸습니다 — 남은 항목의 이유를 확인하세요"
    else:
        status, err = before_status, "하나도 되돌리지 못했습니다 — 항목의 이유를 확인하세요"
    if note:
        err = f"{note}{' — ' + err if err else ''}"
    db.update_run(run_id, status=status, error=err, reverted_at=db.now() if reverted and not still else None)
    c = _counts([i for i in items if i["applied_at"]], ("reverted", "skipped", "failed"))
    return {"run": db.get_run(run_id), "items": items, "counts": c}


# ── 서버 재시작 때 정리 ─────────────────────────────────────────────────────────
def recover_on_startup() -> int:
    """끊긴 실행을 정리한다. 모델을 다시 부르거나 파일을 자동으로 덮어쓰·지우지 않는다. 정리한 실행 수."""
    n = 0
    for run in db.runs_with_status(("queued", "running")):
        db.update_run(run["id"], status="failed", finished_at=db.now(),
                      error="서버가 꺼져 제안이 중단됐습니다 — 다시 실행하세요")
        n += 1
    for run in db.runs_with_status(("applying",)):
        root = Path(run["project"])
        for it in db.list_items(run["id"]):
            if it["status"] != "approved":
                continue
            try:
                _, h = _current(root / it["target"])
            except OSError:
                h = "?"
            if it["planned_hash"] and h == it["planned_hash"]:
                db.update_item(it["id"], status="applied", applied_hash=h, applied_at=db.now())
            elif h == it["source_hash"]:
                db.update_item(it["id"], status="skipped", reason=SKIP_MARK + "서버가 꺼져 적용하지 않음")
            else:
                db.update_item(it["id"], status="skipped",
                               reason=FAIL_MARK + "서버가 꺼진 뒤 상태를 알 수 없음 — 파일을 직접 확인하세요")
        _finish_apply(run["id"], note="서버가 꺼져 적용이 중단된 뒤 정리함")
        n += 1
    for run in db.runs_with_status(("reverting",)):
        root = Path(run["project"])
        for it in db.list_items(run["id"]):
            if it["status"] != "applied":
                continue
            try:
                _, h = _current(root / it["target"])
            except OSError:
                h = "?"
            if h == it["source_hash"]:          # 이미 되살렸거나(있던 파일) 지웠다(없던 파일: 둘 다 None)
                db.update_item(it["id"], status="reverted", reverted_at=db.now(), reason=None)
            elif h != it["applied_hash"]:
                db.update_item(it["id"], reason=FAIL_MARK + "서버가 꺼진 뒤 상태를 알 수 없음 — 파일을 직접 확인하세요")
        any_applied = any(i["applied_at"] for i in db.list_items(run["id"]))
        _finish_revert(run["id"], "partial" if any_applied else "failed", note="서버가 꺼져 되돌리기가 중단된 뒤 정리함")
        n += 1
    if n:
        logger.warning(f"[환경 세팅] 서버 시작 — 끊긴 실행 {n}건 정리(자동 재실행 없음)")
    return n


def has_backups(project_path: str) -> bool:
    """이 프로젝트 ohmypm/setup-backup/ 안에 백업 파일이 하나라도 있나 — 설치 제거가 지우지 못하게 막는 데 쓴다."""
    bd = Path(project_path) / OHMYPM_DIR / BACKUP_DIR
    return bd.is_dir() and any(p.is_file() for p in bd.rglob("*"))

