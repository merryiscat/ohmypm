"""대시보드 데이터 API (JSON). 화면 JS가 이걸 fetch해 카드를 그린다."""

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from src.db import board as board_db
from src.db import issues as issues_db
from src.db import messages as messages_db
from src.db import ports as ports_db
from src.db import projects as projects_db

router = APIRouter(prefix="/api")


@router.get("/projects")
def get_projects() -> list[dict]:
    """관리 대상 프로젝트 목록."""
    return projects_db.list_projects()


@router.get("/issues")
def get_issues(status: str | None = None) -> list[dict]:
    """이슈 목록(선택: 상태 필터). 기한 임박순."""
    return issues_db.list_issues(status)


class StatusUpdate(BaseModel):
    status: str


@router.post("/issues/{issue_id}/status")
def update_issue_status(issue_id: int, upd: StatusUpdate) -> dict:
    """칸반 열 이동 = 이슈 status 변경. open/consulting/resolved/deferred만 허용."""
    if upd.status not in ("open", "consulting", "resolved", "deferred"):
        return {"ok": False, "error": f"알 수 없는 상태: {upd.status}"}
    issues_db.set_status(issue_id, upd.status)
    return {"ok": True}


@router.post("/scan")
def trigger_scan() -> dict:
    """수동 스캔 트리거(대시보드 '스캔' 버튼). 빠른 결정론 수집만 — 판정은 별도."""
    from src.scan import run_scan

    return run_scan()


@router.post("/judge")
def trigger_judge() -> dict:
    """수동 판정 트리거(대시보드 '판정' 버튼). 미판정 기한 후보를 에이전트가 가린다.

    LLM 호출이라 느릴 수 있음 — 스캔과 분리해 즉시 피드백을 안 막는다.
    """
    from src.cc.judge import run_judgment

    return run_judgment()


# ── 메시지 보드 (에이전트 채팅방 + 프로젝트 룸) ───────────────────────────


@router.get("/messages")
def get_messages(room: str = messages_db.GLOBAL_ROOM) -> list[dict]:
    """방의 대화 목록. room 미지정이면 전체 채팅방('global')."""
    return messages_db.list_messages(room)


class PostMessage(BaseModel):
    room: str = messages_db.GLOBAL_ROOM
    author: str = "user"
    body: str


@router.post("/messages")
def post_message(msg: PostMessage, background: BackgroundTasks) -> dict:
    """방에 글 한 줄 추가. 프로젝트 룸에서 사용자가 말하면 그 프로젝트 담당 에이전트가 답한다.

    담당 에이전트 응답은 headless Claude 호출이라 느리다 → 백그라운드로 돌리고
    화면은 폴링으로 답을 받는다(HTTP 응답을 막지 않음).
    """
    body = msg.body.strip()
    if not body:
        return {"ok": False, "error": "빈 메시지"}
    row = messages_db.add_message(msg.room, msg.author, body)
    # 프로젝트 룸(room=프로젝트 path)에서 사용자 발화면 → 담당 에이전트 응답 예약
    if msg.author == "user" and msg.room != messages_db.GLOBAL_ROOM:
        proj = next((p for p in projects_db.list_projects() if p["path"] == msg.room), None)
        if proj:
            from src.cc.room_agent import reply_in_room

            background.add_task(reply_in_room, proj["path"], proj["name"])
    return {"ok": True, "message": row}


# ── 포트 레지스트리 (1단계: 표시·충돌 감지, 읽기 전용) ──────────────────────
@router.get("/ports")
def get_ports() -> dict:
    """등록 포트 + 실시간 점유 상태(UP/PID) + 충돌(같은 포트 여러 프로젝트)."""
    from src.portscan import listening_ports

    regs = ports_db.list_ports()
    live = listening_ports()
    names = {p["path"]: p["name"] for p in projects_db.list_projects(enabled_only=False)}
    rows, by_port = [], {}
    for r in regs:
        info = live.get(r["port"])
        rows.append({
            **r, "name": names.get(r["project"], r["project"]),
            "up": info is not None,
            "pid": info["pid"] if info else None,
            "proc": info["proc"] if info else None,
        })
        by_port.setdefault(r["port"], []).append(names.get(r["project"], r["project"]))
    conflicts = [{"port": p, "projects": ns} for p, ns in by_port.items() if len(ns) > 1]
    return {"rows": rows, "conflicts": conflicts}


class PortReg(BaseModel):
    project: str          # 프로젝트 path
    port: int
    label: str = ""
    start_cmd: str = ""


@router.post("/ports")
def register_port(reg: PortReg) -> dict:
    """포트 등록/갱신."""
    if not (0 < reg.port < 65536):
        return {"ok": False, "error": "포트 범위 오류"}
    row = ports_db.register(reg.project, reg.port, reg.label.strip(), reg.start_cmd.strip())
    return {"ok": True, "port": row}


@router.delete("/ports/{port_id}")
def delete_port(port_id: int) -> dict:
    """포트 등록 삭제."""
    ports_db.delete(port_id)
    return {"ok": True}


class DailyReportReq(BaseModel):
    paths: list[str] | None = None   # 지정 시 그 프로젝트만(테스트). None=전체
    max_rounds: int = 8
    notify: bool = True              # 텔레그램 종합 발송 여부


@router.post("/daily-report")
def trigger_daily_report(background: BackgroundTasks, cfg: DailyReportReq | None = None) -> dict:
    """일간보고 수동 트리거. 오래 걸리는 headless 오케스트레이션이라 백그라운드로 돌리고,
    진행/결과는 '일간보고' 방(room='daily')에 쌓인다(사이드바에서 확인)."""
    cfg = cfg or DailyReportReq()
    from src.cc.daily_report import run_daily_report

    background.add_task(
        run_daily_report,
        paths=cfg.paths,
        max_rounds=cfg.max_rounds,
        notify=cfg.notify,
    )
    return {"ok": True, "started": True}


@router.get("/posts")
def get_posts(board: str = board_db.DAILY_BOARD) -> list[dict]:
    """게시판 글 목록(각 글에 comments 배열 포함). 화면 '게시판'이 이걸 그린다."""
    return board_db.list_posts(board)


@router.get("/posts/{post_id}")
def get_post(post_id: int) -> dict:
    """글 하나 + 댓글(글 상세 화면)."""
    return board_db.get_post(post_id) or {}


class PostComment(BaseModel):
    author: str = "user"     # 화면에서 달면 사용자. 에이전트 토론은 담당명으로 들어감
    body: str


@router.post("/posts/{post_id}/comments")
def add_post_comment(post_id: int, c: PostComment) -> dict:
    """글에 댓글 달기(사용자도 가능)."""
    body = c.body.strip()
    if not body:
        return {"ok": False, "error": "빈 댓글"}
    row = board_db.add_comment(post_id, c.author, body)
    return {"ok": True, "comment": row}


class BoardDiscussionReq(BaseModel):
    paths: list[str] | None = None


@router.post("/board-discussion")
def trigger_board_discussion(background: BackgroundTasks, cfg: BoardDiscussionReq | None = None) -> dict:
    """게시판 토론(4단계) 수동 트리거 — 담당들이 관심 있는 글에 댓글. posts/comments에 쌓인다."""
    cfg = cfg or BoardDiscussionReq()
    from src.cc.daily_report import run_board_discussion

    background.add_task(run_board_discussion, paths=cfg.paths)
    return {"ok": True, "started": True}
