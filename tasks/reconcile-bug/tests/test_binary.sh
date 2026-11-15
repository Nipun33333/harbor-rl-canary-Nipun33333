#!/usr/bin/env bash
# Binary calibration wrapper: 1.0 only when every dense-verifier check passes.
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
VERIFIER_LOG_DIR="${VERIFIER_LOG_DIR:-/logs/verifier}"
DENSE_SCRIPT="${DENSE_SCRIPT:-$(dirname "$0")/test_dense.sh}"
mkdir -p "$VERIFIER_LOG_DIR"

APP_DIR="$APP_DIR" VERIFIER_LOG_DIR="$VERIFIER_LOG_DIR" bash "$DENSE_SCRIPT"
score="$(cat "$VERIFIER_LOG_DIR/reward.txt" 2>/dev/null || printf '0.00')"
if [ "$score" = "1.00" ]; then
  printf '1.0\n' > "$VERIFIER_LOG_DIR/reward.txt"
else
  printf '0.0\n' > "$VERIFIER_LOG_DIR/reward.txt"
fi
