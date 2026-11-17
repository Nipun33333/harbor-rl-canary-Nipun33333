#!/usr/bin/env python3
"""Offline admission gate; never claim Groq exposes a live daily-usage API."""
import argparse
from datetime import datetime, timezone


def check(used, observed_at, now=None, required=160000):
    now = now or datetime.now(timezone.utc)
    stamp = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("usage observation must include timezone")
    age = (now - stamp).total_seconds()
    if not 0 <= age <= 3600:
        raise ValueError("usage observation is stale or in the future")
    if not 0 <= used <= 200000 or 200000 - used < required:
        raise ValueError("declared remaining quota cannot cover smoke + six trials with margin")
    return 200000 - used


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--used", type=int, required=True)
    p.add_argument("--observed-at", required=True)
    a = p.parse_args()
    print(f"Declared remaining tokens: {check(a.used, a.observed_at)}. "
          "This is an operator observation, not a provider guarantee; avoid concurrent usage.")
