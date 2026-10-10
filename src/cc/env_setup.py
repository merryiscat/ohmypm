"""환경 세팅 — 모델 쪽. 수집(코드) → 모델 한 번 → 검증(코드) → DB 저장.

수집·검증·적용·되돌리기는 src/env_setup.py(코드)가 한다. 여기서는 모델을 정확히 한 번 부른다.
읽기 전용 도구만, 중립 작업 폴더에서, 대상 프로젝트는 add_dirs로 읽기만. 플러그인은 싣지 않는다.
응답이 깨졌으면 고쳐 쓰거나 다시 부르지 않고 실행을 '실패'로 남긴다 — 깨진 응답에서 변경안을 추정하지 않는다.
"""

import json

from loguru import logger

from src import env_setup as es
from src.cc.client import run_headless_ex
from src.cc.common import neutral_cwd, parse_json_object
from src.cc.permissions import tools_for
from src.cc.prompts import load, render
from src.db import env_setup as db

ENV_SETUP_SYSTEM = load("env_setup_system")   # 시스템 지시문은 서버 시작 때 읽는다(고치면 재시작)
LLM_TIMEOUT = 300


def job_name(root) -> str:
    return f"env-setup-{es.project_key(root)}"


def start(project_path: str) -> dict:
    """제안 실행을 접수한다(라우트가 부른다). 검사 → 실행 기록 → 백그라운드 작업 시작."""
    from src import jobs

    root = es.resolve_project(project_path)
    name = job_name(root)
    if jobs.is_running(name) or db.active_run(str(root)):
        raise es.EnvSetupError("이 프로젝트의 환경 세팅이 이미 진행 중입니다", 409)
    run_id = db.create_run(str(root))
    if not jobs.start(name, run_env_setup, run_id):
        db.update_run(run_id, status="failed", error="작업을 시작하지 못했습니다(이미 진행 중)", finished_at=db.now())
        raise es.EnvSetupError("이 프로젝트의 환경 세팅이 이미 진행 중입니다", 409)
    return {"run_id": run_id, "job": name}


def run_env_setup(run_id: int) -> dict:
    """백그라운드 작업 본체. 반환 {run_id, status, items}."""
    run = db.get_run(run_id)
    if not run or not db.transition(run_id, ("queued",), "running"):
        return {"run_id": run_id, "status": "skipped"}
    try:
        snapshot = es.collect_snapshot(run["project"])
    except es.EnvSetupError as e:
        db.update_run(run_id, status="failed", error=str(e), finished_at=db.now())
        return {"run_id": run_id, "status": "failed"}
    materials = es.load_materials()
    db.update_run(run_id, snapshot_json=json.dumps(snapshot, ensure_ascii=False),
                  materials_json=json.dumps(materials, ensure_ascii=False))
    prompt = render("env_setup", snapshot=json.dumps(snapshot, ensure_ascii=False, indent=1),
                    materials=json.dumps(materials, ensure_ascii=False, indent=1), max_items=str(es.MAX_ITEMS))
    allowed, disallowed = tools_for("env_setup")
    meta = run_headless_ex(
        prompt,
        cwd=neutral_cwd(),
        allowed_tools=allowed,
        disallowed_tools=disallowed,
        add_dirs=[snapshot["project"]],
        append_system_prompt=ENV_SETUP_SYSTEM,
        timeout=LLM_TIMEOUT,
        task="env_setup",
    )
    raw = meta.get("result")
    db.update_run(run_id, raw_response=raw, model=meta.get("model"), cost_usd=meta.get("cost_usd") or 0,
                  output_tokens=meta.get("output_tokens") or 0)
    if not raw:
        db.update_run(run_id, status="failed", error="모델 호출이 실패했거나 응답이 비었습니다", finished_at=db.now())
        return {"run_id": run_id, "status": "failed"}
    data = parse_json_object(raw)
    try:
        if data is None:
            raise es.ProposalError("응답에서 JSON 객체를 찾지 못했거나 JSON이 깨졌습니다")
        items = es.validate_proposal(data, snapshot, materials)
    except es.ProposalError as e:
        logger.warning(f"[환경 세팅] 실행 {run_id} 제안 검증 실패: {e}")
        db.update_run(run_id, status="failed", error=f"제안이 규칙을 어겨 받지 않았습니다: {e}", finished_at=db.now())
        return {"run_id": run_id, "status": "failed"}
    db.add_items(run_id, items)
    note = None if any(i["applicable"] for i in items) else \
        ("고칠 것을 찾지 못했습니다" if not items else "바로 쓸 수 있는 항목이 없습니다(보여 주기만 하는 항목뿐)")
    db.update_run(run_id, status="proposed", error=note, finished_at=db.now())
    return {"run_id": run_id, "status": "proposed", "items": len(items)}
