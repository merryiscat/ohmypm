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


@router.get("/agents")
def get_agents() -> list[dict]:
    """담당 에이전트 리더보드 — 게시판 점수 재계산 + 프로필(이름·페르소나·보상). 점수 높은 순."""
    from src.db import agents as agents_db

    projs = projects_db.list_projects(enabled_only=True)
    agents_db.refresh_scores({p["path"]: p["name"] for p in projs})
    out = []
    for p in projs:
        prof = agents_db.get_profile(p["path"]) or {}
        pts = prof.get("points", 0) or 0
        out.append({
            "project": p["path"],
            "name": prof.get("name") or p["name"],
            "points": pts,
            "persona": prof.get("persona"),
            "reward": prof.get("reward"),
            "wish": prof.get("wish"),
            "tier": 2 if pts >= agents_db.MILESTONE_WISH else (1 if pts >= agents_db.MILESTONE_MENU else 0),
        })
    out.sort(key=lambda x: x["points"], reverse=True)
    return out


@router.post("/rewards")
def trigger_rewards(background: BackgroundTasks) -> dict:
    """보상 처리 수동 트리거 — 1000점↑ 담당에게 보상 선택, 2000점↑ 소원권."""
    from src.cc.rewards import run_rewards

    background.add_task(run_rewards)
    return {"ok": True, "started": True}


class ProjectPath(BaseModel):
    path: str


@router.post("/projects/remove")
def remove_project(p: ProjectPath) -> dict:
    """프로젝트를 관리에서 제외 — 비활성(enabled=0, 재스캔 재등장 방지) + 관련 데이터 정리
    (이슈·게시판 글/댓글·대화 방). 폴더 자체는 건드리지 않는다."""
    projects_db.set_enabled(p.path, False)
    issues = issues_db.delete_by_project(p.path)
    posts = board_db.delete_by_project(p.path)
    messages_db.delete_for_project(p.path)
    return {"ok": True, "disabled": p.path, "issues_deleted": issues, "posts_deleted": posts}


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


@router.get("/daily")
def get_daily() -> list[dict]:
    """일간보고 트리 — [{date, projects:[{project, name, room}]}], 최신 날짜 먼저.

    방 키 daily::{date}::{path} 를 날짜·프로젝트로 묶는다. 대화는 /api/messages?room=<room>로.
    """
    names = {p["path"]: p["name"] for p in projects_db.list_projects(enabled_only=False)}
    by_date: dict[str, list[dict]] = {}
    for room in messages_db.list_rooms_like("daily::"):
        try:
            _, date, path = room.split("::", 2)
        except ValueError:
            continue
        by_date.setdefault(date, []).append(
            {"project": path, "name": names.get(path, path), "room": room}
        )
    return [
        {"date": d, "projects": sorted(by_date[d], key=lambda x: x["name"].lower())}
        for d in sorted(by_date, reverse=True)
    ]


# ── PM 대화 패널 (사용자 ↔ 총괄 PM, 일간보고 화면 오른쪽) ─────────────────────
class PmChatMsg(BaseModel):
    message: str


@router.post("/pm-chat")
def pm_chat_api(m: PmChatMsg, background: BackgroundTasks) -> dict:
    """사용자가 PM에게 말하면 즉시 방에 기록, PM 답변은 백그라운드(저널+게시판 근거)로."""
    from src.cc.manager import PM_CHAT_ROOM, pm_chat_reply

    body = m.message.strip()
    if not body:
        return {"ok": False, "error": "빈 메시지"}
    messages_db.add_message(PM_CHAT_ROOM, "user", body)
    background.add_task(pm_chat_reply)
    return {"ok": True, "started": True, "room": PM_CHAT_ROOM}


# ── PM 온보딩 검토 (프로젝트 초기 세팅·하네스 read-only 점검) ─────────────────
class OnboardReq(BaseModel):
    path: str


@router.post("/onboarding")
def trigger_onboarding(req: OnboardReq, background: BackgroundTasks) -> dict:
    """PM이 그 프로젝트 세팅·하네스를 read-only로 점검(백그라운드). 리포트는 담당 방에 뜬다."""
    proj = next((p for p in projects_db.list_projects() if p["path"] == req.path), None)
    if not proj:
        return {"ok": False, "error": "unknown project"}
    from src.cc.onboarding import review_project

    background.add_task(review_project, proj["path"], proj["name"])
    return {"ok": True, "started": True}


# ── 전문가 에이전트 (ohmyPM 상주, 웹 지식수집 + PM 자문) ────────────────────
@router.get("/experts")
def get_experts() -> list[dict]:
    """사내 전문가 명부 + 위키 상태."""
    from src.cc import expert as ex

    out = []
    for domain, meta in ex.EXPERTS.items():
        wiki = ex.read_wiki(domain)
        out.append({"domain": domain, "name": meta["name"], "topic": meta["topic"],
                    "wiki_chars": len(wiki)})
    return out


@router.get("/experts/{domain}/wiki")
def get_expert_wiki(domain: str) -> dict:
    """전문가 지식 위키 본문."""
    from src.cc import expert as ex

    return {"domain": domain, "wiki": ex.read_wiki(domain)}


@router.post("/experts/{domain}/collect")
def collect_expert(domain: str, background: BackgroundTasks) -> dict:
    """전문가가 웹으로 최신 지식을 수집해 위키 갱신(백그라운드)."""
    from src.cc.expert import EXPERTS, collect_knowledge

    if domain not in EXPERTS:
        return {"ok": False, "error": "unknown expert"}
    background.add_task(collect_knowledge, domain)
    return {"ok": True, "started": True}


class ExpertQ(BaseModel):
    question: str


@router.post("/experts/{domain}/ask")
def ask_expert_api(domain: str, q: ExpertQ, background: BackgroundTasks) -> dict:
    """전문가에게 질문 — 질문은 즉시 방에 기록, 답변은 백그라운드(위키+웹)로."""
    from src.cc.expert import EXPERTS, ask_expert, expert_room

    if domain not in EXPERTS:
        return {"ok": False, "error": "unknown expert"}
    body = q.question.strip()
    if not body:
        return {"ok": False, "error": "빈 질문"}
    messages_db.add_message(expert_room(domain), "user", body)
    background.add_task(ask_expert, domain, body)
    return {"ok": True, "started": True}


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
    # 등록 안 됐지만 지금 떠 있는 개발 서버(python·node 등)를 자동 감지해 보여준다
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
    """글 좋아요 +1."""
    board_db.like_post(post_id)
    return {"ok": True}


class Reaction(BaseModel):
    reaction: str   # 'like' | 'dislike'


@router.post("/comments/{comment_id}/react")
def react_comment(comment_id: int, r: Reaction) -> dict:
    """댓글 좋아요/싫어요."""
    if r.reaction not in ("like", "dislike"):
        return {"ok": False, "error": "reaction은 like/dislike"}
    board_db.react_comment(comment_id, r.reaction)
    return {"ok": True}


class BoardDiscussionReq(BaseModel):
    paths: list[str] | None = None


@router.post("/board-discussion")
def trigger_board_discussion(background: BackgroundTasks, cfg: BoardDiscussionReq | None = None) -> dict:
    """게시판 토론(4단계) 수동 트리거 — 담당들이 관심 있는 글에 댓글. posts/comments에 쌓인다."""
    cfg = cfg or BoardDiscussionReq()
    from src.cc.daily_report import run_board_discussion

    background.add_task(run_board_discussion, paths=cfg.paths)
    return {"ok": True, "started": True}


@router.post("/post-feedback")
def trigger_post_feedback(background: BackgroundTasks, cfg: BoardDiscussionReq | None = None) -> dict:
    """글쓴이 자동 반응(1b) 수동 트리거 — 글쓴이가 자기 글 댓글에 좋아요/싫어요/대댓글."""
    cfg = cfg or BoardDiscussionReq()
    from src.cc.daily_report import run_post_feedback

    background.add_task(run_post_feedback, paths=cfg.paths)
    return {"ok": True, "started": True}
