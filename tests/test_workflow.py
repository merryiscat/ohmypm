"""Behavior tests use real temporary Git repositories and an isolated Orca adapter double."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "plugin/skills/dispatch/scripts"
sys.path.insert(0, str(RUNTIME))
from workflow_core import Workflow, WorkflowError, git, write_json  # noqa: E402


class FakeOrca:
    """Real Git behavior; no real Orca windows, agents, messages or account changes."""

    def __init__(self, root):
        self.root = root
        self.rows = []
        self.create_count = 0
        self.launch_count = 0
        self.send_count = 0
        self.live = []
        self.lose_create_receipt = False
        self.lose_launch_receipt = False
        self.lose_send_receipt = False

    def doctor(self):
        return {"runtime": {"state": "ready"}}

    def find(self, project, name):
        return [row for row in self.rows if row["displayName"] == name]

    def create(self, project, name, base):
        self.create_count += 1
        self.project = project
        path = self.root / name
        git(project, "worktree", "add", "-b", name, str(path), base)
        row = {"displayName": name, "path": str(path), "id": "fixture::" + str(path)}
        self.rows.append(row)
        if self.lose_create_receipt:
            self.lose_create_receipt = False
            raise WorkflowError("Simulated lost creation receipt")
        return row

    def remove(self, identity):
        row = next(row for row in self.rows if row["id"] == identity)
        git(self.project, "worktree", "remove", row["path"])
        self.rows.remove(row)

    def terminals(self, identity):
        return self.live

    def launch(self, path, spec, profile):
        self.launch_count += 1
        if self.lose_launch_receipt:
            raise WorkflowError("Simulated unknown launch")
        return {"dispatch": {"id": "fixture-dispatch"}, "worktree": str(path)}

    def send(self, address, event):
        self.send_count += 1
        if self.lose_send_receipt:
            raise WorkflowError("Simulated unknown send")
        return {"id": "fixture-message"}


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ohmypm-v1-test-")
        self.root = Path(self.temporary.name).resolve()
        self.main = self.root / "main"
        self.main.mkdir()
        git(self.main, "init", "-b", "main")
        git(self.main, "config", "user.name", "ohmyPM fixture")
        git(self.main, "config", "user.email", "fixture@example.invalid")
        git(self.main, "config", "core.autocrlf", "false")
        (self.main / ".gitignore").write_text(".ohmypm-work/\n.venv/\n__pycache__/\n")
        (self.main / "base.txt").write_text("base\n")
        self.commit(self.main)
        self.request = self.root / "request.txt"
        self.request.write_text("요청 원문 & 수정하지 말 것\n", encoding="utf-8")
        self.spec = self.root / "spec.md"
        self.spec.write_text("# Agreed greeting\nhello is required\n")
        self.decision = self.root / "decision.txt"
        self.decision.write_text("이 버전으로 구현해 주세요.", encoding="utf-8")
        self.manifest = self.root / "task.json"
        self.contract = {
            "criteria": [
                {
                    "id": "C1",
                    "description": "Greeting is hello",
                    "command": [
                        sys.executable,
                        "-c",
                        "from pathlib import Path; assert Path('hello.txt').read_text() == 'hello'",
                    ],
                }
            ],
            "works": [
                {
                    "id": "w1",
                    "paths": ["hello.txt"],
                    "criteria": ["C1"],
                    "depends_on": [],
                    "parallel_safe": False,
                    "resources": [],
                    "harness": {"tools": ["git"], "setup": [], "files": [], "ports": []},
                }
            ],
        }
        self.backend = FakeOrca(self.root / "work")
        self.flow = Workflow(self.main, backend=self.backend)
        self.receipt = self.root / "released.json"
        write_json(self.receipt, {"ok": True, "result": {"released": True}})

    def tearDown(self):
        # Only recursively remove this fixture's freshly allocated absolute temp root.
        assert self.root.is_relative_to(Path(tempfile.gettempdir()).resolve())
        assert self.root.name.startswith("ohmypm-v1-test-")
        self.temporary.cleanup()

    def commit(self, path):
        git(path, "add", "--all")
        git(path, "commit", "-m", "fixture")

    def create(self, approve=True, task="T-TEST"):
        write_json(self.manifest, self.contract)
        state = self.flow.create(
            task,
            self.request,
            self.spec,
            self.manifest,
            self.main,
            "run:fixture",
            "pl conversation",
        )
        if approve:
            state = self.flow.approve(task, 1, self.decision)
        return state

    def implement(self, work="w1", filename="hello.txt", value="hello"):
        item = self.flow.prepare("T-TEST", work)
        path = Path(item["path"])
        (path / filename).parent.mkdir(parents=True, exist_ok=True)
        (path / filename).write_text(value)
        self.commit(path)
        report = self.root / (work + "-report.md")
        report.write_text("Implemented and exercised greeting")
        self.flow.submit("T-TEST", work, report)
        self.flow.check("T-TEST", work)
        return path

    def review(self, work="w1", passed=True):
        state = self.flow.load("T-TEST")
        findings = {
            "reviewer": "pl",
            "candidate": state["works"][work]["submission"],
            "code_review": "Read committed greeting and exercised it",
            "criteria": {
                key: {"status": "pass" if passed else "fail", "evidence": "observed greeting"}
                for key in self.flow.definition(state, work)["criteria"]
            },
        }
        target = self.root / (work + "-review.json")
        write_json(target, findings)
        return self.flow.verdict("T-TEST", work, target)

    def test_approval_and_repeated_design_dialogue(self):
        self.create(approve=False)
        with self.assertRaises(WorkflowError):
            self.flow.prepare("T-TEST", "w1")
        for revision in (1, 2):
            question = self.root / "question.md"
            question.write_text("Which greeting?")
            self.flow.question("T-TEST", question)
            self.spec.write_text(f"Agreed version {revision + 1}")
            self.flow.revise("T-TEST", self.spec, self.manifest)
        with self.assertRaises(WorkflowError):
            self.flow.approve("T-TEST", 1, self.decision)
        state = self.flow.approve("T-TEST", 3, self.decision)
        self.assertEqual(state["request"], self.request.read_text(encoding="utf-8"))
        self.assertEqual(len(state["history"]), 2)

    def test_full_implementation_review_merge_cleanup(self):
        self.create()
        path = self.implement()
        self.review()
        self.flow.merge("T-TEST", "w1")
        self.assertEqual((self.main / "hello.txt").read_text(), "hello")
        self.flow.merge("T-TEST", "w1")  # idempotent replay
        self.flow.cleanup("T-TEST", "w1", self.receipt)
        self.assertFalse(path.exists())
        state = self.flow.show("T-TEST")
        self.assertEqual(state["status"], "done")
        self.assertEqual(state["works"]["w1"]["status"], "cleaned")
        self.assertTrue(Path(state["works"]["w1"]["report"]).exists())

    def test_failed_check_cannot_be_called_passed_by_review(self):
        self.create()
        path = self.implement(value="wrong")
        with self.assertRaises(WorkflowError):
            self.review()
        self.review(passed=False)
        with self.assertRaises(WorkflowError):
            self.flow.merge("T-TEST", "w1")
        self.assertTrue(path.exists())

    def test_missing_automated_evidence_blocks_verdict(self):
        self.create()
        path = Path(self.flow.prepare("T-TEST", "w1")["path"])
        (path / "hello.txt").write_text("hello")
        self.commit(path)
        report = self.root / "report.md"
        report.write_text("I claim it works")
        self.flow.submit("T-TEST", "w1", report)
        with self.assertRaisesRegex(WorkflowError, "checks"):
            self.review()

    def test_result_change_invalidates_pl_verdict(self):
        self.create()
        path = self.implement()
        self.review()
        (path / "hello.txt").write_text("changed after review")
        self.commit(path)
        with self.assertRaisesRegex(WorkflowError, "stale"):
            self.flow.merge("T-TEST", "w1")

    def test_main_advance_requires_integration_and_fresh_verdict(self):
        self.create()
        self.implement()
        self.review()
        (self.main / "base.txt").write_text("new main")
        self.commit(self.main)
        with self.assertRaisesRegex(WorkflowError, "Main advanced"):
            self.flow.merge("T-TEST", "w1")

    def test_dirty_main_and_out_of_scope_changes_are_preserved(self):
        self.create()
        path = self.implement()
        self.review()
        (self.main / "personal.txt").write_text("user work")
        with self.assertRaisesRegex(WorkflowError, "Uncommitted"):
            self.flow.merge("T-TEST", "w1")
        (path / "outside.txt").write_text("not owned")
        self.commit(path)
        with self.assertRaisesRegex(WorkflowError, "outside owned"):
            self.flow.check("T-TEST", "w1")
        self.assertEqual((self.main / "personal.txt").read_text(), "user work")

    def test_snapshot_tampering_invalidates_approval(self):
        state = self.create()
        Path(state["spec_path"]).write_text("lowered acceptance")
        with self.assertRaisesRegex(WorkflowError, "snapshot"):
            self.flow.prepare("T-TEST", "w1")

    def test_parallel_limit_conflicts_dependencies_and_project_wide_ownership(self):
        self.contract["works"] = []
        for name in ("a", "b", "c", "d"):
            self.contract["works"].append(
                {
                    "id": name,
                    "paths": [name + ".txt"],
                    "criteria": ["C1"],
                    "parallel_safe": True,
                    "independence_reason": "Separate files and tests",
                    "resources": [],
                    "depends_on": ["a"] if name == "d" else [],
                    "harness": {},
                }
            )
        self.create()
        self.assertEqual(self.flow.schedule("T-TEST")["ready"], ["a", "b"])
        self.flow.prepare("T-TEST", "a")
        self.flow.prepare("T-TEST", "b")
        self.assertEqual(self.flow.schedule("T-TEST")["ready"], [])
        self.create(task="T-SECOND")
        self.assertEqual(self.flow.schedule("T-SECOND")["ready"], [])
        self.assertFalse(
            self.flow.compatible(
                {"parallel_safe": True, "paths": ["src"]},
                {"parallel_safe": True, "paths": ["src/a.py"]},
            )
        )

    def test_harness_missing_tool_never_launches(self):
        self.contract["works"][0]["harness"]["tools"] = ["ohmypm-deliberately-missing-tool"]
        self.create()
        with self.assertRaisesRegex(WorkflowError, "tool missing"):
            self.flow.prepare("T-TEST", "w1")
        with self.assertRaises(WorkflowError):
            self.flow.launch("T-TEST", "w1")
        self.assertEqual(self.backend.launch_count, 0)

    def test_task_environment_has_local_data_and_no_undeclared_env(self):
        self.create()
        item = self.flow.prepare("T-TEST", "w1")
        os.environ["OHMYPM_PRIVATE_TEST_VALUE"] = "do not inherit"
        try:
            env = self.flow.environment(item)
            self.assertNotIn("OHMYPM_PRIVATE_TEST_VALUE", env)
            self.assertTrue(Path(env["OHMYPM_DATA_DIR"]).is_relative_to(Path(item["path"])))
            result = self.flow.execute(
                "T-TEST",
                "w1",
                [sys.executable, "-c", "import os; print(os.environ['OHMYPM_DATA_DIR'])"],
            )
            self.assertIn(".ohmypm-work", result["stdout"])
        finally:
            del os.environ["OHMYPM_PRIVATE_TEST_VALUE"]

    def test_lost_creation_receipt_is_reconciled_without_duplicate(self):
        self.create()
        self.backend.lose_create_receipt = True
        with self.assertRaises(WorkflowError):
            self.flow.prepare("T-TEST", "w1")
        resumed = Workflow(self.main, backend=self.backend)
        self.assertEqual(resumed.prepare("T-TEST", "w1")["status"], "ready")
        self.assertEqual(self.backend.create_count, 1)

    def test_launch_and_notification_replays_do_not_duplicate(self):
        self.create()
        self.flow.prepare("T-TEST", "w1")
        self.flow.launch("T-TEST", "w1")
        self.flow.launch("T-TEST", "w1")
        self.assertEqual(self.backend.launch_count, 1)
        event = self.flow.events("T-TEST")[0]["id"]
        self.flow.deliver("T-TEST", event)
        self.flow.deliver("T-TEST", event)
        self.assertEqual(self.backend.send_count, 1)

    def test_unknown_launch_and_send_do_not_retry(self):
        self.create()
        self.flow.prepare("T-TEST", "w1")
        self.backend.lose_launch_receipt = True
        for _ in range(2):
            with self.assertRaises(WorkflowError):
                self.flow.launch("T-TEST", "w1")
        self.assertEqual(self.backend.launch_count, 1)
        self.backend.lose_send_receipt = True
        event = self.flow.events("T-TEST")[0]["id"]
        for _ in range(2):
            with self.assertRaises(WorkflowError):
                self.flow.deliver("T-TEST", event)
        self.assertEqual(self.backend.send_count, 1)

    def test_merge_interruption_reconciles_exact_result(self):
        self.create()
        self.implement()
        self.review()
        state = self.flow.load("T-TEST")
        state["works"]["w1"]["status"] = "merging"
        self.flow.save(state)
        git(self.main, "merge", "--ff-only", state["works"]["w1"]["verdict"]["candidate"]["commit"])
        self.assertEqual(self.flow.merge("T-TEST", "w1")["status"], "merged")

    def test_cleanup_preserves_live_terminals_and_new_changes(self):
        self.create()
        path = self.implement()
        self.review()
        self.flow.merge("T-TEST", "w1")
        self.backend.live = [{"handle": "unrelated-user-terminal"}]
        with self.assertRaisesRegex(WorkflowError, "terminals"):
            self.flow.cleanup("T-TEST", "w1", self.receipt)
        self.backend.live = []
        (path / "personal.txt").write_text("retain me")
        with self.assertRaises(WorkflowError):
            self.flow.cleanup("T-TEST", "w1", self.receipt)
        self.assertEqual((path / "personal.txt").read_text(), "retain me")

    def test_retain_allows_revision_without_destroying_old_work(self):
        self.create()
        path = self.implement()
        self.flow.retain("T-TEST", "w1", self.receipt)
        revised = self.flow.revise("T-TEST", self.spec, self.manifest)
        self.assertEqual(revised["revision"], 2)
        self.assertTrue((path / "hello.txt").exists())
        self.assertIsNone(revised["approval"])

    def test_cleanup_resumes_after_lost_removal_receipt(self):
        self.create()
        path = self.implement()
        self.review()
        self.flow.merge("T-TEST", "w1")
        remove = self.backend.remove

        def lost(identity):
            remove(identity)
            raise WorkflowError("Lost removal receipt")

        with patch.object(self.backend, "remove", side_effect=lost):
            with self.assertRaises(WorkflowError):
                self.flow.cleanup("T-TEST", "w1", self.receipt)
        self.assertFalse(path.exists())
        with patch.object(self.backend, "terminals", side_effect=AssertionError("Already removed")):
            self.assertEqual(self.flow.cleanup("T-TEST", "w1", self.receipt)["status"], "cleaned")

    def test_harness_overlay_is_excluded_from_result_and_cleanup_is_retryable(self):
        original = self.main / ".mcp.json"
        original.write_text("{}")
        self.commit(self.main)
        source = self.root / "mcp.json"
        source.write_text('{"mcpServers": {}}')
        self.contract["works"][0]["harness"]["files"] = [
            {"source": str(source), "target": ".mcp.json"}
        ]
        self.create()
        path = Path(self.flow.prepare("T-TEST", "w1")["path"])
        (path / "hello.txt").write_text("hello")
        git(path, "add", "hello.txt")
        git(path, "commit", "-m", "greeting")
        report = self.root / "report.md"
        report.write_text("Implemented greeting")
        self.flow.submit("T-TEST", "w1", report)
        self.flow.check("T-TEST", "w1")
        self.review()
        self.flow.merge("T-TEST", "w1")
        with patch.object(self.backend, "remove", side_effect=WorkflowError("Uncertain removal")):
            with self.assertRaises(WorkflowError):
                self.flow.cleanup("T-TEST", "w1", self.receipt)
        self.assertEqual((path / ".mcp.json").read_text(), "{}")
        self.assertEqual(self.flow.cleanup("T-TEST", "w1", self.receipt)["status"], "cleaned")
        self.assertEqual(original.read_text(), "{}")

    def test_staged_harness_and_changed_sources_are_rejected(self):
        source = self.root / "mcp.json"
        source.write_text("{}")
        self.contract["works"][0]["harness"]["files"] = [
            {"source": str(source), "target": ".mcp.json"}
        ]
        self.create()
        source.write_text('{"changed": true}')
        with self.assertRaisesRegex(WorkflowError, "source changed"):
            self.flow.prepare("T-TEST", "w1")
        source.write_text("{}")
        path = Path(self.flow.prepare("T-TEST", "w1")["path"])
        git(path, "add", ".mcp.json")
        with self.assertRaisesRegex(WorkflowError, "must not be staged"):
            self.flow.check("T-TEST", "w1")

    def test_ignored_personal_files_are_preserved(self):
        with (self.main / ".gitignore").open("a") as stream:
            stream.write("personal/\n")
        self.commit(self.main)
        self.create()
        path = self.implement()
        self.review()
        self.flow.merge("T-TEST", "w1")
        (path / "personal").mkdir()
        (path / "personal/notes.txt").write_text("keep")
        with self.assertRaisesRegex(WorkflowError, "ignored file"):
            self.flow.cleanup("T-TEST", "w1", self.receipt)
        self.assertTrue((path / "personal/notes.txt").exists())

    def test_ports_are_distinct_and_occupied_ports_block_preparation(self):
        import socket

        self.contract["works"][0]["harness"]["ports"] = ["APP_PORT", "TEST_PORT"]
        self.create()
        item = self.flow.prepare("T-TEST", "w1")
        self.assertEqual(len(set(item["ports"].values())), 2)
        state = self.flow.load("T-TEST")
        state["works"]["w1"]["status"] = "preparing"
        self.flow.save(state)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", item["ports"]["APP_PORT"]))
            with self.assertRaises(OSError):
                self.flow.prepare("T-TEST", "w1")

    def test_existing_worktree_name_is_never_adopted(self):
        self.create()
        self.backend.create(self.main, "T-TEST-r1-w1", git(self.main, "rev-parse", "HEAD"))
        for _ in range(2):
            with self.assertRaisesRegex(WorkflowError, "already exists"):
                self.flow.prepare("T-TEST", "w1")
        self.assertEqual(self.flow.load("T-TEST")["works"]["w1"]["status"], "pending")

    def test_failed_behavior_can_be_corrected_and_reverified(self):
        self.create()
        path = self.implement(value="missing requirement")
        self.review(passed=False)
        (path / "hello.txt").write_text("hello")
        self.commit(path)
        report = self.root / "fixed.md"
        report.write_text("Corrected greeting and repeated the scenario")
        self.flow.submit("T-TEST", "w1", report)
        self.flow.check("T-TEST", "w1")
        self.review()
        self.assertEqual(self.flow.merge("T-TEST", "w1")["status"], "merged")

    def test_interrupted_recheck_invalidates_previous_verdict(self):
        self.create()
        self.implement()
        self.review()
        original = __import__("workflow_core").command

        def interrupt(argv, **kwargs):
            if argv[0] == sys.executable:
                raise subprocess.TimeoutExpired(argv, 600)
            return original(argv, **kwargs)

        with patch("workflow_core.command", side_effect=interrupt):
            with self.assertRaises(subprocess.TimeoutExpired):
                self.flow.check("T-TEST", "w1")
        with self.assertRaises(WorkflowError):
            self.flow.merge("T-TEST", "w1")
        self.flow.check("T-TEST", "w1")
        self.review()
        self.assertEqual(self.flow.merge("T-TEST", "w1")["status"], "merged")

    def test_unchanged_initial_copies_can_be_reclaimed(self):
        with (self.main / ".gitignore").open("a") as stream:
            stream.write("copied.env\n")
        self.commit(self.main)
        create = self.backend.create

        def with_copy(*args):
            row = create(*args)
            (Path(row["path"]) / "copied.env").write_text("INITIAL=fixture")
            return row

        with patch.object(self.backend, "create", side_effect=with_copy):
            self.create()
            path = self.implement()
        self.review()
        self.flow.merge("T-TEST", "w1")
        (path / "copied.env").write_text("PERSONAL=changed")
        with self.assertRaisesRegex(WorkflowError, "ignored file"):
            self.flow.cleanup("T-TEST", "w1", self.receipt)
        (path / "copied.env").write_text("INITIAL=fixture")
        self.assertEqual(self.flow.cleanup("T-TEST", "w1", self.receipt)["status"], "cleaned")

    def test_shared_dependencies_are_rejected(self):
        self.create()
        target = self.root / "shared-venv"
        target.mkdir()
        create = self.backend.create

        def shared(*args):
            row = create(*args)
            link = Path(row["path"]) / ".venv"
            if os.name == "nt":
                result = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True
                )
                self.assertEqual(result.returncode, 0)
            else:
                link.symlink_to(target, target_is_directory=True)
            return row

        with patch.object(self.backend, "create", side_effect=shared):
            with self.assertRaisesRegex(WorkflowError, "Shared"):
                self.flow.prepare("T-TEST", "w1")
        self.assertTrue(target.exists())

    def test_shared_data_directories_are_skipped_not_rejected(self):
        # Orca sharedDirectories (예: log_moniteoling의 01_log) 는 main 을 가리키는 디렉터리 링크다.
        # 그 안의 무시 파일은 work 소유가 아니므로 준비를 막지 않고 회수 대상에도 넣지 않는다.
        with (self.main / ".gitignore").open("a") as stream:
            stream.write("shared_logs/\n")
        self.commit(self.main)
        self.create()
        target = self.root / "shared-logs-data"
        (target / "day").mkdir(parents=True)
        (target / "day" / "a.log").write_text("log")
        create = self.backend.create

        def shared(*args):
            row = create(*args)
            link = Path(row["path"]) / "shared_logs"
            if os.name == "nt":
                result = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True
                )
                self.assertEqual(result.returncode, 0)
            else:
                link.symlink_to(target, target_is_directory=True)
            return row

        with patch.object(self.backend, "create", side_effect=shared):
            item = self.flow.prepare("T-TEST", "w1")
        self.assertEqual(item["status"], "ready")
        self.assertFalse(any(name.startswith("shared_logs") for name in item["copied_files"]))
        self.assertTrue((target / "day" / "a.log").exists())

    def test_merge_interrupted_before_mutation_rechecks_and_retries(self):
        self.create()
        self.implement()
        self.review()
        state = self.flow.load("T-TEST")
        state["works"]["w1"]["status"] = "merging"
        self.flow.save(state)
        self.assertEqual(self.flow.merge("T-TEST", "w1")["status"], "merged")

    def test_invalid_manifest_and_path_traversal(self):
        self.contract["works"][0]["paths"] = ["../outside"]
        with self.assertRaises(WorkflowError):
            self.create()
        self.contract["works"][0]["paths"] = ["hello.txt"]
        self.contract["works"][0]["depends_on"] = ["w1"]
        with self.assertRaises(WorkflowError):
            self.create()

    def test_installer_preserves_checkout_and_is_idempotent(self):
        source = ROOT / "plugin/skills/kickoff-workspaces/scripts/ws_upgrade.py"
        spec = importlib.util.spec_from_file_location("ws_upgrade", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        (self.main / "AGENTS.md").write_text("# Local rules\nPreserve this.\n")
        before = git(self.main, "status", "--porcelain")
        result = module.install(self.main, home=self.root / "home")
        self.assertTrue(result["changed"])
        self.assertEqual(result["checkout_changes"], [])
        self.assertFalse((self.main / ".ohmypm").exists())
        self.assertEqual(before, git(self.main, "status", "--porcelain"))
        self.assertFalse(module.install(self.main, home=self.root / "home")["changed"])

    def test_installer_rejects_implicit_migration(self):
        source = ROOT / "plugin/skills/kickoff-workspaces/scripts/ws_upgrade.py"
        spec = importlib.util.spec_from_file_location("ws_upgrade", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaisesRegex(ValueError, "migration-plan"):
            module.install(self.main, migrate=True)


if __name__ == "__main__":
    unittest.main()
