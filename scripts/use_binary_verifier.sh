#!/usr/bin/env bash
# Switch Harbor's active tests/test.sh to the binary 0/1 wrapper for the first six LLM trials.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESTS="$ROOT/tasks/reconcile-bug/tests"
cp "$TESTS/test.sh" "$TESTS/test_dense.sh"
cp "$TESTS/test_binary.sh" "$TESTS/test.sh"
echo "Active verifier is now binary. Run baseline and ablation groups, then run scripts/use_dense_verifier.sh."
