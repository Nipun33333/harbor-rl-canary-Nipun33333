#!/usr/bin/env bash
# Hidden dense-reward verifier. Uses fresh random values on every invocation.
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
VERIFIER_LOG_DIR="${VERIFIER_LOG_DIR:-/logs/verifier}"
mkdir -p "$VERIFIER_LOG_DIR"

python - "$APP_DIR/reconcile.py" "$VERIFIER_LOG_DIR/reward.txt" "$VERIFIER_LOG_DIR/details.json" <<'PYTHON'
import csv
import json
import os
import random
import subprocess
import sys
import tempfile
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

script_path, reward_path, details_path = sys.argv[1:]
rng = random.SystemRandom()


def money(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


def money_millis(millis: int) -> str:
    return f"{millis // 1000}.{millis % 1000:03d}"


def run_case(rows, expected):
    with tempfile.TemporaryDirectory(prefix="reconcile-verifier-") as temp_dir:
        csv_path = os.path.join(temp_dir, f"input-{uuid.uuid4().hex}.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["tx_id", "timestamp", "amount", "status"])
            writer.writeheader()
            writer.writerows(rows)
        try:
            proc = subprocess.run(
                [sys.executable, script_path, csv_path],
                text=True,
                capture_output=True,
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        if proc.returncode != 0:
            return False
        try:
            actual = json.loads(proc.stdout)
            if not isinstance(actual, dict) or set(actual) != set(expected):
                return False
            amount = Decimal(str(actual["total_valid_amount"]))
            wanted_amount = Decimal(str(expected["total_valid_amount"]))
            if amount.quantize(Decimal("0.01")) != wanted_amount.quantize(Decimal("0.01")):
                return False
            return (
                actual["valid_count"] == expected["valid_count"]
                and actual["failed_count"] == expected["failed_count"]
            )
        except (json.JSONDecodeError, KeyError, TypeError, InvalidOperation, ValueError):
            return False


# Check 1 (0.20): the documented one-argument CLI and valid single-record path.
amount_1 = rng.randrange(101, 999999)
rows_1 = [{
    "tx_id": "single-" + uuid.uuid4().hex,
    "timestamp": "2026-04-01T12:00:00Z",
    "amount": money(amount_1),
    "status": "VALID",
}]
check_1 = run_case(rows_1, {
    "total_valid_amount": money(amount_1), "valid_count": 1, "failed_count": 0,
})

# Check 2 (0.30): status semantics on unique IDs; PENDING contributes nothing.
rows_2 = []
valid_amounts = []
failed_count = 0
statuses = ["VALID"] * 5 + ["FAILED"] * 4 + ["PENDING"] * 5
rng.shuffle(statuses)
for status in statuses:
    millis = rng.randrange(1000, 2500000)
    amount_text = money_millis(millis)
    rows_2.append({
        "tx_id": "status-" + uuid.uuid4().hex,
        "timestamp": "2026-05-02T08:00:00+00:00",
        "amount": amount_text,
        "status": status,
    })
    if status == "VALID":
        valid_amounts.append(Decimal(amount_text))
    elif status == "FAILED":
        failed_count += 1
rounded_valid_total = sum(valid_amounts, start=Decimal("0.000")).quantize(
    Decimal("0.01"), rounding=ROUND_HALF_UP
)
check_2 = run_case(rows_2, {
    "total_valid_amount": f"{rounded_valid_total:.2f}",
    "valid_count": len(valid_amounts),
    "failed_count": failed_count,
})

# Check 3 (0.50): duplicate IDs whose wall-clock order differs from UTC order.
# The newer UTC record is deliberately placed first; the later CSV row is older.
rows_3 = []
expected_cents_3 = 0
number_of_ids = 9
for _ in range(number_of_ids):
    tx_id = "tz-" + uuid.uuid4().hex
    newer_cents = rng.randrange(100, 300000)
    older_cents = rng.randrange(100, 300000)
    rows_3.append({
        "tx_id": tx_id,
        "timestamp": "2026-01-01T09:00:00+00:00",  # 09:00 UTC: newest
        "amount": money(newer_cents),
        "status": "VALID",
    })
    rows_3.append({
        "tx_id": tx_id,
        "timestamp": "2026-01-01T10:30:00+02:00",  # 08:30 UTC: older
        "amount": money(older_cents),
        "status": "VALID",
    })
    expected_cents_3 += newer_cents
check_3 = run_case(rows_3, {
    "total_valid_amount": money(expected_cents_3),
    "valid_count": number_of_ids,
    "failed_count": 0,
})

weights = {"cli_and_single_valid": 0.20, "status_filtering": 0.30, "utc_deduplication": 0.50}
checks = {
    "cli_and_single_valid": bool(check_1),
    "status_filtering": bool(check_2),
    "utc_deduplication": bool(check_3),
}
score = sum(weights[name] for name, passed in checks.items() if passed)
score = round(score + 1e-10, 2)

os.makedirs(os.path.dirname(reward_path), exist_ok=True)
with open(reward_path, "w", encoding="utf-8") as handle:
    handle.write(f"{score:.2f}\n")
with open(details_path, "w", encoding="utf-8") as handle:
    json.dump({"checks": checks, "weights": weights, "reward": score}, handle, indent=2)

print("Dense verifier results:")
for name, passed in checks.items():
    print(f"  {'PASS' if passed else 'FAIL'} {name} ({weights[name]:.2f})")
print(f"REWARD={score:.2f}")
PYTHON

status=$?
if [ "$status" -ne 0 ] || [ ! -s "$VERIFIER_LOG_DIR/reward.txt" ]; then
  printf '0.00\n' > "$VERIFIER_LOG_DIR/reward.txt"
  echo "Verifier harness failed; reward forced to 0.00" >&2
fi
