#!/usr/bin/env python3
"""Install ohmyPM's project-local 1.0 workflow without editing outside owned blocks."""

from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import subprocess
from pathlib import Path


def git(project, *args):
    result = subprocess.run(
        ["git", "-C", str(project), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        raise ValueError(result.stderr.strip())
    return result.stdout.strip()


def install(project, migrate=False, dry_run=False):
    project = Path(project).resolve()
    if Path(git(project, "rev-parse", "--show-toplevel")).resolve() != project:
        raise ValueError("Install at the repository checkout root")
    skill = Path(__file__).resolve().parents[1]
    plugin = skill.parents[1]
    version = json.loads((plugin / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))[
        "version"
    ]
    templates = skill / "templates"
    stamp = f"<!-- kickoff-workspaces v{version} — managed by ohmypm -->\n"
    current = project / "docs/protocol.md"
    old = current.read_text(encoding="utf-8-sig") if current.exists() else ""
    if old and not old.startswith(stamp) and not migrate:
        raise ValueError(
            "Existing workflow preserved. Use --migrate-v1 after settling active work."
        )
    config = project / "docs/workflow.json"
    targets = {
        "docs/protocol.md": stamp + (skill / "PROTOCOL.md").read_text(encoding="utf-8"),
        "docs/tasks/_template.md": stamp + (templates / "task.md").read_text(encoding="utf-8"),
        "docs/reviews/_template.md": stamp + (templates / "review.md").read_text(encoding="utf-8"),
        "docs/workflow-guide.md": (plugin / "skills/dispatch/references/runtime.md").read_text(
            encoding="utf-8"
        ),
        ".ohmypm/bin/workflow.py": (plugin / "skills/dispatch/scripts/workflow.py").read_text(
            encoding="utf-8"
        ),
        ".ohmypm/bin/workflow_core.py": (
            plugin / "skills/dispatch/scripts/workflow_core.py"
        ).read_text(encoding="utf-8"),
    }
    hook = project / ".githooks/pre-commit"
    if not hook.exists() or "kickoff-workspaces" in hook.read_text(encoding="utf-8-sig"):
        targets[".githooks/pre-commit"] = (templates / "pre-commit").read_text(encoding="utf-8")
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = project / name
        original = path.read_text(encoding="utf-8-sig") if path.exists() else f"# {project.name}\n"
        block = (templates / (name + ".block")).read_text(encoding="utf-8").rstrip()
        pattern = re.compile(
            r"^## 작업 구조 \(kickoff-workspaces[^)]*\)\n.*?(?=^## |\Z)", re.M | re.S
        )
        targets[name] = (
            pattern.sub(lambda _: block + "\n\n", original, count=1)
            if pattern.search(original)
            else original.rstrip() + "\n\n" + block
        ).rstrip() + "\n"
    roles = project / "docs/roles.md"
    if not roles.exists() or migrate:
        targets["docs/roles.md"] = (templates / "roles.md").read_text(encoding="utf-8")
    if not config.exists():
        targets["docs/workflow.json"] = (templates / "workflow.json").read_text(encoding="utf-8")
    if not (project / "docs/benchmark.md").exists():
        targets["docs/benchmark.md"] = (templates / "benchmark.md").read_text(encoding="utf-8")
    for name, template in (("orca.yaml", "orca.yaml"), (".worktreeinclude", "worktreeinclude")):
        if not (project / name).exists():
            targets[name] = (templates / template).read_text(encoding="utf-8")
    ignore = project / ".gitignore"
    original = ignore.read_text(encoding="utf-8-sig") if ignore.exists() else ""
    additions = [
        entry
        for entry in ("/.ohmypm-work/", "/docs/benchmark.md", "__pycache__/", "*.pyc")
        if entry not in original.splitlines()
    ]
    if additions:
        targets[".gitignore"] = (
            original.rstrip() + "\n\n# ohmyPM task-local runtime\n" + "\n".join(additions) + "\n"
        )
    targets = {
        name: text
        for name, text in targets.items()
        if not (project / name).exists() or (project / name).read_text(encoding="utf-8-sig") != text
    }
    for name in targets:
        if not (project / name).resolve().is_relative_to(project):
            raise ValueError(f"Managed path points outside project; preserve it: {name}")
    common = Path(git(project, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    backup = common / "ohmypm-v1/migrations" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    if not dry_run:
        for name, text in targets.items():
            path = project / name
            if path.exists():
                saved = backup / name
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, saved)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        existing_hooks = subprocess.run(
            ["git", "-C", str(project), "config", "--get", "core.hooksPath"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        if not existing_hooks and ".githooks/pre-commit" in targets:
            git(project, "config", "core.hooksPath", ".githooks")
    return {
        "version": version,
        "dry_run": dry_run,
        "changed": sorted(targets),
        "backup": str(backup) if targets and not dry_run else None,
        "note": "Existing orca.yaml, .worktreeinclude, model config and active work are preserved. "
        "Remove dependency sharing before preparing isolated work; review owned settings.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("--migrate-v1", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                install(args.project, args.migrate_v1, args.dry_run), ensure_ascii=False, indent=2
            )
        )
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + "\n")
