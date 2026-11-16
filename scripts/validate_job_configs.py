#!/usr/bin/env python3
"""Validate every Harbor JobConfig in .github/configs against the installed
Harbor schema and against the Groq-Free operating envelope this repository
depends on.

Why this exists
---------------
The previous workflow asserted a handful of config values inline, in YAML.
When the configuration changed, those assertions silently became stale and the
real failure (an oversized request per turn) was never caught before quota was
spent. Two problems are handled here instead:

1. Schema validation is delegated to Harbor itself (`harbor run --print-config`),
   so an invalid key, a renamed option or a wrong type fails here rather than
   forty minutes into a Docker run. No Harbor import is required, so this works
   with the isolated interpreter that `uv tool install` creates.
2. Policy validation encodes the Free-tier budget: one trial at a time, no
   summarisation requests, no client-side retries, bounded turns, bounded
   completion tokens, and a small terminal pane (the pane is re-sent with every
   turn when incremental diffing is impossible).

Estimated prompt size is reported for information. It is an estimate, not a
measurement; the authoritative numbers come from the trial trajectories.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / ".github" / "configs"

REQUIRED_MODEL = "groq/qwen/qwen3.8-27b"

# Config file -> expectations. Anything not listed here is schema-checked only.
EXPECTED: dict[str, dict] = {
    "harbor-groq-baseline.yml": {"n_attempts": 3, "jobs_dir": "jobs/groq-baseline"},
    "harbor-groq-ablation.yml": {"n_attempts": 3, "jobs_dir": "jobs/groq-ablation"},
    "harbor-groq-smoke.yml": {"n_attempts": 1, "jobs_dir": "jobs/groq-smoke"},
}
LLM_CONFIGS = tuple(EXPECTED)

# Hard caps this repository will not exceed on a 7,000 input-token-per-minute /
# 1,000 output-token-per-minute Free account. The completion cap is deliberately
# well under the output ceiling: the account reserves max_tokens on every request,
# so a cap near the ceiling lets only one request per minute through.
MAX_TURNS = 5
MAX_COMPLETION_TOKENS = 600
MAX_PANE_WIDTH = 120
MAX_PANE_HEIGHT = 24
# The timeout must cover the pacing this repository mandates: 75s per turn for the
# output-token window, so five turns is >=375s of waiting before model latency.
MAX_AGENT_TIMEOUT_SEC = 900
MAX_BASE_PROMPT_TOKENS = 2600

SECRET_PATTERNS = (
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{30,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
)


class ValidationError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def resolve_harbor_bin(explicit: str | None) -> list[str]:
    """Return the argv prefix that runs the Harbor CLI."""
    if explicit:
        return [explicit]
    found = shutil.which("harbor")
    if found:
        return [found]
    uv = shutil.which("uv")
    if uv:
        return [uv, "tool", "run", "--from", "harbor==0.26.0", "harbor"]
    fail(
        "Harbor CLI not found. Install Harbor 0.26.0 (uv tool install harbor==0.26.0) "
        "or pass --harbor-bin."
    )
    return []  # unreachable


def print_config(harbor: list[str], config: Path) -> dict:
    env = dict(os.environ)
    # --print-config resolves the schema only; it makes no network call. A
    # placeholder keeps credential preflight from demanding a real key.
    env.setdefault("GROQ_API_KEY", "validation-placeholder-not-a-real-key")
    proc = subprocess.run(
        [*harbor, "run", "--config", str(config), "--print-config"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
    if proc.returncode != 0:
        fail(
            f"{config.name}: Harbor rejected the config (exit {proc.returncode})\n"
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    text = proc.stdout.strip()
    start = text.find("{")
    if start == -1:
        fail(f"{config.name}: --print-config produced no JSON:\n{text[:400]}")
    try:
        return json.loads(text[start:])
    except json.JSONDecodeError as exc:
        fail(f"{config.name}: --print-config JSON is invalid: {exc}")


def check_secrets(config: Path) -> None:
    text = config.read_text(encoding="utf-8")
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            fail(f"{config.name}: looks like it contains a hardcoded credential")
    for line in text.splitlines():
        stripped = line.split("#", 1)[0]
        if "GROQ_API_KEY:" in stripped and "${GROQ_API_KEY}" not in stripped:
            fail(
                f"{config.name}: GROQ_API_KEY must only ever be a ${{GROQ_API_KEY}} "
                "template, never a literal value"
            )


def check_agent_config(config_name: str, payload: dict) -> dict:
    agents = payload.get("agents") or []
    if len(agents) != 1:
        fail(f"{config_name}: expected exactly one agent, found {len(agents)}")
    agent = agents[0]
    if agent.get("name") != "terminus-2":
        fail(f"{config_name}: agent must be terminus-2, found {agent.get('name')!r}")

    model = agent.get("model_name") or ""
    if model != REQUIRED_MODEL:
        fail(
            f"{config_name}: model must be {REQUIRED_MODEL!r} (verified free-tier "
            f"model), found {model!r}"
        )
    if not model.startswith("groq/"):
        fail(f"{config_name}: {model!r} is not a Groq model; paid providers are not allowed")
    if agent.get("model_api_key_name") != "GROQ_API_KEY":
        fail(f"{config_name}: model_api_key_name must be GROQ_API_KEY")
    if (agent.get("env") or {}).get("GROQ_API_KEY") != "${GROQ_API_KEY}":
        fail(f"{config_name}: GROQ_API_KEY must be passed as ${{GROQ_API_KEY}}")

    timeout = agent.get("override_timeout_sec")
    if timeout is not None and timeout > MAX_AGENT_TIMEOUT_SEC:
        fail(
            f"{config_name}: override_timeout_sec={timeout} exceeds "
            f"{MAX_AGENT_TIMEOUT_SEC}; a longer timeout cannot fix a token limit"
        )

    kwargs = agent.get("kwargs") or {}
    if kwargs.get("enable_summarize") is not False:
        fail(
            f"{config_name}: enable_summarize must be false - summarisation adds a "
            "full-conversation request at the largest point in the run"
        )
    if kwargs.get("proactive_summarization_threshold") not in (0, None):
        fail(f"{config_name}: proactive_summarization_threshold must be 0")
    max_turns = kwargs.get("max_turns")
    if not isinstance(max_turns, int) or max_turns > MAX_TURNS:
        fail(f"{config_name}: max_turns must be an int <= {MAX_TURNS}, found {max_turns!r}")

    width = kwargs.get("tmux_pane_width", 160)
    height = kwargs.get("tmux_pane_height", 40)
    if width > MAX_PANE_WIDTH or height > MAX_PANE_HEIGHT:
        fail(
            f"{config_name}: tmux pane {width}x{height} exceeds {MAX_PANE_WIDTH}x"
            f"{MAX_PANE_HEIGHT}; a larger pane re-sends more terminal text per turn"
        )

    call_kwargs = kwargs.get("llm_call_kwargs") or {}
    max_tokens = call_kwargs.get("max_tokens")
    if not isinstance(max_tokens, int) or max_tokens > MAX_COMPLETION_TOKENS:
        fail(
            f"{config_name}: llm_call_kwargs.max_tokens must be an int <= "
            f"{MAX_COMPLETION_TOKENS} to stay under the 1,000 output-token/min limit"
        )
    if call_kwargs.get("num_retries") not in (0,):
        fail(
            f"{config_name}: llm_call_kwargs.num_retries must be 0 - client-side "
            "replays of a hard rate limit only waste the daily budget"
        )

    if payload.get("n_concurrent_trials") != 1:
        fail(
            f"{config_name}: n_concurrent_trials must be 1; parallel trials exceed "
            "the per-minute input-token ceiling"
        )
    retry = payload.get("retry") or {}
    if retry.get("max_retries") not in (0, None):
        fail(f"{config_name}: retry.max_retries must be 0")

    return agent


def estimate_base_prompt_tokens() -> tuple[int | None, str]:
    """Estimate the fixed part of the first request (system template + task)."""
    try:
        import harbor  # type: ignore
    except ImportError:
        return None, "harbor not importable; prompt estimate skipped"
    template = (
        Path(harbor.__file__).parent
        / "agents"
        / "terminus_2"
        / "templates"
        / "terminus-json-plain.txt"
    )
    if not template.exists():
        return None, "terminus-2 template not found; prompt estimate skipped"
    parts = [template.read_text(encoding="utf-8")]
    instruction = ROOT / "tasks" / "reconcile-bug" / "instruction.baseline.md"
    if instruction.exists():
        parts.append(instruction.read_text(encoding="utf-8"))
    chars = sum(len(part) for part in parts)
    return int(chars / 3.6), f"system template + instruction = {chars} characters"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harbor-bin", default=None, help="Path to the harbor CLI")
    parser.add_argument(
        "--config",
        action="append",
        default=None,
        help="Validate only these config files (default: all in .github/configs)",
    )
    args = parser.parse_args()

    harbor = resolve_harbor_bin(args.harbor_bin)
    if args.config:
        configs = [Path(path).resolve() for path in args.config]
    else:
        configs = sorted(CONFIG_DIR.glob("*.yml"))
    if not configs:
        fail(f"no JobConfig files found in {CONFIG_DIR}")

    resolved: dict[str, dict] = {}
    agents: dict[str, dict] = {}

    for config in configs:
        if not config.exists():
            fail(f"missing config file: {config}")
        check_secrets(config)
        payload = print_config(harbor, config)
        resolved[config.name] = payload

        if "agents" in payload:
            agent = payload["agents"][0]
            if agent.get("name") in ("nop", "oracle"):
                print(f"  {config.name}: schema OK (calibration agent {agent['name']})")
                continue
        agents[config.name] = check_agent_config(config.name, payload)

        expected = EXPECTED.get(config.name)
        if expected:
            if payload.get("n_attempts") != expected["n_attempts"]:
                fail(
                    f"{config.name}: n_attempts must be {expected['n_attempts']}, "
                    f"found {payload.get('n_attempts')}"
                )
            jobs_dir = str(payload.get("jobs_dir") or "")
            if Path(jobs_dir).as_posix().rstrip("/") != expected["jobs_dir"]:
                fail(
                    f"{config.name}: jobs_dir must be {expected['jobs_dir']}, "
                    f"found {jobs_dir!r}"
                )
            task_paths = [t.get("path") for t in (payload.get("tasks") or [])]
            if task_paths != ["tasks/reconcile-bug"]:
                fail(f"{config.name}: tasks must be exactly tasks/reconcile-bug")
        print(f"  {config.name}: schema OK, policy OK")

    # The ablation must differ from the baseline only in the instruction file.
    if "harbor-groq-baseline.yml" in agents and "harbor-groq-ablation.yml" in agents:
        base = json.dumps(agents["harbor-groq-baseline.yml"], sort_keys=True)
        abl = json.dumps(agents["harbor-groq-ablation.yml"], sort_keys=True)
        if base != abl:
            fail("baseline and ablation agent configuration differ; only the instruction may")
        print("  baseline and ablation agents are identical apart from the instruction")

    if "harbor-groq-smoke.yml" in agents and "harbor-groq-baseline.yml" in agents:
        smoke = json.dumps(agents["harbor-groq-smoke.yml"], sort_keys=True)
        base = json.dumps(agents["harbor-groq-baseline.yml"], sort_keys=True)
        if smoke != base:
            fail("the smoke gate must use the same agent settings as the baseline arm")

    # Two configs sharing a directory is fine as long as they name different
    # jobs (Harbor writes jobs_dir/<job_name>/); sharing both would overwrite.
    pairs = [(str(p.get("jobs_dir")), str(p.get("job_name"))) for p in resolved.values()]
    duplicates = {pair for pair in pairs if pairs.count(pair) > 1}
    if duplicates:
        fail(f"configs must not share jobs_dir and job_name together: {sorted(duplicates)}")

    tokens, detail = estimate_base_prompt_tokens()
    if tokens is not None:
        print(f"  estimated fixed prompt per trial: ~{tokens} tokens ({detail})")
        if tokens > MAX_BASE_PROMPT_TOKENS:
            fail(
                f"estimated fixed prompt (~{tokens} tokens) leaves no room for turn "
                "growth under a 7,000 input-token/minute cap"
            )

    print(f"Validated {len(configs)} JobConfig file(s) against Harbor 0.26.0.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        print(f"::error::JobConfig validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
