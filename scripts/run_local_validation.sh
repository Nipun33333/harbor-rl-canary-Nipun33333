#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASK="$ROOT/tasks/reconcile-bug"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
APP="$TMP/app"
mkdir -p "$APP"

run_verifier() {
  local label="$1"
  local expected="$2"
  local logs="$TMP/logs-$label"
  mkdir -p "$logs"
  APP_DIR="$APP" VERIFIER_LOG_DIR="$logs" bash "$TASK/tests/test.sh"
  local got
  got="$(cat "$logs/reward.txt")"
  echo "$label: expected $expected, got $got"
  if [ "$got" != "$expected" ]; then
    echo "Local validation failed at $label" >&2
    exit 1
  fi
}

cp "$TASK/environment/reconcile.py" "$APP/reconcile.py"
run_verifier "starter" "0.00"

APP_DIR="$APP" bash "$TASK/solution/solve.sh"
run_verifier "full-solution" "1.00"

# Simulate the Loom partial-credit canary: Bugs 1 and 2 fixed, UTC handling broken.
sed 's/return parsed.astimezone(dt.timezone.utc)/return parsed.replace(tzinfo=dt.timezone.utc)/' \
  "$TASK/solution/solve.sh" > "$TMP/partial-solve.sh"
chmod +x "$TMP/partial-solve.sh"
APP_DIR="$APP" bash "$TMP/partial-solve.sh"
run_verifier "partial-solution" "0.50"

# Restore the complete solution before applying the deliberate reward-hacking stub.
APP_DIR="$APP" bash "$TASK/solution/solve.sh"
APP_DIR="$APP" bash "$TASK/solution/hack.sh"
run_verifier "hack" "0.00"

echo "All local validation states passed."
