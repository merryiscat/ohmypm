"""headless 태스크 프롬프트 템플릿. 작업 게이트 문구 포함(confused-deputy 항체)."""

GATE = (
    "\n\n[게이트] 되돌리기 어려운 행동(삭제·강제 푸시·외부 발신)은 하지 마라. "
    "변경은 반드시 git 커밋 단위로만. 확신이 서도 허용 목록 밖 행동은 하지 않는다."
)


def summarize_unresolved(project_name: str, items: list[str]) -> str:
    """미해결 항목 요약 + 가장 급한 것 짚기 (읽기 전용 태스크)."""
    body = "\n".join(f"- {t}" for t in items)
    return (
        f"프로젝트 '{project_name}'의 미해결 항목을 2~3줄로 요약하고 가장 급한 것 하나를 짚어줘:\n{body}"
    )
