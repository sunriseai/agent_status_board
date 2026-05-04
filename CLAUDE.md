# Agent Status Board

This is the `astatus` project — a local Flask server that provides a Kanban-style status dashboard for coding agents. Agents report task-level progress via a simple HTTP API; the board displays live status at `http://localhost:5747`.

## Status Reporting

Follow the rules in [STATUS_RULES.md](STATUS_RULES.md) while working in this repo.

Key points:
- Post to `http://localhost:5747/report` before starting any task-sized action
- Use `repo`: `astatus`, a stable `session_id` for this session, and a slug `task_id` per task
- Report `in_progress`, `done`, `blocked`, and direction changes — not every tool call
- If the server is unavailable, say so and continue only if the user allows best-effort reporting

## Project Layout

- `agent_status_board/server.py` — Flask app, all routes, HTML template, and business logic
- `agent_status_board/cli.py` — entry point for the `agent-status-board` console command
- `data/events.jsonl` — persisted event log (newline-delimited JSON)
- `prefs.txt` — runtime preferences (`port`, `refresh_rate_seconds`, `board_statuses`, etc.)
- `STATUS_RULES.md` — agent status reporting rules (give this to any agent working here)
- `test_server.py` — pytest test suite (`make test`)
- `smoke_events.sh` — seeds demo events into a running server

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
agent-status-board        # start the server
make test                 # run tests
make clear-events         # wipe persisted events and restart clean
```

Default port is `5747`. Override via `prefs.txt` or `--port`.
