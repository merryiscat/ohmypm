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
