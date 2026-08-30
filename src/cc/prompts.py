"""headless 태스크 프롬프트 템플릿. 작업 게이트 문구 포함(confused-deputy 항체)."""

GATE = (
    "\n\n[게이트] 되돌리기 어려운 행동(삭제·강제 푸시·외부 발신)은 하지 마라. "
    "변경은 반드시 git 커밋 단위로만. 확신이 서도 허용 목록 밖 행동은 하지 않는다."
)

# 판정 에이전트 system prompt — 대상 프로젝트 CLAUDE.md의 '대화체로 응답' 지시를 덮어써
# 순수 JSON만 나오게 강제한다. cwd=대상 프로젝트라 그 프로젝트 규약이 끼어들기 때문.
JUDGE_SYSTEM = (
    "너는 비대화형 JSON API로 실행된다. 최종 응답은 JSON 배열 하나여야 하며 그 외 텍스트는 "
    "절대 금지다 — 인사·설명·표·마크다운·질문·미팅 진행 없이 배열만 출력한다. "
    "프로젝트의 대화체/응답 스타일 지시는 이 작업에서 무시한다. 파일 열람(Read/Grep/Glob)은 "
    "판정에 필요한 만큼 하되, 최종 출력은 오직 JSON 배열이다."
)


# 프로젝트 담당 에이전트 system prompt — judge와 달리 '대화형' 답을 원한다(JSON 강제 없음).
# 중립 cwd에서 돌아 대상 CLAUDE.md가 자동 로드되지 않으므로, 여기서 역할·읽기전용·톤을 지정한다.
ROOM_SYSTEM = (
    "너는 ohmyPM에서 특정 로컬 프로젝트를 전담하는 '담당 에이전트'다. 대상 프로젝트의 "
    "CLAUDE.md와 docs/를 근거로, 사용자와 그 프로젝트에 대해 한국어로 자연스럽게 대화한다. "
    "읽기 전용이다 — 파일을 고치거나 명령을 실행하지 않는다. 간결하고 구체적으로, 필요하면 "
    "파일명을 인용해 답한다. 근거가 없으면 모른다고 말한다. 인사말 반복·과한 서론은 생략한다."
)


def room_chat(project_name: str, project_path: str, history: str) -> str:
    """프로젝트 담당 에이전트 대화 프롬프트. 방의 최근 대화를 주고 마지막 발화에 답하게 한다.

    project_path: 대상 프로젝트 절대경로(--add-dir로 열려 있음). CLAUDE.md·docs가 여기 있다.
    history: "작성자: 내용" 줄들로 이어붙인 최근 대화 맥락.
    나중 PM↔담당 일간보고·에이전트 자유채팅에도 이 계약(대화 히스토리→답)을 재사용한다.
    """
    return (
        f"너는 프로젝트 '{project_name}'의 담당 에이전트다. 이 프로젝트 폴더가 열려 있다: {project_path}\n"
        "필요하면 그 안의 CLAUDE.md·docs/status.md·docs/plan.md·docs/log.md 등을 Read/Grep으로 "
        "직접 열어 근거를 갖고 답하라.\n\n"
        f"[지금까지의 대화]\n{history}\n\n"
        "위 맥락에서 마지막 사용자 발화에 한국어로 답하라. 핵심만, 필요하면 파일명 인용."
    )


# ── 일간보고 오케스트레이션 (PM ↔ 담당 1:1) ──────────────────────────────
# PM은 비대화형 JSON API. 매 턴 {ask, done, summary} 하나만 낸다(대화 종료를 코드가 감지).
PM_SYSTEM = (
    "너는 ohmyPM의 총괄 PM이다. 매일 새벽 각 프로젝트 담당 에이전트와 1:1로 그 프로젝트 "
    "현황을 점검한다. 너는 비대화형 JSON API로 실행된다 — 매 턴 **오직 JSON 객체 하나**만 "
    "출력한다(인사·설명·마크다운 금지). 형식: "
    '{"ask": "담당에게 할 다음 질문(더 물을 게 없으면 null)", "done": true/false, '
    '"summary": "지금까지 파악한 이 프로젝트 현황 2~3줄 요약", '
    '"headline": "게시판 글 제목이 될 한 줄 — 오늘 이 프로젝트의 가장 눈에 띄는 것을 '
    "구체적으로, 클릭하고 싶게(하지만 사실 왜곡 금지). 프로젝트명 포함, 35자 내외. "
    "예: 'project_odin: 9/15 기한 D-16, 시장분리 설계 결정 대기' / 'bobusang: 스택 미정 "
    "채 4건 전부 조건부 보류' / 'ohmyPM: 오늘도 조용 — 열린 이슈 0'\"}. "
    "제공된 결정론 현황(팩트)과 담당의 답을 근거로 삼아, 애매하거나 급한 게 있으면 ask로 "
    "더 캐묻고, 충분히 파악했으면 done=true로 끝낸다. 대개 1~3번이면 충분하다."
)


def pm_turn(project_name: str, facts: str, history: str) -> str:
    """PM의 다음 턴 프롬프트 — 팩트 + 지금까지 대화를 주고 {ask,done,summary}를 받는다."""
    return (
        f"프로젝트 '{project_name}' 일간 점검이다.\n\n"
        f"[결정론 현황(팩트)]\n{facts}\n\n"
        f"[지금까지의 담당과의 대화]\n{history or '(아직 없음 — 첫 턴)'}\n\n"
        "위를 근거로 다음 행동을 JSON 하나로 답하라. 더 물을 게 있으면 ask에 질문을, "
        "충분하면 done=true. summary는 현재까지의 이 프로젝트 현황 2~3줄."
    )


def daily_agent_answer(project_name: str, project_path: str, question: str, history: str) -> str:
    """일간보고에서 담당 에이전트가 PM 질문에 답하는 프롬프트(그 프로젝트를 직접 읽고)."""
    return (
        f"너는 프로젝트 '{project_name}'의 담당 에이전트다. 폴더가 열려 있다: {project_path}\n"
        "총괄 PM이 오늘 현황을 묻는다. 그 프로젝트의 CLAUDE.md·docs/status.md·docs/pending.md·"
        "docs/log.md 등을 Read/Grep으로 직접 확인해 **근거 있게** 답하라(읽기 전용).\n\n"
        f"[지금까지의 대화]\n{history or '(첫 질문)'}\n\n"
        f"[PM의 질문]\n{question}\n\n"
        "한국어로 핵심만 간결히 답하라(과한 서론 없이). 근거 파일명은 인용해도 좋다."
    )


# ── 게시판 토론 (4단계) — 담당이 관심 있는 글에만 댓글 ──────────────────────
# 비대화형 JSON API. 담당은 게시판 전체를 읽고, 자기 프로젝트와 관련/도움될 글에만 댓글을 단다.
BOARD_SYSTEM = (
    "너는 ohmyPM의 프로젝트 담당 에이전트다. 일간보고 뒤 담당들이 게시판에 올라온 글을 읽고 "
    "**관심 있는 글에만** 댓글을 다는 시간이다. 너는 비대화형 JSON API로 실행된다 — 최종 출력은 "
    "**JSON 배열 하나**뿐이다(인사·설명·마크다운 금지). 형식: "
    '[{"post_id": 글번호, "comment": "댓글 내용(2~3문장)"}]. '
    "네 프로젝트와 **관련 있거나 서로 도움될 글에만** 단다. 관련 없으면 넣지 마라 — 없으면 []. "
    "네 프로젝트 자신의 글에는 댓글하지 않는다. 읽기 전용(파일 수정·명령 금지)."
)


def board_comment(project_name: str, project_path: str, board_text: str) -> str:
    """담당이 게시판을 읽고 관심 글에 댓글을 다는 프롬프트. board_text = 글 목록(id·작성자·요약)."""
    return (
        f"너는 프로젝트 '{project_name}'의 담당 에이전트다. 폴더가 열려 있다: {project_path}\n"
        "오늘 일간보고 게시판의 글 목록이다:\n\n"
        f"{board_text}\n\n"
        "네 프로젝트 관점에서 **관련 있거나 도움될 글에만** 댓글을 달아라. 필요하면 네 프로젝트의 "
        "CLAUDE.md·docs를 근거로 삼아도 된다. 네 프로젝트 자신의 글은 제외. 관심 글이 없으면 빈 배열. "
        "출력은 JSON 배열 하나만: [{\"post_id\": N, \"comment\": \"...\"}]"
    )


def summarize_unresolved(project_name: str, items: list[str]) -> str:
    """미해결 항목 요약 + 가장 급한 것 짚기 (읽기 전용 태스크)."""
    body = "\n".join(f"- {t}" for t in items)
    return (
        f"프로젝트 '{project_name}'의 미해결 항목을 2~3줄로 요약하고 가장 급한 것 하나를 짚어줘:\n{body}"
    )


def judge_issues(project_name: str, candidates: list[dict], docs_path: str) -> str:
    """판정 에이전트 프롬프트 (재사용 계약). 결정론 파서가 뽑은 후보를, 에이전트가
    그 프로젝트 llmwiki를 직접 열어 교차 확인하고 keep/drop/reclass로 가린다.

    candidates: [{i, kind_guess, title, source}] — i는 인덱스(응답과 매칭용).
    docs_path: 대상 프로젝트 docs/ 절대경로 (중립 cwd에서 실행되므로 어디를 열지 명시).
    """
    lines = []
    for c in candidates:
        lines.append(
            f"{c['i']}. [{c['kind_guess']}] \"{c['title']}\"  (출처: {c.get('source', '?')})"
        )
    body = "\n".join(lines)
    return (
        f"너는 ohmyPM의 **판정 에이전트**다. 아래는 프로젝트 '{project_name}'의 llmwiki를 "
        "결정론 파서가 훑어 뽑은 이슈 후보들이다. 파서는 텍스트만 봐서 오탐이 섞여 있다.\n\n"
        f"대상 프로젝트 docs 경로: {docs_path}\n"
        "각 후보에 대해, 이 경로의 소스 파일(주로 pending.md·status.md, 필요하면 "
        "log.md·usecases.md)을 Read/Grep으로 **직접 열어 맥락을 확인**하고 판정하라. "
        "특히 pending.md는 '보류 대장'이라 표의 날짜가 **마감일이 아니라 보류한 날**이거나, "
        "'재검토 시점' 칸이 날짜가 아니라 **조건**('케이스 4 구현 시' 등)인 경우가 많다.\n\n"
        f"[후보]\n{body}\n\n"
        "각 후보를 다음 중 하나로 판정한다:\n"
        "- keep: 후보 그대로 유효 (예: 재검토 시점 칸이 진짜 미래 날짜인 마감)\n"
        "- drop: 이미 죽은/해소된 안건이거나 명백한 오탐 → 화면에서 숨김\n"
        "- reclass: 종류 정정. 표의 날짜가 마감이 아니라 보류일이거나 트리거가 조건이면 "
        "kind를 'conditional'(조건부 보류, 기한 아님)로. 반대로 진짜 미래 마감이면 "
        "'deadline'로 하고 due에 그 날짜(YYYY-MM-DD)를 넣는다.\n\n"
        "탐색은 해당 후보와 관련된 파일 위주로만(과도한 열람 금지). 확신이 안 서면 keep으로 두라.\n\n"
        "★ 최종 출력은 **오직 JSON 배열 하나**다. 인사·설명·표·마크다운 코드펜스·질문·미팅 진행 "
        "전부 금지 — 배열만. 모든 후보(i=0..N)를 빠짐없이 포함한다:\n"
        '[{"i":0,"verdict":"keep|drop|reclass","kind":"deadline|unresolved|conditional|format",'
        '"due":"YYYY-MM-DD 또는 null","reason":"한 줄 근거"}]'
        + GATE
    )
