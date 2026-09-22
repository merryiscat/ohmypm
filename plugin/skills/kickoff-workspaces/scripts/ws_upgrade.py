#!/usr/bin/env python3
"""Register an external environment; never install tracked project files."""

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
PLUGIN = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN / "skills/dispatch/scripts"))
from environment import Environment, data_home, install_package  # noqa: E402
from workflow_core import WorkflowError, read_json  # noqa: E402


def install(project, migrate=False, dry_run=False, home=None, profiles=None):
    if migrate:
        raise ValueError(
            "Use migration-plan/apply with a reviewed digest; implicit migration was removed"
        )
    env = Environment(project)
    env.check_store(data_home(home))
    if dry_run:
        return {"changed": [], "state": str(env.root), "checkout_changes": [], "dry_run": True}
    with env.lock():
        pin = install_package(PLUGIN, home)
        result = env.register(pin, profiles)
        result["checkout_changes"] = []
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--migrate-v1", action="store_true")
    parser.add_argument("--home")
    parser.add_argument("--profiles")
    args = parser.parse_args()
    try:
        result = install(
            args.project,
            args.migrate_v1,
            args.dry_run,
            args.home,
            read_json(args.profiles)["roles"] if args.profiles else None,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (WorkflowError, OSError, ValueError, KeyError) as exc:
        parser.exit(1, str(exc) + "\n")
