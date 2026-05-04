from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from itertools import count
from math import isfinite
from pathlib import Path
from threading import Lock
from typing import Any

from flask import Flask, jsonify, render_template_string, request, send_from_directory


STATUS_ORDER = ("proposed", "in_progress", "blocked", "done")
ALLOWED_STATUSES = set(STATUS_ORDER)
DEFAULT_EVENT_LIMIT = 50
MAX_EVENT_LIMIT = 200
EVENT_CAP = 1000
NEXT_ACTION_MAX_LENGTH = 240
TEXT_MAX_LENGTH = 500
IDENTIFIER_MAX_LENGTH = 120
MAX_CONTENT_LENGTH = 16 * 1024
DEFAULT_SESSION_ID = "default"
DEFAULT_EVENT_LOG_PATH = Path("data/events.jsonl")
DEFAULT_PREFS_PATH = Path("prefs.txt")
DEFAULT_REFRESH_RATE_SECONDS = 1.0
DEFAULT_PORT = 5747
DEFAULT_ALLOW_REMOTE = False
DEFAULT_BOARD_LIMIT = 100
DEFAULT_STREAM_LIMIT = 50
DEFAULT_BOARD_STATUSES = STATUS_ORDER
MIN_REFRESH_RATE_SECONDS = 0.25
MAX_REFRESH_RATE_SECONDS = 60.0
MIN_PORT = 1
MAX_PORT = 65535


HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agent Status Board</title>
  <link id="favicon" rel="icon" href="/cube-dark.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Google+Sans+Code:ital,wght@0,300..800;1,300..800&family=Silkscreen&display=swap" rel="stylesheet">
  <style>
    :root {
      color-scheme: dark;
      --bg: #101214;
      --fg: #f1f5f9;
      --muted: #9aa4b2;
      --line: #2b3139;
      --panel: #171a1f;
      --accent: #60a5fa;
      --proposed: #7c3aed;
      --in-progress: #0369a1;
      --done: #15803d;
      --blocked: #b42318;
    }

    body[data-theme="light"] {
      color-scheme: light;
      --bg: #ffffff;
      --fg: #17191c;
      --muted: #667085;
      --line: #d8dde6;
      --panel: #ffffff;
      --accent: #2563eb;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--fg);
      font-family: "Google Sans Code", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      font-size: 14px;
    }

    main {
      max-width: 1120px;
      margin: 0 auto;
      padding: 20px;
    }

    .meta {
      color: var(--muted);
      font-size: 13px;
      margin-top: 4px;
    }

    button {
      appearance: none;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      color: var(--fg);
      cursor: pointer;
      font: inherit;
      padding: 7px 10px;
    }

    .theme-toggle {
      align-items: center;
      display: inline-flex;
      height: 34px;
      justify-content: center;
      min-width: 34px;
      padding: 0;
      width: 34px;
    }

    .view-toggle {
      align-items: center;
      display: inline-flex;
      height: 34px;
      justify-content: center;
      min-width: 34px;
      padding: 0;
      width: 34px;
    }

    .section-meta {
      align-items: center;
      display: flex;
      gap: 10px;
    }

    .section-title {
      align-items: baseline;
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin: 22px auto 10px;
      max-width: var(--board-width, 1120px);
      width: 100%;
    }

    .section-title h2 {
      font-size: 16px;
      line-height: 1.2;
      margin: 0;
    }

    .board-icon {
      display: block;
      height: 24px;
      width: 24px;
    }

    body[data-view="stream"] .board,
    body[data-view="stream"] #board-summary,
    body[data-view="board"] .stream,
    body[data-view="board"] #stream-summary {
      display: none;
    }

    .board {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(var(--board-column-count, 4), minmax(0, 260px));
      justify-content: center;
      margin-left: auto;
      margin-right: auto;
      max-width: var(--board-width, 1120px);
    }

    .column {
      min-width: 0;
    }

    .column-header {
      align-items: center;
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
    }

    .column-title {
      font-size: 13px;
      font-weight: 800;
      text-transform: uppercase;
    }

    .count {
      color: var(--muted);
      font-size: 12px;
    }

    .cards,
    .stream {
      display: grid;
      gap: 8px;
    }

    .card,
    .event {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
    }

    .event {
      display: grid;
      grid-template-columns: 160px 120px 1fr;
      gap: 12px;
      position: relative;
    }

    .card {
      border-top: 4px solid var(--line);
      min-height: 150px;
      position: relative;
    }

    .card.proposed { border-top-color: var(--proposed); }
    .card.in_progress { border-top-color: var(--in-progress); }
    .card.done { border-top-color: var(--done); }
    .card.blocked { border-top-color: var(--blocked); }

    .card-meta {
      align-items: center;
      display: flex;
      font-family: "Silkscreen", monospace;
      gap: 8px;
      justify-content: space-between;
      margin-bottom: 8px;
      min-height: 22px;
      padding-right: 32px;
    }

    .card-meta-main {
      align-items: center;
      display: inline-flex;
      gap: 6px;
      min-width: 0;
    }

    .card-meta .time,
    .repo-pill,
    .duration-pill {
      font-family: "Silkscreen", monospace;
      font-size: 8px;
      font-weight: 400;
      letter-spacing: 0;
      line-height: 1;
    }

    .repo-pill {
      background: color-mix(in srgb, var(--accent) 12%, transparent);
      border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent);
      border-radius: 999px;
      color: var(--muted);
      display: inline-block;
      max-width: 92px;
      overflow: hidden;
      padding: 4px 6px;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .duration-pill {
      background: color-mix(in srgb, var(--done) 12%, transparent);
      border: 1px solid color-mix(in srgb, var(--done) 32%, transparent);
      border-radius: 999px;
      color: var(--muted);
      display: inline-block;
      margin-top: 8px;
      padding: 4px 6px;
      white-space: nowrap;
    }

    .time,
    .details {
      color: var(--muted);
      font-size: 13px;
    }

    .badge {
      align-self: start;
      border-radius: 999px;
      color: white;
      display: inline-block;
      font-size: 12px;
      font-weight: 700;
      justify-self: start;
      line-height: 1;
      padding: 6px 8px;
      text-transform: uppercase;
    }

    .badge.proposed { background: var(--proposed); }
    .badge.in_progress { background: var(--in-progress); }
    .badge.done { background: var(--done); }
    .badge.blocked { background: var(--blocked); }

    .action {
      font-weight: 700;
      line-height: 1.35;
      margin-bottom: 4px;
    }

    .reason {
      line-height: 1.4;
    }

    .duration-row {
      margin-top: 8px;
    }

    .hide-button {
      align-items: center;
      border-radius: 999px;
      color: var(--muted);
      display: inline-flex;
      font-size: 12px;
      height: 22px;
      justify-content: center;
      line-height: 1;
      padding: 0;
      position: absolute;
      right: 8px;
      top: 7px;
      width: 22px;
    }

    .hide-button:hover {
      border-color: var(--blocked);
      color: var(--fg);
    }

    .details {
      margin-top: 6px;
    }

    .card-details {
      border-collapse: collapse;
      color: var(--muted);
      font-family: "Silkscreen", monospace;
      font-size: 8px;
      font-weight: 400;
      letter-spacing: 0;
      line-height: 1.2;
      margin-top: 10px;
      table-layout: fixed;
      width: 100%;
    }

    .card-disclosure {
      margin-top: 8px;
    }

    .card-disclosure summary {
      color: var(--muted);
      cursor: pointer;
      font-family: "Silkscreen", monospace;
      font-size: 8px;
      font-weight: 400;
      line-height: 1;
      list-style-position: inside;
    }

    .card-disclosure summary::marker {
      font-size: 8px;
    }

    .card-details th,
    .card-details td {
      overflow-wrap: anywhere;
      padding: 2px 0;
      text-align: left;
      vertical-align: top;
    }

    .card-details th {
      color: var(--muted);
      font-weight: 400;
      padding-right: 8px;
      text-transform: uppercase;
      width: 56px;
    }

    .card-details td {
      color: var(--fg);
    }

    .confidence-cell {
      text-align: right;
      width: 18px;
    }

    .confidence-dot {
      border: 1px solid color-mix(in srgb, var(--fg) 22%, transparent);
      border-radius: 999px;
      display: inline-block;
      height: 10px;
      width: 10px;
    }

    .empty,
    .error {
      border: 1px dashed var(--line);
      border-radius: 8px;
      color: var(--muted);
      padding: 28px;
      text-align: center;
    }

    .error {
      color: var(--blocked);
    }

    @media (max-width: 760px) {
      .board,
      .event {
        display: block;
      }

      .column {
        margin-bottom: 14px;
      }

      .badge {
        margin: 8px 0;
      }
    }
  </style>
</head>
<body>
  <main>
    <section class="section-title">
      <h2><img class="board-icon" id="board-icon" src="/cube-dark.svg" alt="Agent Status Board"></h2>
      <div class="section-meta">
        <div class="meta" id="board-summary">Loading tasks...</div>
        <div class="meta" id="stream-summary">Loading events...</div>
        <button class="view-toggle" id="view-toggle" type="button" title="Show event stream" aria-label="Show event stream">▤</button>
        <button class="theme-toggle" id="theme-toggle" type="button" title="Switch to light mode" aria-label="Switch to light mode">☀</button>
      </div>
    </section>
    <section class="board" id="board" aria-live="polite"></section>
    <section class="stream" id="stream" aria-live="polite"></section>
  </main>

  <script>
    const statuses = {{ board_statuses_json | safe }};
    const statusLabels = {
      proposed: "Proposed",
      in_progress: "In Progress",
      blocked: "Blocked",
      done: "Done"
    };
    const board = document.querySelector("#board");
    const boardSummary = document.querySelector("#board-summary");
    const stream = document.querySelector("#stream");
    const streamSummary = document.querySelector("#stream-summary");
    const boardIcon = document.querySelector("#board-icon");
    const favicon = document.querySelector("#favicon");
    const viewToggle = document.querySelector("#view-toggle");
    const themeToggle = document.querySelector("#theme-toggle");
    const openCardDetails = new Set();
    const boardColumnWidth = 260;
    const boardColumnGap = 12;
    const refreshIntervalMs = {{ refresh_interval_ms }};
    const boardLimit = {{ board_limit }};
    const streamLimit = {{ stream_limit }};

    function applyBoardLayout() {
      const columnCount = Math.max(1, statuses.length);
      const boardWidth = (columnCount * boardColumnWidth) + ((columnCount - 1) * boardColumnGap);
      document.documentElement.style.setProperty("--board-column-count", String(columnCount));
      document.documentElement.style.setProperty("--board-width", `${boardWidth}px`);
    }

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      })[char]);
    }

    function formatTime(value) {
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) {
        return value;
      }
      return date.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
      });
    }

    function formatDuration(seconds) {
      if (seconds === undefined || seconds === null) {
        return "";
      }

      const totalSeconds = Math.max(0, Math.round(Number(seconds)));
      const hours = Math.floor(totalSeconds / 3600);
      const minutes = Math.floor((totalSeconds % 3600) / 60);
      const remainder = totalSeconds % 60;

      if (hours > 0) {
        return `${hours}h ${minutes}m`;
      }
      if (minutes > 0) {
        return `${minutes}m ${remainder}s`;
      }
      return `${remainder}s`;
    }

    function eventDetails(event) {
      return [
        visibleRepo(event.repo) ? `Repo: ${escapeHtml(event.repo)}` : "",
        event.session_id ? `Session: ${escapeHtml(event.session_id)}` : "",
        event.task_id ? `Task: ${escapeHtml(event.task_id)}` : "",
        event.intent ? `Intent: ${escapeHtml(event.intent)}` : "",
        event.confidence === undefined || event.confidence === null ? "" : `Confidence: ${escapeHtml(event.confidence)}`
      ].filter(Boolean).join(" · ");
    }

    function visibleRepo(repo) {
      return repo && repo !== "default";
    }

    function confidenceDot(event) {
      if (event.confidence === undefined || event.confidence === null) {
        return "";
      }

      const confidence = Math.max(0, Math.min(1, Number(event.confidence)));
      const hue = Math.round(confidence * 120);
      const percent = Math.round(confidence * 100);
      return `<span class="confidence-dot" title="Confidence ${percent}%" style="background-color: hsl(${hue} 70% 45%)"></span>`;
    }

    function cardDetails(task) {
      const rows = [
        ["Session", task.session_id],
        ["Task", task.task_id],
        ["Intent", task.intent]
      ].filter(([, value]) => value);

      if (rows.length === 0 && (task.confidence === undefined || task.confidence === null)) {
        return "";
      }

      const confidence = confidenceDot(task);
      const taskKey = task.task_key || `event-${task.id}`;
      const openAttribute = openCardDetails.has(taskKey) ? " open" : "";
      return `
        <details class="card-disclosure" data-task-key="${escapeHtml(taskKey)}"${openAttribute}>
          <summary aria-label="Show details"></summary>
          <table class="card-details">
            <tbody>
              ${rows.map(([label, value], index) => `
                <tr>
                  <th>${escapeHtml(label)}</th>
                  <td>${escapeHtml(value)}</td>
                  ${index === 0 ? `<td class="confidence-cell" rowspan="${Math.max(rows.length, 1)}">${confidence}</td>` : ""}
                </tr>
              `).join("")}
              ${rows.length === 0 ? `<tr><td class="confidence-cell">${confidence}</td></tr>` : ""}
            </tbody>
          </table>
        </details>
      `;
    }

    function hideButton(eventId) {
      if (eventId === undefined || eventId === null) {
        return "";
      }

      return `<button class="hide-button" type="button" data-hide-event-id="${escapeHtml(eventId)}" title="Hide this" aria-label="Hide this">×</button>`;
    }

    function repoPill(task) {
      if (!visibleRepo(task.repo)) {
        return "";
      }

      return `<span class="repo-pill" title="Repo ${escapeHtml(task.repo)}">${escapeHtml(task.repo)}</span>`;
    }

    function bindCardDisclosures() {
      document.querySelectorAll(".card-disclosure").forEach((details) => {
        details.addEventListener("toggle", () => {
          const taskKey = details.dataset.taskKey;
          if (!taskKey) {
            return;
          }

          if (details.open) {
            openCardDetails.add(taskKey);
          } else {
            openCardDetails.delete(taskKey);
          }
        });
      });
    }

    function renderBoard(groupedTasks) {
      const allTasks = statuses.flatMap((status) => groupedTasks[status] || []);
      boardSummary.textContent = `${allTasks.length} visible task${allTasks.length === 1 ? "" : "s"}`;
      applyBoardLayout();

      board.innerHTML = statuses.map((status) => {
        const tasks = groupedTasks[status] || [];
        const cards = tasks.length === 0 ? '<div class="empty">No tasks.</div>' : tasks.map((task) => {
          const details = cardDetails(task);
          const duration = task.status === "done" ? formatDuration(task.duration_seconds) : "";
          return `
            <article class="card ${escapeHtml(task.status)}">
              ${hideButton(task.id)}
              <div class="card-meta">
                <span class="card-meta-main">
                  <time class="time" datetime="${escapeHtml(task.timestamp)}">${escapeHtml(formatTime(task.timestamp))}</time>
                  ${repoPill(task)}
                </span>
              </div>
              <div class="action">${escapeHtml(task.next_action)}</div>
              <div class="reason">${escapeHtml(task.reason)}</div>
              ${duration ? `<div class="duration-row"><span class="duration-pill">Done in ${escapeHtml(duration)}</span></div>` : ""}
              ${details}
            </article>
          `;
        }).join("");

        return `
          <div class="column" data-column="${escapeHtml(status)}">
            <div class="column-header">
              <span class="column-title">${escapeHtml(statusLabels[status] || status)}</span>
              <span class="count" data-count="${escapeHtml(status)}">${tasks.length}</span>
            </div>
            <div class="cards" data-cards="${escapeHtml(status)}">${cards}</div>
          </div>
        `;
      }).join("");

      bindCardDisclosures();
    }

    function renderEvents(events) {
      streamSummary.textContent = `${events.length} visible event${events.length === 1 ? "" : "s"}`;

      if (events.length === 0) {
        stream.innerHTML = '<div class="empty">No events yet.</div>';
        return;
      }

      stream.innerHTML = events.map((event) => {
        const details = eventDetails(event);

        return `
          <article class="event">
            ${hideButton(event.id)}
            <time class="time" datetime="${escapeHtml(event.timestamp)}">${escapeHtml(formatTime(event.timestamp))}</time>
            <span class="badge ${escapeHtml(event.status)}">${escapeHtml(event.status.replace("_", " "))}</span>
            <div>
              <div class="action">${escapeHtml(event.next_action)}</div>
              <div class="reason">${escapeHtml(event.reason)}</div>
              ${details ? `<div class="details">${details}</div>` : ""}
            </div>
          </article>
        `;
      }).join("");
    }

    async function hideEvent(eventId, button) {
      button.disabled = true;

      try {
        const response = await fetch(`/events/${encodeURIComponent(eventId)}/hide`, {
          method: "POST"
        });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        refresh();
      } catch (error) {
        button.disabled = false;
        button.title = `Unable to hide: ${error.message}`;
      }
    }

    function queryParams(limit) {
      const params = new URLSearchParams({ limit: String(limit) });
      return params;
    }

    function applyTheme(theme) {
      document.body.dataset.theme = theme;
      const isDark = theme === "dark";
      const iconPath = isDark ? "/cube-dark.svg" : "/cube.svg";
      boardIcon.src = iconPath;
      favicon.href = iconPath;
      themeToggle.textContent = isDark ? "☀" : "◐";
      themeToggle.title = isDark ? "Switch to light mode" : "Switch to dark mode";
      themeToggle.setAttribute("aria-label", themeToggle.title);
      localStorage.setItem("agent-status-theme", theme);
    }

    function applyView(view) {
      document.body.dataset.view = view;
      const isBoard = view === "board";
      viewToggle.textContent = isBoard ? "▤" : "▦";
      viewToggle.title = isBoard ? "Show event stream" : "Show board";
      viewToggle.setAttribute("aria-label", viewToggle.title);
      localStorage.setItem("agent-status-view", view);
    }

    async function loadTasks() {
      const params = queryParams(boardLimit);

      try {
        const response = await fetch(`/tasks?${params.toString()}`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload = await response.json();
        renderBoard(payload.tasks || {});
      } catch (error) {
        boardSummary.textContent = "Unable to load tasks";
        board.style.setProperty("--board-column-count", "1");
        board.innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
      }
    }

    async function loadEvents() {
      const params = queryParams(streamLimit);

      try {
        const response = await fetch(`/events?${params.toString()}`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload = await response.json();
        renderEvents(payload.events || []);
      } catch (error) {
        streamSummary.textContent = "Unable to load events";
        stream.innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
      }
    }

    function refresh() {
      loadTasks();
      loadEvents();
    }

    themeToggle.addEventListener("click", () => {
      applyTheme(document.body.dataset.theme === "dark" ? "light" : "dark");
    });
    viewToggle.addEventListener("click", () => {
      applyView(document.body.dataset.view === "board" ? "stream" : "board");
    });
    document.addEventListener("click", (event) => {
      const button = event.target.closest("[data-hide-event-id]");
      if (!button) {
        return;
      }

      event.preventDefault();
      hideEvent(button.dataset.hideEventId, button);
    });

    applyTheme(localStorage.getItem("agent-status-theme") || "dark");
    applyView(localStorage.getItem("agent-status-view") || "board");
    applyBoardLayout();
    refresh();
    setInterval(refresh, refreshIntervalMs);
  </script>
</body>
</html>
"""


def create_app(
    event_log_path: str | Path | None = DEFAULT_EVENT_LOG_PATH,
    preferences: dict[str, Any] | None = None,
) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
    resolved_preferences = normalize_preferences(preferences or {})
    resolved_event_log_path = resolve_event_log_path(event_log_path)
    events = load_events(resolved_event_log_path)
    next_id = count(next_event_id(events))
    lock = Lock()

    @app.post("/report")
    def report():
        payload = request.get_json(silent=True)
        errors = validate_report_payload(payload)

        if errors:
            return jsonify({"status": "error", "errors": errors}), 400

        assert isinstance(payload, dict)
        event = {
            "id": next(next_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "next_action": payload["next_action"].strip(),
            "status": payload["status"],
            "reason": payload["reason"].strip(),
            "session_id": payload.get("session_id", DEFAULT_SESSION_ID).strip(),
        }

        task_id = payload.get("task_id")
        if task_id is not None:
            event["task_id"] = task_id.strip()

        intent = payload.get("intent")
        if intent is not None:
            event["intent"] = intent.strip()

        if "confidence" in payload:
            event["confidence"] = float(payload["confidence"])

        repo = payload.get("repo")
        if repo is not None and repo.strip() and repo.strip() != "default":
            event["repo"] = repo.strip()

        with lock:
            events.append(event)
            del events[:-EVENT_CAP]
            append_event(resolved_event_log_path, event)

        return jsonify({"status": "ok", "event": event})

    @app.post("/events/<int:event_id>/hide")
    def hide_event(event_id: int):
        hidden_event = None

        with lock:
            for event in events:
                if event.get("id") == event_id:
                    event["hidden"] = True
                    hidden_event = event
                    break

            if hidden_event is None:
                return jsonify({"status": "error", "errors": ["event not found"]}), 404

            append_event_hide(resolved_event_log_path, event_id)

        return jsonify({"status": "ok", "event_id": event_id})

    @app.get("/events")
    def get_events():
        status = request.args.get("status")
        session_id = request.args.get("session_id")
        task_id = request.args.get("task_id")
        repo = request.args.get("repo")
        limit = parse_limit(request.args.get("limit"))

        with lock:
            selected = visible_events(events)

        selected = filter_events(selected, status, session_id, task_id, repo)
        selected = list(reversed(selected))[:limit]
        return jsonify({"events": selected})

    @app.get("/tasks")
    def get_tasks():
        status = request.args.get("status")
        session_id = request.args.get("session_id")
        task_id = request.args.get("task_id")
        repo = request.args.get("repo")
        limit = parse_limit(request.args.get("limit"))

        with lock:
            selected = visible_events(events)

        selected = filter_events(selected, status, session_id, task_id, repo)
        tasks = derive_tasks(selected, limit)
        return jsonify({"tasks": tasks})

    @app.get("/")
    def index():
        return render_template_string(
            HTML,
            refresh_interval_ms=round(
                resolved_preferences["refresh_rate_seconds"] * 1000
            ),
            board_limit=resolved_preferences["board_limit"],
            board_statuses_json=json.dumps(resolved_preferences["board_statuses"]),
            stream_limit=resolved_preferences["stream_limit"],
        )

    @app.get("/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "event_count": len(events),
                "event_log_path": str(resolved_event_log_path)
                if resolved_event_log_path is not None
                else None,
                "persistence": resolved_event_log_path is not None,
                "preferences": {
                    "allow_remote": resolved_preferences["allow_remote"],
                    "bind_host": bind_host(resolved_preferences),
                    "board_limit": resolved_preferences["board_limit"],
                    "board_statuses": resolved_preferences["board_statuses"],
                    "port": resolved_preferences["port"],
                    "refresh_rate_seconds": resolved_preferences[
                        "refresh_rate_seconds"
                    ],
                    "stream_limit": resolved_preferences["stream_limit"],
                },
            }
        )

    @app.get("/cube.svg")
    @app.get("/cube-dark.svg")
    def cube_icon():
        return send_from_directory(
            Path(__file__).parent / "static",
            request.path.removeprefix("/"),
            mimetype="image/svg+xml",
        )

    app.config["EVENTS"] = events
    app.config["EVENT_LOG_PATH"] = resolved_event_log_path
    app.config["PREFERENCES"] = resolved_preferences
    return app


def validate_report_payload(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["request body must be JSON object"]

    errors: list[str] = []
    required_fields = ("next_action", "status", "reason")

    for field in required_fields:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} is required")

    next_action = payload.get("next_action")
    if isinstance(next_action, str) and len(next_action.strip()) > NEXT_ACTION_MAX_LENGTH:
        errors.append(f"next_action must be {NEXT_ACTION_MAX_LENGTH} characters or fewer")

    reason = payload.get("reason")
    if isinstance(reason, str) and len(reason.strip()) > TEXT_MAX_LENGTH:
        errors.append(f"reason must be {TEXT_MAX_LENGTH} characters or fewer")

    intent = payload.get("intent")
    if intent is not None:
        if not isinstance(intent, str):
            errors.append("intent must be a string")
        elif len(intent.strip()) > TEXT_MAX_LENGTH:
            errors.append(f"intent must be {TEXT_MAX_LENGTH} characters or fewer")

    for field in ("session_id", "task_id"):
        value = payload.get(field)
        if value is not None:
            if not isinstance(value, str):
                errors.append(f"{field} must be a string")
            elif not value.strip():
                errors.append(f"{field} must not be empty")
            elif len(value.strip()) > IDENTIFIER_MAX_LENGTH:
                errors.append(f"{field} must be {IDENTIFIER_MAX_LENGTH} characters or fewer")

    repo = payload.get("repo")
    if repo is not None:
        if not isinstance(repo, str):
            errors.append("repo must be a string")
        elif repo.strip() and len(repo.strip()) > IDENTIFIER_MAX_LENGTH:
            errors.append(f"repo must be {IDENTIFIER_MAX_LENGTH} characters or fewer")

    status = payload.get("status")
    if isinstance(status, str) and status not in ALLOWED_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_STATUSES))
        errors.append(f"status must be one of: {allowed}")

    confidence = payload.get("confidence")
    if confidence is not None:
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            errors.append("confidence must be a number")
        elif not isfinite(confidence) or confidence < 0 or confidence > 1:
            errors.append("confidence must be between 0 and 1")

    return errors


def parse_limit(raw_limit: str | None) -> int:
    if raw_limit is None:
        return DEFAULT_EVENT_LIMIT

    try:
        limit = int(raw_limit)
    except ValueError:
        return DEFAULT_EVENT_LIMIT

    if limit < 1:
        return DEFAULT_EVENT_LIMIT

    return min(limit, MAX_EVENT_LIMIT)


def filter_events(
    events: list[dict[str, Any]],
    status: str | None = None,
    session_id: str | None = None,
    task_id: str | None = None,
    repo: str | None = None,
) -> list[dict[str, Any]]:
    selected = events

    if status in ALLOWED_STATUSES:
        selected = [event for event in selected if event["status"] == status]
    elif status:
        return []

    if session_id:
        selected = [event for event in selected if event.get("session_id") == session_id]

    if task_id:
        selected = [event for event in selected if event.get("task_id") == task_id]

    if repo:
        selected = [event for event in selected if event.get("repo") == repo]

    return selected


def visible_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if not event.get("hidden")]


def derive_tasks(events: list[dict[str, Any]], limit: int) -> dict[str, list[dict[str, Any]]]:
    events_by_task: dict[str, list[dict[str, Any]]] = {}

    for event in events:
        task_key = event.get("task_id") or f"event-{event['id']}"
        events_by_task.setdefault(task_key, []).append(event)

    latest_by_task: dict[str, dict[str, Any]] = {}
    for task_key, task_events in events_by_task.items():
        latest_event = task_events[-1]
        task = dict(latest_event)
        task["task_key"] = task_key
        add_lifecycle_metrics(task, task_events)
        latest_by_task[task_key] = task

    latest_tasks = sorted(
        latest_by_task.values(),
        key=lambda task: task["id"],
        reverse=True,
    )[:limit]

    grouped = {status: [] for status in STATUS_ORDER}
    for task in latest_tasks:
        grouped[task["status"]].append(task)

    return grouped


def add_lifecycle_metrics(task: dict[str, Any], events: list[dict[str, Any]]) -> None:
    started_at = first_timestamp_for_status(events, "in_progress")
    completed_at = latest_timestamp_for_status(events, "done")

    if started_at is not None:
        task["started_at"] = started_at.isoformat()

    if completed_at is not None:
        task["completed_at"] = completed_at.isoformat()

    if started_at is not None and completed_at is not None:
        task["duration_seconds"] = max(
            0,
            round((completed_at - started_at).total_seconds()),
        )


def first_timestamp_for_status(
    events: list[dict[str, Any]], status: str
) -> datetime | None:
    for event in events:
        if event["status"] != status:
            continue
        timestamp = parse_timestamp(event.get("timestamp"))
        if timestamp is not None:
            return timestamp
    return None


def latest_timestamp_for_status(
    events: list[dict[str, Any]], status: str
) -> datetime | None:
    for event in reversed(events):
        if event["status"] != status:
            continue
        timestamp = parse_timestamp(event.get("timestamp"))
        if timestamp is not None:
            return timestamp
    return None


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None

    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError:
        return None

    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)

    return timestamp


def resolve_event_log_path(event_log_path: str | Path | None) -> Path | None:
    if event_log_path is None:
        return None

    return Path(event_log_path)


def configured_event_log_path() -> Path | None:
    raw_path = os.environ.get("AGENT_STATUS_EVENT_LOG")
    if raw_path == "":
        return None
    return Path(raw_path) if raw_path else DEFAULT_EVENT_LOG_PATH


def configured_prefs_path() -> Path:
    return Path(os.environ.get("AGENT_STATUS_PREFS", DEFAULT_PREFS_PATH))


def default_preferences() -> dict[str, Any]:
    return {
        "allow_remote": DEFAULT_ALLOW_REMOTE,
        "board_limit": DEFAULT_BOARD_LIMIT,
        "board_statuses": list(DEFAULT_BOARD_STATUSES),
        "port": DEFAULT_PORT,
        "refresh_rate_seconds": DEFAULT_REFRESH_RATE_SECONDS,
        "stream_limit": DEFAULT_STREAM_LIMIT,
    }


def load_preferences(prefs_path: str | Path | None = DEFAULT_PREFS_PATH) -> dict[str, Any]:
    preferences = default_preferences()
    if prefs_path is None:
        return preferences

    path = Path(prefs_path)
    if not path.exists():
        return preferences

    with path.open("r", encoding="utf-8") as prefs_file:
        for line in prefs_file:
            raw_line = line.strip()
            if not raw_line or raw_line.startswith("#"):
                continue
            if "=" not in raw_line:
                continue

            key, raw_value = [part.strip() for part in raw_line.split("=", 1)]
            apply_preference(preferences, key, raw_value)

    return preferences


def apply_preference(
    preferences: dict[str, Any],
    key: str,
    raw_value: str,
) -> None:
    if key == "refresh_rate_seconds":
        value = parse_float(raw_value)
        if value is not None:
            preferences[key] = clamp(
                value,
                MIN_REFRESH_RATE_SECONDS,
                MAX_REFRESH_RATE_SECONDS,
            )
    elif key == "port":
        value = parse_int(raw_value)
        if value is not None:
            preferences[key] = clamp(value, MIN_PORT, MAX_PORT)
    elif key == "allow_remote":
        value = parse_bool(raw_value)
        if value is not None:
            preferences[key] = value
    elif key in {"board_limit", "stream_limit"}:
        value = parse_int(raw_value)
        if value is not None:
            preferences[key] = clamp(value, 1, MAX_EVENT_LIMIT)
    elif key == "board_statuses":
        statuses = parse_board_statuses(raw_value)
        if statuses:
            preferences[key] = statuses


def normalize_preferences(preferences: dict[str, Any]) -> dict[str, Any]:
    normalized = default_preferences()
    for key, value in preferences.items():
        if key == "board_statuses" and isinstance(value, (list, tuple)):
            statuses = [status for status in value if status in ALLOWED_STATUSES]
            if statuses:
                normalized[key] = statuses
        else:
            apply_preference(normalized, key, str(value))
    return normalized


def parse_float(raw_value: str) -> float | None:
    try:
        return float(raw_value)
    except ValueError:
        return None


def parse_int(raw_value: str) -> int | None:
    try:
        return int(raw_value)
    except ValueError:
        return None


def parse_bool(raw_value: str) -> bool | None:
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def parse_board_statuses(raw_value: str) -> list[str]:
    statuses: list[str] = []
    for raw_status in raw_value.split(","):
        status = raw_status.strip()
        if status in ALLOWED_STATUSES and status not in statuses:
            statuses.append(status)
    return statuses


def clamp(value: int | float, minimum: int | float, maximum: int | float) -> Any:
    return max(minimum, min(value, maximum))


def bind_host(preferences: dict[str, Any]) -> str:
    return "0.0.0.0" if preferences["allow_remote"] else "127.0.0.1"


def load_events(event_log_path: Path | None) -> list[dict[str, Any]]:
    if event_log_path is None or not event_log_path.exists():
        return []

    events: list[dict[str, Any]] = []
    hidden_event_ids: set[int] = set()
    with event_log_path.open("r", encoding="utf-8") as event_log:
        for line in event_log:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                if event.get("type") == "hide" and isinstance(event.get("event_id"), int):
                    hidden_event_ids.add(event["event_id"])
                    continue
                if "session_id" not in event:
                    event["session_id"] = DEFAULT_SESSION_ID
                events.append(event)

    for event in events:
        if event.get("id") in hidden_event_ids:
            event["hidden"] = True

    return events[-EVENT_CAP:]


def append_event(event_log_path: Path | None, event: dict[str, Any]) -> None:
    append_log_record(event_log_path, event)


def append_event_hide(event_log_path: Path | None, event_id: int) -> None:
    append_log_record(
        event_log_path,
        {
            "type": "hide",
            "event_id": event_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def append_log_record(event_log_path: Path | None, record: dict[str, Any]) -> None:
    if event_log_path is None:
        return

    event_log_path.parent.mkdir(parents=True, exist_ok=True)
    with event_log_path.open("a", encoding="utf-8") as event_log:
        event_log.write(json.dumps(record, allow_nan=False, separators=(",", ":")))
        event_log.write("\n")


def next_event_id(events: list[dict[str, Any]]) -> int:
    ids = [event.get("id") for event in events if isinstance(event.get("id"), int)]
    return max(ids, default=0) + 1


runtime_preferences = load_preferences(configured_prefs_path())
app = create_app(configured_event_log_path(), runtime_preferences)
