#!/usr/bin/env python3
"""Unit tests for the free daily-usage gate in scripts/groq_preflight.py.

No network and no key: the sizing, parsing and verdict helpers are pure, and the
provider message used here is a real one captured from a run on 2026-11-16.

Why this exists: the workflow twice spent a smoke trial discovering that the
account's day was already exhausted. Groq never publishes the day's running
total in a response header - it only appears inside a 429 body - so the gate
provokes a rejection on the per-minute ceiling (which costs nothing) and reads
the daily attribution out of it. These tests pin the parts that decision rests
on: the message it recognises, the numbers it extracts, and the verdict.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from groq_preflight import (  # noqa: E402
    daily_verdict,
    extract_organization,
    parse_daily_limits,
    probe_body_over,
)

# Captured verbatim from the failing run, trimmed only at the tail.
OLD_ORG = "org_01m32b0rsqexabshe4ryhtfb10"

REAL_TPD_MESSAGE = (
    "Rate limit reached for model `qwen/qwen3.8-27b` in organization "
    "`org_01m32b0rsqexabshe4ryhtfb10` service tier `on_demand` on tokens per day "
    "(TPD): Limit 200000, Used 196364, Requested 12000. Please try again in 38m42s"
)

REAL_TPM_MESSAGE = (
    "Rate limit reached for model `qwen/qwen3.8-27b` in organization "
    "`org_01m32b0rsqexabshe4ryhtfb10` service tier `on_demand` on tokens per "
    "minute (TPM): Limit 8000, Used 5432, Requested 4966. Please try again in 17s"
)


def test_verdict() -> None:
    assert daily_verdict(200_000, 196_364, 105_000) == (3_636, False)
    assert daily_verdict(200_000, 0, 105_000) == (200_000, True)
    # A used figure above the limit must clamp, not go negative.
    assert daily_verdict(200_000, 250_000, 1) == (0, False)
    # Exactly enough is enough.
    assert daily_verdict(200_000, 95_000, 105_000) == (105_000, True)


def test_parses_daily_attribution() -> None:
    parsed = parse_daily_limits(REAL_TPD_MESSAGE)
    assert parsed["limit"] == 200_000, parsed
    assert parsed["used"] == 196_364, parsed
    assert parsed["retry_hint"] == "38m42s", parsed
    assert parsed["scope"] == "day", parsed


def test_rejects_per_minute_message() -> None:
    # A per-minute rejection says nothing about the day, so it must not be read
    # as one - otherwise a busy minute would be mistaken for an exhausted day.
    assert parse_daily_limits(REAL_TPM_MESSAGE) == {}


def test_unrelated_message_is_not_parsed() -> None:
    assert parse_daily_limits("Invalid API Key") == {}
    assert parse_daily_limits("") == {}


def test_oversize_request_always_exceeds_its_ceiling() -> None:
    # The gate is only free if the request is actually rejected, so the sizing
    # must sit above the ceiling it was derived from, at any free-tier ceiling.
    for ceiling in (2_000, 8_000, 11_000):
        body = probe_body_over(ceiling)
        words = body["messages"][0]["content"].count("compute")
        assert words > ceiling, (ceiling, words)
        assert body["max_tokens"] == 1, body["max_tokens"]


# Captured from the real rejection that a replaced-but-same-organization key
# produces. The organization id is the only reliable account identity Groq
# states, and it appears in per-minute rejections too, not just daily ones.
REAL_TPM_MESSAGE_SAME_ORG = (
    "Rate limit reached for model `qwen/qwen3.8-27b` in organization "
    "`org_01m32b0rsqexabshe4ryhtfb10` service tier `on_demand` on tokens per "
    "minute (TPM): Limit 8000, Used 7500, Requested 12000."
)


def test_extracts_organization_from_rejection():
    assert extract_organization(REAL_TPD_MESSAGE) == OLD_ORG
    assert extract_organization(REAL_TPM_MESSAGE_SAME_ORG) == OLD_ORG
    other = REAL_TPD_MESSAGE.replace(OLD_ORG, "org_09zzdifferent00")
    assert extract_organization(other) == "org_09zzdifferent00"


def test_no_organization_leaves_identity_unknown():
    assert extract_organization("") is None
    assert extract_organization("Invalid API Key") is None
    assert extract_organization('{"error": {"message": "bad request"}}') is None


def main() -> int:
    tests = [
        test_verdict,
        test_parses_daily_attribution,
        test_rejects_per_minute_message,
        test_unrelated_message_is_not_parsed,
        test_oversize_request_always_exceeds_its_ceiling,
        test_extracts_organization_from_rejection,
        test_no_organization_leaves_identity_unknown,
    ]
    print("Groq daily-usage gate tests")
    for test in tests:
        test()
        print(f"  {test.__name__}: ok")
    print("All preflight gate cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
