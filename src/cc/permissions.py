"""화이트리스트 → allowedTools/disallowedTools 조립 (자율경계 강제, L1·L2).

★ 되돌리기 불가능한 행동은 화이트리스트를 아무리 넓혀도 항상 deny (plan 안전장치).
   에이전트가 "안전한가"를 판단하지 않는다 — 여기 목록이 결정론적으로 정한다.
"""

# 절대 허용 안 함 — 되돌리기 불가능·외부 발신 (도구 레벨). disallow가 allow를 이긴다.
NEVER_ALLOW = [
    "Bash(rm:*)",
    "Bash(git push --force:*)",
    "Bash(git push -f:*)",
    "WebFetch",
]

# 태스크 유형별 허용 도구. 사용자 화이트리스트(alerts.whitelist.*)가 켜진 것만 실제 자율 실행.
TASK_TOOLS = {
    "scan": ["Read", "Grep", "Glob"],  # 읽기 전용
    # 판정 에이전트(자가 확인형) — 대상 프로젝트 llmwiki를 직접 열어보고 이슈를 가린다. 읽기만.
    "judge": ["Read", "Grep", "Glob"],
    # 프로젝트 담당 에이전트(룸 채팅) — CLAUDE.md·docs를 읽고 대화만. 읽기 전용.
    "room_chat": ["Read", "Grep", "Glob"],
    # 일간보고: PM(팩트로 판단, 필요 시 읽기)·담당(프로젝트 읽고 답) — 둘 다 읽기 전용.
    "daily_pm": ["Read", "Grep", "Glob"],
    "daily_agent": ["Read", "Grep", "Glob"],
    # 형식 표준화 = git 커밋 단위 자율(변경→add→commit). push는 NEVER_ALLOW로 차단.
    "format_standardize": ["Read", "Edit", "Write", "Bash(git add:*)", "Bash(git commit:*)"],
}


def tools_for(task: str) -> tuple[list[str], list[str]]:
    """(allowed_tools, disallowed_tools) 반환. 미등록 태스크는 읽기 전용 기본."""
    allowed = TASK_TOOLS.get(task, ["Read", "Grep", "Glob"])
    return allowed, NEVER_ALLOW
