"""각 프로젝트에 ohmyPM 발자국을 설치·제거한다 — `ohmypm/` 폴더 하나 + 지침 블록 하나.

설치 발자국(2026-10-09 사용자 결정):
  <프로젝트>/ohmypm/.gitignore   "*" 한 줄 — 폴더가 스스로를 git에서 뺀다(로컬 전용, 프로젝트 저장소가 안 더러워짐)
  <프로젝트>/ohmypm/README.md    이 폴더가 무엇인지 한 단락
  <프로젝트>/ohmypm/state.md     지금 상태 뼈대(프로젝트의 Claude가 작업 매듭에 갱신)
  <프로젝트>/CLAUDE.md, AGENTS.md  끝에 표식으로 감싼 블록(없는 파일은 블록만 든 파일로 생성)

주간보고(weekly.md)와 랩실 제안(proposals.md)은 각 기능이 이 폴더에 쓴다.
멱등: 있는 것은 건너뛴다. 제거: 폴더와 블록만 지우고, 블록만 있던 파일은 파일째 지운다.
커밋은 하지 않는다 — CLAUDE.md 변경은 사용자가 diff로 보고 올린다.
"""

import re
import shutil
from pathlib import Path

from src.cc.common import is_self_project

OHMYPM_DIR = "ohmypm"
BLOCK_START = "<!-- ohmypm:start -->"
BLOCK_END = "<!-- ohmypm:end -->"
BLOCK_BODY = (
    "## ohmyPM\n"
    "- 이 프로젝트는 ohmyPM이 관리한다. 주간보고·현황·제안에 관한 질문을 받으면 `ohmypm/` 폴더"
    "(weekly.md·proposals.md·state.md)를 먼저 읽는다.\n"
    "- 작업을 매듭지을 때 `ohmypm/state.md`의 '지금 상태' 절을 한두 줄로 갱신한다.\n"
)
INSTRUCTION_FILES = ("CLAUDE.md", "AGENTS.md")

README_TEXT = (
    "# ohmypm/\n\n"
    "ohmyPM(로컬 프로젝트 관리 도구)이 이 프로젝트에 쓰는 자리다. 폴더 안 `.gitignore`가 `*`라\n"
    "git에는 올라가지 않는다(이 PC 전용). `weekly.md`는 주간보고에서 이 프로젝트 몫, `proposals.md`는\n"
    "랩실 연구원이 이 프로젝트에 낸 제안, `state.md`는 지금 상태 메모다. 지우려면 ohmyPM 화면의\n"
    "'설치 제거'를 쓰면 이 폴더와 CLAUDE.md·AGENTS.md의 ohmyPM 블록만 사라진다.\n"
)
STATE_TEXT = (
    "# 지금 상태\n\n(아직 기록 없음 — 작업을 매듭지을 때 한두 줄로)\n\n"
    "# 막힌 것\n\n(없음)\n\n"
    "# 다음\n\n(없음)\n"
)
_BLOCK_RE = re.compile(
    r"\r?\n?" + re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END) + r"\r?\n?", re.S)


def _read(p: Path) -> str:
    """원문 그대로 읽는다 — newline=""라야 CRLF가 LF로 바뀌지 않는다(사용자 파일을 되돌릴 수 있게)."""
    if not p.exists():
        return ""
    with p.open(encoding="utf-8", newline="") as f:
        return f.read()


def _write(p: Path, text: str) -> None:
    p.write_text(text, encoding="utf-8", newline="")


def _upsert_block(path: Path) -> bool:
    """지침 파일 끝에 블록을 붙인다. 이미 있으면 False. 파일이 없으면 블록만 든 파일을 만든다."""
    text = _read(path)
    if BLOCK_START in text:
        return False
    nl = "\r\n" if "\r\n" in text else "\n"
    body = BLOCK_BODY.replace("\n", nl)
    block = f"{BLOCK_START}{nl}{body}{BLOCK_END}{nl}"
    if text and not text.endswith(("\n", "\r\n")):
        text += nl
    if text:
        text += nl                      # 앞 내용과 한 줄 띄운다
    _write(path, text + block)
    return True


def _remove_block(path: Path) -> bool:
    """블록을 떼어낸다. 블록만 있던 파일(나머지가 공백뿐)은 파일째 지운다. 바뀐 게 없으면 False."""
    if not path.exists():
        return False
    text = _read(path)
    if BLOCK_START not in text:
        return False
    new = _BLOCK_RE.sub("", text, count=1)
    if not new.strip():
        path.unlink()
    else:
        _write(path, new.rstrip("\r\n") + ("\r\n" if "\r\n" in new else "\n"))
    return True


def is_installed(project_path: str) -> bool:
    return (Path(project_path) / OHMYPM_DIR).is_dir()


def install_project(project_path: str) -> dict:
    """ohmypm/ 폴더·파일과 지침 블록을 설치한다. 멱등. 반환 {created: [...], skipped: [...], self?}."""
    root = Path(project_path)
    if is_self_project(project_path):
        return {"created": [], "skipped": ["self"], "self": True}
    if not root.is_dir():
        raise FileNotFoundError(f"프로젝트 폴더 없음: {project_path}")
    created: list[str] = []
    skipped: list[str] = []
    d = root / OHMYPM_DIR
    if not d.exists():
        d.mkdir()
        created.append(OHMYPM_DIR + "/")
    for name, text in ((".gitignore", "*\n"), ("README.md", README_TEXT), ("state.md", STATE_TEXT)):
        f = d / name
        if f.exists():
            skipped.append(f"{OHMYPM_DIR}/{name}")
        else:
            _write(f, text)
            created.append(f"{OHMYPM_DIR}/{name}")
    claude, agents = root / "CLAUDE.md", root / "AGENTS.md"
    # 내용 있는 AGENTS.md만 있던 프로젝트에 CLAUDE.md를 새로 만들면, Claude Code는 CLAUDE.md가
    # 생긴 순간부터 AGENTS.md를 안 읽는다 → 새 CLAUDE.md 첫 줄에서 AGENTS.md를 불러오게 한다.
    if not claude.exists() and _BLOCK_RE.sub("", _read(agents)).strip():
        _write(claude, "@AGENTS.md\n")
    for name in INSTRUCTION_FILES:
        path = root / name
        if name == "CLAUDE.md" and _imports_agents(path):
            # CLAUDE.md가 AGENTS.md를 불러오면 블록은 AGENTS.md 한 곳에만 — 두 번 실리지 않게
            # (2026-10-10 orca에서 확인한 중복). 예전에 붙은 CLAUDE.md 쪽 블록은 뗀다.
            _remove_block(path)
            skipped.append(name)
            continue
        (created if _upsert_block(path) else skipped).append(name)
    return {"created": created, "skipped": skipped}


_IMPORT_AGENTS_RE = re.compile(r"^\s*@\.?/?AGENTS\.md\s*$", re.M)


def _imports_agents(path: Path) -> bool:
    """CLAUDE.md가 '@AGENTS.md' 줄로 AGENTS.md를 불러오는가."""
    return bool(_IMPORT_AGENTS_RE.search(_read(path)))


def uninstall_project(project_path: str) -> dict:
    """ohmypm/ 폴더와 지침 블록을 지운다. 반환 {removed: [...]}."""
    root = Path(project_path)
    removed: list[str] = []
    d = root / OHMYPM_DIR
    # 환경 세팅 백업(ohmypm/setup-backup/)이 남아 있으면 폴더째 지우지 않는다 — 되돌리기에 필요한 원본이다.
    from src.env_setup import has_backups   # 순환 import를 피해 여기서

    if has_backups(project_path):
        return {"removed": [], "blocked": f"{OHMYPM_DIR}/setup-backup/에 환경 세팅 백업이 있어 설치 제거를 멈췄습니다. "
                                          "되돌릴 일이 없으면 그 폴더를 직접 옮기거나 지운 뒤 다시 하세요."}
    if d.is_dir():
        shutil.rmtree(d)
        removed.append(OHMYPM_DIR + "/")
    for name in INSTRUCTION_FILES:
        if _remove_block(root / name):
            removed.append(name)
    return {"removed": removed}
