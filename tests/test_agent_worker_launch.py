from __future__ import annotations

import contextlib
import io
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


def load_agent_worker_launch():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "scripts" / "agent_worker_launch.py"
    scripts_dir = str(repo_root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("agent_worker_launch", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["agent_worker_launch"] = module
    spec.loader.exec_module(module)
    return module


def launch_args(**overrides):
    values = {
        "engine": "codex",
        "issue_url": "https://github.com/440ai/hermes-render/issues/21",
        "issue_json": None,
        "allow_active": False,
        "scope": "Inspect wrapper behavior",
        "non_goals": "Do not modify files",
        "permission_boundary": "Read-only tools only",
        "verification": "Run dry-run wrapper checks",
        "secret_boundary": "No raw secrets",
        "expected_evidence": "Prompt path, output path, and command",
        "workdir": ".",
        "artifact_dir": tempfile.mkdtemp(prefix="agent-launch-test-"),
        "execute": False,
        "codex_sandbox": "read-only",
        "claude_allowed_tools": "Read",
        "claude_max_turns": 3,
        "check_claude_auth": False,
    }
    values.update(overrides)
    return types.SimpleNamespace(**values)


class AgentWorkerLaunchTests(unittest.TestCase):
    def test_prompt_includes_permission_boundary(self):
        launch = load_agent_worker_launch()

        prompt = launch.prompt_with_permission_boundary(
            engine="codex",
            issue_url="https://github.com/440ai/hermes-render/issues/21",
            scope="Inspect wrapper behavior",
            non_goals="Do not modify files",
            permission_boundary="Read-only tools only",
            verification="Run dry-run wrapper checks",
            secret_boundary="No raw secrets",
            expected_evidence="Prompt path, output path, and command",
        )

        self.assertIn("Allowed tools / permission level:\nRead-only tools only", prompt)
        self.assertIn("Verification plan:\nRun dry-run wrapper checks", prompt)

    def test_build_launch_plan_uses_safe_codex_defaults(self):
        launch = load_agent_worker_launch()
        args = launch_args(workdir="/tmp")

        plan = launch.build_launch_plan(args, stamp="20260703T000000Z")

        self.assertEqual(plan.engine, "codex")
        self.assertIn("--sandbox", plan.command)
        self.assertIn("read-only", plan.command)
        self.assertEqual(plan.command[-1], "-")
        self.assertEqual(plan.artifacts.prompt_path.name, "worker-prompt.md")
        self.assertEqual(plan.artifacts.output_path.name, "worker-output.md")
        self.assertIn("440ai-hermes-render-21", str(plan.artifacts.run_dir))
        self.assertIn("20260703T000000Z-codex-", plan.artifacts.run_dir.name)

    def test_artifact_dirs_are_unique_per_launch(self):
        launch = load_agent_worker_launch()
        args = launch_args(workdir="/tmp")

        first = launch.build_launch_plan(args, stamp="20260703T000000Z")
        second = launch.build_launch_plan(args, stamp="20260703T000000Z")

        self.assertNotEqual(first.artifacts.run_dir, second.artifacts.run_dir)

    def test_preflight_blocks_active_issue_without_override(self):
        launch = load_agent_worker_launch()
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            json.dump(
                {
                    "url": "https://github.com/440ai/hermes-render/issues/21",
                    "title": "demo",
                    "state": "OPEN",
                    "labels": [{"name": "status: active"}],
                },
                f,
            )
            issue_json = f.name

        try:
            args = launch_args(issue_json=issue_json)
            self.assertEqual(
                launch.preflight(args),
                ["issue already has status: active; coordinator confirmation required"],
            )

            args.allow_active = True
            self.assertEqual(launch.preflight(args), [])
        finally:
            Path(issue_json).unlink(missing_ok=True)

    def test_command_launch_dry_run_writes_prompt_without_running_engine(self):
        launch = load_agent_worker_launch()
        with tempfile.TemporaryDirectory() as tmpdir:
            issue_json = Path(tmpdir) / "issue.json"
            issue_json.write_text(
                json.dumps(
                    {
                        "url": "https://github.com/440ai/hermes-render/issues/21",
                        "title": "demo",
                        "state": "OPEN",
                        "labels": [],
                    }
                ),
                encoding="utf-8",
            )
            args = launch_args(issue_json=str(issue_json), artifact_dir=tmpdir)

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = launch.command_launch(args)

            self.assertEqual(exit_code, 0)
            prompts = list(Path(tmpdir).glob("**/worker-prompt.md"))
            self.assertEqual(len(prompts), 1)
            self.assertIn("Allowed tools / permission level", prompts[0].read_text())

    def test_claude_auth_blocker_uses_taxonomy(self):
        launch = load_agent_worker_launch()

        blocker = launch.claude_auth_blocker("Not logged in. Run claude auth login to authenticate.", 1)

        assert blocker is not None
        self.assertIn("Status: blocked — needs-permission", blocker)
        self.assertIn("claude auth login", blocker)

    def test_display_command_elides_prompt_argument(self):
        launch = load_agent_worker_launch()

        safe = launch.display_command(["claude", "-p", "secret-ish prompt"], "secret-ish prompt", Path("/tmp/prompt.md"))

        self.assertEqual(safe, ["claude", "-p", "<prompt from /tmp/prompt.md>"])


if __name__ == "__main__":
    unittest.main()
