#!/usr/bin/env python3
"""Dump accessible Slack users, channels, messages, and thread replies to a DB."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


DEFAULT_BACKFILL_DAYS = 90
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_PAGE_LIMIT = 200


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slack_ts_now() -> float:
    return time.time()


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.replace("\n", ",").split(",") if item.strip()]


def safe_error(error: Exception) -> str:
    text = str(error)
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if token:
        text = text.replace(token, "[REDACTED]")
    return text


class SlackApiError(RuntimeError):
    pass


class SlackClient:
    def __init__(self, token: str, timeout_seconds: int = 30) -> None:
        self.token = token
        self.timeout_seconds = timeout_seconds

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"https://slack.com/api/{method}"
        data = urllib.parse.urlencode(params or {}).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        while True:
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    break
            except urllib.error.HTTPError as error:
                if error.code == 429:
                    retry_after = int(error.headers.get("Retry-After", "5"))
                    time.sleep(min(max(retry_after, 1), 60))
                    continue
                raise

        if not payload.get("ok"):
            raise SlackApiError(f"{method} failed: {payload.get('error', 'unknown_error')}")
        return payload

    def paged(self, method: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        cursor = ""
        while True:
            page_params = dict(params or {})
            page_params.setdefault("limit", str(DEFAULT_PAGE_LIMIT))
            if cursor:
                page_params["cursor"] = cursor
            payload = self.call(method, page_params)
            if "messages" in payload:
                items.extend(payload["messages"])
            elif "channels" in payload:
                items.extend(payload["channels"])
            elif "members" in payload:
                items.extend(payload["members"])
            else:
                raise SlackApiError(f"{method} returned an unsupported page shape")
            cursor = payload.get("response_metadata", {}).get("next_cursor") or ""
            if not cursor:
                return items


@dataclass
class ChannelCursor:
    last_message_ts: float | None


class ArchiveDb:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.is_postgres = database_url.startswith(("postgres://", "postgresql://"))
        if self.is_postgres:
            try:
                import psycopg
            except ImportError as exc:
                raise RuntimeError("Postgres URLs require psycopg. Build the image with psycopg installed.") from exc

            self.psycopg = psycopg
            self.conn = psycopg.connect(database_url)
            self.conn.autocommit = True
        else:
            path = self._sqlite_path(database_url)
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            self.conn = sqlite3.connect(path)
            self.conn.row_factory = sqlite3.Row

    @staticmethod
    def _sqlite_path(database_url: str) -> str:
        if database_url.startswith("sqlite:///"):
            return database_url.removeprefix("sqlite:///")
        if database_url.startswith("sqlite://"):
            return database_url.removeprefix("sqlite://")
        return database_url

    def close(self) -> None:
        self.conn.close()

    def init_schema(self) -> None:
        if self.is_postgres:
            statements = [
                """
                CREATE TABLE IF NOT EXISTS slack_backup_runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TIMESTAMPTZ NOT NULL,
                    finished_at TIMESTAMPTZ,
                    status TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    channel_count INTEGER NOT NULL DEFAULT 0,
                    user_count INTEGER NOT NULL DEFAULT 0,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    thread_reply_count INTEGER NOT NULL DEFAULT 0,
                    error TEXT
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS slack_workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    team_name TEXT,
                    url TEXT,
                    raw_json JSONB NOT NULL,
                    last_seen_at TIMESTAMPTZ NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS slack_users (
                    workspace_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    name TEXT,
                    real_name TEXT,
                    display_name TEXT,
                    is_bot BOOLEAN,
                    is_deleted BOOLEAN,
                    raw_json JSONB NOT NULL,
                    last_seen_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (workspace_id, user_id)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS slack_channels (
                    workspace_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    name TEXT,
                    is_channel BOOLEAN,
                    is_group BOOLEAN,
                    is_private BOOLEAN,
                    is_archived BOOLEAN,
                    is_member BOOLEAN,
                    last_message_ts DOUBLE PRECISION,
                    raw_json JSONB NOT NULL,
                    last_seen_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (workspace_id, channel_id)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS slack_messages (
                    workspace_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    message_ts TEXT NOT NULL,
                    thread_ts TEXT,
                    parent_user_id TEXT,
                    user_id TEXT,
                    bot_id TEXT,
                    message_type TEXT,
                    subtype TEXT,
                    text TEXT,
                    raw_json JSONB NOT NULL,
                    ingested_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (workspace_id, channel_id, message_ts)
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_slack_messages_thread ON slack_messages (workspace_id, channel_id, thread_ts)",
                "CREATE INDEX IF NOT EXISTS idx_slack_messages_user ON slack_messages (workspace_id, user_id)",
            ]
        else:
            statements = [
                """
                CREATE TABLE IF NOT EXISTS slack_backup_runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    channel_count INTEGER NOT NULL DEFAULT 0,
                    user_count INTEGER NOT NULL DEFAULT 0,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    thread_reply_count INTEGER NOT NULL DEFAULT 0,
                    error TEXT
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS slack_workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    team_name TEXT,
                    url TEXT,
                    raw_json TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS slack_users (
                    workspace_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    name TEXT,
                    real_name TEXT,
                    display_name TEXT,
                    is_bot INTEGER,
                    is_deleted INTEGER,
                    raw_json TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    PRIMARY KEY (workspace_id, user_id)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS slack_channels (
                    workspace_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    name TEXT,
                    is_channel INTEGER,
                    is_group INTEGER,
                    is_private INTEGER,
                    is_archived INTEGER,
                    is_member INTEGER,
                    last_message_ts REAL,
                    raw_json TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    PRIMARY KEY (workspace_id, channel_id)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS slack_messages (
                    workspace_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    message_ts TEXT NOT NULL,
                    thread_ts TEXT,
                    parent_user_id TEXT,
                    user_id TEXT,
                    bot_id TEXT,
                    message_type TEXT,
                    subtype TEXT,
                    text TEXT,
                    raw_json TEXT NOT NULL,
                    ingested_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (workspace_id, channel_id, message_ts)
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_slack_messages_thread ON slack_messages (workspace_id, channel_id, thread_ts)",
                "CREATE INDEX IF NOT EXISTS idx_slack_messages_user ON slack_messages (workspace_id, user_id)",
            ]

        cur = self.conn.cursor()
        for statement in statements:
            cur.execute(statement)
        if not self.is_postgres:
            self.conn.commit()

    def json_value(self, value: Any) -> Any:
        if self.is_postgres:
            from psycopg.types.json import Jsonb

            return Jsonb(value)
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    def bool_value(self, value: Any) -> Any:
        return bool(value) if self.is_postgres else int(bool(value))

    def start_run(self, run_id: str, mode: str) -> None:
        if self.is_postgres:
            self.conn.execute(
                """
                INSERT INTO slack_backup_runs (run_id, started_at, status, mode)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (run_id) DO NOTHING
                """,
                (run_id, utc_now(), "running", mode),
            )
        else:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO slack_backup_runs (run_id, started_at, status, mode)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, utc_now(), "running", mode),
            )
            self.conn.commit()

    def finish_run(
        self,
        run_id: str,
        status: str,
        channel_count: int,
        user_count: int,
        message_count: int,
        thread_reply_count: int,
        error: str | None = None,
    ) -> None:
        if self.is_postgres:
            self.conn.execute(
                """
                UPDATE slack_backup_runs
                SET finished_at = %s,
                    status = %s,
                    channel_count = %s,
                    user_count = %s,
                    message_count = %s,
                    thread_reply_count = %s,
                    error = %s
                WHERE run_id = %s
                """,
                (utc_now(), status, channel_count, user_count, message_count, thread_reply_count, error, run_id),
            )
        else:
            self.conn.execute(
                """
                UPDATE slack_backup_runs
                SET finished_at = ?,
                    status = ?,
                    channel_count = ?,
                    user_count = ?,
                    message_count = ?,
                    thread_reply_count = ?,
                    error = ?
                WHERE run_id = ?
                """,
                (utc_now(), status, channel_count, user_count, message_count, thread_reply_count, error, run_id),
            )
            self.conn.commit()

    def upsert_workspace(self, workspace: dict[str, Any]) -> str:
        team_id = workspace["team_id"]
        values = (team_id, workspace.get("team"), workspace.get("url"), self.json_value(workspace), utc_now())
        if self.is_postgres:
            self.conn.execute(
                """
                INSERT INTO slack_workspaces (workspace_id, team_name, url, raw_json, last_seen_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (workspace_id) DO UPDATE
                SET team_name = EXCLUDED.team_name,
                    url = EXCLUDED.url,
                    raw_json = EXCLUDED.raw_json,
                    last_seen_at = EXCLUDED.last_seen_at
                """,
                values,
            )
        else:
            self.conn.execute(
                """
                INSERT INTO slack_workspaces (workspace_id, team_name, url, raw_json, last_seen_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (workspace_id) DO UPDATE
                SET team_name = excluded.team_name,
                    url = excluded.url,
                    raw_json = excluded.raw_json,
                    last_seen_at = excluded.last_seen_at
                """,
                values,
            )
            self.conn.commit()
        return team_id

    def upsert_user(self, workspace_id: str, user: dict[str, Any]) -> None:
        profile = user.get("profile") or {}
        values = (
            workspace_id,
            user["id"],
            user.get("name"),
            user.get("real_name") or profile.get("real_name"),
            profile.get("display_name"),
            self.bool_value(user.get("is_bot")),
            self.bool_value(user.get("deleted")),
            self.json_value(user),
            utc_now(),
        )
        if self.is_postgres:
            self.conn.execute(
                """
                INSERT INTO slack_users
                    (workspace_id, user_id, name, real_name, display_name, is_bot, is_deleted, raw_json, last_seen_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (workspace_id, user_id) DO UPDATE
                SET name = EXCLUDED.name,
                    real_name = EXCLUDED.real_name,
                    display_name = EXCLUDED.display_name,
                    is_bot = EXCLUDED.is_bot,
                    is_deleted = EXCLUDED.is_deleted,
                    raw_json = EXCLUDED.raw_json,
                    last_seen_at = EXCLUDED.last_seen_at
                """,
                values,
            )
        else:
            self.conn.execute(
                """
                INSERT INTO slack_users
                    (workspace_id, user_id, name, real_name, display_name, is_bot, is_deleted, raw_json, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (workspace_id, user_id) DO UPDATE
                SET name = excluded.name,
                    real_name = excluded.real_name,
                    display_name = excluded.display_name,
                    is_bot = excluded.is_bot,
                    is_deleted = excluded.is_deleted,
                    raw_json = excluded.raw_json,
                    last_seen_at = excluded.last_seen_at
                """,
                values,
            )

    def upsert_channel(self, workspace_id: str, channel: dict[str, Any], last_message_ts: float | None = None) -> None:
        values = (
            workspace_id,
            channel["id"],
            channel.get("name"),
            self.bool_value(channel.get("is_channel")),
            self.bool_value(channel.get("is_group")),
            self.bool_value(channel.get("is_private")),
            self.bool_value(channel.get("is_archived")),
            self.bool_value(channel.get("is_member")),
            last_message_ts,
            self.json_value(channel),
            utc_now(),
        )
        if self.is_postgres:
            self.conn.execute(
                """
                INSERT INTO slack_channels
                    (workspace_id, channel_id, name, is_channel, is_group, is_private, is_archived, is_member,
                     last_message_ts, raw_json, last_seen_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (workspace_id, channel_id) DO UPDATE
                SET name = EXCLUDED.name,
                    is_channel = EXCLUDED.is_channel,
                    is_group = EXCLUDED.is_group,
                    is_private = EXCLUDED.is_private,
                    is_archived = EXCLUDED.is_archived,
                    is_member = EXCLUDED.is_member,
                    last_message_ts = GREATEST(
                        COALESCE(slack_channels.last_message_ts, 0),
                        COALESCE(EXCLUDED.last_message_ts, 0)
                    ),
                    raw_json = EXCLUDED.raw_json,
                    last_seen_at = EXCLUDED.last_seen_at
                """,
                values,
            )
        else:
            self.conn.execute(
                """
                INSERT INTO slack_channels
                    (workspace_id, channel_id, name, is_channel, is_group, is_private, is_archived, is_member,
                     last_message_ts, raw_json, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (workspace_id, channel_id) DO UPDATE
                SET name = excluded.name,
                    is_channel = excluded.is_channel,
                    is_group = excluded.is_group,
                    is_private = excluded.is_private,
                    is_archived = excluded.is_archived,
                    is_member = excluded.is_member,
                    last_message_ts = MAX(
                        COALESCE(slack_channels.last_message_ts, 0),
                        COALESCE(excluded.last_message_ts, 0)
                    ),
                    raw_json = excluded.raw_json,
                    last_seen_at = excluded.last_seen_at
                """,
                values,
            )

    def get_channel_cursor(self, workspace_id: str, channel_id: str) -> ChannelCursor:
        if self.is_postgres:
            row = self.conn.execute(
                "SELECT last_message_ts FROM slack_channels WHERE workspace_id = %s AND channel_id = %s",
                (workspace_id, channel_id),
            ).fetchone()
            return ChannelCursor(last_message_ts=row[0] if row else None)

        row = self.conn.execute(
            "SELECT last_message_ts FROM slack_channels WHERE workspace_id = ? AND channel_id = ?",
            (workspace_id, channel_id),
        ).fetchone()
        return ChannelCursor(last_message_ts=row["last_message_ts"] if row else None)

    def upsert_message(self, workspace_id: str, channel_id: str, message: dict[str, Any]) -> None:
        message_ts = message["ts"]
        thread_ts = message.get("thread_ts") or message_ts
        values = (
            workspace_id,
            channel_id,
            message_ts,
            thread_ts,
            message.get("parent_user_id"),
            message.get("user"),
            message.get("bot_id"),
            message.get("type"),
            message.get("subtype"),
            message.get("text"),
            self.json_value(message),
            utc_now(),
            utc_now(),
        )
        if self.is_postgres:
            self.conn.execute(
                """
                INSERT INTO slack_messages
                    (workspace_id, channel_id, message_ts, thread_ts, parent_user_id, user_id, bot_id,
                     message_type, subtype, text, raw_json, ingested_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (workspace_id, channel_id, message_ts) DO UPDATE
                SET thread_ts = EXCLUDED.thread_ts,
                    parent_user_id = EXCLUDED.parent_user_id,
                    user_id = EXCLUDED.user_id,
                    bot_id = EXCLUDED.bot_id,
                    message_type = EXCLUDED.message_type,
                    subtype = EXCLUDED.subtype,
                    text = EXCLUDED.text,
                    raw_json = EXCLUDED.raw_json,
                    updated_at = EXCLUDED.updated_at
                """,
                values,
            )
        else:
            self.conn.execute(
                """
                INSERT INTO slack_messages
                    (workspace_id, channel_id, message_ts, thread_ts, parent_user_id, user_id, bot_id,
                     message_type, subtype, text, raw_json, ingested_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (workspace_id, channel_id, message_ts) DO UPDATE
                SET thread_ts = excluded.thread_ts,
                    parent_user_id = excluded.parent_user_id,
                    user_id = excluded.user_id,
                    bot_id = excluded.bot_id,
                    message_type = excluded.message_type,
                    subtype = excluded.subtype,
                    text = excluded.text,
                    raw_json = excluded.raw_json,
                    updated_at = excluded.updated_at
                """,
                values,
            )

    def commit(self) -> None:
        if not self.is_postgres:
            self.conn.commit()


def discover_channels(client: SlackClient, allowed: list[str], channel_types: str) -> list[dict[str, Any]]:
    channels = client.paged(
        "conversations.list",
        {
            "exclude_archived": "false",
            "types": channel_types,
        },
    )
    if not allowed:
        return channels
    allowed_lower = {item.lower() for item in allowed}
    return [
        channel
        for channel in channels
        if channel.get("id", "").lower() in allowed_lower or channel.get("name", "").lower() in allowed_lower
    ]


def fetch_channel_messages(
    client: SlackClient,
    channel_id: str,
    oldest: float,
    latest: float,
) -> list[dict[str, Any]]:
    return client.paged(
        "conversations.history",
        {
            "channel": channel_id,
            "oldest": f"{oldest:.6f}",
            "latest": f"{latest:.6f}",
            "inclusive": "true",
        },
    )


def fetch_thread_replies(client: SlackClient, channel_id: str, thread_ts: str) -> list[dict[str, Any]]:
    return client.paged(
        "conversations.replies",
        {
            "channel": channel_id,
            "ts": thread_ts,
            "inclusive": "true",
        },
    )


@dataclass
class DumpCounts:
    channels: int = 0
    users: int = 0
    messages: int = 0
    thread_replies: int = 0


def dump_slack(client: SlackClient, db: ArchiveDb, args: argparse.Namespace) -> DumpCounts:
    workspace_payload = client.call("auth.test")
    workspace_id = db.upsert_workspace(workspace_payload)

    users = client.paged("users.list")
    for user in users:
        db.upsert_user(workspace_id, user)
    db.commit()

    allowed_channels = parse_list(args.channel_allowlist)
    channels = discover_channels(client, allowed_channels, args.channel_types)
    latest = slack_ts_now()
    counts = DumpCounts(channels=len(channels), users=len(users))

    for channel in channels:
        channel_id = channel["id"]
        cursor = db.get_channel_cursor(workspace_id, channel_id)
        if args.full_backfill or cursor.last_message_ts is None:
            oldest = latest - (args.backfill_days * 86400)
        else:
            oldest = max(0.0, cursor.last_message_ts - (args.lookback_days * 86400))

        messages = fetch_channel_messages(client, channel_id, oldest, latest)
        max_ts = cursor.last_message_ts
        seen_thread_roots: set[str] = set()

        for message in messages:
            db.upsert_message(workspace_id, channel_id, message)
            counts.messages += 1
            try:
                max_ts = max(max_ts or 0.0, float(message["ts"]))
            except (KeyError, ValueError, TypeError):
                pass

            reply_count = int(message.get("reply_count") or 0)
            thread_ts = message.get("thread_ts") or message.get("ts")
            if args.include_threads and reply_count > 0 and thread_ts and thread_ts not in seen_thread_roots:
                seen_thread_roots.add(thread_ts)
                try:
                    replies = fetch_thread_replies(client, channel_id, thread_ts)
                except SlackApiError as error:
                    print(f"[slack-backup] warning: skipped thread {channel_id}/{thread_ts}: {safe_error(error)}", file=sys.stderr)
                    continue
                for reply in replies:
                    db.upsert_message(workspace_id, channel_id, reply)
                    counts.thread_replies += 1

        db.upsert_channel(workspace_id, channel, max_ts)
        db.commit()
        print(
            f"[slack-backup] channel={channel.get('name') or channel_id} messages={len(messages)} "
            f"threads={len(seen_thread_roots)} oldest={oldest:.6f} latest={latest:.6f}"
        )

    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("SLACK_BACKUP_DATABASE_URL") or os.environ.get("DATABASE_URL") or "sqlite:////opt/data/slack-backup.sqlite3")
    parser.add_argument("--channel-allowlist", default=os.environ.get("SLACK_BACKUP_CHANNEL_ALLOWLIST") or os.environ.get("SLACK_ALLOWED_CHANNELS") or "")
    parser.add_argument(
        "--channel-types",
        default=os.environ.get("SLACK_BACKUP_CHANNEL_TYPES", "public_channel,private_channel,mpim,im"),
    )
    parser.add_argument("--backfill-days", type=int, default=int(os.environ.get("SLACK_BACKUP_BACKFILL_DAYS", str(DEFAULT_BACKFILL_DAYS))))
    parser.add_argument("--lookback-days", type=int, default=int(os.environ.get("SLACK_BACKUP_LOOKBACK_DAYS", str(DEFAULT_LOOKBACK_DAYS))))
    parser.add_argument("--full-backfill", action="store_true", default=parse_bool(os.environ.get("SLACK_BACKUP_FULL_BACKFILL")))
    parser.add_argument(
        "--include-threads",
        action="store_true",
        default=parse_bool(os.environ.get("SLACK_BACKUP_INCLUDE_THREADS"), default=True),
    )
    parser.add_argument("--no-include-threads", dest="include_threads", action="store_false")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("[slack-backup] SLACK_BOT_TOKEN is required", file=sys.stderr)
        return 2

    run_id = f"slack-backup-{int(time.time())}"
    db = ArchiveDb(args.database_url)
    db.init_schema()
    db.start_run(run_id, "full_backfill" if args.full_backfill else "incremental")

    try:
        counts = dump_slack(SlackClient(token), db, args)
    except Exception as error:
        db.finish_run(run_id, "failed", 0, 0, 0, 0, safe_error(error))
        print(f"[slack-backup] failed: {safe_error(error)}", file=sys.stderr)
        return 1
    finally:
        db.close()

    db = ArchiveDb(args.database_url)
    db.finish_run(
        run_id,
        "succeeded",
        counts.channels,
        counts.users,
        counts.messages,
        counts.thread_replies,
    )
    db.close()
    print(
        f"[slack-backup] succeeded channels={counts.channels} users={counts.users} "
        f"messages={counts.messages} thread_replies={counts.thread_replies}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
