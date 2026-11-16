#!/usr/bin/env python3
"""Validate one Harbor arm (smoke, baseline or ablation) from its real artifacts.

The rule this enforces: a group is green only when it contains the required
number of trials, every trial finished without an exception, every trial has a
parseable result.json, and the agent's trajectory.json shows it actually worked
in the container. Reward values are reported, never manufactured - a low reward
is a result, an exception is a failure.

Artifact layout this reads (Harbor 0.26.0):
    <jobs_root>/<job_name>/result.json                 job-level stats
    <jobs_root>/<job_name>/<trial>/result.json         trial-level result
    <jobs_root>/<job_name>/<trial>/agent/trajectory.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

# Terminus 2 records parsed keystrokes as tool calls; the Agent's own source
# notes that it uses text command parsing rather than native tool calling.
TERMINAL_TOOL = "bash_command"
# Ways an agent writes the program in place. Deliberately broad: the check is
# "did it change the file", not "did it use our favourite command".
WRITE_MARKERS = (
    "cat >",
    "cat >>",
    "tee ",
    "python - <<",
    "python3 - <<",
    ">> /app",
    "sed -i",
    "apply_patch",
    "cp ",
)
RUN_MARKERS = ("reconcile.py",)
WARN_MAX_PROMPT_TOKENS = 5000


class GroupFailure(RuntimeError):
    def __init__(self, message: str, *, incomplete: bool = False) -> None:
        super().__init__(message)
        self.incomplete = incomplete


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GroupFailure(f"missing artifact: {path}", incomplete=True) from exc
    except json.JSONDecodeError as exc:
        raise GroupFailure(f"invalid JSON in {path}: {exc}") from exc


def job_level_result(job_dir: Path) -> dict:
    path = job_dir / "result.json"
    data = load_json(path)
    if not isinstance(data, dict) or "stats" not in data:
        raise GroupFailure(f"{path} has no stats block; the job did not finish")
    return data


def trial_dirs(job_dir: Path) -> list[Path]:
    found = []
    for child in sorted(job_dir.iterdir()):
        if not child.is_dir():
            continue
        if (child / "result.json").exists() or (child / "agent").exists():
            found.append(child)
    return found


def rewards_of(trial_result: dict) -> dict[str, float]:
    verifier = trial_result.get("verifier_result") or {}
    rewards = verifier.get("rewards") or {}
    return {key: value for key, value in rewards.items() if isinstance(value, (int, float))}


def exception_entries(trial_result: dict) -> list[dict]:
    entries = []
    info = trial_result.get("exception_info")
    if info:
        entries.append(info)
    for step in trial_result.get("step_results") or []:
        if step.get("exception_info"):
            entries.append(step["exception_info"])
    return entries


def describe_exception(info: dict) -> str:
    kind = info.get("exception_type", "Exception")
    message = (info.get("exception_message") or "").strip().splitlines()
    first = message[0][:300] if message else ""
    return f"{kind}: {first}" if first else kind


def terminal_commands(trajectory: dict) -> list[str]:
    commands = []
    for step in trajectory.get("steps") or []:
        for call in step.get("tool_calls") or []:
            if call.get("function_name") != TERMINAL_TOOL:
                continue
            keys = (call.get("arguments") or {}).get("keystrokes")
            if isinstance(keys, str) and keys.strip():
                commands.append(keys)
    return commands


def token_totals(trajectory: dict) -> tuple[int, int, int]:
    total_in = total_out = max_prompt = 0
    for step in trajectory.get("steps") or []:
        metrics = step.get("metrics") or {}
        prompt = metrics.get("prompt_tokens") or 0
        completion = metrics.get("completion_tokens") or 0
        if isinstance(prompt, int):
            total_in += prompt
            max_prompt = max(max_prompt, prompt)
        if isinstance(completion, int):
            total_out += completion
    return total_in, total_out, max_prompt


def pass_at_k(n: int, c: int, k: int) -> float | None:
    if n < k or n == 0:
        return None
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def verify(
    jobs_root: Path,
    job_name: str,
    expected: int,
    require_workspace_edit: bool,
    require_test_command: bool,
    skip_trajectory_checks: bool = False,
    expect_reward: float | None = None,
) -> dict:
    job_dir = jobs_root / job_name
    if not job_dir.is_dir():
        raise GroupFailure(f"job directory not found: {job_dir}", incomplete=True)

    job = job_level_result(job_dir)
    stats = job.get("stats") or {}
    failures: list[str] = []
    warnings: list[str] = []

    total = job.get("n_total_trials", stats.get("n_total_trials"))
    completed = stats.get("n_completed_trials")
    errored = stats.get("n_errored_trials", 0)
    cancelled = stats.get("n_cancelled_trials", 0)
    retries = stats.get("n_retries", 0)

    if total != expected:
        failures.append(f"job reports {total} trials, expected {expected}")
    if completed != expected:
        failures.append(f"job reports {completed} completed trials, expected {expected}")
    if errored:
        failures.append(f"job reports {errored} errored trial(s)")
    if cancelled:
        failures.append(f"job reports {cancelled} cancelled trial(s)")
    if retries:
        failures.append(f"job replayed {retries} trial(s); retries waste the daily budget")

    for key, group in (stats.get("evals") or {}).items():
        if group.get("n_errors"):
            failures.append(f"eval {key!r} reports {group['n_errors']} error(s)")
        exceptions = group.get("exception_stats") or {}
        for exception_type, trials in exceptions.items():
            failures.append(
                f"eval {key!r}: {exception_type} in {len(trials)} trial(s): "
                f"{', '.join(trials[:5])}"
            )

    trials = trial_dirs(job_dir)
    if len(trials) != expected:
        failures.append(f"found {len(trials)} trial directories, expected {expected}")

    rows: list[dict] = []
    total_in = total_out = 0
    max_prompt = 0

    for trial in trials:
        result_path = trial / "result.json"
        row: dict[str, Any] = {"trial": trial.name}
        if not result_path.exists():
            failures.append(f"{trial.name}: no result.json")
            rows.append(row)
            continue

        result = load_json(result_path)
        exceptions = exception_entries(result)
        if exceptions:
            reasons = "; ".join(describe_exception(info) for info in exceptions)
            failures.append(f"{trial.name}: exception(s) recorded - {reasons}")
            row["exceptions"] = reasons

        rewards = rewards_of(result)
        if not rewards:
            failures.append(f"{trial.name}: no verifier reward recorded")
        else:
            row["rewards"] = rewards
            if result.get("reward_valid") is False:
                failures.append(f"{trial.name}: reward is not valid (exception policy)")

        trajectory_path = trial / "agent" / "trajectory.json"
        if skip_trajectory_checks:
            rows.append(row)
            continue
        if not trajectory_path.exists():
            failures.append(f"{trial.name}: agent/trajectory.json is missing")
            rows.append(row)
            continue

        trajectory = load_json(trajectory_path)
        steps = trajectory.get("steps") or []
        if len(steps) < 2:
            failures.append(f"{trial.name}: trajectory has {len(steps)} step(s)")

        commands = terminal_commands(trajectory)
        if not commands:
            failures.append(f"{trial.name}: trajectory shows no terminal interaction")
        row["terminal_commands"] = len(commands)

        if require_workspace_edit:
            edits = [
                command
                for command in commands
                if "reconcile.py" in command
                and (
                    any(marker in command for marker in WRITE_MARKERS)
                    or re.search(r">\s*/app/reconcile\.py", command) is not None
                )
            ]
            if not edits:
                failures.append(
                    f"{trial.name}: no command wrote /app/reconcile.py; the agent did "
                    "not modify the task environment"
                )
            row["workspace_edits"] = len(edits)

        if require_test_command:
            checks = [
                command
                for command in commands
                if any(marker in command for marker in RUN_MARKERS)
                and ("py_compile" in command or "python" in command)
            ]
            if not checks:
                failures.append(
                    f"{trial.name}: no command executed the program; the agent did not "
                    "test what it wrote"
                )
            row["executions"] = len(checks)

        step_in, step_out, step_max = token_totals(trajectory)
        total_in += step_in
        total_out += step_out
        max_prompt = max(max_prompt, step_max)
        row["tokens"] = {"input": step_in, "output": step_out, "max_prompt": step_max}
        rows.append(row)

    if max_prompt > WARN_MAX_PROMPT_TOKENS:
        warnings.append(
            f"largest single request was {max_prompt} input tokens; on a 7,000 "
            "input-token/minute plan there is little headroom left"
        )

    values = []
    for row in rows:
        rewards = row.get("rewards") or {}
        if not rewards:
            continue
        # Harbor records the verifier's reward under "reward"; fall back to the
        # single value if a task ever publishes a differently named metric.
        value = rewards.get("reward", max(rewards.values()))
        values.append(float(value))
    if expect_reward is not None:
        best = max(values) if values else None
        if best is None or best < expect_reward:
            failures.append(
                f"expected a reward of at least {expect_reward:g}, got "
                f"{'none' if best is None else f'{best:g}'}"
            )

    summary: dict[str, Any] = {
        "job_name": job_name,
        "expected_trials": expected,
        "trials": rows,
        "n_trials": len(rows),
        "n_scored": len(values),
        "tokens": {
            "input": total_in,
            "output": total_out,
            "total": total_in + total_out,
            "max_prompt": max_prompt,
        },
        "failures": failures,
        "warnings": warnings,
        "ok": not failures,
    }
    if values:
        mean = sum(values) / len(values)
        summary["rewards"] = {
            "values": values,
            "mean": round(mean, 4),
            "pass_at_2": None if expected < 2 else round(pass_at_k(len(values), sum(1 for v in values if v >= 1.0), 2) or 0.0, 4),
            "zeros": sum(1 for v in values if v == 0),
            "advantages": [round(v - mean, 4) for v in values],
        }
    return summary


def render_markdown(summary: dict) -> str:
    lines = [f"### Harbor arm `{summary['job_name']}`", ""]
    lines.append("| Trial | Reward | Terminal cmds | Input tok | Output tok | Max prompt | Exceptions |")
    lines.append("| :-- | --: | --: | --: | --: | --: | :-- |")
    for row in summary["trials"]:
        reward = row.get("rewards")
        reward_text = ", ".join(f"{k}={v:g}" for k, v in reward.items()) if reward else "-"
        tokens = row.get("tokens") or {}
        lines.append(
            "| {trial} | {reward} | {cmds} | {tin} | {tout} | {mx} | {exc} |".format(
                trial=row["trial"],
                reward=reward_text,
                cmds=row.get("terminal_commands", 0),
                tin=tokens.get("input", 0),
                tout=tokens.get("output", 0),
                mx=tokens.get("max_prompt", 0),
                exc=row.get("exceptions", "none"),
            )
        )
    rewards = summary.get("rewards")
    if rewards:
        pass_at_2 = rewards.get("pass_at_2")
        lines += [
            "",
            f"Mean reward **{rewards['mean']:g}** over {summary['n_scored']} trial(s); "
            f"pass@2 {'n/a' if pass_at_2 is None else pass_at_2}; "
            f"zero-reward trials {rewards['zeros']}.",
            f"RL advantages (reward - group mean): {rewards['advantages']}",
        ]
    lines.append("")
    lines.append(
        f"Tokens consumed by this arm: {summary['tokens']['input']} input + "
        f"{summary['tokens']['output']} output = {summary['tokens']['total']}."
    )
    if summary["failures"]:
        lines.append("")
        lines.append("**FAILED**")
        lines += [f"- {item}" for item in summary["failures"]]
    if summary["warnings"]:
        lines.append("")
        lines += [f"- note: {item}" for item in summary["warnings"]]
    if summary["ok"]:
        lines.append("")
        lines.append("All required trials completed with zero exceptions.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs-root", required=True, type=Path)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--expected", required=True, type=int)
    parser.add_argument("--arm", default="arm")
    parser.add_argument("--require-workspace-edit", action="store_true")
    parser.add_argument("--require-test-command", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--skip-trajectory-checks",
        action="store_true",
        help="Calibration agents (nop/oracle) write no trajectory.json.",
    )
    parser.add_argument(
        "--expect-reward",
        type=float,
        default=None,
        help="Fail unless at least one trial scored this reward or better.",
    )
    args = parser.parse_args()

    try:
        summary = verify(
            args.jobs_root,
            args.job_name,
            args.expected,
            args.require_workspace_edit,
            args.require_test_command,
            args.skip_trajectory_checks,
            args.expect_reward,
        )
    except GroupFailure as exc:
        message = f"{args.arm}: {exc}"
        print(message, file=sys.stderr)
        print(f"::error::{message}")
        return 2

    summary["arm"] = args.arm
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    markdown = render_markdown(summary)
    print(markdown)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write(markdown + "\n")

    if not summary["ok"]:
        for item in summary["failures"]:
            print(f"::error::{args.arm}: {item}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
