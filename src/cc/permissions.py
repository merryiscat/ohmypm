"""화이트리스트 → allowedTools/disallowedTools 조립 (자율경계 강제).

★ 되돌리기 불가능한 행동은 화이트리스트를 아무리 넓혀도 항상 deny.
   에이전트가 "안전한가"를 판단하지 않는다 — 여기 목록이 결정론적으로 정한다.
"""

# 절대 허용 안 함 — 되돌리기 불가능·외부 발신 (도구 레벨). disallow가 allow를 이긴다.
NEVER_ALLOW = [
    "Bash(rm:*)",
    "Bash(git push --force:*)",
    "Bash(git push -f:*)",
    "WebFetch",
]

# 태스크 유형별 허용 도구.
TASK_TOOLS = {
    # 프로젝트 담당 에이전트(사용자와의 룸 대화) — 2026-09-09 사용자 확정으로 편집 허용.
    #   사용자가 그 자리에서 지시하고 결과를 바로 보므로 승인이 곧 사용자 판단이다.
    #   Bash는 없어 임의 명령·푸시는 불가하고, 커밋도 하지 않는다 — 변경은 작업 폴더에 남는다.
    "room_chat": ["Read", "Grep", "Glob", "Edit", "Write"],
    # 게시판 토론(글쓰기·둘러보기·반응·대대댓글) — 자기 프로젝트를 읽고 쓸 뿐, 파일은 안 고친다.
    "board": ["Read", "Grep", "Glob"],
    # 랩실 연구원 — 웹으로 최신 지식 수집·자문(읽기 전용 + 웹). 파일 쓰기는 코드가 한다.
    "expert": ["Read", "Grep", "Glob", "WebSearch", "WebFetch"],
}


def tools_for(task: str) -> tuple[list[str], list[str]]:
    """(allowed_tools, disallowed_tools) 반환. 미등록 태스크는 읽기 전용 기본.

    disallowed는 '허용 목록에 없는' NEVER_ALLOW만 — 예: 연구원은 WebFetch를 허용하므로
    그 태스크에선 WebFetch가 disallow에서 빠지되, rm·force push는 항상 막힌다(허용에 없음).
    """
    allowed = TASK_TOOLS.get(task, ["Read", "Grep", "Glob"])
    disallowed = [t for t in NEVER_ALLOW if t not in allowed]
    return allowed, disallowed
