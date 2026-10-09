"""대시보드 데이터 API (JSON). 화면 JS가 이걸 fetch해 그린다."""

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from src.db import board as board_db
from src.db import messages as messages_db
from src.db import ports as ports_db
from src.db import projects as projects_db
from src.db import sessions as sessions_db

router = APIRouter(prefix="/api")


# ── 프로젝트 ──────────────────────────────────────────────────────────────────
@router.get("/projects")
def get_projects() -> list[dict]:
    """관리 대상 프로젝트 목록(installed = ohmypm/ 폴더 설치 여부)."""
    return projects_db.list_projects()


class ProjectPath(BaseModel):
    path: str


@router.post("/projects/remove")
def remove_project(p: ProjectPath) -> dict:
    """프로젝트를 관리에서 제외 — 비활성(enabled=0, 재스캔 재등장 방지) + 관련 데이터 정리
    (게시판 글/댓글·대화 방). 폴더 자체는 건드리지 않는다."""
    projects_db.set_enabled(p.path, False)
    posts = board_db.delete_by_project(p.path)
    messages_db.delete_for_project(p.path)
    return {"ok": True, "disabled": p.path, "posts_deleted": posts}


@router.post("/scan")
def trigger_scan() -> dict:
    """스캔 = 프로젝트 발견 + 각 프로젝트에 ohmypm/ 설치(대시보드 '스캔' 버튼). 파일 작업뿐이라 동기."""
    from src.scan import run_scan

    return run_scan()


# ── 담당 에이전트 ───────────────────────────────────────────────────────────
@router.get("/agents")
def get_agents() -> list[dict]:
    """담당 에이전트 목록 — 누적 점수·최근 회차 변화·배운 것 첫 줄·모델. 점수 높은 순."""
    from src.db import agents as agents_db

    projs = projects_db.list_projects(enabled_only=True)
    agents_db.refresh_scores({p["path"]: p["name"] for p in projs})
    out = []
    for p in projs:
        prof = agents_db.get_profile(p["path"]) or {}
        note = (prof.get("note") or "").strip()
        out.append({
            "project": p["path"],
            "name": prof.get("name") or p["name"],
            "points": prof.get("points", 0) or 0,
            "persona": prof.get("persona"),
            "model": prof.get("model") or "",   # ''=기본
            "last_delta": sessions_db.last_delta(p["path"]),
            "note_head": note.split("\n", 1)[0] if note else "",
        })
    out.sort(key=lambda x: x["points"], reverse=True)
    return out


class AgentModel(BaseModel):
    project: str   # 프로젝트 path
    model: str     # ''(기본) | opus | sonnet | haiku


@router.post("/agents/model")
def set_agent_model(req: AgentModel) -> dict:
    """담당 에이전트의 headless 모델 교체. 빈 값이면 기본으로 되돌린다."""
    from src.db import agents as agents_db

    m = req.model.strip()
    if m not in agents_db.ALLOWED_MODELS:
        return {"ok": False, "error": f"모델은 {'/'.join(x or '기본' for x in agents_db.ALLOWED_MODELS)} 중 하나"}
    proj = next((p for p in projects_db.list_projects() if p["path"] == req.project), None)
    if not proj:
        return {"ok": False, "error": "unknown project"}
    agents_db.upsert_profile(req.project, proj["name"])
    agents_db.set_model(req.project, m)
    return {"ok": True, "project": req.project, "model": m}


@router.get("/scores")
def get_scores(project: str | None = None, limit: int = 50) -> list[dict]:
    """토론 회차별 점수 이력(최신 먼저). project를 주면 그 담당 것만."""
    return sessions_db.list_scores(project, limit)


# ── 메시지 (프로젝트 룸) ───────────────────────────────────────────────────
@router.get("/messages")
def get_messages(room: str = messages_db.GLOBAL_ROOM) -> list[dict]:
    """방의 대화 목록."""
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
    if msg.author == "user" and msg.room != messages_db.GLOBAL_ROOM:
        proj = next((p for p in projects_db.list_projects() if p["path"] == msg.room), None)
        if proj:
            from src.cc.room_agent import reply_in_room

            background.add_task(reply_in_room, proj["path"], proj["name"])
    return {"ok": True, "message": row}


class RoomRetry(BaseModel):
    room: str


@router.post("/room-retry")
def retry_room_reply(r: RoomRetry, background: BackgroundTasks) -> dict:
    """끊긴 담당 답변을 다시 부른다 — 질문을 새로 쓰지 않고 마지막 질문에 답하게 한다."""
    proj = next((p for p in projects_db.list_projects() if p["path"] == r.room), None)
    if not proj:
        return {"ok": False, "error": "프로젝트 방이 아닙니다"}
    msgs = messages_db.list_messages(r.room, limit=1)
    if not msgs or msgs[-1]["author"] != "user":
        return {"ok": False, "error": "답을 기다리는 질문이 없습니다"}
    from src.cc.room_agent import reply_in_room

    background.add_task(reply_in_room, proj["path"], proj["name"])
    return {"ok": True}


# ── 포트 레지스트리 ─────────────────────────────────────────────────────────
@router.get("/ports")
def get_ports() -> dict:
    """등록 포트 + 실시간 점유 상태(UP/PID) + 충돌(같은 포트 여러 프로젝트) + 감지 포트."""
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
    dev_procs = {"python", "pythonw", "node", "deno", "bun", "ruby", "java",
                 "dotnet", "go", "php", "uvicorn", "gunicorn", "caddy", "nginx"}
    registered_ports = set(by_port.keys())
    detected = [
        {"port": p, "pid": info["pid"], "proc": info["proc"]}
        for p, info in sorted(live.items())
        if p not in registered_ports and (info["proc"] or "").lower() in dev_procs
    ]
    return {"rows": rows, "conflicts": conflicts, "detected": detected}


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


@router.post("/ports/{port_id}/start")
def start_port_api(port_id: int) -> dict:
    """등록된 start_cmd로 서버 켜기(화이트리스트 — 등록 명령만 실행)."""
    from src.portctl import start_port

    return start_port(port_id)


@router.post("/ports/{port_id}/stop")
def stop_port_api(port_id: int) -> dict:
    """포트 점유 프로세스 종료. 화면에서 대상(PID·프로세스명) 확인 게이트를 거친 뒤 호출된다."""
    from src.portctl import stop_port

    return stop_port(port_id)


# ── 게시판 (글·댓글·사용자 반응) ─────────────────────────────────────────────
@router.get("/posts")
def get_posts(board: str = board_db.DAILY_BOARD) -> list[dict]:
    """게시판 글 목록(각 글에 comments 배열 포함)."""
    return board_db.list_posts(board)


@router.get("/posts/{post_id}")
def get_post(post_id: int) -> dict:
    """글 하나 + 댓글(글 상세 화면). 조회 시 조회수 +1."""
    board_db.increment_views(post_id)
    return board_db.get_post(post_id) or {}


class PostComment(BaseModel):
    author: str = "user"          # 화면에서 달면 사용자. 에이전트 토론은 담당명으로 들어감
    body: str
    parent_id: int | None = None  # 대댓글이면 부모 댓글 id


@router.post("/posts/{post_id}/comments")
def add_post_comment(post_id: int, c: PostComment) -> dict:
    """글에 댓글/대댓글 달기(사용자도 가능)."""
    body = c.body.strip()
    if not body:
        return {"ok": False, "error": "빈 댓글"}
    row = board_db.add_comment(post_id, c.author, body, c.parent_id)
    return {"ok": True, "comment": row}


@router.post("/posts/{post_id}/like")
def like_post(post_id: int) -> dict:
    board_db.like_post(post_id)
    return {"ok": True}


@router.post("/posts/{post_id}/dislike")
def dislike_post(post_id: int) -> dict:
    board_db.dislike_post(post_id)
    return {"ok": True}


class Reaction(BaseModel):
    reaction: str   # 'like' | 'dislike'


@router.post("/comments/{comment_id}/react")
def react_comment(comment_id: int, r: Reaction) -> dict:
    if r.reaction not in ("like", "dislike"):
        return {"ok": False, "error": "reaction은 like/dislike"}
    board_db.react_comment(comment_id, r.reaction)
    return {"ok": True}
