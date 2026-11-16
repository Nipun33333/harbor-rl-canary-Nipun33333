#!/usr/bin/env python3
"""Unit tests for the harness-level pacing in scripts/paced_harbor.py.

No Harbor, no network, no real waiting: the clock and the sleep are injected, so
these tests pin the arithmetic that makes a trial survive the 8,000-tokens-per-
rolling-minute ceiling.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from paced_harbor import Pacer  # noqa: E402


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_first_call_never_waits():
    clock = FakeClock()
    pacer = Pacer(75.0, monotonic=clock.monotonic, sleep=clock.sleep)
    assert asyncio.run(pacer.wait()) == 0.0
    assert clock.slept == []


def test_second_call_waits_the_remainder_of_the_interval():
    clock = FakeClock()
    pacer = Pacer(75.0, monotonic=clock.monotonic, sleep=clock.sleep)
    asyncio.run(pacer.wait())
    pacer.mark()          # the model responded at t=1000
    clock.now += 5        # and only 5 seconds have passed since
    waited = asyncio.run(pacer.wait())
    assert waited == 70.0, waited
    assert clock.slept == [70.0]


def test_no_wait_when_the_interval_already_elapsed():
    clock = FakeClock()
    pacer = Pacer(75.0, monotonic=clock.monotonic, sleep=clock.sleep)
    asyncio.run(pacer.wait())
    pacer.mark()       # the model responded at t=1000
    clock.now += 120   # a slow response already covered the interval
    assert asyncio.run(pacer.wait()) == 0.0
    assert clock.slept == []


def test_consecutive_calls_stay_at_least_the_interval_apart():
    clock = FakeClock()
    pacer = Pacer(75.0, monotonic=clock.monotonic, sleep=clock.sleep)
    starts = []
    for _ in range(5):
        asyncio.run(pacer.wait())
        starts.append(clock.now)
        pacer.mark()      # response returned
        clock.now += 3    # model latency
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert all(gap >= 75.0 for gap in gaps), gaps


def main() -> int:
    tests = [
        test_first_call_never_waits,
        test_second_call_waits_the_remainder_of_the_interval,
        test_no_wait_when_the_interval_already_elapsed,
        test_consecutive_calls_stay_at_least_the_interval_apart,
    ]
    print("Paced-Harbor tests")
    for test in tests:
        test()
        print(f"  {test.__name__}: ok")
    print("All pacing cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
