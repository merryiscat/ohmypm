#!/usr/bin/env python3
"""Explicit environment installation, request routing, role recovery and migration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from environment import Environment, data_home, install_package, verify_package  # noqa: E402
from migration import Migration  # noqa: E402
from roles import RoleAdapter, Roles  # noqa: E402
from workflow_core import Orca, WorkflowError, read_json  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".")
    parser.add_argument("--orca")
    subs = parser.add_subparsers(dest="command", required=True)
    p = subs.add_parser("register")
    p.add_argument("--plugin", required=True)
    p.add_argument("--home")
    p.add_argument("--profiles", help="JSON file containing roles; values, not secrets")
    p = subs.add_parser("select-runtime")
    p.add_argument("--pin", required=True, help="Saved pin JSON; affects future tasks only")
    subs.add_parser("disable")
    subs.add_parser("doctor")
    subs.add_parser("reconnect")
    p = subs.add_parser("export")
    p.add_argument("--destination", required=True)
    p = subs.add_parser("route")
    p.add_argument("--request-id", required=True)
    p.add_argument("--request-file", required=True)
    p.add_argument("--path", choices=["direct", "pl"], required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--scope", required=True)
    p.add_argument("--small-clear-reversible", action="store_true")
    p = subs.add_parser("direct-exec")
    p.add_argument("--request-id", required=True)
    p.add_argument("argv", nargs=argparse.REMAINDER)
    for name in (
        "context",
        "role-connect",
        "role-show",
        "role-reconcile",
        "role-exit",
        "role-accept",
    ):
        p = subs.add_parser(name)
        p.add_argument(
            "--role",
            choices=["main", "pl"] if name != "context" else ["main", "pl", "work"],
            required=True,
        )
        if name in ("role-reconcile", "role-exit"):
            p.add_argument("--receipt", required=True)
        if name == "role-accept":
            p.add_argument("--generation", type=int, required=True)
            p.add_argument("--digest", required=True)
    p = subs.add_parser("enqueue")
    p.add_argument("--role", choices=["main", "pl"], required=True)
    p.add_argument("--message-id", required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--revision", type=int, required=True)
    p.add_argument("--body-file", required=True)
    for name in ("deliver", "acknowledge"):
        p = subs.add_parser(name)
        p.add_argument("--message-id", required=True)
        if name == "acknowledge":
            p.add_argument("--generation", type=int, required=True)
            p.add_argument("--revision", type=int, required=True)
            p.add_argument("--completed", action="store_true")
    for name in ("migration-plan", "migration-apply", "migration-rollback"):
        p = subs.add_parser(name)
        p.add_argument("--catalog", help="Defaults to pinned legacy-v1 catalog")
        if name != "migration-plan":
            p.add_argument("--id", required=True)
        if name == "migration-apply":
            p.add_argument("--digest", required=True)
    args = parser.parse_args()
    env = Environment(args.project)
    roles = Roles(args.project, RoleAdapter(Orca(args.orca)))
    with env.lock():
        cmd = args.command
        if cmd == "register":
            env.check_store(data_home(args.home))
            pin = install_package(args.plugin, args.home)
            profiles = read_json(args.profiles)["roles"] if args.profiles else None
            result = env.register(pin, profiles)
        elif cmd == "select-runtime":
            result = env.register(read_json(args.pin))
        elif cmd == "doctor":
            cfg = env.config(enabled=False)
            result = {
                "config": cfg,
                "package": verify_package(cfg["runtime"]),
                "active": env.active(),
                "roles": {r: roles.load(r) for r in ("main", "pl")},
                "note": "Installation only; role delivery and behavior need separate evidence",
            }
        elif cmd == "disable":
            result = env.disable()
        elif cmd == "reconnect":
            result = env.reconnect()
        elif cmd == "export":
            result = env.export(args.destination)
        elif cmd == "route":
            result = env.route(
                args.request_id,
                Path(args.request_file).read_text(encoding="utf-8-sig"),
                args.path,
                args.reason,
                args.scope,
                args.small_clear_reversible,
            )
        elif cmd == "direct-exec":
            argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
            result = env.direct(args.request_id, argv)
        elif cmd == "context":
            result = {"context": env.context(args.role)}
        elif cmd == "role-connect":
            result = roles.connect(args.role)
        elif cmd == "role-show":
            result = roles.load(args.role)
        elif cmd == "role-reconcile":
            result = roles.reconcile(args.role, read_json(args.receipt))
        elif cmd == "role-exit":
            result = roles.observe_exit(args.role, read_json(args.receipt))
        elif cmd == "role-accept":
            result = roles.accept(args.role, args.generation, args.digest)
        elif cmd == "enqueue":
            result = roles.enqueue(
                args.role,
                args.message_id,
                args.task,
                args.revision,
                Path(args.body_file).read_text(encoding="utf-8-sig"),
            )
        elif cmd == "deliver":
            result = roles.deliver(args.message_id)
        elif cmd == "acknowledge":
            result = roles.acknowledge(
                args.message_id, args.generation, args.revision, args.completed
            )
        else:
            catalog = args.catalog or str(
                Path(env.config(enabled=False)["runtime"]["path"]) / "references/legacy-v1.json"
            )
            migration = Migration(args.project, catalog)
            if cmd == "migration-plan":
                result = migration.plan()
            elif cmd == "migration-apply":
                result = migration.apply(args.id, args.digest)
            else:
                result = migration.rollback(args.id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        sys.exit(main())
    except (WorkflowError, ValueError, KeyError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
