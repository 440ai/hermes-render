from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_agent_worker_contract():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "agent_worker_contract.py"
    spec = importlib.util.spec_from_file_location("agent_worker_contract", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["agent_worker_contract"] = module
    spec.loader.exec_module(module)
    return module


class AgentWorkerContractTests(unittest.TestCase):
    def test_parse_issue_url_accepts_github_issue_urls(self):
        contract = load_agent_worker_contract()

        ref = contract.parse_issue_url("https://github.com/440ai/hermes-render/issues/18")

        self.assertEqual(ref.owner, "440ai")
        self.assertEqual(ref.repo, "hermes-render")
        self.assertEqual(ref.number, 18)
        self.assertEqual(ref.slug, "440ai/hermes-render")

    def test_parse_issue_url_rejects_non_issue_urls(self):
        contract = load_agent_worker_contract()

        with self.assertRaises(ValueError):
            contract.parse_issue_url("https://github.com/440ai/hermes-render/pull/18")

    def test_preflight_blocks_already_active_issue_by_default(self):
        contract = load_agent_worker_contract()
        issue = {"state": "OPEN", "labels": [{"name": "status: active"}]}

        errors = contract.preflight_errors(issue)

        self.assertIn("issue already has status: active; coordinator confirmation required", errors)

    def test_preflight_can_allow_active_when_coordinator_overrides(self):
        contract = load_agent_worker_contract()
        issue = {"state": "OPEN", "labels": [{"name": "status: active"}]}

        errors = contract.preflight_errors(issue, allow_active=True)

        self.assertEqual(errors, [])

    def test_preflight_blocks_closed_issue(self):
        contract = load_agent_worker_contract()
        issue = {"state": "CLOSED", "labels": []}

        errors = contract.preflight_errors(issue)

        self.assertEqual(errors, ["issue is not open: CLOSED"])

    def test_closeout_requires_evidence_and_verification_without_blocker(self):
        contract = load_agent_worker_contract()

        errors = contract.closeout_errors("", "")

        self.assertEqual(
            errors,
            [
                "evidence is required before closeout",
                "verification is required unless the issue is explicitly blocked",
            ],
        )

    def test_closeout_accepts_blocker_without_verification(self):
        contract = load_agent_worker_contract()

        errors = contract.closeout_errors("blocked by missing scope", "", blocker="needs-permission")

        self.assertEqual(errors, [])

    def test_prompt_includes_contract_and_engine_boundaries(self):
        contract = load_agent_worker_contract()

        prompt = contract.build_worker_prompt(
            engine="codex",
            issue_url="https://github.com/440ai/hermes-render/issues/18",
            scope="Implement wrapper checks",
            non_goals="Do not touch secrets",
            verification="Run unit tests",
            secret_boundary="No raw secrets",
            expected_evidence="Diff and test output",
        )

        self.assertIn("You are a 440.ai codex worker", prompt)
        self.assertIn("Issue URL: https://github.com/440ai/hermes-render/issues/18", prompt)
        self.assertIn("Do not touch secrets", prompt)
        self.assertIn("--- PORTABLE CONTRACT ---", prompt)
        self.assertIn("status: active", prompt)
        self.assertIn("If blocked by missing context", prompt)


if __name__ == "__main__":
    unittest.main()
