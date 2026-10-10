"""대시보드 데이터 API (JSON). 화면 JS가 이걸 fetch해 그린다."""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.db import board as board_db
from src.db import cards as cards_db
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
    cards_db.delete_for_project(p.path)
    return {"ok": True, "disabled": p.path, "posts_deleted": posts}


# ── 칸반 카드 ─────────────────────────────────────────────────────────────────
# PM(주간보고)·담당(채팅)은 src/cc/cards.py로, 사용자는 여기 API로 카드를 만들고 옮긴다.
@router.get("/cards")
def get_cards(project: str) -> dict:
    """이 프로젝트의 카드 전부 + 칸 목록(화면이 칸 이름·순서를 여기서 받는다)."""
    return {"statuses": [{"key": k, "label": v} for k, v in cards_db.STATUSES],
            "cards": cards_db.list_cards(project)}


class CardNew(BaseModel):
    project: str
    title: str
    status: str = "todo"
    note: str | None = None
    due: str | None = None


@router.post("/cards")
def add_card(c: CardNew) -> dict:
    title = c.title.strip()
    if not title:
        return {"ok": False, "error": "제목이 비었습니다"}
    return {"ok": True, "card": cards_db.add_card(c.project, title[:200], c.status, c.note, c.due, "user")}


class CardEdit(BaseModel):
    title: str | None = None
    note: str | None = None
    status: str | None = None
    due: str | None = None


@router.post("/cards/{card_id}")
def edit_card(card_id: int, c: CardEdit) -> dict:
    """준 필드만 고친다. due를 빈 문자열로 주면 기한을 지운다."""
    fields = c.model_dump(exclude_unset=True)
    card = cards_db.update_card(card_id, **fields)
    return {"ok": bool(card), "card": card} if card else {"ok": False, "error": "없는 카드이거나 잘못된 칸"}


@router.delete("/cards/{card_id}")
def remove_card(card_id: int) -> dict:
    return {"ok": cards_db.delete_card(card_id)}


@router.post("/scan")
def trigger_scan() -> dict:
    """스캔 = 프로젝트 발견 + 각 프로젝트에 ohmypm/ 설치(대시보드 '스캔' 버튼). 파일 작업뿐이라 동기."""
    from src.scan import run_scan

    return run_scan()


@router.post("/projects/install")
def install_one(p: ProjectPath) -> dict:
    """프로젝트 하나에 ohmypm/ 폴더와 지침 블록을 설치(룸의 '설치' 버튼). 멱등."""
    from src.install import install_project
    from src.scan.discover import discover_projects

    try:
        r = install_project(p.path)
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}
    discover_projects()    # installed 표시 갱신
    return {"ok": True, **r}


@router.post("/projects/uninstall")
def uninstall_one(p: ProjectPath) -> dict:
    """프로젝트에서 ohmypm/ 폴더와 지침 블록만 제거(룸의 '설치 제거' 버튼)."""
    from src.install import uninstall_project
    from src.scan.discover import discover_projects

    r = uninstall_project(p.path)
    discover_projects()
    return {"ok": True, **r}


@router.get("/jobs/{name}")
def job_status(name: str) -> dict:
    """백그라운드 작업 상태(주간보고·랩실 조사). 화면이 폴링한다."""
    from src import jobs

    return jobs.status(name)


# ── 주간보고 ────────────────────────────────────────────────────────────────
@router.get("/weekly")
def get_weekly() -> list[dict]:
    """주간보고 목록 — [{date, overall_room, projects:[{project, name, room, written}]}], 최신 먼저."""
    from src.cc.weekly_report import list_reports

    return list_reports()


@router.post("/weekly/run")
def run_weekly() -> dict:
    """주간보고 실행(백그라운드, 몇 분). 상태는 /api/jobs/weekly."""
    from src import jobs
    from src.cc.weekly_report import JOB_NAME, run_weekly_report

    if not jobs.start(JOB_NAME, run_weekly_report):
        return {"ok": False, "error": "주간보고가 이미 작성 중입니다"}
    return {"ok": True, "started": True}


# ── 랩실 ──────────────────────────────────────────────────────────────────
@router.get("/lab")
def get_lab() -> list[dict]:
    """연구원 명부 + 위키 크기·마지막 조사·진행 여부."""
    from src.cc import lab

    return lab.list_researchers()


@router.get("/lab/{rid}/wiki")
def get_lab_wiki(rid: str) -> dict:
    """연구원 위키(모델 연구원은 벤더별 탭 2개)."""
    from src.cc import lab

    return {"tabs": lab.wiki_tabs(rid)}


@router.get("/lab/{rid}/notes")
def get_lab_notes(rid: str) -> list[dict]:
    from src.cc import lab

    return lab.research_notes(rid)


@router.get("/lab/{rid}/notes/{key}/assets/{filename}")
def get_lab_note_asset(rid: str, key: str, filename: str) -> FileResponse:
    from src.cc import lab

    note = next((n for n in lab.research_notes(rid) if n["key"] == key), None)
    if note and any(a["name"] == filename for a in note["assets"]):
        path = lab.note_file(rid, filename)
        if path:
            return FileResponse(path)
    raise HTTPException(status_code=404, detail="첨부 파일을 찾을 수 없습니다")


@router.post("/lab/{rid}/run")
def run_lab(rid: str) -> dict:
    """연구원 조사 실행(백그라운드, 웹 조사라 몇 분). 상태는 /api/lab."""
    from src import jobs
    from src.cc import lab

    if rid not in lab.RESEARCHERS:
        return {"ok": False, "error": "unknown researcher"}
    if not jobs.start(lab.job_name(rid), lab.research, rid):
        return {"ok": False, "error": "이미 조사 중입니다"}
    return {"ok": True, "started": True}


class LabQ(BaseModel):
    question: str


@router.post("/lab/{rid}/ask")
def ask_lab(rid: str, q: LabQ, background: BackgroundTasks) -> dict:
    """연구원에게 질문 — 질문은 즉시 방에 기록, 답은 백그라운드."""
    from src.cc import lab

    if rid not in lab.RESEARCHERS:
        return {"ok": False, "error": "unknown researcher"}
    body = q.question.strip()
    if not body:
        return {"ok": False, "error": "빈 질문"}
    messages_db.add_message(lab.lab_room(rid), "user", body)
    background.add_task(lab.ask, rid, body)
    return {"ok": True, "started": True}


@router.get("/lab/proposals")
def get_proposals(researcher: str | None = None, project: str | None = None) -> list[dict]:
    """제안서 목록. project를 주면 그 프로젝트 대상 + 전체 대상."""
    from src.cc import lab
    from src.db import lab as lab_db

    names = {p["path"]: p["name"] for p in projects_db.list_projects(enabled_only=False)}
    out = lab_db.list_proposals(researcher, project)
    for r in out:
        r["researcher_name"] = lab.RESEARCHERS.get(r["researcher"], {}).get("name", r["researcher"])
        r["target_name"] = names.get(r["target_project"] or "", "") or (r["target_project"] or "")
    return out


class ProposalStatus(BaseModel):
    status: str   # open | done | dismissed


@router.post("/lab/proposals/{pid}/status")
def set_proposal_status(pid: int, s: ProposalStatus) -> dict:
    from src.db import lab as lab_db

    if not lab_db.set_status(pid, s.status):
        return {"ok": False, "error": "상태는 open/done/dismissed"}
    return {"ok": True}


# ── 게시판 토론 세션 ────────────────────────────────────────────────────────
class SessionReq(BaseModel):
    minutes: int = 30
    paths: list[str] | None = None   # 지정하면 그 프로젝트들만(테스트용)


@router.post("/board/session")
def start_session(req: SessionReq) -> dict:
    """토론 시작 — 담당들이 정한 시간 동안 글쓰기→둘러보기→반응→대대댓글→복기를 돈다(백그라운드 스레드)."""
    from src.cc import board_session

    return board_session.start(req.minutes, req.paths)


@router.get("/board/session")
def get_session() -> dict | None:
    """최근 세션 상태(+남은 시간). 없으면 null."""
    from src.cc import board_session

    return board_session.current()


@router.post("/board/session/stop")
def stop_session() -> dict:
    """진행 중인 토론에 중지 신호 — 도는 호출은 끝까지 가고 새 호출만 멈춘다."""
    from src.cc import board_session

    return board_session.stop()


@router.get("/board/sessions")
def list_sessions(limit: int = 20) -> list[dict]:
    """토론 이력(최신 먼저)."""
    return sessions_db.list_sessions(limit)


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
    # 미등록인데 떠 있는 포트는 운영체제 서비스만 빼고 전부 — 명령줄 경로로 맞춘 프로젝트가 있으면 먼저
    from src.portscan import SYSTEM_PROCS

    registered_ports = set(by_port.keys())
    detected = []
    for port, info in live.items():
        if port in registered_ports or (info.get("proc") or "").lower() in SYSTEM_PROCS:
            continue
        detected.append({"port": port, "pid": info["pid"], "proc": info["proc"],
                         "cmdline": (info.get("cmdline") or "")[:160],
                         "project": info.get("project"),
                         "project_name": names.get(info.get("project") or "", "") or
                                         ("ohmyPM" if info.get("project") and not names.get(info["project"]) else "")})
    detected.sort(key=lambda x: (0 if x["project"] else 1, x["port"]))
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
