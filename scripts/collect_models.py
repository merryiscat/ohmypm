# -*- coding: utf-8 -*-
"""모델 동향 공식 출처 4개(Claude 모델·릴리스, Codex 모델·changelog)를 수집해
`docs/experts/models.md`를 갱신한다(T-007 r2).

    uv run python scripts/collect_models.py               # 전체 수집(변경 있으면 LLM 반영)
    uv run python scripts/collect_models.py --fetch-only   # 본문만 받아 저장, LLM 반영은 건너뜀
    uv run python scripts/collect_models.py --source claude-models

기존 `POST /api/experts/models/collect`도 같은 수집기(`src.cc.model_catalog`)를 호출한다.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cc import model_catalog  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="모델 동향 공식 출처 수집")
    ap.add_argument("--fetch-only", action="store_true",
                     help="본문만 받아 저장, LLM 반영은 건너뜀(미반영 diff는 다음 실행에 재시도)")
    ap.add_argument("--source", choices=sorted(model_catalog.SOURCES),
                     help="지정하면 그 출처만 수집(기본: 전체 4개)")
    args = ap.parse_args()

    if args.source:
        one = model_catalog.collect_source(args.source, fetch_only=args.fetch_only)
        result = {args.source: one}
        ok = one.get("ok", False)
    else:
        batch = model_catalog.collect_all_sources(fetch_only=args.fetch_only)
        result = batch["sources"]
        ok = batch["ok"]

    for key, r in result.items():
        status = "OK" if r.get("ok") else f"FAIL({r.get('error')})"
        print(f"{key}: {status} changed={r.get('changed')} llm_called={r.get('llm_called')}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
