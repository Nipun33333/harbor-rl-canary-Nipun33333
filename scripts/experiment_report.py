#!/usr/bin/env python3
"""Derive binary/dense advantages from the same real verifier checks.

No candidate execution and no API calls: test_binary.sh retains details.json
from its dense checks, then converts only reward.txt to binary. Both scores
therefore refer to the exact same candidate and randomized input datasets.
"""
import argparse
import hashlib
import json
from pathlib import Path


WEIGHTS = {"cli_and_single_valid": .2, "status_filtering": .3, "utc_deduplication": .5}


def summarize(job, expected=3):
    rows = []
    for path in sorted(Path(job).glob("*/result.json")):
        result = json.loads(path.read_text())
        if result.get("exception_info") or any(
            step.get("exception_info") for step in result.get("step_results", [])
        ) or result.get("reward_valid") is False:
            raise ValueError(f"{path.parent.name}: invalid or exceptional trial")
        verifier = path.parent / "verifier"
        details = json.loads((verifier / "details.json").read_text())
        checks = details["checks"]
        if set(checks) != set(WEIGHTS) or any(type(v) is not bool for v in checks.values()):
            raise ValueError("missing or invalid independent check evidence")
        if details["weights"] != WEIGHTS:
            raise ValueError("unexpected verifier weights")
        dense = round(sum(WEIGHTS[k] for k, v in checks.items() if v), 2)
        binary = float(all(checks.values()))
        observed = result.get("verifier_result", {}).get("rewards", {}).get("reward")
        if observed != binary or details["reward"] != dense:
            raise ValueError("recorded reward disagrees with verifier evidence")
        candidate = (verifier / "candidate.py").read_bytes()
        trajectory = json.loads((path.parent / "agent/trajectory.json").read_text())
        if not trajectory.get("steps"):
            raise ValueError("empty trajectory")
        rows.append({"trial": path.parent.name, "binary": binary, "dense": dense,
                     "checks": checks, "candidate_sha256": hashlib.sha256(candidate).hexdigest()})
    if len(rows) != expected:
        raise ValueError(f"expected {expected} trials, found {len(rows)}")
    means = {key: sum(r[key] for r in rows) / len(rows) for key in ("binary", "dense")}
    for row in rows:
        for key in means:
            row[key + "_advantage"] = row[key] - means[key]
    return {"trials": rows, "means": means}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--job", type=Path, required=True)
    p.add_argument("--expected", type=int, default=3)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = summarize(args.job, args.expected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
