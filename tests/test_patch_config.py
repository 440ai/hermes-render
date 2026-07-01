from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


def load_patch_config():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "patch-config.py"
    spec = importlib.util.spec_from_file_location("patch_config", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules.setdefault("yaml", types.SimpleNamespace())
    spec.loader.exec_module(module)
    return module


class PatchConfigTests(unittest.TestCase):
    def test_default_render_mcp_entry_does_not_filter_tools(self):
        patch_config = load_patch_config()

        render_entry = patch_config._render_entry()

        self.assertNotIn("tools", render_entry)

    def test_dashboard_oauth_defaults_are_insert_only(self):
        patch_config = load_patch_config()
        config = {}

        changed = patch_config.ensure_dashboard_oauth(config)

        self.assertTrue(changed)
        self.assertEqual(config["dashboard"]["oauth"]["provider"], "self-hosted")
        self.assertEqual(
            config["dashboard"]["oauth"]["self_hosted"]["issuer"],
            "${HERMES_DASHBOARD_OIDC_ISSUER}",
        )

    def test_existing_dashboard_oauth_is_not_overwritten(self):
        patch_config = load_patch_config()
        config = {"dashboard": {"oauth": {"provider": "basic"}}}

        changed = patch_config.ensure_dashboard_oauth(config)

        self.assertTrue(changed)
        self.assertEqual(config["dashboard"]["oauth"]["provider"], "basic")
        self.assertIn("self_hosted", config["dashboard"]["oauth"])

    def test_existing_self_hosted_dashboard_oauth_is_not_overwritten(self):
        patch_config = load_patch_config()
        config = {"dashboard": {"oauth": {"provider": "basic", "self_hosted": {"issuer": "custom"}}}}

        changed = patch_config.ensure_dashboard_oauth(config)

        self.assertFalse(changed)
        self.assertEqual(config["dashboard"]["oauth"]["provider"], "basic")
        self.assertEqual(config["dashboard"]["oauth"]["self_hosted"], {"issuer": "custom"})

    def test_partial_upstream_dashboard_oauth_is_augmented(self):
        patch_config = load_patch_config()
        config = {"dashboard": {"oauth": {"client_id": "", "portal_url": ""}}}

        changed = patch_config.ensure_dashboard_oauth(config)

        self.assertTrue(changed)
        self.assertEqual(config["dashboard"]["oauth"]["client_id"], "")
        self.assertEqual(config["dashboard"]["oauth"]["provider"], "self-hosted")
        self.assertIn("self_hosted", config["dashboard"]["oauth"])
