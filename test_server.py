from __future__ import annotations

import json

from agent_status_board.cli import apply_cli_overrides, build_parser, main
from agent_status_board.server import EVENT_CAP, bind_host, create_app, load_preferences


def make_client(event_log_path=None, preferences=None):
    app = create_app(event_log_path=event_log_path, preferences=preferences)
    app.config.update(TESTING=True)
    return app.test_client(), app


def valid_payload(**overrides):
    payload = {
        "next_action": "Update status UI filters",
        "status": "in_progress",
        "reason": "The event stream needs status filtering.",
        "intent": "Make the status surface useful during development",
        "confidence": 0.78,
        "session_id": "session-a",
        "task_id": "task-filter-ui",
    }
    payload.update(overrides)
    return payload


def post_report(client, **overrides):
    return client.post("/report", json=valid_payload(**overrides))


def test_report_accepts_valid_payload():
    client, _ = make_client()

    response = post_report(client, repo="astatus")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["event"]["id"] == 1
    assert body["event"]["next_action"] == "Update status UI filters"
    assert body["event"]["status"] == "in_progress"
    assert body["event"]["repo"] == "astatus"
    assert body["event"]["session_id"] == "session-a"
    assert body["event"]["task_id"] == "task-filter-ui"
    assert "timestamp" in body["event"]


def test_report_defaults_session_id_when_omitted():
    client, _ = make_client()
    payload = valid_payload()
    del payload["session_id"]

    response = client.post("/report", json=payload)

    assert response.status_code == 200
    assert response.get_json()["event"]["session_id"] == "default"


def test_report_omits_blank_and_default_repo_values():
    client, _ = make_client()

    blank_response = post_report(client, repo=" ")
    default_response = post_report(client, repo="default")

    assert blank_response.status_code == 200
    assert default_response.status_code == 200
    assert "repo" not in blank_response.get_json()["event"]
    assert "repo" not in default_response.get_json()["event"]


def test_report_rejects_missing_required_fields():
    client, _ = make_client()

    response = client.post("/report", json={})

    assert response.status_code == 400
    assert response.get_json() == {
        "status": "error",
        "errors": [
            "next_action is required",
            "status is required",
            "reason is required",
        ],
    }


def test_report_rejects_non_json_requests():
    client, _ = make_client()

    response = client.post("/report", data="not json")

    assert response.status_code == 400
    assert response.get_json() == {
        "status": "error",
        "errors": ["request body must be JSON object"],
    }


def test_report_rejects_unsupported_statuses():
    client, _ = make_client()

    response = post_report(client, status="started")

    assert response.status_code == 400
    assert response.get_json()["errors"] == [
        "status must be one of: blocked, done, in_progress, proposed"
    ]


def test_report_rejects_invalid_session_task_and_repo_identifiers():
    client, _ = make_client()

    empty_session_response = post_report(client, session_id=" ")
    numeric_task_response = post_report(client, task_id=123)
    long_task_response = post_report(client, task_id="x" * 121)
    numeric_repo_response = post_report(client, repo=123)
    long_repo_response = post_report(client, repo="x" * 121)

    assert empty_session_response.status_code == 400
    assert numeric_task_response.status_code == 400
    assert long_task_response.status_code == 400
    assert numeric_repo_response.status_code == 400
    assert long_repo_response.status_code == 400
    assert empty_session_response.get_json()["errors"] == ["session_id must not be empty"]
    assert numeric_task_response.get_json()["errors"] == ["task_id must be a string"]
    assert long_task_response.get_json()["errors"] == [
        "task_id must be 120 characters or fewer"
    ]
    assert numeric_repo_response.get_json()["errors"] == ["repo must be a string"]
    assert long_repo_response.get_json()["errors"] == [
        "repo must be 120 characters or fewer"
    ]


def test_report_rejects_invalid_confidence_values():
    client, _ = make_client()

    low_response = post_report(client, confidence=-0.1)
    high_response = post_report(client, confidence=1.1)
    nan_response = post_report(client, confidence=float("nan"))
    inf_response = post_report(client, confidence=float("inf"))
    negative_inf_response = post_report(client, confidence=float("-inf"))
    text_response = post_report(client, confidence="high")
    bool_response = post_report(client, confidence=True)

    assert low_response.status_code == 400
    assert high_response.status_code == 400
    assert nan_response.status_code == 400
    assert inf_response.status_code == 400
    assert negative_inf_response.status_code == 400
    assert text_response.status_code == 400
    assert bool_response.status_code == 400
    assert low_response.get_json()["errors"] == ["confidence must be between 0 and 1"]
    assert high_response.get_json()["errors"] == ["confidence must be between 0 and 1"]
    assert nan_response.get_json()["errors"] == ["confidence must be between 0 and 1"]
    assert inf_response.get_json()["errors"] == ["confidence must be between 0 and 1"]
    assert negative_inf_response.get_json()["errors"] == [
        "confidence must be between 0 and 1"
    ]
    assert text_response.get_json()["errors"] == ["confidence must be a number"]
    assert bool_response.get_json()["errors"] == ["confidence must be a number"]


def test_report_rejects_raw_json_non_finite_confidence_values():
    client, _ = make_client()

    for value in ("NaN", "Infinity", "-Infinity"):
        response = client.post(
            "/report",
            data=(
                '{"next_action":"Task","status":"in_progress",'
                f'"reason":"Reason","confidence":{value}}}'
            ),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.get_json()["errors"] == ["confidence must be between 0 and 1"]


def test_report_rejects_oversized_request_body():
    client, _ = make_client()

    response = client.post(
        "/report",
        data="{" + ('"x": "y",' * 3000) + '"end": "value"}',
        content_type="application/json",
    )

    assert response.status_code == 413


def test_report_overwrites_client_owned_id_and_timestamp():
    client, _ = make_client()

    response = post_report(client, id=999, timestamp="2000-01-01T00:00:00")

    assert response.status_code == 200
    event = response.get_json()["event"]
    assert event["id"] == 1
    assert event["timestamp"] != "2000-01-01T00:00:00"


def test_event_cap_keeps_latest_events():
    client, _ = make_client()

    for index in range(EVENT_CAP + 5):
        response = post_report(
            client,
            next_action=f"Persist status report batch item {index}",
            reason=f"Exercise the in-memory cap with report batch item {index}.",
        )
        assert response.status_code == 200

    response = client.get("/events", query_string={"limit": 200})
    events = response.get_json()["events"]

    assert len(events) == 200
    assert events[0]["next_action"] == f"Persist status report batch item {EVENT_CAP + 4}"
    assert (
        events[-1]["next_action"]
        == f"Persist status report batch item {EVENT_CAP + 4 - 199}"
    )


def test_events_returns_newest_first_ordering():
    client, _ = make_client()

    post_report(client, next_action="Validate report payload schema")
    post_report(client, next_action="Persist accepted report to JSONL")
    post_report(client, next_action="Refresh event stream from events API")

    response = client.get("/events")

    assert response.status_code == 200
    assert [event["next_action"] for event in response.get_json()["events"]] == [
        "Refresh event stream from events API",
        "Persist accepted report to JSONL",
        "Validate report payload schema",
    ]


def test_events_filters_blocked_status():
    client, _ = make_client()

    post_report(client, next_action="Implement event stream filters", status="in_progress")
    post_report(client, next_action="Run browser smoke test for filters", status="blocked")

    response = client.get("/events", query_string={"status": "blocked"})

    assert response.status_code == 200
    assert [event["next_action"] for event in response.get_json()["events"]] == [
        "Run browser smoke test for filters"
    ]


def test_events_filters_session_id_and_task_id():
    client, _ = make_client()

    post_report(
        client,
        next_action="Persist accepted reports for desktop review",
        session_id="codex-desktop-2026-05-04",
        task_id="jsonl-report-persistence",
    )
    post_report(
        client,
        next_action="Persist accepted reports for CLI review",
        session_id="codex-cli-2026-05-04",
        task_id="jsonl-report-persistence",
    )
    post_report(
        client,
        next_action="Filter desktop reports by task",
        session_id="codex-desktop-2026-05-04",
        task_id="event-filter-controls",
    )

    response = client.get(
        "/events",
        query_string={
            "session_id": "codex-desktop-2026-05-04",
            "task_id": "jsonl-report-persistence",
        },
    )

    assert response.status_code == 200
    assert [event["next_action"] for event in response.get_json()["events"]] == [
        "Persist accepted reports for desktop review"
    ]


def test_events_filters_repo():
    client, _ = make_client()

    post_report(
        client,
        next_action="Render astatus board cards",
        repo="astatus",
        task_id="kanban-board-rendering",
    )
    post_report(
        client,
        next_action="Render other project board cards",
        repo="other-project",
        task_id="kanban-board-rendering",
    )

    response = client.get("/events", query_string={"repo": "astatus"})

    assert response.status_code == 200
    assert [event["next_action"] for event in response.get_json()["events"]] == [
        "Render astatus board cards"
    ]


def test_events_limit_parameter():
    client, _ = make_client()

    post_report(client, next_action="Validate report payload schema")
    post_report(client, next_action="Persist accepted report to JSONL")
    post_report(client, next_action="Refresh event stream from events API")

    response = client.get("/events", query_string={"limit": 2})

    assert response.status_code == 200
    assert [event["next_action"] for event in response.get_json()["events"]] == [
        "Refresh event stream from events API",
        "Persist accepted report to JSONL",
    ]


def test_hide_event_excludes_event_from_events():
    client, _ = make_client()

    post_report(client, next_action="Validate report payload schema")
    post_report(client, next_action="Persist accepted report to JSONL")

    response = client.post("/events/2/hide")
    events_response = client.get("/events")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "event_id": 2}
    assert [event["next_action"] for event in events_response.get_json()["events"]] == [
        "Validate report payload schema"
    ]


def test_hide_event_returns_404_for_unknown_event():
    client, _ = make_client()

    response = client.post("/events/999/hide")

    assert response.status_code == 404
    assert response.get_json() == {
        "status": "error",
        "errors": ["event not found"],
    }


def test_index_returns_html():
    client, _ = make_client()

    response = client.get("/")

    assert response.status_code == 200
    assert response.content_type.startswith("text/html")
    assert b"Agent Status Board" in response.data
    assert b'href="/cube-dark.svg"' in response.data
    assert b'src="/cube-dark.svg"' in response.data
    assert b'"/cube.svg"' in response.data
    assert b"Google Sans Code" in response.data
    assert b'id="board"' in response.data
    assert b'id="stream"' in response.data
    assert b'id="view-toggle"' in response.data
    assert b'agent-status-view' in response.data
    assert b'id="theme-toggle"' in response.data
    assert b'agent-status-theme' in response.data
    assert b"const refreshIntervalMs = 1000;" in response.data
    assert b"const boardLimit = 100;" in response.data
    assert b'const statuses = ["proposed", "in_progress", "blocked", "done"];' in response.data
    assert b"--board-column-count" in response.data
    assert b"const streamLimit = 50;" in response.data
    assert b"Repo" in response.data
    assert b"visibleRepo" in response.data
    assert b"applyBoardLayout" in response.data
    assert b"--board-width" in response.data
    assert b"repo-pill" in response.data
    assert b"duration-row" in response.data
    assert b"openCardDetails" in response.data
    assert b"data-task-key" in response.data
    assert b"data-hide-event-id" in response.data
    assert b"/hide" in response.data
    assert b"hide-button" in response.data
    assert b"card-disclosure" in response.data
    assert b"card-details" in response.data
    assert b"confidence-dot" in response.data


def test_index_uses_configured_refresh_rate_and_limits():
    client, _ = make_client(
        event_log_path=None,
        preferences={
            "refresh_rate_seconds": 2.5,
            "board_limit": 25,
            "board_statuses": ["in_progress", "blocked"],
            "stream_limit": 10,
        },
    )

    response = client.get("/")

    assert response.status_code == 200
    assert b"const refreshIntervalMs = 2500;" in response.data
    assert b"const boardLimit = 25;" in response.data
    assert b'const statuses = ["in_progress", "blocked"];' in response.data
    assert b"const streamLimit = 10;" in response.data


def test_cube_svgs_are_served():
    client, _ = make_client()

    light_response = client.get("/cube.svg")
    dark_response = client.get("/cube-dark.svg")

    assert light_response.status_code == 200
    assert dark_response.status_code == 200
    assert light_response.content_type.startswith("image/svg+xml")
    assert dark_response.content_type.startswith("image/svg+xml")
    assert b"<svg" in light_response.data
    assert b"<svg" in dark_response.data
    assert b"fill:#fff;fill-rule:nonzero" in dark_response.data


def test_tasks_collapses_events_by_task_id_and_uses_latest_status():
    client, _ = make_client()

    post_report(
        client,
        next_action="Start JSONL persistence",
        status="in_progress",
        task_id="jsonl-report-persistence",
    )
    post_report(
        client,
        next_action="Finish JSONL persistence",
        status="done",
        task_id="jsonl-report-persistence",
    )

    response = client.get("/tasks")

    assert response.status_code == 200
    tasks = response.get_json()["tasks"]
    assert tasks["in_progress"] == []
    assert len(tasks["done"]) == 1
    assert tasks["done"][0]["next_action"] == "Finish JSONL persistence"
    assert tasks["done"][0]["task_key"] == "jsonl-report-persistence"
    assert "started_at" in tasks["done"][0]
    assert "completed_at" in tasks["done"][0]
    assert "duration_seconds" in tasks["done"][0]


def test_tasks_groups_latest_task_states_by_status():
    client, _ = make_client()

    post_report(
        client,
        next_action="Draft status report schema",
        status="proposed",
        task_id="status-report-schema",
    )
    post_report(
        client,
        next_action="Implement board rendering",
        status="in_progress",
        task_id="kanban-board-rendering",
    )
    post_report(
        client,
        next_action="Investigate browser reload failure",
        status="blocked",
        task_id="browser-reload-smoke",
    )
    post_report(
        client,
        next_action="Finish event stream filters",
        status="done",
        task_id="event-stream-filters",
    )

    response = client.get("/tasks")

    assert response.status_code == 200
    tasks = response.get_json()["tasks"]
    assert [task["task_id"] for task in tasks["proposed"]] == ["status-report-schema"]
    assert [task["task_id"] for task in tasks["in_progress"]] == [
        "kanban-board-rendering"
    ]
    assert [task["task_id"] for task in tasks["blocked"]] == ["browser-reload-smoke"]
    assert [task["task_id"] for task in tasks["done"]] == ["event-stream-filters"]


def test_tasks_filters_session_id_and_task_id():
    client, _ = make_client()

    post_report(
        client,
        next_action="Render desktop board cards",
        session_id="codex-desktop-2026-05-04",
        task_id="kanban-board-rendering",
    )
    post_report(
        client,
        next_action="Render CLI board cards",
        session_id="codex-cli-2026-05-04",
        task_id="kanban-board-rendering",
    )
    post_report(
        client,
        next_action="Refresh desktop stream",
        session_id="codex-desktop-2026-05-04",
        task_id="event-stream-refresh",
    )

    response = client.get(
        "/tasks",
        query_string={
            "session_id": "codex-desktop-2026-05-04",
            "task_id": "kanban-board-rendering",
        },
    )

    assert response.status_code == 200
    tasks = response.get_json()["tasks"]
    assert [task["next_action"] for task in tasks["in_progress"]] == [
        "Render desktop board cards"
    ]


def test_tasks_filters_repo():
    client, _ = make_client()

    post_report(
        client,
        next_action="Render astatus board cards",
        repo="astatus",
        task_id="kanban-board-rendering",
    )
    post_report(
        client,
        next_action="Render other project board cards",
        repo="other-project",
        task_id="kanban-board-rendering",
    )

    response = client.get("/tasks", query_string={"repo": "astatus"})

    assert response.status_code == 200
    tasks = response.get_json()["tasks"]
    assert [task["next_action"] for task in tasks["in_progress"]] == [
        "Render astatus board cards"
    ]


def test_tasks_keeps_events_without_task_id_as_individual_cards():
    client, _ = make_client()
    payload = valid_payload()
    del payload["task_id"]

    first_response = client.post(
        "/report",
        json={**payload, "next_action": "Inspect report validation behavior"},
    )
    second_response = client.post(
        "/report",
        json={**payload, "next_action": "Inspect event stream rendering"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    response = client.get("/tasks")

    assert response.status_code == 200
    tasks = response.get_json()["tasks"]["in_progress"]
    assert [task["next_action"] for task in tasks] == [
        "Inspect event stream rendering",
        "Inspect report validation behavior",
    ]
    assert [task["task_key"] for task in tasks] == ["event-2", "event-1"]


def test_tasks_limit_parameter_caps_derived_tasks():
    client, _ = make_client()

    post_report(client, next_action="Validate report payload schema", task_id="schema")
    post_report(client, next_action="Persist accepted report to JSONL", task_id="jsonl")
    post_report(client, next_action="Refresh event stream from events API", task_id="ui")

    response = client.get("/tasks", query_string={"limit": 2})

    assert response.status_code == 200
    tasks = response.get_json()["tasks"]["in_progress"]
    assert [task["task_id"] for task in tasks] == ["ui", "jsonl"]


def test_tasks_falls_back_when_latest_task_event_is_hidden():
    client, _ = make_client()

    post_report(
        client,
        next_action="Start event hiding controls",
        status="in_progress",
        task_id="hide-events-ui",
    )
    post_report(
        client,
        next_action="Finish event hiding controls",
        status="done",
        task_id="hide-events-ui",
    )

    hide_response = client.post("/events/2/hide")
    tasks_response = client.get("/tasks")

    assert hide_response.status_code == 200
    tasks = tasks_response.get_json()["tasks"]
    assert tasks["done"] == []
    assert [task["next_action"] for task in tasks["in_progress"]] == [
        "Start event hiding controls"
    ]


def test_tasks_computes_duration_from_first_in_progress_to_latest_done():
    client, app = make_client()

    client.post(
        "/report",
        json=valid_payload(
            next_action="Start Kanban board rendering",
            status="in_progress",
            task_id="kanban-board-rendering",
        ),
    )
    app.config["EVENTS"][-1]["timestamp"] = "2026-05-04T10:00:00+00:00"

    client.post(
        "/report",
        json=valid_payload(
            next_action="Retry Kanban board rendering",
            status="in_progress",
            task_id="kanban-board-rendering",
        ),
    )
    app.config["EVENTS"][-1]["timestamp"] = "2026-05-04T10:02:00+00:00"

    client.post(
        "/report",
        json=valid_payload(
            next_action="Finish Kanban board rendering",
            status="done",
            task_id="kanban-board-rendering",
        ),
    )
    app.config["EVENTS"][-1]["timestamp"] = "2026-05-04T10:05:30+00:00"

    response = client.get("/tasks")

    assert response.status_code == 200
    task = response.get_json()["tasks"]["done"][0]
    assert task["started_at"] == "2026-05-04T10:00:00+00:00"
    assert task["completed_at"] == "2026-05-04T10:05:30+00:00"
    assert task["duration_seconds"] == 330


def test_tasks_omits_duration_when_done_without_in_progress():
    client, _ = make_client()

    post_report(
        client,
        next_action="Mark documentation cleanup complete",
        status="done",
        task_id="documentation-cleanup",
    )

    response = client.get("/tasks")

    assert response.status_code == 200
    task = response.get_json()["tasks"]["done"][0]
    assert "completed_at" in task
    assert "started_at" not in task
    assert "duration_seconds" not in task


def test_health_returns_runtime_status(tmp_path):
    event_log_path = tmp_path / "events.jsonl"
    client, _ = make_client(event_log_path=event_log_path)
    post_report(client, next_action="Check status server health")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "event_count": 1,
        "event_log_path": str(event_log_path),
        "persistence": True,
        "preferences": {
            "allow_remote": False,
            "bind_host": "127.0.0.1",
            "board_limit": 100,
            "board_statuses": ["proposed", "in_progress", "blocked", "done"],
            "port": 5747,
            "refresh_rate_seconds": 1.0,
            "stream_limit": 50,
        },
    }


def test_events_persist_to_jsonl_and_reload(tmp_path):
    event_log_path = tmp_path / "events.jsonl"
    client, _ = make_client(event_log_path=event_log_path)

    response = post_report(
        client,
        next_action="Persist accepted report to JSONL",
        repo="astatus",
        session_id="session-persist",
        task_id="task-persist",
    )

    assert response.status_code == 200
    assert event_log_path.exists()
    persisted = json.loads(event_log_path.read_text(encoding="utf-8").strip())
    assert persisted["next_action"] == "Persist accepted report to JSONL"
    assert persisted["repo"] == "astatus"
    assert persisted["session_id"] == "session-persist"
    assert persisted["task_id"] == "task-persist"

    reloaded_client, _ = make_client(event_log_path=event_log_path)
    reload_response = reloaded_client.get("/events")

    assert reload_response.status_code == 200
    assert (
        reload_response.get_json()["events"][0]["next_action"]
        == "Persist accepted report to JSONL"
    )


def test_persisted_events_continue_monotonic_ids(tmp_path):
    event_log_path = tmp_path / "events.jsonl"
    client, _ = make_client(event_log_path=event_log_path)
    post_report(client, next_action="Persist accepted report to JSONL")

    reloaded_client, _ = make_client(event_log_path=event_log_path)
    response = post_report(reloaded_client, next_action="Reload persisted event IDs")

    assert response.status_code == 200
    assert response.get_json()["event"]["id"] == 2


def test_load_preferences_reads_runtime_settings(tmp_path):
    prefs_path = tmp_path / "prefs.txt"
    prefs_path.write_text(
        "\n".join(
            [
                "refresh_rate_seconds=2.5",
                "port=6000",
                "allow_remote=true",
                "board_limit=25",
                "board_statuses=in_progress,blocked",
                "stream_limit=10",
            ]
        ),
        encoding="utf-8",
    )

    preferences = load_preferences(prefs_path)

    assert preferences == {
        "allow_remote": True,
        "board_limit": 25,
        "board_statuses": ["in_progress", "blocked"],
        "port": 6000,
        "refresh_rate_seconds": 2.5,
        "stream_limit": 10,
    }
    assert bind_host(preferences) == "0.0.0.0"


def test_load_preferences_clamps_invalid_runtime_settings(tmp_path):
    prefs_path = tmp_path / "prefs.txt"
    prefs_path.write_text(
        "\n".join(
            [
                "refresh_rate_seconds=0",
                "port=70000",
                "allow_remote=definitely",
                "board_limit=999",
                "board_statuses=nope,done,done,blocked",
                "stream_limit=0",
            ]
        ),
        encoding="utf-8",
    )

    preferences = load_preferences(prefs_path)

    assert preferences == {
        "allow_remote": False,
        "board_limit": 200,
        "board_statuses": ["done", "blocked"],
        "port": 65535,
        "refresh_rate_seconds": 0.25,
        "stream_limit": 1,
    }
    assert bind_host(preferences) == "127.0.0.1"


def test_cli_init_creates_default_preferences(tmp_path):
    prefs_path = tmp_path / "prefs.txt"

    main(["--prefs", str(prefs_path), "--init"])

    preferences = load_preferences(prefs_path)
    assert prefs_path.exists()
    assert preferences["port"] == 5747
    assert preferences["refresh_rate_seconds"] == 1.0
    assert preferences["allow_remote"] is False
    assert preferences["board_statuses"] == ["proposed", "in_progress", "blocked", "done"]


def test_cli_overrides_preferences():
    parser = build_parser()
    args = parser.parse_args(["--port", "6000", "--allow-remote"])
    preferences = load_preferences(None)

    apply_cli_overrides(preferences, args)

    assert preferences["port"] == 6000
    assert preferences["allow_remote"] is True
    assert bind_host(preferences) == "0.0.0.0"


def test_hidden_events_persist_to_jsonl_and_reload(tmp_path):
    event_log_path = tmp_path / "events.jsonl"
    client, _ = make_client(event_log_path=event_log_path)
    post_report(client, next_action="Persist accepted report to JSONL")
    post_report(client, next_action="Hide noisy report from board")

    hide_response = client.post("/events/2/hide")
    reloaded_client, _ = make_client(event_log_path=event_log_path)
    reload_response = reloaded_client.get("/events")

    assert hide_response.status_code == 200
    records = [
        json.loads(line)
        for line in event_log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert records[-1]["type"] == "hide"
    assert records[-1]["event_id"] == 2
    assert [event["next_action"] for event in reload_response.get_json()["events"]] == [
        "Persist accepted report to JSONL"
    ]
