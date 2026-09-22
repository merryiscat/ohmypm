"""External environment behavior on real Git repos; role transport is explicit test double."""

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import test_workflow as legacy

ROOT = legacy.ROOT
from environment import (  # noqa: E402
    Environment,
    file_lock,
    install_package,
    task_runtime,
    verify_package,
)
from migration import Migration  # noqa: E402
from roles import Roles  # noqa: E402
from workflow_core import Workflow, WorkflowError, git, read_json, write_json  # noqa: E402


class FakeRoles:
    def __init__(self):
        self.starts = 0
        self.sends = 0
        self.status = "live"
        self.lose_start = False
        self.lose_send = False

    def start(self, project, role, token, profile):
        self.starts += 1
        if self.lose_start:
            raise WorkflowError("lost create response")
        return {
            "terminal": {
                "handle": f"role-{self.starts}",
                "title": f"ohmyPM-{role}-{token}",
                "worktreeId": "fixture::" + str(project),
            }
        }

    def observe(self, handle, session=None):
        return {"status": self.status, "ready": self.status == "live"}

    def send(self, handle, text):
        self.sends += 1
        if self.lose_send:
            raise WorkflowError("lost send response")
        return {"accepted": True}


class EnvironmentTest(unittest.TestCase):
    commit = legacy.WorkflowTest.commit
    implement = legacy.WorkflowTest.implement
    review = legacy.WorkflowTest.review
    tearDown = legacy.WorkflowTest.tearDown

    def setUp(self):
        legacy.WorkflowTest.setUp(self)
        self.pin = install_package(ROOT / "plugin", self.root / "home")
        self.env = Environment(self.main)
        self.env.register(self.pin)
        self.flow = Workflow(self.main, backend=self.backend)
        self.catalog = ROOT / "plugin/skills/dispatch/references/legacy-v1.json"
        self.roles_backend = FakeRoles()
        self.roles = Roles(self.main, self.roles_backend)

    def create(self, approve=True, task="T-TEST"):
        self.env.route(
            task, self.request.read_text(encoding="utf-8"), "pl", "new feature", "greeting"
        )
        write_json(self.manifest, self.contract)
        state = self.flow.create(
            task,
            self.request,
            self.spec,
            self.manifest,
            self.main,
            "run:fixture",
            "pl",
            request_id=task,
        )
        if approve:
            state = self.flow.approve(task, 1, self.decision)
        return state

    def test_dirty_checkout_install_update_disable_preserve_every_file_and_index(self):
        (self.main / "base.txt").write_text("personal staged")
        git(self.main, "add", "base.txt")
        (self.main / "base.txt").write_text("personal unstaged")
        (self.main / "AGENTS.md").write_text("personal instructions")
        before = (
            git(self.main, "status", "--porcelain"),
            git(self.main, "ls-files", "--stage"),
            git(self.main, "rev-parse", "HEAD"),
            (self.main / "base.txt").read_bytes(),
        )
        self.env.register(self.pin)
        self.env.disable()
        self.assertEqual(
            before,
            (
                git(self.main, "status", "--porcelain"),
                git(self.main, "ls-files", "--stage"),
                git(self.main, "rev-parse", "HEAD"),
                (self.main / "base.txt").read_bytes(),
            ),
        )
        self.assertFalse((self.main / ".ohmypm").exists())

    def test_worktree_shares_state_and_preserves_project_rules(self):
        (self.main / "AGENTS.md").write_text("project rules")
        self.commit(self.main)
        self.create()
        item = self.flow.prepare("T-TEST", "w1")
        path = Path(item["path"])
        other = Environment(path)
        self.assertEqual(other.config()["id"], self.env.config()["id"])
        self.assertEqual((path / "AGENTS.md").read_text(), "project rules")
        self.assertFalse((path / ".ohmypm-work").exists())
        self.assertTrue(Path(item["private"]).is_relative_to(self.env.root))
        self.assertIn(
            "Session entry contract",
            (Path(item["private"]) / "context.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(git(path, "status", "--porcelain"), "")

    def test_full_external_lifecycle_keeps_runtime_files_out_of_commit(self):
        self.create()
        path = self.implement()
        self.review()
        self.flow.merge("T-TEST", "w1")
        self.flow.cleanup("T-TEST", "w1", self.receipt)
        self.assertFalse(path.exists())
        self.assertEqual(git(self.main, "show", "--pretty=", "--name-only", "HEAD"), "hello.txt")
        self.assertTrue((self.env.root / "tasks/T-TEST/r1/w1/environment").is_dir())

    def test_request_route_and_approval_are_required(self):
        write_json(self.manifest, self.contract)
        with self.assertRaisesRegex(WorkflowError, "Route record"):
            self.flow.create("T-NO", self.request, self.spec, self.manifest, self.main)
        self.create(approve=False)
        with self.assertRaisesRegex(WorkflowError, "approval"):
            self.flow.prepare("T-TEST", "w1")
        with self.assertRaisesRegex(WorkflowError, "small"):
            self.env.route("typo", "fix typo", "direct", "typo", "one label")
        self.env.route("typo", "fix typo", "direct", "typo", "one label", small=True)
        result = self.env.direct("typo", [sys.executable, "-c", "print('direct route')"])
        self.assertIn("direct route", result["stdout"])
        self.env.route("typo", "fix typo", "pl", "scope expanded", "new navigation")
        with self.assertRaisesRegex(WorkflowError, "Direct route"):
            self.env.direct("typo", [sys.executable, "-c", "print('must not run')"])

    def test_profile_change_and_runtime_selection_do_not_rewrite_active_contract(self):
        state = self.create()
        old = copy.deepcopy(state["contract"])
        roles = self.env.config()["roles"]
        roles["work"]["model"] = "different-model"
        self.env.register(self.pin, roles)
        self.assertEqual(self.flow.load("T-TEST")["contract"], old)
        self.flow.prepare("T-TEST", "w1")
        self.assertEqual(
            task_runtime(self.main, "T-TEST"), Path(self.pin["path"]) / "scripts/workflow.py"
        )
        self.env.disable()
        self.flow.approved(self.flow.load("T-TEST"))
        with self.assertRaisesRegex(WorkflowError, "disabled"):
            self.env.snapshot()

    def test_tampered_or_missing_package_fails_closed(self):
        self.create()
        entry = Path(self.pin["path"]) / "PROTOCOL.md"
        entry.write_text("lowered rules")
        with self.assertRaisesRegex(WorkflowError, "modified"):
            self.flow.prepare("T-TEST", "w1")
        entry.unlink()
        with self.assertRaises(WorkflowError):
            verify_package(self.pin)

    def test_tracked_and_untracked_config_are_never_overwritten(self):
        source = self.root / "mcp-source.json"
        source.write_text("{}")
        self.contract["works"][0]["harness"]["files"] = [
            {"source": str(source), "target": ".mcp.json"}
        ]
        (self.main / ".mcp.json").write_text("user config")
        self.commit(self.main)
        self.create()
        with self.assertRaisesRegex(WorkflowError, "Tracked"):
            self.flow.prepare("T-TEST", "w1")
        path = Path(self.flow.load("T-TEST")["works"]["w1"]["path"])
        self.assertEqual((path / ".mcp.json").read_text(), "user config")

    def test_projection_staging_and_user_changes_block_cleanup(self):
        source = self.root / "mcp-source.json"
        source.write_text("{}")
        self.contract["works"][0]["harness"]["files"] = [
            {"source": str(source), "target": ".mcp.json"}
        ]
        self.create()
        path = Path(self.flow.prepare("T-TEST", "w1")["path"])
        self.assertEqual(git(path, "status", "--porcelain"), "")
        git(path, "add", "-f", ".mcp.json")
        with self.assertRaisesRegex(WorkflowError, "must not be staged"):
            self.flow.check("T-TEST", "w1")
        git(path, "reset", "HEAD", "--", ".mcp.json")
        (path / ".mcp.json").write_text("personal change")
        with self.assertRaisesRegex(WorkflowError, "configuration changed"):
            self.flow.check("T-TEST", "w1")

    def test_exclude_ownership_preserves_other_owners_and_personal_content(self):
        target = self.env.common / "info/exclude"
        original = target.read_bytes()
        self.env.exclusions("first", [".mcp.json"])
        self.env.exclusions("second", [".mcp.json", ".claude/settings.local.json"])
        self.env.exclusions("first")
        self.assertIn(b"/.mcp.json", target.read_bytes())
        target.write_bytes(target.read_bytes() + b"personal/\n")
        self.env.exclusions("second")
        self.assertEqual(target.read_bytes(), original + b"personal/\n")

    def test_pl_restart_preserves_questions_and_fences_old_generation(self):
        self.create()
        first = self.roles.connect("pl")
        self.roles.accept("pl", first["generation"], first["context_digest"])
        self.roles.enqueue("pl", "question-1", "T-TEST", 1, "Review existing spec")
        self.roles.deliver("question-1")
        self.roles_backend.status = "exited"
        second = self.roles.connect("pl")
        self.assertEqual(second["generation"], 2)
        self.roles_backend.status = "live"
        second = self.roles.connect("pl")
        self.roles.accept("pl", 2, second["context_digest"])
        self.roles.deliver("question-1")
        with self.assertRaisesRegex(WorkflowError, "Stale"):
            self.roles.acknowledge("question-1", 1, 1)
        self.roles.acknowledge("question-1", 2, 1)
        self.roles.acknowledge("question-1", 2, 1, completed=True)
        self.assertIsNotNone(self.flow.load("T-TEST")["approval"])
        self.assertEqual(self.roles_backend.starts, 2)

    def test_pl_unknown_liveness_and_lost_start_never_duplicate(self):
        self.roles_backend.lose_start = True
        with self.assertRaises(WorkflowError):
            self.roles.connect("pl")
        with self.assertRaisesRegex(WorkflowError, "unknown"):
            self.roles.connect("pl")
        self.assertEqual(self.roles_backend.starts, 1)
        self.roles.reconcile(
            "pl",
            {
                "terminal": {
                    "handle": "reconciled",
                    "title": "ohmyPM-pl-" + self.roles.load("pl")["token"],
                    "worktreeId": "fixture::" + str(self.main),
                }
            },
        )
        self.roles_backend.status = "unverifiable"
        self.roles.connect("pl")
        self.assertEqual(self.roles_backend.starts, 1)

    def test_lost_mail_does_not_resend_or_claim_acceptance(self):
        record = self.roles.connect("pl")
        self.roles.accept("pl", 1, record["context_digest"])
        self.roles.enqueue("pl", "mail", "T-DESIGN", 1, "question")
        self.roles_backend.lose_send = True
        with self.assertRaises(WorkflowError):
            self.roles.deliver("mail")
        self.roles.deliver("mail")
        self.assertEqual(self.roles_backend.sends, 2)  # one context, one uncertain mail
        self.assertEqual(read_json(self.env.root / "outbox/mail.json")["status"], "pending")

    def test_two_role_preparations_are_serialized_by_repository_lock(self):
        with self.env.lock():
            with self.assertRaisesRegex(WorkflowError, "locked"):
                with file_lock(self.env.root / "lock"):
                    pass

    def legacy_fixture(self):
        catalog = read_json(self.catalog)
        (self.main / "AGENTS.md").write_text(
            "# project rules\n\n" + catalog["blocks"]["AGENTS.md"] + "\n\n## Local\nkeep\n",
            encoding="utf-8",
        )
        (self.main / "docs").mkdir(exist_ok=True)
        (self.main / "docs/workflow.json").write_text(
            json.dumps({"roles": self.env.config()["roles"]})
        )
        (self.main / "docs/protocol.md").write_text("user-modified protocol")
        self.commit(self.main)
        return Migration(self.main, self.catalog)

    def test_migration_preserves_unknown_assets_and_roundtrips_exact_bytes(self):
        migration = self.legacy_fixture()
        agents = (self.main / "AGENTS.md").read_bytes()
        model = (self.main / "docs/workflow.json").read_bytes()
        plan = migration.plan()
        result = migration.apply(plan["id"], plan["digest"])
        self.assertTrue(result["preserved_conflicts"])
        self.assertNotIn(b"kickoff-workspaces", (self.main / "AGENTS.md").read_bytes())
        self.assertIn("## Local\nkeep", (self.main / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertEqual((self.main / "docs/protocol.md").read_text(), "user-modified protocol")
        migration.rollback(plan["id"])
        self.assertEqual((self.main / "AGENTS.md").read_bytes(), agents)
        self.assertEqual((self.main / "docs/workflow.json").read_bytes(), model)
        self.assertEqual(git(self.main, "status", "--porcelain"), "")

    def test_migration_stale_plan_and_rollback_conflict_preserve_user_work(self):
        migration = self.legacy_fixture()
        plan = migration.plan()
        (self.main / "AGENTS.md").write_text("user change")
        with self.assertRaisesRegex(WorkflowError, "Stale"):
            migration.apply(plan["id"], plan["digest"])
        self.assertTrue((self.main / "docs/workflow.json").exists())
        plan = migration.plan()
        migration.apply(plan["id"], plan["digest"])
        (self.main / "docs/workflow.json").write_text("new config")
        with self.assertRaisesRegex(WorkflowError, "conflict"):
            migration.rollback(plan["id"])
        self.assertEqual((self.main / "docs/workflow.json").read_text(), "new config")

    def test_migration_interruption_resumes_without_losing_original(self):
        migration = self.legacy_fixture()
        plan = migration.plan()
        real = migration.write_target
        calls = []

        def fail_after_write(path, value):
            real(path, value)
            calls.append(path)
            raise OSError("interrupted after write")

        with patch.object(migration, "write_target", side_effect=fail_after_write):
            with self.assertRaises(OSError):
                migration.apply(plan["id"], plan["digest"])
        migration.apply(plan["id"], plan["digest"])
        migration.rollback(plan["id"])
        self.assertEqual(git(self.main, "status", "--porcelain"), "")

    def test_active_legacy_work_prevents_removal(self):
        migration = self.legacy_fixture()
        write_json(
            self.env.common / "ohmypm-v1/tasks/OLD/state.json",
            {"works": {"w": {"status": "running"}}},
        )
        plan = migration.plan()
        with self.assertRaisesRegex(WorkflowError, "Active legacy"):
            migration.apply(plan["id"], plan["digest"])
        self.assertTrue((self.main / "docs/workflow.json").exists())

    def test_backup_and_fresh_clone_identity(self):
        destination = self.root / "backup"
        self.env.export(destination)
        self.assertEqual(read_json(destination / "project.json"), self.env.config())
        clone = self.root / "clone"
        git(self.root, "clone", str(self.main), str(clone))
        other = Environment(clone)
        other.register(self.pin)
        self.assertNotEqual(other.config()["id"], self.env.config()["id"])

    def test_external_cli_routes_to_pinned_runtime(self):
        self.create()
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "plugin/skills/dispatch/scripts/workflow.py"),
                "--project",
                str(self.main),
                "show",
                "--task",
                "T-TEST",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["contract"]["environment"]["runtime"], self.pin)

    def test_codex_pl_uses_user_authorized_bypass_and_pins_it(self):
        from roles import launcher_argv

        profile = self.env.config()["roles"]["pl"]
        argv = launcher_argv(profile)
        self.assertEqual(argv[:2], ["codex", "--dangerously-bypass-approvals-and-sandbox"])
        state = self.create()
        self.assertEqual(state["contract"]["environment"]["roles"]["pl"]["approval"], "bypass")
        profile["approval"] = "default"
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", launcher_argv(profile))

    def test_shell_idle_is_not_model_liveness_and_runner_exit_is_positive(self):
        from roles import RoleAdapter

        lifecycle = self.root / "lifecycle.json"
        write_json(
            lifecycle,
            {
                "token": "token",
                "status": "running",
                "pid": 999999,
                "process_identity": "old-pid-instance",
            },
        )
        session = {"token": "token", "lifecycle": str(lifecycle)}
        adapter = RoleAdapter()
        with patch.object(
            adapter.orca, "call", side_effect=AssertionError("Must not use shell idle")
        ):
            self.assertEqual(adapter.observe("shell", session)["status"], "unverifiable")
            write_json(lifecycle, {"token": "token", "status": "exited", "exit_code": 0})
            self.assertEqual(adapter.observe("shell", session)["status"], "exited")

    def test_role_runner_retains_real_process_exit(self):
        import os

        from role_runner import process_identity

        self.assertIsNotNone(process_identity(os.getpid()))
        request = self.root / "launch.json"
        lifecycle = self.root / "life.json"
        write_json(
            request,
            {
                "project": str(self.main),
                "token": "test-token",
                "lifecycle": str(lifecycle),
                "argv": [sys.executable, "-c", "raise SystemExit(7)"],
            },
        )
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "plugin/skills/dispatch/scripts/role_runner.py"),
                "--record",
                str(request),
            ],
            capture_output=True,
        )
        self.assertEqual(result.returncode, 7)
        self.assertEqual(read_json(lifecycle)["status"], "exited")
        self.assertEqual(read_json(lifecycle)["exit_code"], 7)

    def test_pl_reconcile_rejects_receipt_for_another_session(self):
        self.roles_backend.lose_start = True
        with self.assertRaises(WorkflowError):
            self.roles.connect("pl")
        with self.assertRaisesRegex(WorkflowError, "token"):
            self.roles.reconcile("pl", {"terminal": {"handle": "wrong", "title": "somebody else"}})


if __name__ == "__main__":
    unittest.main()
