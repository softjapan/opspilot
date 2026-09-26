#!/usr/bin/env bash
# End-to-end smoke test for the OpsPilot demo stack.
#
# Assumes `docker compose up -d --build` has already been run (this script
# does not start/stop the stack, so repeated runs stay fast). Exits non-zero
# on the first failure.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

API_BASE="${OPSPILOT_API_BASE:-http://localhost:8000}"

fail() {
    echo "FAIL: $1" >&2
    exit 1
}

echo "==> Waiting for opspilot-api to respond..."
for _ in $(seq 1 30); do
    if curl -sf "$API_BASE/openapi.json" > /dev/null 2>&1; then
        break
    fi
    sleep 1
done
curl -sf "$API_BASE/openapi.json" > /dev/null 2>&1 || fail "opspilot-api did not become reachable at $API_BASE"
echo "    ok"

echo "==> Running CLI investigation against the demo target..."
CLI_OUTPUT="$(uv run opspilot investigate --target demo -q "smoke test" 2>&1)" \
    || fail "CLI 'opspilot investigate' exited non-zero:\n$CLI_OUTPUT"
echo "$CLI_OUTPUT" | grep -q "Confidence:" || fail "CLI output did not contain a Confidence line"
echo "    ok"

echo "==> Creating an investigation via the API..."
CREATE_RESPONSE="$(curl -sf -X POST "$API_BASE/investigations" \
    -H "Content-Type: application/json" \
    -d '{"target":"demo","question":"smoke test"}')" \
    || fail "POST /investigations failed"
INVESTIGATION_ID="$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['id'])" "$CREATE_RESPONSE")"
[ -n "$INVESTIGATION_ID" ] || fail "Could not parse investigation id from: $CREATE_RESPONSE"
echo "    ok (id=$INVESTIGATION_ID)"

echo "==> Streaming SSE events for the investigation..."
EVENTS="$(curl -sf -N --max-time 15 "$API_BASE/investigations/$INVESTIGATION_ID/events")" \
    || fail "GET /investigations/$INVESTIGATION_ID/events failed"
echo "$EVENTS" | grep -q '"type": "report"' || fail "SSE stream did not contain a report event:\n$EVENTS"
echo "    ok"

echo ""
echo "All smoke checks passed."
