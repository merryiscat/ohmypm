"""주간보고 — 지난 7일 커밋을 모아 "이번 주 뭘 했나" 한 장 보고 (유스케이스 10).

博客园 주보 패턴을 따른다: **수집은 결정론적 코드(git log), LLM은 요약만**.
어떤 커밋을 셀지 코드가 정하므로 결과가 들쭉날쭉하지 않고, LLM에는 정리된 팩트만
넘어가 토큰도 아낀다.

2026-10-08 첫 구현. 정시 배치는 걸지 않는다 — 2026-10-07 배치 축소 결정(수동 실행만)과
같은 방향. 결과는 반환하고, 주간보고 방(messages room='weekly::{날짜}')에도 저장해
나중에 다시 볼 수 있게 한다.
"""

import subprocess
from datetime import datetime

from loguru import logger

from src.cc.client import run_headless_ex
from src.cc.daily_report import _tool_commit  # 도구 커밋(ohmypm 등) 판정을 일간보고와 공유
from src.cc.permissions import tools_for
from src.cc.room_agent import _neutral_cwd
from src.config.settings import ensure_env
from src.db import messages as messages_db
from src.proc import NO_WINDOW
from src.scan.discover import discover_projects

DAYS = 7            # 보고가 덮는 기간(일)
GIT_TIMEOUT = 30    # 프로젝트 하나의 git log 제한 시간(초)
LLM_TIMEOUT = 300   # 요약 호출 제한 시간(초)

# LLM에 주는 역할 지시 — 요약만 시키고, 쉬운 말·이모지 금지 등 출력 규칙을 못박는다.
WEEKLY_SYSTEM = (
    "너는 여러 로컬 프로젝트를 돌보는 PM의 주간보고 작성자다. "
    "입력으로 받은 커밋 팩트만 근거로 쓰고, 없는 일을 지어내지 않는다. "
    "비개발자가 읽는 보고다 — 쉬운 말로, 내부 용어·파일명을 문장의 주어로 쓰지 않는다. "
    "이모지는 쓰지 않는다. 출력은 마크다운."
)


def collect_weekly_commits(days: int = DAYS) -> list[dict]:
    """프로젝트별 최근 N일 커밋 제목을 모은다(결정론 수집 — LLM 없음).

    반환: [{path, name, commits: ["10-05 커밋제목", ...]}] — 커밋 없는 프로젝트도
    빈 목록으로 포함한다(조용한 프로젝트가 소리 없이 사라지지 않게, 놓침0 원칙).
    git 저장소가 아닌 폴더는 git log가 실패하므로 빈 목록 처리.
    도구가 남긴 커밋(ohmypm 등 표식)은 사람 활동이 아니므로 뺀다 — 일간보고와 같은 기준.
    """
    ensure_env()  # .env 없으면 기본값 생성(2026-10-07 자가복구) — 스캔과 같은 안전망
    result: list[dict] = []
    for p in discover_projects():
        commits: list[str] = []
        try:
            r = subprocess.run(
                ["git", "log", f"--since={days} days ago",
                 "--pretty=format:%ad %s", "--date=format:%m-%d"],
                cwd=p["path"], capture_output=True, text=True, timeout=GIT_TIMEOUT,
                encoding="utf-8", errors="replace", creationflags=NO_WINDOW,
            )
            if r.returncode == 0:
                for line in (r.stdout or "").splitlines():
                    line = line.strip()
                    # "MM-DD 제목" 꼴 — 제목 부분만 도구 커밋 판정에 넘긴다
                    subject = line.split(" ", 1)[1] if " " in line else line
                    if line and not _tool_commit(subject):
                        commits.append(line)
        except Exception as e:
            logger.warning(f"[주간보고] {p['name']} 커밋 수집 실패: {e}")
        result.append({"path": p["path"], "name": p["name"], "commits": commits})
    total = sum(len(x["commits"]) for x in result)
    logger.info(f"[주간보고] 수집 — 프로젝트 {len(result)}개 · 커밋 {total}건 (최근 {days}일)")
    return result


def _facts_text(collected: list[dict]) -> str:
    """수집 결과를 LLM에 넘길 팩트 본문으로 조립한다."""
    lines: list[str] = []
    for p in collected:
        lines.append(f"### {p['name']}")
        if p["commits"]:
            lines += [f"- {c}" for c in p["commits"]]
        else:
            lines.append("- (이번 주 커밋 없음)")
        lines.append("")
    return "\n".join(lines)


def run_weekly_report(model: str | None = None, days: int = DAYS) -> dict:
    """주간보고 1회 실행: 커밋 수집 → LLM 요약 → 방에 저장. 요약 통계와 보고 본문 반환.

    model은 명시적 override(예: 'claude-opus-5-5') — 없으면 작업 등급표(weekly_report)의
    모델을 쓴다. 호출은 요약뿐이라 읽기 전용 기본 도구만 열어 준다(파일 접근 불필요).
    """
    collected = collect_weekly_commits(days)
    total = sum(len(x["commits"]) for x in collected)
    today = datetime.now().strftime("%Y-%m-%d")

    prompt = (
        f"아래는 최근 {days}일({today} 기준) 각 프로젝트의 git 커밋 기록이다.\n"
        "이번 주 주간보고를 작성하라.\n\n"
        "형식:\n"
        "1. 맨 위에 '이번 주 한 줄' — 전체 흐름을 쉬운 말 한 문장으로.\n"
        "2. 프로젝트별 절 — 커밋이 있는 프로젝트만, 활동이 많은 순서로. "
        "커밋 제목을 나열하지 말고 무엇을 이뤘는지 2~4개의 짧은 문장으로 묶어라.\n"
        "3. 마지막에 '조용했던 프로젝트' 한 줄 — 커밋 없는 프로젝트 이름만 쉼표로.\n\n"
        f"{_facts_text(collected)}"
    )

    allowed, disallowed = tools_for("weekly_report")  # 미등록 태스크 기본 = 읽기 전용
    meta = run_headless_ex(
        prompt,
        cwd=_neutral_cwd(),  # 중립 폴더 — 어느 프로젝트의 훅·지침도 끌려오지 않게
        allowed_tools=allowed,
        disallowed_tools=disallowed,
        timeout=LLM_TIMEOUT,
        append_system_prompt=WEEKLY_SYSTEM,
        model=model,
        task="weekly_report",
    )
    report = meta["result"]
    if report:
        # 다시 볼 수 있게 저장 — 일간보고(daily::)와 같은 메시지 방 구조를 따른다
        messages_db.add_message(f"weekly::{today}", "ohmyPM", report)
    else:
        logger.warning("[주간보고] 요약 실패 — 보고 없음(수집 통계만 반환)")
    return {
        "date": today,
        "projects": len(collected),
        "commits": total,
        "model": meta["model"],
        "cost_usd": meta["cost_usd"],
        "report": report,
    }
