#!/usr/bin/env bash
# Restore the final 0.20/0.30/0.50 dense verifier after the six binary-scored trials.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESTS="$ROOT/tasks/reconcile-bug/tests"
if [ ! -f "$TESTS/test_dense.sh" ]; then
  echo "Missing test_dense.sh. Run scripts/use_binary_verifier.sh first or restore the dense verifier backup." >&2
  exit 1
fi
cp "$TESTS/test_dense.sh" "$TESTS/test.sh"
echo "Active verifier restored to dense reward."
