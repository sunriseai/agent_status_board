# Agent Status Surface (MVP)

## Product + Technical Specification

---

# 1. Overview

## Problem

When using coding agents such as Codex or Claude Code, there is no reliable, always-visible way to understand:

- What task the agent is working on now
- What it intends to do next
- Whether it is progressing, blocked, or drifting

Most developer tools assume humans author and update tasks directly. Modern agent workflows often look more like:

> Human defines direction -> Agent proposes and executes task-sized work

The missing surface is a lightweight activity board for agent intent.

---

## Goal

Build a minimal local system that:

1. Prompts a coding agent to report task-level intent before starting meaningful work
2. Receives those reports through a local HTTP server
3. Displays reports in a live updating UI with an event stream and filters
4. Gives the developer a practical way to observe agent progress while developing this project

Codex Desktop is the first target. Codex CLI compatibility is desirable, but the MVP should optimize for Desktop if the two environments diverge.

---

## Non-Goals (MVP)

- No authentication
- No durable persistence beyond process memory
- No multi-agent orchestration
- No Git integration
- No strict enforcement layer
- No attempt to track every tool call or shell command
- No automatic proof that a report occurred before a code change

Prompt-only compliance is acceptable for the MVP.

---

# 2. Core Concept

> Agents should externalize task-level intent before starting meaningful work.

This is achieved through:

- A prompt contract for Codex
- A local HTTP reporting endpoint
- An always-visible browser UI
- A lightweight event model that resembles a task board activity feed

This is not intended to be low-level telemetry. It should not require the agent to report every file read, search command, or exploratory inspection. Reports should correspond to task-sized work items that might reasonably appear on a Kanban or Jira board.

Examples of meaningful actions:

- Fix broken links in generated documentation
- Change `_clean_up` to handle null strings
- Add regression tests for failed login
- Refactor authentication middleware
- Investigate why the browser smoke test is failing
- Update the status UI to support filtering

Examples that do not need reports by default:

- Read a file to understand nearby code
- Search the repository for a symbol
- Inspect current git status
- Run a formatting command that is part of an already reported task

---

# 3. User Experience

## Developer Flow

1. Start the local server:

   ```bash
   python server.py
   ```

2. Open the UI:

   ```text
   http://localhost:5747
   ```

3. Start Codex Desktop with `STATUS_RULES.md` included in the working context.

4. Watch live task reports while development continues:

   ```text
   10:14:03  in_progress  Update status UI filters
             Reason: The event stream needs status filtering for development use.

   10:18:42  blocked      Run browser smoke test
             Reason: The local dev server is not responding on port 5747.

   10:20:11  done         Update status UI filters
             Reason: Filters are implemented and unit tests pass.
   ```

---

## UI Behavior

The MVP UI should be an event stream, not a full Kanban board.

Required behavior:

- Auto-refresh every 1 second, or fetch events every 1 second with JavaScript
- Show the most recent 50 events
- Sort newest first by server timestamp
- Filter by status:
  - `proposed`
  - `in_progress`
  - `done`
  - `blocked`
- Display:
  - timestamp
  - status
  - next action
  - reason
  - intent, when provided
  - confidence, when provided

Future versions may add grouped columns or timeline replay after the event model proves useful.

---

# 4. System Architecture

## Components

### 1. Agent

- Codex Desktop first
- Codex CLI compatibility where practical
- Sends task-level status reports by HTTP before beginning meaningful task work

### 2. Local Server

- Receives reports
- Validates request bodies
- Adds server-side timestamps and IDs
- Stores events in memory
- Serves JSON and HTML UI

### 3. UI Surface

- Displays recent agent activity
- Updates continuously
- Supports status filtering

---

## Data Flow

```text
Codex
  -> POST /report
  -> Local server validates and stores event
  -> UI fetches /events
  -> Developer observes progress
```

---

# 5. API Specification

## `POST /report`

Receives a single task-level status event.

### Request Body

```json
{
  "next_action": "Update status UI filters",
  "status": "in_progress",
  "reason": "The event stream needs status filtering for development use.",
  "repo": "astatus",
  "intent": "Make the agent status surface usable during project development",
  "confidence": 0.78
}
```

### Fields

| Field | Required | Type | Validation | Description |
| --- | --- | --- | --- | --- |
| `next_action` | yes | string | non-empty, max 240 chars | Task-sized work the agent is about to do |
| `status` | yes | string | one of `proposed`, `in_progress`, `done`, `blocked` | Current state of the task |
| `reason` | yes | string | non-empty, max 500 chars | Why the action is being taken |
| `repo` | no | string | max 120 chars; blank or `default` is omitted from display | Short repository or workspace name |
| `intent` | no | string | max 500 chars | Higher-level goal this action supports |
| `confidence` | no | number | float from 0 to 1 | Agent confidence in the action |

The server owns these fields and should ignore or overwrite client-provided values:

| Field | Description |
| --- | --- |
| `id` | Monotonic event ID assigned by the server |
| `timestamp` | ISO-8601 timestamp assigned when the server receives the report |

### Success Response

```json
{
  "status": "ok",
  "event": {
    "id": 1,
    "timestamp": "2026-05-04T10:14:03.123456",
    "next_action": "Update status UI filters",
    "status": "in_progress",
    "reason": "The event stream needs status filtering for development use.",
    "repo": "astatus",
    "intent": "Make the agent status surface usable during project development",
    "confidence": 0.78
  }
}
```

### Error Response

Invalid requests should return HTTP `400`:

```json
{
  "status": "error",
  "errors": [
    "next_action is required",
    "status must be one of: proposed, in_progress, done, blocked"
  ]
}
```

---

## `GET /events`

Returns recent events for the UI and test scripts.

### Query Parameters

| Parameter | Required | Description |
| --- | --- | --- |
| `limit` | no | Number of events to return. Default `50`, maximum `200`. |
| `status` | no | Optional status filter. |

### Response

```json
{
  "events": [
    {
      "id": 1,
      "timestamp": "2026-05-04T10:14:03.123456",
      "next_action": "Update status UI filters",
      "status": "in_progress",
      "reason": "The event stream needs status filtering for development use.",
      "intent": "Make the agent status surface usable during project development",
      "confidence": 0.78
    }
  ]
}
```

---

## `GET /`

Serves the browser UI.

---

# 6. Server Implementation (MVP)

## Tech Stack

- Python
- Flask
- In-memory list for events
- Server-rendered HTML plus small JavaScript fetch loop, or simple HTML refresh if JavaScript is deferred

## Example Validation Rules

The server should:

- Reject non-JSON requests
- Require `next_action`, `status`, and `reason`
- Reject unknown statuses
- Enforce string length limits
- Reject non-numeric `confidence`
- Reject `confidence` values below `0` or above `1`
- Assign `id` and `timestamp` server-side
- Keep only the latest in-memory events if memory grows beyond a reasonable cap, such as 1,000 events

---

# 7. Agent Instruction Contract

## File: `STATUS_RULES.md`

````md
# Agent Status Reporting Rules

You are working with a local Agent Status Surface.

Before starting a meaningful task-level action, send a status report to:

http://localhost:5747/report

A meaningful action is task-sized work that could appear on a Kanban or Jira board. Examples:

- Fix broken links in generated documentation
- Change `_clean_up` to handle null strings
- Add regression tests for failed login
- Refactor authentication middleware
- Investigate why the browser smoke test is failing

Do not report every tool call. Repository searches, file reads, git status checks, and other small inspection steps do not need separate reports unless they become their own investigation task.

Use this command shape:

```bash
curl -s -X POST http://localhost:5747/report \
  -H "Content-Type: application/json" \
  -d '{
    "next_action": "Update status UI filters",
    "status": "in_progress",
    "reason": "The event stream needs status filtering for development use.",
    "intent": "Make the agent status surface usable during project development",
    "confidence": 0.78
  }'
```

Repeat reporting when:

- Starting a new task-level action
- Marking a task as done
- Becoming blocked
- Changing direction in a meaningful way
- Beginning a retry that changes the plan

If the status server is unavailable, state that reporting failed and continue only if the user has allowed best-effort reporting.
````

---

# 8. Development Execution Plan

The goal of the execution plan is to make the tool usable while it is being built.

## Step 1: Prepare the Spec and Contract

- Clean up this Markdown document
- Create `STATUS_RULES.md`
- Keep the reporting scope task-level, not tool-level
- Document Desktop-first behavior and CLI compatibility goals

## Step 2: Build the Local Server

- Implement `server.py`
- Add `POST /report`
- Add validation and structured error responses
- Add server-side `id` and `timestamp`
- Add `GET /events`
- Add `GET /`

## Step 3: Add the Event Stream UI

- Render recent events newest first
- Add status filters
- Refresh every second
- Keep the layout dense enough to use during development

## Step 4: Add Developer Commands

- Add a simple command to run the server, such as:

  ```bash
  python server.py
  ```

- Optionally add `Makefile` targets:

  ```bash
  make dev
  make test
  ```

## Step 5: Add Unit Tests

Test what can be tested directly:

- Valid reports are accepted
- Invalid reports are rejected
- Server-assigned fields cannot be spoofed
- Event limits work
- `/events` returns expected ordering and filters
- The UI endpoint returns successfully

The MVP cannot automatically prove that an agent reported before execution. Unit tests can verify server behavior, and manual trials can evaluate prompt compliance.

## Step 6: Add Manual Smoke Fixtures

Create sample `curl` commands or a small script to seed events:

```bash
curl -s -X POST http://localhost:5747/report \
  -H "Content-Type: application/json" \
  -d '{
    "next_action": "Fix broken links in generated documentation",
    "status": "in_progress",
    "reason": "The docs contain stale references after a route rename.",
    "repo": "astatus"
  }'
```

Use these fixtures to test the UI without involving Codex.

## Step 7: Use the Tool While Developing It

Once the server and UI are minimally working:

1. Start the status server.
2. Open `http://localhost:5747`.
3. Include `STATUS_RULES.md` in the Codex Desktop context.
4. Continue building the project.
5. Treat missed or vague reports as feedback for improving the instruction contract.

## Step 8: Run Agent Compliance Trials

Run three manual trials:

| Trial | Prompt | Expected Report Pattern |
| --- | --- | --- |
| Basic fix | Fix a small bug and add a test | 2-4 task-level reports |
| Multi-step change | Refactor a module, add UI behavior, then test | Distinct reports per task-sized step |
| Blocked/retry flow | Ask for a task with a missing dependency or failing test | `blocked` or retry report appears when direction changes |

For each trial, manually record:

- Expected task-level actions
- Reports received
- Missing reports
- Vague reports
- Whether the UI stayed useful during development

---

# 9. Test Plan

## Unit Tests

Required:

- `POST /report` accepts a valid payload
- `POST /report` rejects missing required fields
- `POST /report` rejects unsupported statuses
- `POST /report` rejects invalid confidence values
- `POST /report` overwrites client-provided `id` and `timestamp`
- `GET /events` returns newest-first events
- `GET /events?status=blocked` filters correctly
- `GET /` returns HTML successfully

## Manual Tests

Required:

- Seed events with `curl`
- Confirm the UI updates within roughly 1 second
- Confirm filters work
- Run one Codex Desktop task with `STATUS_RULES.md`
- Compare observed task-sized actions against reports

---

# 10. Success Criteria

The MVP is successful if:

- Codex Desktop reports at least 70% of meaningful task-level actions during manual trials
- Reports are specific enough for a developer to understand current work
- The UI updates in near real time, roughly within 1 second
- The UI is useful enough to keep open while developing this project
- Unit tests cover API validation and event retrieval behavior

The MVP does not need to prove report-before-execution ordering automatically.

---

# 11. Known Limitations

- Codex may ignore prompt instructions
- Prompt-only compliance can drift over long sessions
- No enforcement layer exists yet
- Reports may be inconsistent across agent runtimes
- The system does not verify reports against actual code changes
- The system does not track every tool call
- In-memory events disappear when the server restarts

---

# 12. Future Extensions

## Phase 2

- Add lightweight persistence
- Add a file or Git diff watcher
- Correlate reported intent with actual changed files

## Phase 3

- Add Codex CLI-specific setup instructions
- Add Claude Code hooks where available
- Add multi-agent labels

## Phase 4

- Replace polling with WebSockets or Server-Sent Events
- Add timeline and replay UI
- Add grouped board view

## Phase 5

- Add intervention controls such as approve, reject, redirect, and pause
- Explore enforcement mechanisms where the agent runtime allows them

---

# 13. Key Insight

This system is not primarily logging.

It is:

> A lightweight way to make an agent's task-level planning loop visible while work is happening.

---

# 14. Summary

Build a local Desktop-first status surface where the agent declares task-level work before acting, the server validates and stores those reports, and the developer can watch progress in a live event stream while the project is being developed.
