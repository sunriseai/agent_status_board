#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:5747}"

post_event() {
  curl -fsS -X POST "${BASE_URL}/report" \
    -H "Content-Type: application/json" \
    -d "$1"
  printf '\n'
}

post_event '{
  "next_action": "Define event stream layout for agent status reports",
  "status": "proposed",
  "reason": "The MVP needs a visible event stream before agent trials begin.",
  "repo": "astatus",
  "session_id": "smoke-demo-2026-05-04",
  "task_id": "event-stream-layout",
  "intent": "Make the status surface usable during development",
  "confidence": 0.82
}'

post_event '{
  "next_action": "Implement reporting API validation",
  "status": "in_progress",
  "reason": "The server must reject malformed agent reports before the UI relies on the data.",
  "repo": "astatus",
  "session_id": "smoke-demo-2026-05-04",
  "task_id": "report-payload-validation",
  "intent": "Build the local reporting MVP",
  "confidence": 0.91
}'

post_event '{
  "next_action": "Verify newest-first status filtering",
  "status": "done",
  "reason": "The events endpoint now returns newest-first filtered results.",
  "repo": "astatus",
  "session_id": "smoke-demo-2026-05-04",
  "task_id": "event-filter-verification",
  "intent": "Keep MVP behavior testable",
  "confidence": 0.88
}'

post_event '{
  "next_action": "Run browser smoke test for live event refresh",
  "status": "blocked",
  "reason": "The local server must be running on the configured port before browser verification.",
  "repo": "astatus",
  "session_id": "smoke-demo-2026-05-04",
  "task_id": "live-refresh-browser-smoke",
  "intent": "Verify the live UI manually",
  "confidence": 0.64
}'
