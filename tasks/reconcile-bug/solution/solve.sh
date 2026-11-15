#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR"
cat > "$APP_DIR/reconcile.py" <<'PYTHON'
#!/usr/bin/env python3
"""Correct payment transaction reconciler."""

import csv
import datetime as dt
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

REQUIRED_COLUMNS = {"tx_id", "timestamp", "amount", "status"}
CENT = Decimal("0.01")
VALID_STATUSES = {"VALID", "FAILED", "PENDING"}


def parse_utc_timestamp(value: str) -> dt.datetime:
    """Parse a timezone-aware ISO-8601 timestamp and normalize it to UTC."""
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(dt.timezone.utc)


def reconcile(csv_path: str) -> dict:
    latest = {}
    with open(csv_path, "r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):
            missing = sorted(REQUIRED_COLUMNS - set(reader.fieldnames or []))
            raise ValueError("missing required CSV headers: " + ", ".join(missing))

        for row_number, row in enumerate(reader):
            try:
                tx_id = (row.get("tx_id") or "").strip()
                status = (row.get("status") or "").strip().upper()
                if not tx_id or status not in VALID_STATUSES:
                    continue
                timestamp = parse_utc_timestamp(row.get("timestamp") or "")
                amount = Decimal((row.get("amount") or "").strip())
                if not amount.is_finite():
                    continue
                # Preserve source precision; only round the final aggregate.
            except (InvalidOperation, ValueError, TypeError, KeyError):
                continue

            previous = latest.get(tx_id)
            # Later CSV row wins only when two timestamps represent the same instant.
            if previous is None or (timestamp, row_number) >= (previous[0], previous[1]):
                latest[tx_id] = (timestamp, row_number, amount, status)

    total = sum(
        (record[2] for record in latest.values() if record[3] == "VALID"),
        start=Decimal("0.00"),
    ).quantize(CENT, rounding=ROUND_HALF_UP)
    valid_count = sum(1 for record in latest.values() if record[3] == "VALID")
    failed_count = sum(1 for record in latest.values() if record[3] == "FAILED")
    return {
        "total_valid_amount": float(total),
        "valid_count": valid_count,
        "failed_count": failed_count,
    }


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("Usage: reconcile.py INPUT.csv", file=sys.stderr)
        return 2
    try:
        result = reconcile(argv[0])
    except (OSError, csv.Error, ValueError) as exc:
        print(f"reconcile: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PYTHON
chmod +x "$APP_DIR/reconcile.py"
