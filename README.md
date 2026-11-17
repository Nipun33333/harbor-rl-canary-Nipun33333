# Harbor RL Submission — Nipun Agarwal (@Nipun33333)

> **2026-11-17 safety/evidence update:** The full experiment remains incomplete.
> The workflow now requires a fresh (under one hour old) Groq dashboard usage
> observation and at least 160,000 declared remaining tokens before it makes
> any network request. This is an admission check, not proof of future quota.
> No oversized identity/day probes are used; the legacy `org` and `daily` CLI
> commands now refuse to run. Historical statements below that call oversized
> probes free, reliable, or a live daily quota measurement are not valid.
> A tiny successful completion proves neither daily headroom nor Free billing status.
>
> The verifier now saves `verifier/candidate.py` alongside `details.json`.
> Binary grading is derived from the same independent checks whose dense score
> is retained in `details.json`; `scripts/experiment_report.py` checks consistency
> and calculates both group-centered advantages without executing candidate code
> on the host. The report refuses missing snapshots, trajectories or exceptional
> trials. Original result files are not rewritten. Existing historical jobs
> without snapshots cannot be retroactively represented as fully captured runs.
>
> The CLI-example ablation remains a proposal, not a measured improvement. The
> latest observed tuple-unpacking failure does not establish that CLI clarification
> addresses it. Revisit the single-change hypothesis after an exception-free
> baseline, before spending tokens on an ablation. A 3/3 passing baseline stops
> the workflow for recalibration. Genuine coding transcripts and the applicant's
> own unedited narrated video remain outstanding; do not substitute benchmark
> trajectories for the task-authoring transcript.

> **Submission state:** The Harbor task, reference solution, dense verifier and anti-cheat canary are implemented. Local verifier checks are included. The six `terminus-2` trials and their trajectory analysis are intended to run through the included GitHub Actions workflow after an API key is added as a repository secret; the Loom recording is still to be produced by the applicant. No trial result or video link has been invented.

## 1. Loom Walkthrough Video

- **Video URL:** `ADD_YOUR_LOOM_OR_UNLISTED_YOUTUBE_LINK`
- Set sharing to **Anyone with the link can view**.
- Follow [`docs/LOOM_WALKTHROUGH.md`](docs/LOOM_WALKTHROUGH.md) for a timed, under-five-minute walkthrough.

## 2. Task & Calibration Summary

- **Bug 1 (Easy):** The documented CLI accepts one input CSV path and prints JSON, but the starter program incorrectly requires a second output-file argument.
- **Bug 2 (Medium):** The starter program incorrectly includes `PENDING` transactions in the valid amount and valid count.
- **Bug 3 (Hard):** The starter program drops timezone offsets before comparing duplicate timestamps, so it can select an earlier UTC transaction over a later one.
- **Dense reward weights:** Bug 1 / CLI = `0.20`; Bug 2 / status accounting = `0.30`; Bug 3 / UTC deduplication = `0.50`.
- **Expected calibration:** `nop` = `0.00`; `oracle` with `solve.sh` = `1.00`; partial oracle after fixing Bugs 1 and 2 but intentionally breaking UTC normalization = `0.50`; `hack.sh` against the hardened verifier = `0.00`.

The binary calibration verifier is all-or-nothing: a trial receives `1.00` only when all three business-rule checks pass, otherwise `0.00`. The final verifier upgrades this to the dense weights above.

## 3. Ablation & RL Advantage Table (`terminus-2`, `k=3`)

**Fill this table only from clean, real Harbor jobs.** Harbor 0.26.0 Docker smoke tests have passed: `nop` scored `0.00` and `oracle` scored `1.00`.  Legacy run #4 was a diagnostic pilot: baseline rewards were `0.00`, `0.00`, and `1.00` (mean `0.333`), but all three ended with `AgentTimeoutError` and the ablation group was skipped. Those pilot values are documented below but are not entered as final comparison data. The failures came from Groq Free input-token-per-minute and tokens-per-day limits, not an invalid API key.

**Latest diagnostic attempt (GitHub Actions run #18; still not a valid final experiment):** the baseline report recorded `1.00, 1.00, 0.00`, but trial `reconcile-bug__42NsA2t` also ended with a Groq daily-token `RateLimitError` (200,000 limit; 196,020 used; 5,754 requested). The workflow therefore rejected the baseline group and skipped ablation. The two exception-free trials were `reconcile-bug__dwFyLaa` (`1.00`) and `reconcile-bug__pWb5A3f` (`0.00`). Do not use the apparent `[1, 1, 0]` mean as final experiment data. The real logs are available in [GitHub Actions run #18](https://github.com/Nipun33333/harbor-rl-canary-Nipun33333/actions/runs/43958484922); see [the diagnostic note](jobs_summary/diagnostic-run-2026-11-16.md).

| Run | Change tested | Trial 1 (Binary / Dense) | Trial 2 (Binary / Dense) | Trial 3 (Binary / Dense) | Mean Binary | Mean Dense | Binary advantages (T1, T2, T3) | Dense advantages (T1, T2, T3) |
| :-- | :-- | :-- | :-- | :-- | --: | --: | :-- | :-- |
| Run 1: Baseline | Base task + shared execution guidance | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |
| Run 2: Ablation | Baseline + one explicit CLI invocation/output example | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |

For each run and each reward type, calculate:

`group_mean = (reward_1 + reward_2 + reward_3) / 3`

`advantage_i = reward_i - group_mean`

A small offline helper is provided at `scripts/calculate_advantages.py`. It calculates means and advantages from six reward values copied from the real `result.json` files; it does not create trial results.

## 4. Trajectory Forensics (`trajectory.json`)

- **Latest diagnostic Run 1 failure:** In trial `reconcile-bug__pWb5A3f`, the agent ran `python3 -m py_compile /app/reconcile.py` successfully, then ran `python3 /app/reconcile.py /tmp/t.csv`. The program crashed with `ValueError: too many values to unpack (expected 2)`: the implementation stored more than two fields per value in `latest`, but later unpacked each value into only two variables. This is visible in the real `agent/trajectory.json` inside the run #18 artifact.
- **Ablation status:** The one intended ablation is an explicit CLI invocation/output example in the instructions. It was **not run** in run #18 because baseline validation failed on the TPD exception. There is no Run 2 trajectory or measured ablation effect yet.

- **Legacy run #4 failure:** Qwen3.8-27B split `/app/reconcile.py` into multiple append operations, re-read the full file, and ran extra checks. This grew the conversation until requests exceeded Groq Free ITPM/TPD limits. All three trials ended with `AgentTimeoutError` after 300 seconds; one had a correct implementation and binary reward `1.00` but still timed out. The new baseline and ablation both use the same execution-efficiency guidance so the single ablation example remains the only treatment difference.
- **Ablation hypothesis:** The added CLI example should reduce invocation/interface mistakes. Compare actual Run 1 and Run 2 trajectories to see whether the agent first discovers the intended one-argument CLI and whether that change affects its later tests. Do not claim an improvement unless the logs show it.
- **Run 2 result:** PENDING. Run #4 failed before the ablation group started.

## 5. Dense Reward & Anti-Cheat Design

### Weights

| Check | What it verifies | Weight |
| :-- | :-- | --: |
| 1 | One-argument CLI and correct single valid transaction output | 0.20 |
| 2 | Correct `VALID` / `FAILED` / `PENDING` accounting on unique transaction IDs | 0.30 |
| 3 | Latest duplicate transaction chosen by UTC instant, despite conflicting wall-clock order | 0.50 |
| **Total** |  | **1.00** |

The hidden verifier creates fresh transaction IDs and random amounts each time it runs. It executes each check independently and writes the weighted sum to `/logs/verifier/reward.txt` with two decimal places.

### Cheat attempt and defense

`solution/hack.sh` replaces the program with a stub that always returns a memorized summary (`42.00`, one valid row, zero failed rows). That can fool a naive verifier that repeatedly uses one public fixture. It fails here because the verifier generates new IDs and amounts at runtime and checks the exact output for three independent datasets.

### Remaining reward-hacking risk

A more adaptive agent could make its program detect characteristics of the verifier invocation or attempt to tamper with verifier-side files rather than solve reconciliation. In a production evaluation, run the candidate in a least-privilege container, keep verifier assets inaccessible and read-only, execute checks in a separate process, overwrite the reward only after all checks finish, and vary hidden datasets/seeds across trials.

## 6. RL Reasoning Questions

1. **Why dense advantages provide a learning signal:** With binary scoring, three incomplete attempts can all receive `0.00`; their group mean is `0.00`, so all three advantages are zero. With dense scoring, an attempt that fixes only the CLI and status logic receives `0.50`, while an attempt that fixes only the CLI receives `0.20`. Those partial outcomes can be compared against the group mean, reinforcing the more useful sequence of actions and penalizing weaker attempts.

   *Illustrative calculation only, not measured job data:* binary rewards `[0, 0, 0]` have mean `0.00` and advantages `[0, 0, 0]`. Dense rewards `[0.50, 0.20, 0.00]` have mean `0.2333`, giving approximate advantages `[+0.2667, -0.0333, -0.2333]`.

2. **Could the policy settle for easy points?** Yes. The first two checks currently offer `0.50` combined, so a model may learn to stop before attempting the edge case if Bug 3 is costly or risky. If observed over many runs, shift more weight to the hard check (for example `0.15 / 0.25 / 0.60`) and consider a verifier design that rewards incremental progress on multiple independent UTC-deduplication cases rather than a single brittle test. Compare learning stability before adopting new weights.

3. **One remaining cheat:** An adaptive program could attempt to identify the verifier process or modify its reward artifact. Defenses include an isolated verifier process, read-only hidden tests, minimal filesystem permissions, independent random fixtures, and writing the reward only after verifier completion.

## 7. AI Tool Workflow

- **AI coding tool and model:** Harbor `terminus-2` with Groq-hosted `qwen/qwen3.8-27b` using the Groq Free plan. The current configuration limits the agent to five turns, caps each completion at 700 tokens, sets a 900-second agent timeout, disables context summarisation, shrinks the terminal pane to 100×20 so far less terminal text is re-sent with every turn, and states the one-minute pacing the free tier requires in the shared execution guidance of both arms. See section 11 for why each of those numbers is what it is.
- **Transcript export:** Add the authentic exported chat/session file(s) to `ai_transcripts/`. Do not put API keys, `.env` files, or credentials in this repository.
- **Prompt leakage:** Keep the task instruction focused on the public interface and business rules; do not include implementation details, bug line numbers, verifier weights, or hidden test construction in the agent-facing instruction. This submission keeps the task instruction separate from the hidden verifier file.

## 8. GitHub Actions

> Provider note: this submission uses **Groq** (spelled with a `q`), not **Grok** from xAI. The selected model is `qwen/qwen3.8-27b` through Groq's Free plan. No paid model or fallback is configured. Keep the account on the Free plan. Its model-specific input/output and daily token limits still apply.


- `Local reward verifier` runs the four local calibration / anti-cheat states on pushes and pull requests. The separate Harbor Docker smoke jobs run `nop` and `oracle`; the latest GitHub Actions run passed both, with reward means `0.00` and `1.00` respectively.
- `Harbor LLM trials (FREE Groq model only)` is manually dispatched after adding `GROQ_API_KEY` as a repository Actions secret. It never asks for a key change and never prints the secret. Its order is deliberate and each step is a gate:

  1. validate every JobConfig against the installed Harbor 0.26.0 schema and against the Free-tier policy (`scripts/validate_job_configs.py`);
  2. confirm `qwen/qwen3.8-27b` is listed for this key (no inference);
  3. read the live rate-limit headers with one 1-token request (`scripts/groq_preflight.py probe`) — a 429 stops the run here with Groq's own numbers;
  4. run the `oracle` Docker smoke (no LLM tokens) to prove the environment and verifier work;
  5. run **one** genuine `terminus-2` trial and require it to be exception-free with evidence in `trajectory.json` that the agent wrote the file and executed it (`scripts/verify_trial_group.py --require-workspace-edit --require-test-command`);
  6. project the cost of the remaining trials from what that one trial actually consumed and stop if it does not fit the day's budget (`scripts/groq_preflight.py budget`);
  7. only then run the baseline group, validate it, cool down, run the ablation group, validate it.

  A group is green only when it holds the required number of trials, every trial finished with zero exceptions, `result.json` parses, and `trajectory.json` exists. Rewards are never adjusted and a failing trial is never replayed. Artifacts upload even when the run fails, and the job exits non-zero when any arm is incomplete or contains an exception.
- Groq Free limits are the binding constraint, not the settings: see section 11.

## 9. Local Validation

The supplied local script validates four cases without Docker or model API calls:

1. Starter implementation fails (`0.00`).
2. `solve.sh` passes (`1.00`).
3. A temporary UTC-normalization mutation earns the expected partial score (`0.50`).
4. `hack.sh` fails the randomized hardened verifier (`0.00`).

For the initial six LLM trials, switch to binary scoring with `bash scripts/use_binary_verifier.sh`. Restore the dense verifier with `bash scripts/use_dense_verifier.sh` after the three baseline and three ablation trials.

From the project root in a Bash shell:

```bash
bash scripts/run_local_validation.sh
```

## 10. Harbor Runs and GitHub Submission

Follow [`docs/SETUP_AND_SUBMISSION.md`](docs/SETUP_AND_SUBMISSION.md). Run all six model trials with `-n 1`, save the real `result.json` and `trajectory.json` files, export the authentic AI coding-tool transcript, update the table above, record the Loom video, and then push the clean folder.

Do not commit `jobs/`, `.venv/`, `.env`, API keys, or Docker images.

## 11. Groq Free-tier diagnosis and remediation

The earlier attempts failed on quota, not on task design and not on Harbor configuration keys. Every JobConfig key in this repository validates against the installed Harbor 0.26.0 schema (`harbor run --print-config`), so no option was being silently ignored.

### What the Free plan actually allows

Groq's published Free-plan table (and `/openai/v1/models` for this key) gives:

| Model | RPM | TPM | TPD |
| :-- | --: | --: | --: |
| `qwen/qwen3.8-27b` | 30 | 8K | 200K |
| `openai/gpt-oss-120b` | 30 | 8K | 200K |
| `openai/gpt-oss-20b` | 30 | 8K | 200K |
| `openai/gpt-oss-safeguard-20b` | 3 | 2K | 200K |

Every free text model shares an 8K TPM / 200K TPD ceiling, and this account's 8K TPM is split into **7,000 input + 1,000 output tokens per minute**. Switching model therefore cannot buy quota — which is why the `gpt-oss-20b → qwen3.8-27b` switch did not help. `terminus-2` on `qwen/qwen3.8-27b` remains the right choice because it is the model without the `tool_use_failed` failure mode described below.

### Root causes

1. **The conversation, not the setting, grew past 7,000 input tokens.** `terminus-2` re-sends the entire conversation on every turn. Turn one is only ~1,500 tokens (730-token system template, ~480-token instruction plus the initial screen), but each turn appends the model's own JSON reply *and* the terminal output. With Harbor's default 160×40 pane, a screen fallback alone can attach ~6,400 characters (~1,600 tokens). By turn three the prompt was 7,122 tokens — a request no retry can make legal.
2. **The daily budget was already spent.** 200K TPD and roughly 15–20K tokens per 5–6 turn trial means six trials need ~100–130K. The failing runs started with ~194K already consumed, so every later request hit TPD regardless of size.
3. **Retries amplified the damage.** Harbor's LiteLLM wrapper retries any exception three times with 4–15 s exponential backoff, and the config also set `num_retries: 3`, so a hard limit was attempted up to nine times. The server's `retry-after`, `x-ratelimit-remaining-tokens` and `x-ratelimit-reset-tokens` headers were never consulted.
4. **`AgentTimeoutError` was a symptom.** The trials were not slow for lack of wall-clock time; they were spending it in backoff. Raising the timeout from 300 s to 900 s multiplied the wasted attempts. Two `0.0` rewards plus one `1.0` with a mean of `0.333` is what "one trial happened to finish before backoff" looks like, not a benchmark result.
5. **`Tool choice is none, but model called a tool` is a Groq-side rejection.** It is Groq's `tool_use_failed` 400: the model emitted a tool-call block while the request declared no tools. Harbor 0.26.0's `terminus-2` never sends tool definitions at all — it parses JSON keystrokes from plain text (its own source says so), and the package contains no `tool_choice` handling. Nothing in the JobConfig can enable or disable native tool calling for this agent; the model itself has to be one that does not self-invoke tools. `gpt-oss` variants on Groq are known for it; `qwen3.8-27b` is not.

### What the fix changes, and why that is the right lever

- `max_tokens: 700`: the account reserves `max_tokens` on every request against its 1,000-token-per-minute output allowance, so the cap decides how many requests can share a minute. 800 was tried and truncated the model's file write mid-response; 600 fit but split the write into three chunks that were then re-sent every turn. 700 holds a compact rewrite in one response and, with the harness allowing one request per 75 s, never crosses the per-minute allowance.
- `tmux_pane_width: 100` / `tmux_pane_height: 20` (was the 160×40 default) cuts the largest possible per-turn terminal attachment by roughly two thirds.
- `max_turns: 5` (was 6): measured, not assumed. A trial's cost is the conversation it re-sends, so the turn count *is* the cost: six turns cost 24,777 input tokens, five cost 19,517. Four was tried and is too few — the smoke read the program, spent a turn on an inspection command, wrote the file, and ended before verifying it (reward 0.0). Five covers read, write, verify and one repair, at about 20K tokens per trial.
- `max_tokens: 700` (was 600): 600 forced the model to write the ~800-token program in three chunks, and every chunk was re-sent on each later turn — the single biggest multiplier in the 26,652-token trial. 700 lets a compact rewrite fit in one command and still stays under the 1,000-token-per-minute output allowance, since the harness allows only one request per 75 s.
- `enable_summarize: false` and `proactive_summarization_threshold: 0`: summarisation issues an extra whole-conversation request — the most expensive possible call — exactly when the context is largest.
- `num_retries: 0` and `retry.max_retries: 0`: a hard limit is not a transient error, so nothing is replayed.
- `n_concurrent_trials: 1` plus explicit cooldowns between the arms: parallel or back-to-back trials multiply per-minute demand and guarantee 429s.
- Pacing between model calls is enforced by the harness, not requested politely. `terminus-2` has no inter-turn delay, and telling the agent to wait does not work: the same instruction produced `duration: 60.0` in one trial and `duration: 0.5` in the next. `scripts/paced_harbor.py` wraps the CLI and guarantees 75 seconds between the end of one model call and the start of the next, which is what keeps two ~5K-token prompts out of the same rolling minute. It is a real wait, identical for both arms, and invisible to the task.
- `override_timeout_sec: 900`: arithmetic, not optimism. The harness enforces 75 s between model calls to stay inside the 8,000-token-per-minute window, so five turns need 375 s of pure waiting before any model latency; at 420 s a trial that had already earned reward `1.0` was killed by its own pacing.
- The daily figure is declared, not fetched, because Groq does not expose it. There is no usage endpoint on the Free plan, the per-minute headers carry no day total, and the day's `Used` appears only inside a 429 `tokens per day` body — which can only be provoked when the *minute* still has room and the *day* does not. An oversized probe on a healthy account is rejected earlier, at the edge (HTTP 413) or by the per-minute limit, so it reads nothing. The budget gate therefore takes `GROQ_TPD_ALREADY_USED` (a repository variable) as the tokens this organisation already spent today outside the current run, adds the tokens this run's own trials consumed, and compares the measured cost of one real trial — not an estimate — against what is left. The probe is still kept as a cheap early stop for the one case it can detect: a day that is genuinely nearly spent.

Artifact totals also *under*-state the day. On 2026-11-16 the six dispatches of that day summed to 133,738 tokens across every `result.json` and `trajectory.json`, while Groq's own TPD rejection read `Used 196407` — a trial killed by a timeout or a rate limit never records the tokens it had already spent, and the gap was ~63K. So the projection is an admission check, not a measurement: it decides whether starting is defensible, and a `tokens per day` rejection inside an arm is the authoritative figure. The workflow treats that rejection as a hard stop and never replays the trial.

Measured on real trials: turn one costs ~1,330 input tokens; each later turn adds the previous command plus whatever the agent wrote, so a trial that patches in place costs far less than one that rewrites the file (24,777 input tokens for a rewrite trial, for a task whose reference solution is ~800 tokens of code).

Confirmed by a real trial on a fresh Free organisation: one genuine `terminus-2` trial scored reward `1.0` with zero exceptions, seven terminal commands, and a largest single request of 6,049 tokens — under both the 7,000 input and 8,000 total per-minute ceilings, with the harness pacing in force.
