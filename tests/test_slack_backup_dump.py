from __future__ import annotations

import importlib.util
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path


def load_slack_backup_dump():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "slack_backup_dump.py"
    spec = importlib.util.spec_from_file_location("slack_backup_dump", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["slack_backup_dump"] = module
    spec.loader.exec_module(module)
    return module


class FakeSlackClient:
    def call(self, method, params=None):
        if method == "auth.test":
            return {"ok": True, "team_id": "T1", "team": "440", "url": "https://example.slack.com/"}
        raise AssertionError(f"unexpected call: {method}")

    def paged(self, method, params=None):
        params = params or {}
        if method == "users.list":
            return [
                {
                    "id": "U1",
                    "name": "kevin",
                    "real_name": "Kevin",
                    "profile": {"display_name": "Kevin"},
                    "is_bot": False,
                    "deleted": False,
                }
            ]
        if method == "conversations.list":
            return [{"id": "C1", "name": "agent-ops", "is_channel": True, "is_member": True}]
        if method == "conversations.history":
            assert params["channel"] == "C1"
            return [
                {
                    "type": "message",
                    "user": "U1",
                    "text": "root message",
                    "ts": "1000.000000",
                    "reply_count": 1,
                    "thread_ts": "1000.000000",
                }
            ]
        if method == "conversations.replies":
            assert params["channel"] == "C1"
            assert params["ts"] == "1000.000000"
            return [
                {
                    "type": "message",
                    "user": "U1",
                    "text": "root message",
                    "ts": "1000.000000",
                    "reply_count": 1,
                    "thread_ts": "1000.000000",
                },
                {
                    "type": "message",
                    "user": "U1",
                    "text": "reply",
                    "ts": "1001.000000",
                    "thread_ts": "1000.000000",
                    "parent_user_id": "U1",
                },
            ]
        raise AssertionError(f"unexpected paged call: {method}")


class SlackBackupDumpTests(unittest.TestCase):
    def test_dump_slack_writes_users_channels_messages_and_thread_replies(self):
        slack_backup_dump = load_slack_backup_dump()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "slack.sqlite3"
            db = slack_backup_dump.ArchiveDb(f"sqlite:///{db_path}")
            db.init_schema()

            args = types.SimpleNamespace(
                channel_allowlist="",
                channel_types="public_channel,private_channel,mpim,im",
                full_backfill=True,
                backfill_days=90,
                lookback_days=7,
                include_threads=True,
            )

            counts = slack_backup_dump.dump_slack(FakeSlackClient(), db, args)
            db.close()

            self.assertEqual(counts.channels, 1)
            self.assertEqual(counts.users, 1)
            self.assertEqual(counts.messages, 1)
            self.assertEqual(counts.thread_replies, 2)

            conn = sqlite3.connect(db_path)
            try:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM slack_users").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM slack_channels").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM slack_messages").fetchone()[0], 2)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
