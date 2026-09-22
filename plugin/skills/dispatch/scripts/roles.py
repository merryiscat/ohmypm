"""Durable role connection and generation-fenced mail; no timeout-based restarts."""

from __future__ import annotations

import uuid
from pathlib import Path

from environment import Environment, validate_profiles
from workflow_core import Orca, WorkflowError, digest, read_json, require, safe_id, write_json


def launcher_argv(profile):
    validate_profiles({r: profile for r in ("main", "pl", "work")})
    argv = [profile["agent"]]
    if profile.get("approval") == "bypass":
        require(profile["agent"] == "codex", "Bypass profile is only supported for Codex")
        argv.append("--dangerously-bypass-approvals-and-sandbox")
    if profile.get("model"):
        argv += ["--model", profile["model"]]
    if profile.get("effort"):
        if profile["agent"] == "codex":
            argv += ["-c", 'model_reasoning_effort="' + profile["effort"] + '"']
        else:
            argv += ["--effort", profile["effort"]]
    return argv


class RoleAdapter:
    def __init__(self, orca=None):
        self.orca = orca or Orca()

    def start(self, project, role, token, profile):
        import os
        import shlex
        import sys
        from pathlib import Path

        env = Environment(project)
        folder = env.root / "roles" / role
        record_path = folder / (token + ".launch.json")
        lifecycle = folder / (token + ".lifecycle.json")
        argv = launcher_argv(profile)
        state = read_json(folder / "state.json")
        initial_context = state["context"] + "\nContext digest: " + state["context_digest"]
        argv.append(initial_context)
        write_json(
            record_path,
            {"project": str(project), "token": token, "lifecycle": str(lifecycle), "argv": argv},
        )
        runner = Path(env.config()["runtime"]["path"]) / "scripts/role_runner.py"
        launch = [sys.executable, "-B", str(runner), "--record", str(record_path)]
        args = [
            "terminal",
            "create",
            "--worktree",
            "path:" + str(project),
            "--title",
            f"ohmyPM-{role}-{token}",
        ]
        if os.name == "nt":
            # Explicit shell and PowerShell literal quoting, not JSON or shell interpolation.
            command = "& " + " ".join("'" + a.replace("'", "''") + "'" for a in launch)
            args += ["--shell", "powershell.exe"]
        else:
            command = shlex.join(launch)
        receipt = self.orca.call(*args, "--command", command)
        receipt["initial_context"] = True
        return receipt

    def observe(self, handle, session=None):
        from pathlib import Path

        from role_runner import process_identity

        if not session or not Path(session["lifecycle"]).is_file():
            return {"status": "unverifiable", "ready": False, "reason": "No process receipt"}
        life = read_json(session["lifecycle"])
        if life.get("token") != session["token"]:
            return {"status": "unverifiable", "ready": False, "reason": "Process token mismatch"}
        if life.get("status") == "exited":
            return {"status": "exited", "ready": False, "receipt": life}
        identity = life.get("process_identity")
        if not identity or process_identity(life.get("pid")) != identity:
            return {"status": "unverifiable", "ready": False, "reason": "Process unproven"}
        try:
            idle = self.orca.call(
                "terminal",
                "wait",
                "--terminal",
                handle,
                "--for",
                "tui-idle",
                "--timeout-ms",
                "1000",
            )
            ready = bool(idle.get("wait", {}).get("satisfied"))
            if ready:
                view = self.orca.call("terminal", "read", "--terminal", handle, "--limit", "30")
                tail = "\n".join(view.get("terminal", {}).get("tail", [])).lower()
                if any(
                    marker in tail
                    for marker in ("quick safety check", "do you trust", "trust this folder")
                ):
                    return {"status": "live", "ready": False, "reason": "Workspace trust prompt"}
            return {"status": "live", "ready": ready, "receipt": idle}
        except (WorkflowError, OSError) as exc:
            return {"status": "live", "ready": False, "reason": str(exc)}

    def send(self, handle, text):
        return self.orca.call(
            "terminal",
            "send",
            "--terminal",
            handle,
            "--text",
            text,
            "--enter",
            "--wait-submit",
            "10",
        )


class Roles:
    def __init__(self, project, adapter=None):
        self.env = Environment(project)
        self.adapter = adapter or RoleAdapter()

    def path(self, role):
        require(
            role in ("main", "pl"),
            "Role sessions are main/pl; work uses supervised workflow launch",
        )
        return self.env.root / "roles" / role / "state.json"

    def load(self, role):
        path = self.path(role)
        return read_json(path) if path.exists() else None

    def save(self, role, state):
        write_json(self.path(role), state)

    def connect(self, role):
        old = self.load(role)
        if old and old["status"] != "exited":
            require(
                old.get("handle"),
                "Role creation outcome unknown; reconcile its receipt, do not restart",
            )
            observation = self.adapter.observe(old["handle"], old)
            old["observation"] = observation
            old["requires_reconnect"] = old["environment"] != self.env.snapshot()
            self.save(role, old)
            if observation["status"] != "exited":
                if (
                    observation["status"] == "live"
                    and observation.get("ready", False)
                    and old["status"] == "created"
                ):
                    return self.deliver_context(role)
                return old  # live/unknown: never duplicate, never infer acceptance.
            old["status"] = "exited"
            self.save(role, old)
        snap = self.env.snapshot()
        generation = (old or {}).get("generation", 0) + 1
        if old:
            write_json(self.path(role).parent / f"generation-{old['generation']}.json", old)
        token = uuid.uuid4().hex
        context = self.env.context(role, snap)
        context += (
            f"\nRole generation: {generation}\n"
            "Before doing work, read preserved tasks/requests/outbox and acknowledge this context "
            f"using environment_cli.py --project <project> role-accept --role {role} "
            f"--generation {generation} --digest <context digest shown in the delivery>.\n"
        )
        record = {
            "role": role,
            "generation": generation,
            "token": token,
            "lifecycle": str(self.path(role).parent / (token + ".lifecycle.json")),
            "status": "starting",
            "environment": snap,
            "context": context,
            "context_digest": digest(context.encode("utf-8")),
        }
        self.save(role, record)  # durable intent BEFORE creating the terminal.
        receipt = self.adapter.start(self.env.project, role, token, snap["roles"][role])
        return self.reconcile(role, receipt)

    def reconcile(self, role, receipt):
        record = self.load(role)
        require(record and record["status"] == "starting", "No unknown role creation to reconcile")
        result = receipt.get("result", receipt)
        terminal = result.get("terminal", result.get("session", {}))
        handle = terminal.get("handle") or result.get("handle")
        require(handle, "Creation receipt has no terminal handle; preserve and inspect it")
        require(
            terminal.get("title") == f"ohmyPM-{role}-{record['token']}",
            "Receipt does not match the role creation token",
        )
        workspace = terminal.get("worktreeId", "").split("::", 1)
        require(
            len(workspace) == 2 and Path(workspace[1]).resolve() == self.env.project,
            "Receipt belongs to another workspace",
        )
        record.update(handle=handle, creation_receipt=receipt, status="created")
        if result.get("initial_context"):
            record["status"] = "awaiting_acceptance"
            record["delivery_receipt"] = {"mode": "initial-argv", "accepted_by_model": False}
        self.save(role, record)
        if result.get("initial_context"):
            return record
        return self.deliver_context(role)

    def deliver_context(self, role):
        record = self.load(role)
        require(
            record["status"] == "created", "Context delivery already attempted; inspect receipt"
        )
        observation = self.adapter.observe(record["handle"], record)
        record["observation"] = observation
        self.save(role, record)
        if observation["status"] != "live" or not observation.get("ready", False):
            return record
        record["status"] = "sending_context"
        self.save(role, record)
        receipt = self.adapter.send(
            record["handle"], record["context"] + "\nContext digest: " + record["context_digest"]
        )
        record.update(status="awaiting_acceptance", delivery_receipt=receipt)
        self.save(role, record)
        return record

    def accept(self, role, generation, context_digest):
        record = self.load(role)
        require(
            record
            and record["generation"] == generation
            and record["context_digest"] == context_digest,
            "Stale role generation/context; preserve the late response",
        )
        require(
            record["status"] in ("sending_context", "awaiting_acceptance", "ready"),
            "Context not delivered",
        )
        record["status"] = "ready"
        self.save(role, record)
        return record

    def observe_exit(self, role, receipt):
        """Use positive exit evidence, never missing inventory or elapsed time."""
        record = self.load(role)
        require(record and record.get("handle"), "No connected role")
        result = receipt.get("result", receipt)
        wait = result.get("wait", {})
        terminal = result.get("terminal", {})
        closed = result.get("close", {})
        require(
            receipt.get("ok", True) is True
            and (
                terminal.get("handle") == record["handle"]
                or wait.get("handle", wait.get("terminalHandle")) == record["handle"]
                or closed.get("handle") == record["handle"]
            )
            and (
                (wait.get("satisfied") is True and wait.get("condition", wait.get("for")) == "exit")
                or terminal.get("status") == "exited"
                or closed.get("ptyKilled") is True
            ),
            "Receipt does not prove this role's exit",
        )
        record.update(status="exited", exit_receipt=receipt)
        self.save(role, record)
        return record

    def enqueue(self, role, message_id, task, revision, body):
        self.path(role)
        safe_id(message_id)
        safe_id(task)
        require(revision > 0 and body.strip(), "Message needs a revision and body")
        target = self.env.root / "outbox" / (message_id + ".json")
        content = {"id": message_id, "role": role, "task": task, "revision": revision, "body": body}
        if target.exists():
            old = read_json(target)
            require(
                all(old[k] == v for k, v in content.items()),
                "Message ID already belongs to another request",
            )
            return old
        content.update(status="pending", attempts=[])
        write_json(target, content)
        return content

    def deliver(self, message_id):
        target = self.env.root / "outbox" / (safe_id(message_id) + ".json")
        message = read_json(target)
        record = self.load(message["role"])
        require(record and record["status"] == "ready", "Role must accept restored context first")
        self.current_revision(message)
        generation = record["generation"]
        previous = [a for a in message["attempts"] if a["generation"] == generation]
        if previous:
            return message  # unknown send is never blindly repeated.
        attempt = {"generation": generation, "status": "sending"}
        message["attempts"].append(attempt)
        write_json(target, message)
        payload = {k: message[k] for k in ("id", "task", "revision", "body")}
        payload["generation"] = generation
        import json

        receipt = self.adapter.send(record["handle"], json.dumps(payload, ensure_ascii=False))
        attempt.update(status="sent", receipt=receipt)
        write_json(target, message)
        return message

    def current_revision(self, message):
        state = self.env.root / "tasks" / message["task"] / "state.json"
        if state.exists():
            require(
                read_json(state)["revision"] == message["revision"],
                "Message refers to a stale task revision",
            )

    def acknowledge(self, message_id, generation, revision, completed=False):
        target = self.env.root / "outbox" / (safe_id(message_id) + ".json")
        message = read_json(target)
        record = self.load(message["role"])
        self.current_revision(message)
        require(
            record
            and record["status"] == "ready"
            and record["generation"] == generation
            and message["revision"] == revision,
            "Stale generation/revision response",
        )
        require(
            any(a["generation"] == generation for a in message["attempts"]),
            "Message was not delivered to this generation",
        )
        require(
            not completed or message["status"] == "accepted",
            "Accept the message before completing it",
        )
        message.update(
            status="completed" if completed else "accepted", accepted_generation=generation
        )
        write_json(target, message)
        return message
