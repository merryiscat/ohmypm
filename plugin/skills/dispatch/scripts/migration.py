"""Reviewable, hash-guarded removal of proven v1 installation assets.

Plan/apply/rollback never stage, commit, rewrite history, or touch other projects.
Unknown ownership and active legacy work preserve the old installation.
"""

from __future__ import annotations

import base64
import copy
import uuid
from pathlib import Path

from environment import Environment, no_links, validate_profiles
from workflow_core import digest, git, read_json, require, safe_id, write_json


def blob(value):
    return None if value is None else base64.b64encode(value).decode("ascii")


def unblob(value):
    return None if value is None else base64.b64decode(value)


def bytes_at(path):
    return path.read_bytes() if path.is_file() else None


class Migration:
    def __init__(self, project, catalog):
        self.env = Environment(project)
        self.project = self.env.project
        self.catalog = read_json(catalog)
        self.root = self.env.root / "migrations"

    def fingerprint(self):
        return {
            "head": git(self.project, "rev-parse", "HEAD"),
            "index": digest(git(self.project, "ls-files", "--stage", "-z")),
            "hooks": git(
                self.project, "config", "--get", "core.hooksPath", check=False
            ).stdout.strip(),
        }

    def active_legacy(self):
        return [
            p for p in self.env.active() if Path(p).is_relative_to(self.env.common / "ohmypm-v1")
        ]

    def plan(self):
        cfg = self.env.config(enabled=False)
        rows, changes = [], []

        def propose(name, before, after, reason):
            rows.append(
                {"path": name, "action": "remove" if after is None else "edit", "reason": reason}
            )
            changes.append({"path": name, "before": blob(before), "after": blob(after)})

        for name, expected in self.catalog["files"].items():
            target = no_links(self.project, self.project / name)
            before = bytes_at(target)
            if before is None:
                continue
            # Hook provenance is not recoverable from a matching filename alone.
            if name.startswith(".githooks/") and self.fingerprint()["hooks"]:
                rows.append(
                    {
                        "path": name,
                        "action": "conflict",
                        "reason": "hooksPath provenance unknown; preserve",
                    }
                )
            elif digest(before.replace(b"\r\n", b"\n")) == expected:
                propose(name, before, None, "Exact known v1 installation content")
            else:
                rows.append(
                    {
                        "path": name,
                        "action": "conflict",
                        "reason": "Unknown or user-modified content",
                    }
                )
        for name, block in self.catalog["blocks"].items():
            target = no_links(self.project, self.project / name)
            before = bytes_at(target)
            if before is None:
                continue
            variants = [block.encode("utf-8"), block.replace("\n", "\r\n").encode("utf-8")]
            matching = [b for b in variants if before.count(b) == 1]
            if matching:
                block_bytes = matching[0]
                start = before.index(block_bytes)
                end = start + len(block_bytes)
                # Exact block only, with line boundaries. Never remove a whole file.
                if (start == 0 or before[start - 1 : start] == b"\n") and (
                    end == len(before) or before[end : end + 1] in (b"\n", b"\r")
                ):
                    propose(
                        name,
                        before,
                        before[:start] + before[end:],
                        "Exact known managed block; preserve other bytes",
                    )
                else:
                    rows.append(
                        {
                            "path": name,
                            "action": "conflict",
                            "reason": "Managed block boundaries changed",
                        }
                    )
            else:
                rows.append({"path": name, "action": "keep", "reason": "No exact owned block"})
        model_file = no_links(self.project, self.project / "docs/workflow.json")
        desired_cfg = copy.deepcopy(cfg)
        if model_file.is_file():
            try:
                value = read_json(model_file)
                require(set(value) <= {"version", "roles"}, "Unknown model config fields")
                desired_cfg["roles"] = validate_profiles(value["roles"])
                propose(
                    "docs/workflow.json",
                    model_file.read_bytes(),
                    None,
                    "Transfer validated role profiles to local state",
                )
            except (ValueError, KeyError, RuntimeError):
                rows.append(
                    {
                        "path": "docs/workflow.json",
                        "action": "conflict",
                        "reason": "Unknown profile schema; preserve",
                    }
                )
        for name in (".gitignore", "orca.yaml", ".worktreeinclude", "docs/tasks", "docs/reviews"):
            rows.append(
                {
                    "path": name,
                    "action": "keep",
                    "reason": "Shared project assets; no ownership proof",
                }
            )
        plan = {
            "id": "migration-" + uuid.uuid4().hex,
            "project": str(self.project),
            "fingerprint": self.fingerprint(),
            "active_legacy": self.active_legacy(),
            "rows": rows,
            "changes": changes,
            "config_before": cfg,
            "config_after": desired_cfg,
        }
        plan["digest"] = digest(plan)
        write_json(self.root / plan["id"] / "plan.json", plan)
        return plan

    def load(self, identity):
        plan = read_json(self.root / safe_id(identity) / "plan.json")
        expected = plan.pop("digest")
        require(digest(plan) == expected, "Migration plan changed; regenerate it")
        plan["digest"] = expected
        require(plan["project"] == str(self.project), "Plan belongs to another checkout")
        return plan

    def write_target(self, path, value):
        no_links(self.project, path)
        if value is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_name(path.name + ".ohmypm-" + uuid.uuid4().hex)
            temp.write_bytes(value)
            temp.replace(path)

    def apply(self, identity, expected_digest):
        plan = self.load(identity)
        require(expected_digest == plan["digest"], "Apply must name the reviewed plan digest")
        require(not self.active_legacy(), "Active legacy work; preserve its installation")
        require(plan["fingerprint"] == self.fingerprint(), "Stale plan: HEAD/index/hooks changed")
        folder = self.root / identity
        receipt_path = folder / "receipt.json"
        receipt = (
            read_json(receipt_path)
            if receipt_path.exists()
            else {"status": "applying", "steps": []}
        )
        require(
            receipt["status"] in ("applying", "applied"),
            "Migration was rolled back; make a new plan",
        )
        require(
            self.env.config(enabled=False) in (plan["config_before"], plan["config_after"]),
            "Local profile changed",
        )
        # Check every target first; an interrupted apply may have written the after bytes.
        for change in plan["changes"]:
            target = no_links(self.project, self.project / change["path"])
            current = bytes_at(target)
            allowed = (
                (unblob(change["before"]), unblob(change["after"]))
                if receipt_path.exists()
                else (unblob(change["before"]),)
            )
            require(current in allowed, f"Stale plan: {change['path']} changed; preserve it")
        # plan already contains exact original bytes; persist intent before writes.
        write_json(receipt_path, receipt)
        for change in plan["changes"]:
            target = self.project / change["path"]
            if bytes_at(target) != unblob(change["after"]):
                self.write_target(target, unblob(change["after"]))
            if change["path"] not in receipt["steps"]:
                receipt["steps"].append(change["path"])
                write_json(receipt_path, receipt)
        write_json(self.env.config_path, plan["config_after"])
        receipt["status"] = "applied"
        write_json(receipt_path, receipt)
        return {
            "receipt": receipt,
            "preserved_conflicts": [r for r in plan["rows"] if r["action"] == "conflict"],
            "note": "Review checkout diff separately; nothing staged or committed",
        }

    def rollback(self, identity):
        plan = self.load(identity)
        target = self.root / identity / "receipt.json"
        receipt = read_json(target)
        require(
            plan["fingerprint"] == self.fingerprint(),
            "HEAD/index/hooks changed; manual recovery required",
        )
        require(
            self.env.config(enabled=False) in (plan["config_before"], plan["config_after"]),
            "Profile changed; preserve it",
        )
        for change in plan["changes"]:
            path = no_links(self.project, self.project / change["path"])
            require(
                bytes_at(path) in (unblob(change["before"]), unblob(change["after"])),
                f"Rollback conflict; both versions preserved: {change['path']}",
            )
        receipt["status"] = "rolling_back"
        write_json(target, receipt)
        for change in reversed(plan["changes"]):
            self.write_target(self.project / change["path"], unblob(change["before"]))
        write_json(self.env.config_path, plan["config_before"])
        receipt["status"] = "rolled_back"
        write_json(target, receipt)
        return receipt
