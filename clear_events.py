from __future__ import annotations

from agent_status_board.server import configured_event_log_path


def main() -> None:
    event_log_path = configured_event_log_path()

    if event_log_path is None:
        print("Persistence is disabled; no event log to clear.")
        return

    if not event_log_path.exists():
        print(f"No event log found at {event_log_path}.")
        return

    event_count = sum(1 for _ in event_log_path.open("r", encoding="utf-8"))
    event_log_path.unlink()
    print(f"Deleted {event_count} persisted events from {event_log_path}.")
    print("Restart the status server to clear in-memory events from the UI.")


if __name__ == "__main__":
    main()
