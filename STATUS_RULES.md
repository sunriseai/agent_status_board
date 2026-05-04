# Agent Status Reporting Rules

You are working with a local Agent Status Surface.

Before starting a meaningful task-level action, send a status report to:

```text
http://localhost:5747/report
```

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
    "repo": "astatus",
    "session_id": "codex-desktop-2026-05-04",
    "task_id": "status-ui-filters",
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

Status meanings:

- `proposed`: A possible next task has been identified, but execution has not started. Use this when discussing plans, surfacing follow-up work, or waiting for the user to choose whether to proceed.
- `in_progress`: The default state for task-sized work that is about to start or is actively underway.
- `done`: The task-sized action has completed.
- `blocked`: Meaningful progress cannot continue without required user approval, missing credentials, unavailable network/local services, missing files, unclear requirements, or another external dependency.

Do not use `blocked` for routine approvals that are quickly granted and do not
materially pause or change the task. Use `blocked` when approval is denied,
unavailable, or required before the task can continue.

Use the same `task_id` for reports about the same task, such as `in_progress`, `blocked`, and `done`. Use the same `session_id` for all reports in one Codex session. If you do not provide a `session_id`, the server records `default`.

Include `repo` when you know the current repository or workspace name, especially
when multiple repositories may post to the same board. Use a stable short name,
such as the repository directory name. Omit `repo`, or send it as blank, when it
is unknown. Do not send `repo` as `default`.

Naming guidance:

- Write `next_action` as a specific verb phrase, such as `Add JSONL persistence for accepted reports`.
- Use `repo` for the current repository/workspace, such as `astatus`, not a full local path.
- Use stable, lowercase, slug-like `task_id` values, such as `jsonl-report-persistence`.
- Use `session_id` for the working session, not the task, such as `codex-desktop-2026-05-04`.
- Avoid vague placeholders like `task-1`, `session-a`, `First task`, `misc`, or `update stuff`.

If the status server is unavailable, state that reporting failed and continue only if the user has allowed best-effort reporting.

Codex may need sandbox approval before posting to `localhost` for the first
time. Request approval for the local status report if needed. If approval is
denied or unavailable, state that reporting failed and continue only if the user
has allowed best-effort reporting.
