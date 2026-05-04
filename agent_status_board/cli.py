from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from agent_status_board.server import (
    DEFAULT_PREFS_PATH,
    bind_host,
    configured_event_log_path,
    configured_prefs_path,
    create_app,
    load_preferences,
)


DEFAULT_PREFS_TEXT = """# Agent Status Surface preferences.
# Format: key=value

# Browser refresh interval in seconds. Values below 0.25 are raised to 0.25.
refresh_rate_seconds=1

# Local HTTP port used by make dev / python server.py.
port=5747

# Keep false for local-only access. Set true to bind to 0.0.0.0 so other
# machines on your network can connect.
allow_remote=false

# Number of items requested by the browser for each view.
board_limit=100
stream_limit=50

# Board columns to show, in order. Valid statuses are:
# proposed, in_progress, blocked, done
board_statuses=proposed,in_progress,blocked,done
"""


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    prefs_path = Path(args.prefs) if args.prefs else configured_prefs_path()

    if args.init:
        init_prefs(prefs_path)
        return

    preferences = load_preferences(prefs_path)
    apply_cli_overrides(preferences, args)

    event_log_path = resolve_event_log_path(args)
    app = create_app(event_log_path=event_log_path, preferences=preferences)
    app.run(host=bind_host(preferences), port=preferences["port"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the local Agent Status Board server.",
    )
    parser.add_argument(
        "--prefs",
        default=None,
        help=f"Path to prefs.txt. Defaults to AGENT_STATUS_PREFS or {DEFAULT_PREFS_PATH}.",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Create a default prefs file and exit.",
    )
    parser.add_argument(
        "--event-log",
        default=None,
        help="Path to the JSONL event log. Defaults to AGENT_STATUS_EVENT_LOG or data/events.jsonl.",
    )
    parser.add_argument(
        "--no-persistence",
        action="store_true",
        help="Disable JSONL persistence for this run.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Override the HTTP port from prefs.txt.",
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Bind to 0.0.0.0 instead of 127.0.0.1.",
    )
    return parser


def apply_cli_overrides(preferences: dict[str, object], args: argparse.Namespace) -> None:
    if args.port is not None:
        preferences["port"] = max(1, min(int(args.port), 65535))

    if args.allow_remote:
        preferences["allow_remote"] = True


def resolve_event_log_path(args: argparse.Namespace) -> Path | None:
    if args.no_persistence:
        return None

    if args.event_log:
        return Path(args.event_log)

    return configured_event_log_path()


def init_prefs(prefs_path: Path) -> None:
    if prefs_path.exists():
        print(f"Preferences already exist at {prefs_path}.")
        return

    prefs_path.parent.mkdir(parents=True, exist_ok=True)
    prefs_path.write_text(DEFAULT_PREFS_TEXT, encoding="utf-8")
    print(f"Created default preferences at {prefs_path}.")
