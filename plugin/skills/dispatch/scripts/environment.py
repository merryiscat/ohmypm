"""External, content-addressed runtime and repository-local operating records.

No installation operation writes the checkout, index, hooks, or global Git config.
All mutable records live in the Git common directory. CLI callers take lock().
"""

from __future__ import annotations

import contextlib
import copy
import os
import shutil
import uuid
from pathlib import Path

from workflow_core import WorkflowError, digest, git, read_json, require, safe_id, write_json

SCHEMA = 2
VERSION = "2.0.0"


@contextlib.contextmanager
def file_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0)
        stream.write(b"0")
        stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise WorkflowError("Environment is locked; retry after the owner finishes") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def no_links(root, path):
    """Reject every link/junction component, including links that stay inside root."""
    root, path = Path(root).absolute(), Path(path).absolute()
    require(path != root and path.is_relative_to(root), "Path escapes owner")
    for part in [path, *path.parents]:
        require(
            not part.is_symlink() and not getattr(part, "is_junction", lambda: False)(),
            f"Link/junction must be preserved: {part}",
        )
        if part == root:
            break
    return path


def data_home(override=None):
    if override or os.environ.get("OHMYPM_HOME"):
        return Path(override or os.environ["OHMYPM_HOME"]).expanduser().resolve()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "ohmypm"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "ohmypm"


def package_sources(plugin):
    plugin = Path(plugin).resolve()
    sources = {}
    for path in sorted((plugin / "skills/dispatch/scripts").glob("*.py")):
        sources["scripts/" + path.name] = path.read_bytes()
    for path in sorted((plugin / "skills/dispatch/references").glob("*")):
        if path.is_file():
            sources["references/" + path.name] = path.read_bytes()
    sources["PROTOCOL.md"] = (plugin / "skills/kickoff-workspaces/PROTOCOL.md").read_bytes()
    for name in ("workflow.json", "task.md", "review.md"):
        path = plugin / "skills/kickoff-workspaces/templates" / name
        sources["templates/" + name] = path.read_bytes()
    return sources


def verify_package(pin):
    path = Path(pin["path"])
    require(path.name == pin["id"], "Package identity/path mismatch")
    no_links(path.parent, path)
    manifest = read_json(path / "package.json")
    require(digest(manifest) == pin["id"], "Runtime manifest hash mismatch; restore exact package")
    require(manifest["schema"] == SCHEMA, "Unsupported runtime schema")
    for name, expected in manifest["files"].items():
        target = no_links(path, path / name)
        require(
            target.is_file() and digest(target.read_bytes()) == expected,
            f"Runtime file missing or modified: {target}; restore exact package",
        )
    return manifest


def install_package(plugin, home=None):
    sources = package_sources(plugin)
    manifest = {
        "version": VERSION,
        "schema": SCHEMA,
        "adapter": 1,
        "files": {name: digest(value) for name, value in sources.items()},
    }
    identity = digest(manifest)
    root = data_home(home) / "runtimes"
    target = root / identity
    pin = {"id": identity, "path": str(target.resolve()), "version": VERSION}
    root.mkdir(parents=True, exist_ok=True)
    with file_lock(root / "install.lock"):
        if not target.exists():
            staging = root / ("staging-" + uuid.uuid4().hex)
            staging.mkdir()
            for name, value in sources.items():
                dest = staging / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(value)
            write_json(staging / "package.json", manifest)
            staging.rename(target)
        verify_package(pin)
    return pin


def validate_profiles(roles):
    require(set(roles) == {"main", "pl", "work"}, "Profiles must define main/pl/work")
    roles = copy.deepcopy(roles)
    if roles["pl"].get("agent") == "codex":
        roles["pl"].setdefault("approval", "bypass")
    for role, profile in roles.items():
        require(
            profile.get("approval", "default") in ("default", "bypass"), "Unknown approval policy"
        )
        require(set(profile) <= {"agent", "model", "effort", "approval"}, "Unknown profile field")
        require(profile.get("agent") in ("claude", "codex"), f"Unsupported adapter: {role}")
        import re

        require(
            all(
                isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_.-]+", v) for v in profile.values()
            ),
            "Unsafe/invalid launcher profile",
        )
    return copy.deepcopy(roles)


class Environment:
    def __init__(self, project):
        self.project = Path(git(project, "rev-parse", "--show-toplevel")).resolve()
        self.common = Path(
            git(project, "rev-parse", "--path-format=absolute", "--git-common-dir")
        ).resolve()
        self.root = self.common / "ohmypm"
        self.config_path = self.root / "project.json"

    def lock(self):
        return file_lock(self.root / "lock")

    def config(self, enabled=True):
        require(self.config_path.is_file(), "Project not registered; run environment register")
        cfg = read_json(self.config_path)
        require(
            cfg["schema"] == SCHEMA,
            "Unsupported state schema; preserve state and restore matching runtime",
        )
        require(
            cfg["common"] == str(self.common), "Repository moved/copied; explicitly reconnect first"
        )
        require(not enabled or cfg["enabled"], "Environment disabled; enable explicitly")
        return cfg

    def register(self, pin, roles=None):
        self.check_store(Path(pin["path"]))
        verify_package(pin)
        current = self.config(enabled=False) if self.config_path.exists() else None
        roles = validate_profiles(
            roles
            or (current or {}).get("roles")
            or read_json(Path(pin["path"]) / "templates/workflow.json")["roles"]
        )
        cfg = {
            "schema": SCHEMA,
            "id": (current or {}).get("id", uuid.uuid4().hex),
            "common": str(self.common),
            "enabled": True,
            "runtime": pin,
            "roles": roles,
        }
        if current != cfg:
            if current:
                write_json(self.root / "config-history" / (uuid.uuid4().hex + ".json"), current)
            write_json(self.config_path, cfg)
        return {"config": cfg, "changed": current != cfg, "state": str(self.root)}

    def check_store(self, path):
        path = Path(path).resolve()
        rows = git(self.project, "worktree", "list", "--porcelain", "-z").split("\0")
        for row in rows:
            if row.startswith("worktree "):
                checkout = Path(row[len("worktree ") :]).resolve()
                require(
                    not path.is_relative_to(checkout),
                    "Runtime store must be outside all project checkouts",
                )

    def reconnect(self):
        cfg = read_json(self.config_path)
        require(cfg["schema"] == SCHEMA, "Unsupported schema")
        verify_package(cfg["runtime"])
        old_common = Path(cfg["common"])
        require(
            not old_common.exists() or old_common.resolve() == self.common,
            "Original repository still exists; a copied clone must use a new registration",
        )
        # Task paths and session handles require explicit reconciliation after a move.
        require(
            not list((self.root / "tasks").glob("*/state.json")),
            "Repository has tasks; preserve records and reconcile their paths before reconnecting",
        )
        cfg["common"] = str(self.common)
        write_json(self.config_path, cfg)
        return cfg

    def disable(self):
        cfg = self.config(enabled=False)
        # Disable new work without deleting running work, evidence, or pinned packages.
        cfg["enabled"] = False
        write_json(self.config_path, cfg)
        return {"enabled": False, "preserved": str(self.root), "active": self.active()}

    def active(self):
        rows = []
        for root in (self.root, self.common / "ohmypm-v1"):
            for path in (root / "tasks").glob("*/state.json"):
                state = read_json(path)
                if any(w["status"] not in ("cleaned", "retained") for w in state["works"].values()):
                    rows.append(str(path))
        return rows

    def snapshot(self):
        cfg = self.config()
        verify_package(cfg["runtime"])
        return {
            "runtime": copy.deepcopy(cfg["runtime"]),
            "roles": copy.deepcopy(cfg["roles"]),
            "project_id": cfg["id"],
            "schema": SCHEMA,
        }

    def route(self, request_id, request, path, reason, scope, small=False):
        safe_id(request_id)
        require(
            path in ("direct", "pl") and request.strip() and reason.strip() and scope.strip(),
            "Route needs original request, path, rationale and scope",
        )
        require(
            path != "direct" or small, "Direct work must explicitly be small, clear and reversible"
        )
        cfg = self.snapshot()
        target = self.root / "requests" / request_id / "route.json"
        old = read_json(target) if target.exists() else None
        row = {
            "id": request_id,
            "request": request,
            "path": path,
            "reason": reason,
            "scope": scope,
            "small_clear_reversible": bool(small),
            "environment": cfg,
            "revision": (old or {}).get("revision", 0) + 1,
        }
        if old:
            require(
                old["request"] == request, "Request ID already belongs to another original request"
            )
            write_json(target.parent / f"route-r{old['revision']}.json", old)
        write_json(target, row)
        return {**row, "announcement": f"처리 경로: {path} / 근거: {reason} / 요청 범위: {scope}"}

    def route_record(self, request_id):
        return read_json(self.root / "requests" / safe_id(request_id) / "route.json")

    def direct(self, request_id, argv):
        from workflow_core import command

        route = self.route_record(request_id)
        require(
            route["path"] == "direct" and route["small_clear_reversible"], "Direct route required"
        )
        require(
            route["environment"] == self.snapshot(), "Route environment changed; reclassify first"
        )
        evidence = self.root / "requests" / request_id / ("exec-" + uuid.uuid4().hex + ".json")
        write_json(evidence, {"route": route, "argv": argv, "status": "starting"})
        result = command(argv, cwd=self.project, timeout=600)
        write_json(
            evidence,
            {
                "route": route,
                "argv": argv,
                "status": "finished",
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
        )
        require(result.returncode == 0, f"Direct command failed; evidence: {evidence}")
        return {"evidence": str(evidence), "stdout": result.stdout}

    def context(self, role, snapshot=None):
        require(role in ("main", "pl", "work"), "Unknown role")
        snap = snapshot or self.snapshot()
        verify_package(snap["runtime"])
        package = Path(snap["runtime"]["path"])
        rules = (package / "references/entry.md").read_text(encoding="utf-8")
        return (
            f"# ohmyPM role: {role}\nProject: {self.project}\n"
            f"Runtime: {package}\nRuntime hash: {snap['runtime']['id']}\n"
            f"Project state: {self.root}\n"
            f"Read project-specific AGENTS.md/CLAUDE.md if present; preserve them.\n"
            f"Protocol: {package / 'PROTOCOL.md'}\n"
            f"Workflow CLI: {package / 'scripts/workflow.py'}\n"
            f"Environment CLI: {package / 'scripts/environment_cli.py'}\n"
            f"Recovery: inspect tasks, requests, roles and outbox in state.\n\n{rules}"
        )

    def export(self, destination):
        """Back up operating state into a new directory outside the checkout and state."""
        destination = Path(destination).resolve()
        require(
            not destination.exists()
            and not destination.is_relative_to(self.common)
            and not destination.is_relative_to(self.project),
            "Backup must be a new external path",
        )
        shutil.copytree(
            self.root, destination, symlinks=True, ignore=shutil.ignore_patterns("lock", "*.tmp")
        )
        return {
            "backup": str(destination),
            "runtime_packages": "Back up referenced runtimes separately",
        }

    def exclusions(self, owner, paths=None):
        """Reference-count owned info/exclude entries; preserve every non-owned byte."""
        import base64

        from workflow_core import relative

        registry_path = self.root / "excludes.json"
        target = self.common / "info/exclude"
        registry = (
            read_json(registry_path) if registry_path.exists() else {"owners": {}, "block": ""}
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        current = target.read_bytes() if target.exists() else b""
        pending = registry.get("pending")
        if pending:
            before, after = (base64.b64decode(pending[k]) for k in ("before", "after"))
            require(
                current in (before, after), "Exclude changed during interrupted update; preserve it"
            )
            if current == before:
                target.write_bytes(after)
            registry = pending["registry"]
            write_json(registry_path, registry)
            current = after
        block = registry["block"].encode("utf-8")
        require(not block or current.count(block) == 1, "Owned exclude block changed; preserve it")
        base = current.replace(block, b"", 1) if block else current
        owners = copy.deepcopy(registry["owners"])
        if paths is None:
            owners.pop(owner, None)
        else:
            owners[owner] = [relative(p) for p in paths]
        names = sorted({p for values in owners.values() for p in values})
        new_block = (
            (
                "\n# ohmyPM projections BEGIN\n"
                + "".join("/" + p + "\n" for p in names)
                + "# ohmyPM projections END\n"
            )
            if names
            else ""
        )
        after = base + new_block.encode("utf-8")
        updated = {"owners": owners, "block": new_block}
        write_json(
            registry_path,
            {
                **registry,
                "pending": {
                    "before": base64.b64encode(current).decode(),
                    "after": base64.b64encode(after).decode(),
                    "registry": updated,
                },
            },
        )
        target.write_bytes(after)
        write_json(registry_path, updated)


def task_runtime(project, task):
    env = Environment(project)
    new = env.root / "tasks" / safe_id(task) / "state.json"
    old = env.common / "ohmypm-v1/tasks" / safe_id(task) / "state.json"
    require(not (new.exists() and old.exists()), "Ambiguous task ID in old and new states")
    if new.exists():
        state = read_json(new)
        pin = state["contract"]["environment"]["runtime"]
        verify_package(pin)
        return Path(pin["path"]) / "scripts/workflow.py"
    require(
        not old.exists(), "Legacy task: use its preserved 1.0 runtime; do not convert it implicitly"
    )
    raise WorkflowError("Unknown task")
