# -*- coding: utf-8 -*-
"""모델 동향 공식 출처를 벤더별로 수집해 `docs/experts/models-<vendor>.md`를 갱신한다(T-007·R-010).

    uv run python scripts/collect_models.py                    # 전 벤더 수집(변경 시 LLM 반영)
    uv run python scripts/collect_models.py --vendor claude    # Claude만
    uv run python scripts/collect_models.py --source codex-changelog
    uv run python scripts/collect_models.py --fetch-only       # 본문만 받아 저장, LLM 반영은 건너뜀
    uv run python scripts/collect_models.py --profiles claude  # 수집 없이 어긋난 프로필만 다시 씀

대시보드 전문가 탭의 수집 버튼(`POST /api/experts/<domain>/collect`)도 같은 수집기를 부른다.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cc import model_catalog as mc  # noqa: E402


def _print_sources(results: dict) -> None:
    for key, r in results.items():
        if key == "profiles":
            print(f"  프로필 재시도: 갱신 {r.get('updated')} 실패 {r.get('failed')}")
            continue
        status = "OK" if r.get("ok") else f"FAIL({r.get('error')})"
        extra = ""
        if r.get("changed"):
            extra = f" changes={r.get('changes')} models={r.get('models')}"
            if r.get("profiles_failed"):
                extra += f" profiles_failed={r['profiles_failed']}"
        print(f"  {key}: {status} changed={r.get('changed')} "
              f"llm_called={r.get('llm_called')}{extra}")


def main() -> int:
    ap = argparse.ArgumentParser(description="모델 동향 공식 출처 수집(벤더별)")
    ap.add_argument("--fetch-only", action="store_true",
                     help="본문만 받아 저장, LLM 반영은 건너뜀(미반영 diff는 다음 실행에 재시도)")
    ap.add_argument("--vendor", choices=sorted(mc.VENDORS), help="지정하면 그 벤더만(기본: 전체)")
    ap.add_argument("--source", choices=sorted(mc.SOURCES), help="지정하면 그 출처만")
    ap.add_argument("--profiles", choices=sorted(mc.VENDORS), metavar="VENDOR",
                     help="수집 없이 그 벤더의 어긋난 모델 프로필만 다시 쓴다")
    args = ap.parse_args()

    if args.profiles:
        r = mc.refresh_profiles(args.profiles)
        print(f"{args.profiles}: 프로필 갱신 {r['updated']} 실패 {r['failed']}")
        return 0 if r["ok"] else 1

    if args.source:
        r = mc.collect_source(args.source, fetch_only=args.fetch_only)
        print(mc.vendor_of_source(args.source))
        _print_sources({args.source: r})
        return 0 if r.get("ok") else 1

    vendors = [args.vendor] if args.vendor else list(mc.VENDORS)
    ok = True
    for v in vendors:
        batch = mc.collect_vendor(v, fetch_only=args.fetch_only)
        print(f"{v} ({mc.VENDORS[v]['name']}): {'OK' if batch['ok'] else 'FAIL'}")
        _print_sources(batch["sources"])
        ok = ok and batch["ok"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
