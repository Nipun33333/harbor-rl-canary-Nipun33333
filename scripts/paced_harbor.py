#!/usr/bin/env python3
"""Run the Harbor CLI with a guaranteed minimum interval between model calls.

Why this exists
---------------
The Groq Free account allows 8,000 tokens per rolling minute, and `terminus-2`
re-sends the whole conversation on every turn - measured prompts reach ~5,000
tokens by the fifth turn. Two calls inside one minute therefore exceed the
ceiling even when each one is legal on its own.

The obvious fix is to ask the agent to wait: `terminus-2` passes a per-command
`duration` to tmux, and the instruction tells the model to set it. That was tried
and it is not reliable - the same instruction produced `duration: 60.0` in one
trial and `duration: 0.5` in the next, because a small model does not follow a
timing rule consistently.

So pacing is enforced here instead, outside the model's control: every
`LiteLLM.call` waits until at least `--min-interval` seconds have passed since
the previous call returned. A real wait, applied identically to both arms, and
invisible to the task itself.

Usage (same arguments as `harbor`):

    python3 scripts/paced_harbor.py run --config .github/configs/harbor-groq-smoke.yml --yes

Requires the Harbor package importable by this interpreter.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

DEFAULT_MIN_INTERVAL_SEC = 75.0
TIMEOUTS: list[float] = []


class Pacer:
    """Enforces a minimum gap between the end of one call and the start of the next.

    Time and sleeping are injectable so the behaviour can be tested without
    waiting for real seconds to pass.
    """

    def __init__(self, min_interval: float, monotonic=time.monotonic, sleep=asyncio.sleep):
        self.min_interval = float(min_interval)
        self._monotonic = monotonic
        self._sleep = sleep
        self._last_finished: float | None = None
        self._lock = asyncio.Lock()
        self.waits: list[float] = []

    async def wait(self) -> float:
        """Sleep for whatever remains of the interval. Returns the seconds waited."""
        async with self._lock:
            if self._last_finished is None:
                return 0.0
            remaining = self.min_interval - (self._monotonic() - self._last_finished)
            if remaining <= 0:
                return 0.0
            self.waits.append(remaining)
            print(
                f"[paced-harbor] waiting {remaining:.1f}s to keep model calls "
                f"{self.min_interval:.0f}s apart",
                flush=True,
            )
            await self._sleep(remaining)
            return remaining

    def mark(self) -> None:
        self._last_finished = self._monotonic()


def install_pacing(min_interval: float, monotonic=time.monotonic, sleep=asyncio.sleep) -> Pacer:
    """Wrap LiteLLM.call so consecutive model calls cannot share a minute."""
    from harbor.llms.lite_llm import LiteLLM

    pacer = Pacer(min_interval, monotonic=monotonic, sleep=sleep)
    original = LiteLLM.call

    async def paced_call(self, *args, **kwargs):
        await pacer.wait()
        try:
            return await original(self, *args, **kwargs)
        finally:
            pacer.mark()

    LiteLLM.call = paced_call
    return pacer


def main() -> int:
    interval = float(
        os.environ.get("HARBOR_MIN_CALL_INTERVAL_SEC", DEFAULT_MIN_INTERVAL_SEC)
    )
    install_pacing(interval)
    print(
        f"[paced-harbor] model calls will be at least {interval:.0f}s apart "
        "(Groq Free: 8,000 tokens per rolling minute, whole conversation re-sent "
        "on every turn).",
        flush=True,
    )

    from harbor.cli.main import app

    return app()


if __name__ == "__main__":
    raise SystemExit(main())
