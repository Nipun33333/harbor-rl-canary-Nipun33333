#!/usr/bin/env python3
"""Groq Free-tier preflight: confirm the model, read the live quota, project the run.

Three subcommands, all of which only ever read the key from the environment and
never print it:

  models   GET /openai/v1/models and assert the configured model ID exists for
           this key. No inference, no token spend.
  probe    One deliberately tiny completion (max_tokens=1) to read the
           rate-limit response headers the API returns on every call. Costs a
           handful of tokens and tells us the live per-minute budget instead of
           the published figure. A 429 here is reported with the exact numbers
           Groq returns, and exits 3 so no trial is launched.
  budget   Project the cost of the full experiment from the tokens a real trial
           actually used, and refuse to start when the projection does not fit
           in what is left of the daily budget.

Groq does not expose "tokens used today" in any response header, so the daily
figure is supplied (GROQ_TPD_ALREADY_USED, default 0) and the hard stop for a
surprise exhaustion is the fail-fast 429 handling in probe plus the arm
validators refusing to continue after an error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_ROOT = "https://api.groq.com/openai/v1"
USER_AGENT = "harbor-rl-canary-preflight/1.0"
REQUIRED_MODEL = "qwen/qwen3.8-27b"

# The Free-plan text models and their published ceilings (Groq "Rate Limits",
# Free plan table). All text models on the plan share an 8K TPM / 200K TPD
# ceiling, which is why switching models cannot buy quota.
FREE_TEXT_MODELS = {
    "openai/gpt-oss-120b": {"rpm": 30, "tpm": 8000, "tpd": 200000},
    "openai/gpt-oss-20b": {"rpm": 30, "tpm": 8000, "tpd": 200000},
    "openai/gpt-oss-safeguard-20b": {"rpm": 3, "tpm": 2000, "tpd": 200000},
    "qwen/qwen3.8-27b": {"rpm": 30, "tpm": 8000, "tpd": 200000},
}

HEADERS_OF_INTEREST = (
    "x-ratelimit-limit-requests",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-reset-requests",
    "x-ratelimit-limit-tokens",
    "x-ratelimit-remaining-tokens",
    "x-ratelimit-reset-tokens",
    "retry-after",
)


def api_key() -> str:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        print("::error::GROQ_API_KEY is not set for this job.", file=sys.stderr)
        raise SystemExit(2)
    return key


def request(method: str, path: str, key: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{API_ROOT}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # api.groq.com sits behind an edge that rejects the default
            # Python-urllib user agent outright (Cloudflare 1010), which would
            # look like an auth failure. Send an explicit agent.
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.status, dict(response.headers), json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw[:800]}
        return exc.code, dict(exc.headers or {}), payload


def pick_headers(headers: dict) -> dict:
    lowered = {name.lower(): value for name, value in headers.items()}
    return {name: lowered.get(name) for name in HEADERS_OF_INTEREST if lowered.get(name)}


def cmd_models(args: argparse.Namespace) -> int:
    key = api_key()
    status, headers, payload = request("GET", "/models", key)
    if status != 200:
        print(f"::error::Groq model listing failed with HTTP {status}.", file=sys.stderr)
        print(json.dumps(payload)[:600], file=sys.stderr)
        return 2

    model_ids = {item.get("id") for item in payload.get("data", []) if item.get("id")}
    if REQUIRED_MODEL not in model_ids:
        print(
            f"::error::Model {REQUIRED_MODEL!r} is not available to this key. "
            f"Accessible IDs: {sorted(model_ids)}",
            file=sys.stderr,
        )
        return 2

    print(f"Model listing OK: {REQUIRED_MODEL} is available to this key.")
    print("Free-plan text models and published ceilings (Groq Rate Limits docs):")
    for model_id, limits in FREE_TEXT_MODELS.items():
        state = "available" if model_id in model_ids else "not listed for this key"
        print(f"  {model_id:32s} {limits['rpm']:>3} RPM {limits['tpm']:>6} TPM "
              f"{limits['tpd']:>7} TPD  ({state})")
    print(
        "Every free text model shares the same 8K TPM / 200K TPD ceiling, so the "
        "model choice cannot raise the quota - only the request size can."
    )
    limits = pick_headers(headers)
    if limits:
        print(f"Rate-limit headers on the listing call: {limits}")
    return 0


def extract_quota_numbers(message: str) -> dict:
    numbers = {}
    for name in ("Limit", "Used", "Requested"):
        match = re.search(rf"{name}\s+(\d+)", message)
        if match:
            numbers[name.lower()] = int(match.group(1))
    wait = re.search(r"try again in ([0-9hms.]+)", message, re.IGNORECASE)
    if wait:
        numbers["retry_hint"] = wait.group(1)
    return numbers


def cmd_probe(args: argparse.Namespace) -> int:
    key = api_key()
    body = {
        "model": REQUIRED_MODEL,
        "messages": [{"role": "user", "content": "ok"}],
        "max_tokens": 1,
        "temperature": 0,
    }
    status, headers, payload = request("POST", "/chat/completions", key, body)
    limits = pick_headers(headers)
    report: dict = {"status": status, "model": REQUIRED_MODEL, "headers": limits}

    if status == 200:
        usage = payload.get("usage") or {}
        report["probe_tokens"] = {
            "prompt": usage.get("prompt_tokens"),
            "completion": usage.get("completion_tokens"),
        }
        report["ok"] = True
        print("Quota probe OK (one 1-token request).")
        print(f"  live rate-limit headers: {limits}")
        print(
            "  remaining input tokens this minute: "
            f"{limits.get('x-ratelimit-remaining-tokens')} "
            f"(reset {limits.get('x-ratelimit-reset-tokens')})"
        )
        print(
            "  remaining requests today: "
            f"{limits.get('x-ratelimit-remaining-requests')} "
            f"(reset {limits.get('x-ratelimit-reset-requests')})"
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 0

    message = ""
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = str(error.get("message", ""))
        message = message or json.dumps(payload)[:800]
    report["error"] = message
    numbers = extract_quota_numbers(message)

    if status == 429:
        print("::error::Groq rejected the quota probe with HTTP 429 (rate limited).")
        if numbers:
            limit = numbers.get("limit")
            used = numbers.get("used")
            requested = numbers.get("requested")
            print(f"  reported limit={limit} used={used} requested={requested}")
            if limit is not None and used is not None:
                remaining = max(limit - used, 0)
                print(f"  remaining before this request would have been {remaining} tokens")
                if requested is not None and requested > remaining:
                    print(
                        "  this request alone would have needed "
                        f"{requested} tokens, more than the {remaining} left"
                    )
            if numbers.get("retry_hint"):
                print(f"  Groq's own retry hint: {numbers['retry_hint']}")
        else:
            print(f"  provider message: {message[:400]}")
        print(
            "  No trial was started. Re-dispatch this workflow after the daily "
            "window resets; nothing can be done to make the request smaller enough "
            "to fit a quota that is already spent."
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 3

    print(f"::error::Quota probe failed with HTTP {status}: {message[:400]}")
    return 2


def sum_tokens_used(jobs_root: Path) -> tuple[int, int]:
    """Total tokens already spent by jobs under this directory."""
    total_in = total_out = 0
    for result_path in jobs_root.rglob("result.json"):
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        stats = data.get("stats") if isinstance(data, dict) else None
        if not isinstance(stats, dict):
            continue
        total_in += int(stats.get("n_input_tokens") or 0)
        total_out += int(stats.get("n_output_tokens") or 0)
    return total_in, total_out


def cmd_budget(args: argparse.Namespace) -> int:
    per_trial = 0
    if args.smoke_summary and args.smoke_summary.exists():
        summary = json.loads(args.smoke_summary.read_text(encoding="utf-8"))
        per_trial = int((summary.get("tokens") or {}).get("total") or 0)

    used_in, used_out = sum_tokens_used(args.jobs_root)
    used_run = used_in + used_out
    remaining = args.daily_limit - args.already_used - used_run
    projected = int(per_trial * args.trials * args.safety)
    report = {
        "daily_limit_tpd": args.daily_limit,
        "already_used_today": args.already_used,
        "used_by_this_run": used_run,
        "remaining": remaining,
        "measured_tokens_per_trial": per_trial,
        "planned_trials": args.trials,
        "safety_factor": args.safety,
        "projected_cost": projected,
        "fits": projected <= remaining,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"Daily token budget    : {args.daily_limit:,}")
    print(f"Declared used today   : {args.already_used:,}")
    print(f"Used by this workflow : {used_run:,}")
    print(f"Remaining             : {remaining:,}")
    if per_trial == 0:
        print(
            "::warning::No token usage was recorded by the smoke trial, so the "
            "remaining cost cannot be projected; continuing with the configured caps."
        )
        return 0
    print(f"Measured per trial    : {per_trial:,} tokens")
    print(
        f"Projected for {args.trials} trials x {args.safety} safety: {projected:,} tokens"
    )
    if not report["fits"]:
        print(
            "::error::The remaining daily quota cannot cover the full experiment. "
            f"Projected {projected:,} tokens against {remaining:,} remaining. "
            "Stopping before any trial runs."
        )
        return 4
    print("Budget projection fits; the full experiment may proceed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    models = sub.add_parser("models", help="Confirm the model ID without inference")
    models.set_defaults(func=cmd_models)

    probe = sub.add_parser("probe", help="Read live rate limits with one 1-token call")
    probe.add_argument("--output", type=Path, default=None)
    probe.set_defaults(func=cmd_probe)

    budget = sub.add_parser("budget", help="Project the full run against the daily budget")
    budget.add_argument("--jobs-root", type=Path, default=Path("jobs"))
    budget.add_argument("--smoke-summary", type=Path, default=None)
    budget.add_argument("--trials", type=int, default=6)
    budget.add_argument(
        "--daily-limit",
        type=int,
        default=int(os.environ.get("GROQ_TPD_LIMIT") or 200000),
    )
    budget.add_argument(
        "--already-used",
        type=int,
        default=int(os.environ.get("GROQ_TPD_ALREADY_USED") or 0),
    )
    budget.add_argument("--safety", type=float, default=1.3)
    budget.add_argument("--output", type=Path, default=None)
    budget.set_defaults(func=cmd_budget)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
