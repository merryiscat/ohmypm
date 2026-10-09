"""스캔 — 프로젝트 발견(discover) + 각 프로젝트에 ohmypm/ 설치(install).

★ 모델 호출 없이 파일 작업만. 한 프로젝트 실패가 전체를 멈추지 않게 프로젝트별 try/except.
(2026-10-09: 옛 llmwiki 파서·이슈 적재는 제거 — 각 프로젝트의 docs 위키가 폐기됐다.)
"""

from loguru import logger

from src.config.settings import ensure_env
from src.scan.discover import discover_projects


def run_scan() -> dict:
    """전체 스캔: .env 확인 → 프로젝트 발견 → 각 프로젝트에 ohmypm/ 설치. 요약 통계 반환."""
    from src.install import install_project

    ensure_env()
    projects = discover_projects()
    out = {"projects": len(projects), "installed": 0, "already": 0, "self_skipped": 0, "errors": []}
    for p in projects:
        try:
            r = install_project(p["path"])
        except Exception as e:  # 한 프로젝트 실패 → 로그만, 다음 계속
            logger.warning(f"[스캔] {p['name']} 설치 실패: {e}")
            out["errors"].append({"name": p["name"], "error": str(e)[:200]})
            continue
        if r.get("self"):
            out["self_skipped"] += 1
        elif r.get("created"):
            out["installed"] += 1
        else:
            out["already"] += 1
    logger.info(f"[스캔] 프로젝트 {out['projects']}개 — 새로 설치 {out['installed']}, "
                f"이미 설치 {out['already']}, 자기 자신 제외 {out['self_skipped']}, 실패 {len(out['errors'])}")
    return out
