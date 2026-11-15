#!/usr/bin/env python3
"""Intentionally flawed payment reconciliation CLI for the Harbor task."""

import csv
import json
import sys
from datetime import datetime


def main() -> int:
    # BUG 1: The documented interface accepts one CSV argument and prints JSON,
    # but this program incorrectly requires a second output-file argument.
    if len(sys.argv) != 3:
        print("Usage: reconcile.py INPUT.csv OUTPUT.json", file=sys.stderr)
        return 2

    input_path, output_path = sys.argv[1], sys.argv[2]
    latest = {}
    with open(input_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row_number, row in enumerate(reader):
            tx_id = (row.get("tx_id") or "").strip()
            try:
                # BUG 3: Removing the timezone makes wall-clock values look
                # comparable even when their UTC order is different.
                timestamp = datetime.fromisoformat(row["timestamp"]).replace(tzinfo=None)
                amount = float(row["amount"])
                status = (row.get("status") or "").strip().upper()
            except (KeyError, TypeError, ValueError):
                continue
            if not tx_id:
                continue
            current = latest.get(tx_id)
            if current is None or timestamp >= current[0]:
                latest[tx_id] = (timestamp, amount, status, row_number)

    total_valid_amount = 0.0
    valid_count = 0
    failed_count = 0
    for _, amount, status, _ in latest.values():
        # BUG 2: PENDING transactions must not be included in valid totals.
        if status in ("VALID", "PENDING"):
            total_valid_amount += amount
            valid_count += 1
        elif status == "FAILED":
            failed_count += 1

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "total_valid_amount": round(total_valid_amount, 2),
                "valid_count": valid_count,
                "failed_count": failed_count,
            },
            handle,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
