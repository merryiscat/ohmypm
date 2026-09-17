"""반영(#4) — 당일 **일간보고 대화**와 **게시판 조언**을 담당이 프로젝트에 실제로 반영한다.
반영처(docs·코드 주석·설정 등)는 조언 성격에 맞게 에이전트가 판단한다(2026-09-06 사용자
확정: "꼭 docs가 아니더라도 반영할 수 있는 방법을 찾고 반영해"). 게시판 원본은 남긴다.

안전 설계:
- 에이전트는 Write/Edit만(Bash 없음). 임의 명령·git 푸시를 물리적으로 못 한다.
- git 커밋은 코드가 대신 하되, **에이전트가 이번에 새로 바꾼 파일만** 스테이징한다 —
  실행 전 이미 더러웠던(사용자 작업 중) 파일은 건드리지 않는다(WIP 보호). push 없음.
- cwd=대상 프로젝트라 그 프로젝트 규약(CLAUDE.md·docs)을 그대로 따른다.
"""

import json
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

from src.cc.client import run_headless
from src.cc.permissions import tools_for
from src.cc.prompts import REPROCESS_SYSTEM, reprocess_docs
from src.db import agents as agents_db
from src.db import board as board_db
from src.proc import NO_WINDOW

REPROCESS_TIMEOUT = 300
_OBJ = re.compile(r"\{.*\}", re.DOTALL)   # 응답 끝의 {lesson, files_changed} 추출


def _git(path: str, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", path, *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
        creationflags=NO_WINDOW,
    )


def _material_for(path: str, posts: list[dict]) -> str:
    """이 프로젝트가 쓴 글 + 그 글에 달린 조언을 스레드(댓글→답글) 구조로 텍스트화.

    왕복(대댓글·대대댓글)까지 이어진 논의는 결론이 아래쪽에 있으므로, 들여쓰기로
    흐름이 보이게 해서 에이전트가 '정리된 결론'을 집어내기 쉽게 한다.
    """
    own = [p for p in posts if p.get("project") == path]
    lines: list[str] = []
    for p in own:
        cmts = p.get("comments", [])
        if not cmts:
            continue
        lines.append(f"[내 글] {p['title']}\n{(p['body'] or '')[:400]}")
        def _who(c: dict) -> str:
            return "사용자" if c["author"] == "user" else c["author"]
        def _thread(parent_id: int | None, depth: int) -> None:
            for c in cmts:
                if c.get("parent_id") != parent_id:
                    continue
                pad = "  " * (depth + 1)
                label = "조언" if depth == 0 else "답글"
                lines.append(f"{pad}- {label}({_who(c)}): {(c['body'] or '')[:300]}")
                _thread(c["id"], depth + 1)
        _thread(None, 0)
    return "\n".join(lines)


def daily_transcript(path: str, date: str) -> str:
    """오늘 일간보고에서 PM과 나눈 대화 — 거기서 확정된 것도 기록장에 반영해야 한다.

    2026-09-09 사용자 지적: "대화를 했으면 기록장에도 작성을 하게 해줘야지".
    PM이 기한을 다시 잡고 담당이 상태를 정정해도 그 결과가 ohmyPM 안에만 남고
    프로젝트 docs는 옛날 그대로였다 → 다음 스캔이 옛 문서를 다시 읽어 원위치.
    """
    from src.db import messages as messages_db

    msgs = messages_db.list_messages(f"daily::{date}::{path}", limit=40)
    if not msgs:
        return ""
    # 변화 없어 자동 한 줄만 남은 방은 반영할 대화가 아니다
    if len(msgs) == 1 and "작업 내용 없음" in (msgs[0].get("body") or ""):
        return ""
    lines = []
    for m in msgs:
        who = "PM" if m["author"] == "pm" else "나(담당)"
        lines.append(f"- {who}: {(m['body'] or '')[:600]}")
    return "\n".join(lines)


USER_SAYS_MARK = "user_says_reflected:"   # alerts 설정 키 접두사 — 여기까지 반영했다는 표시
USER_SAYS_FIRST_DAYS = 10                # 처음 도입 시 거슬러 볼 날수(옛 질문 잡음 차단)


def pending_user_says(path: str) -> tuple[str, int]:
    """아직 기록장에 반영 안 된 **사용자 발언**을 날짜를 가로질러 모은다. (재료, 마지막 id)

    ★ 2026-09-12 사용자 지적: "구글 로그인 권한 관련해서 말한 게 전혀 다음으로 안 이어진다".
      실제로 사용자가 09-09 방에 "공개 해둠"이라고 답했는데, 반영 단계는 **그날 방만** 읽어서
      그 답이 기록장에 오르지 못했다. 다음 밤부터 PM은 옛 문서만 보고 같은 질문을 다시 했고,
      09-11·09-12까지 사흘을 같은 자리에서 맴돌았다.
      사용자 발언은 이 시스템에서 가장 값진 신호다 — 반영될 때까지 계속 따라다니게 한다.
    """
    from src.db import alerts as alerts_db
    from src.db import messages as messages_db

    try:
        after = int(alerts_db.get_setting(USER_SAYS_MARK + path) or 0)
    except (TypeError, ValueError):
        after = 0
    rows = messages_db.user_says_for_project(path, after)
    if not after:
        # 처음 도입되는 날 — 몇 달 치 옛 질문까지 끌어오면 잡음이다. 최근 것만 본다.
        cutoff = (datetime.now() - timedelta(days=USER_SAYS_FIRST_DAYS)).strftime("%Y-%m-%d")
        rows = [r for r in rows if (r.get("created_at") or "") >= cutoff]
    if not rows:
        return "", after
    lines = []
    for r in rows:
        when = (r.get("created_at") or "")[:10]
        lines.append(f"- [{when} 사용자] {(r.get('body') or '').strip()[:600]}")
    return "\n".join(lines), rows[-1]["id"]


def _dirty_files(path: str) -> set[str]:
    """git이 보는 변경 파일 목록(스테이징 여부 무관). 커밋 범위 산정용."""
    out = _git(path, "status", "--porcelain").stdout
    return {ln[3:].strip().strip('"') for ln in out.splitlines() if ln.strip()}


def _commit_changes(path: str, date: str, before: set[str], msg: str | None = None) -> dict:
    """에이전트 실행으로 **새로 바뀐 파일만** 커밋(push 안 함).

    before = 실행 전 변경 파일 스냅샷. 그 전부터 더러웠던 파일(사용자 작업 중)은
    스테이징하지 않는다 — 사용자 WIP가 에이전트 커밋에 섞이는 사고 방지.
    """
    if not (Path(path) / ".git").exists():
        return {"committed": False, "reason": "git 저장소 아님"}
    new_files = sorted(_dirty_files(path) - before)
    if not new_files:
        return {"committed": False, "reason": "새 변경 없음"}
    _git(path, "add", "--", *new_files)
    staged = _git(path, "diff", "--cached", "--name-only").stdout.strip()
    if not staged:
        return {"committed": False, "reason": "스테이징 실패"}
    msg = msg or f"chore: {date} 일간보고·게시판 반영 (ohmyPM 담당)"
    c = _git(path, "commit", "-m", msg)
    ok = c.returncode == 0
    if not ok:
        logger.warning(f"[조언반영] {path} 커밋 실패: {(c.stderr or '')[:160]}")
    return {"committed": ok, "files": staged.splitlines(), "msg": msg}


def _mentor_material() -> str:
    """점수 1위 멘토의 전문·배움 요약 — 조언 반영 때 참고로 얹는다(멘토 자동 자문, C층)."""
    m = agents_db.top_mentor()
    if not m:
        return ""
    bits = []
    if m.get("expertise"):
        bits.append(f"전문: {m['expertise']}")
    if m.get("note"):
        bits.append(f"배움: {m['note'][:300]}")
    if not bits:
        return ""
    return f"\n\n[멘토 {m.get('name') or '선배'}의 조언 — 참고]\n" + " / ".join(bits)


def reprocess_one(path: str, name: str, posts: list[dict], date: str) -> dict:
    """한 프로젝트: 받은 조언을 반영(반영처는 에이전트 판단) → 코드가 새 변경만 커밋 + 성장 기록. dict."""
    material = _material_for(path, posts)
    talk = daily_transcript(path, date)
    if talk:
        material = (material + "\n\n" if material.strip() else "") + \
            "[오늘 일간보고에서 PM과 나눈 대화 — 여기서 확정된 것은 기록장에 반드시 반영]\n" + talk
    # 사용자가 직접 한 말은 지난 날짜 것이라도 반영될 때까지 따라온다 — 맨 앞에 놓는다
    says, says_mark = pending_user_says(path)
    if says:
        material = ("[사용자가 직접 남긴 말 — 아직 기록장에 반영 안 됐다. 무엇보다 먼저 반영하라.\n"
                    " 사용자가 '했다/해뒀다'고 말한 것은 확인된 사실로 보고 해당 항목을 닫아라]\n"
                    + says + "\n\n" + material)
    if not material.strip():
        return {"name": name, "path": path, "skipped": True, "reason": "반영할 것 없음"}
    # 자기가 멘토가 아니면 점수 1위 멘토의 배움을 참고로 얹는다(멘토 자동 자문)
    if not agents_db.is_mentor(path):
        material += _mentor_material()
    allowed, disallowed = tools_for("reprocess")

    before = _dirty_files(path)   # 실행 전 스냅샷 — 사용자 WIP와 에이전트 변경을 구분
    out = run_headless(
        prompt=reprocess_docs(name, path, material),
        cwd=path,
        allowed_tools=allowed,
        disallowed_tools=disallowed,
        permission_mode="acceptEdits",   # 파일 저장 자동 승인(임의 명령은 애초에 도구가 없음)
        timeout=REPROCESS_TIMEOUT,
        append_system_prompt=REPROCESS_SYSTEM,
        model=agents_db.model_for(path),
    )
    # 사용자 발언 반영 표시 — 담당이 응답했을 때만 전진시킨다(무응답이면 내일 다시 물고 온다).
    # 응답했는데도 기록에 안 남기면 그대로 흘러가므로, 프롬프트에서 '먼저 반영하라'로 못박았다.
    if out and says:
        from src.db import alerts as alerts_db

        alerts_db.set_setting(USER_SAYS_MARK + path, str(says_mark))
    # 성장 기록 — 오늘 배운 것 한 줄을 프로필 note에 쌓는다(다음 콜에 다시 주어짐, A층)
    if out:
        m = _OBJ.search(out)
        if m:
            try:
                lesson = (json.loads(m.group(0)).get("lesson") or "").strip()
                if lesson:
                    agents_db.append_note(path, lesson)
            except json.JSONDecodeError:
                pass
    result = _commit_changes(path, date, before)
    return {"name": name, "path": path, "skipped": False, **result}


def run_reprocess(paths: list[str] | None = None) -> dict:
    """당일 일간보고 대화 + 게시판 조언을 각 담당이 자기 기록장에 반영(커밋, push 안 함)."""
    date = datetime.now().strftime("%Y-%m-%d")
    all_posts = board_db.list_posts(board_db.DAILY_BOARD)
    # ★ 오늘(day=date) 올라온 글만 재가공 대상 — 안 그러면 어제 조언을 매일 다시 반영해
    #   중복 커밋이 쌓인다(09-01 야간에 08-31 조언이 재처리된 버그). material도 오늘 글 기준.
    posts = [p for p in all_posts if p.get("day") == date]
    targets: dict[str, str] = {}
    for p in posts:
        if p.get("project") and p.get("comments"):
            targets.setdefault(p["project"], p["author"])
    # 게시판 조언이 없어도 **오늘 일간보고 대화가 있으면** 반영 대상이다(2026-09-09).
    #   대화에서 정한 기한·상태가 기록장에 안 남으면 다음 스캔이 옛 문서를 다시 읽어 원위치한다.
    from src.db import projects as projects_db

    for q in projects_db.list_projects(enabled_only=True):
        if q["path"] in targets:
            continue
        # 오늘 대화가 없어도, 미반영 사용자 발언이 남아 있으면 반영 대상이다(2026-09-12)
        if daily_transcript(q["path"], date) or pending_user_says(q["path"])[0]:
            targets[q["path"]] = q["name"]
    if paths:
        wanted = set(paths)
        targets = {k: v for k, v in targets.items() if k in wanted}
    # ★ 기록 자동 반영이 켜진 프로젝트만(2026-09-17 사용자 확정 — 기본 끔, 룸에서 프로젝트별 켜기)
    from src.db import alerts as alerts_db

    targets = {k: v for k, v in targets.items() if alerts_db.docs_autowrite(k)}

    committed, results = 0, []
    for path, name in targets.items():
        try:
            r = reprocess_one(path, name, posts, date)
        except Exception as e:  # 한 프로젝트 실패가 전체를 안 멈춤
            logger.warning(f"[재가공] {name} 실패: {e}")
            r = {"name": name, "path": path, "skipped": False, "committed": False, "reason": str(e)}
        results.append(r)
        if r.get("committed"):
            committed += 1
    logger.info(f"[조언반영] {committed}개 프로젝트 커밋(push 안 함)")
    return {"committed": committed, "results": results}
