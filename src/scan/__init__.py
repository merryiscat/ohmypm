"""관리 대상 스캔 — 프로젝트 발견(discover) + llmwiki 파싱(llmwiki)을 묶는 파이프라인.

★ headless·LLM 없이 순수 결정론적 파싱. "수집=스크립트, 요약만 LLM" 원칙(08-22).
   status 341KB 같은 비대 문서도 통째로 LLM에 안 던지고 여기서 미해결 목록만 추출한다.
"""

from loguru import logger

from src.db import issues as issues_db
from src.scan.discover import discover_projects
from src.scan.llmwiki import parse_wiki


def run_scan() -> dict:
    """전체 스캔: 프로젝트 발견 → 각 위키 파싱 → 이슈 적재. 요약 통계 반환.

    한 프로젝트 실패가 배치 전체를 멈추지 않게 per-project try/except.
    """
    projects = discover_projects()
    total_issues = 0
    for p in projects:
        try:
            for issue in parse_wiki(p["path"]):
                issues_db.upsert_issue(
                    project=p["path"],
                    kind=issue["kind"],
                    title=issue["title"],
                    due=issue.get("due"),
                    source=issue.get("source"),
                )
                total_issues += 1
        except Exception as e:  # 한 프로젝트 파싱 실패 → 로그만, 다음 계속
            logger.warning(f"[스캔] {p['name']} 파싱 실패: {e}")
    # ★ 날짜 없는 활성 이슈에 기본 재확인일(+14일)을 채운다(2026-09-06 사용자 확정:
    #   "날짜 없으면 묻힌다"). PM이 일간보고에서 더 좋은 날짜를 잡으면 그걸로 덮인다.
    filled = issues_db.fill_default_due(days=14)
    logger.info(f"[스캔] 프로젝트 {len(projects)}개, 이슈 {total_issues}건 적재, 재확인일 부여 {filled}건")
    return {"projects": len(projects), "issues": total_issues, "due_filled": filled}
