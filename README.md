# Harbor RL Submission — Nipun Agarwal (@Nipun33333)

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

**Fill this table only from real Harbor jobs.** Harbor 0.26.0 Docker smoke tests have passed: `nop` scored `0.00` and `oracle` scored `1.00`. Run #4 completed the three baseline evaluations but all three ended with `AgentTimeoutError`; their binary verifier rewards were `0.00`, `0.00`, and `1.00` (mean `0.333`). The ablation group was skipped. No clean six-trial comparison is available yet. The failures came from Groq Free input-token-per-minute and tokens-per-day limits, not an invalid API key.

| Run | Change tested | Trial 1 (Binary / Dense) | Trial 2 (Binary / Dense) | Trial 3 (Binary / Dense) | Mean Binary | Mean Dense | Binary advantages (T1, T2, T3) | Dense advantages (T1, T2, T3) |
| :-- | :-- | :-- | :-- | :-- | --: | --: | :-- | :-- |
| Run 1: Baseline (run #4; timed out) | Original instruction | `0.00 / PENDING` | `0.00 / PENDING` | `1.00 / PENDING` | `0.333` | PENDING | `-0.333, -0.333, +0.667` | PENDING |
| Run 2: Ablation | Add one explicit CLI invocation/output example to `instruction.md` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |

For each run and each reward type, calculate:

`group_mean = (reward_1 + reward_2 + reward_3) / 3`

`advantage_i = reward_i - group_mean`

A small offline helper is provided at `scripts/calculate_advantages.py`. It calculates means and advantages from six reward values copied from the real `result.json` files; it does not create trial results.

## 4. Trajectory Forensics (`trajectory.json`)

- **Run 1 failure (run #4):** Qwen3.8-27B repeatedly split `/app/reconcile.py` into multiple append operations, then re-read the full file and performed additional checks. This grew the conversation until requests exceeded Groq Free ITPM/TPD limits; each trial ended with `AgentTimeoutError` after 300 seconds. The third trial had a correct implementation and a binary verifier reward of `1.00`, but still timed out.
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

- **AI coding tool and model:** Harbor `terminus-2` with Groq-hosted `qwen/qwen3.8-27b` using the Groq Free plan. Current configuration uses `qwen/qwen3.8-27b`, limits the agent to six turns, caps each completion at 512 tokens, sets a 900-second agent timeout, and reduces unnecessary full-file terminal output.
- **Transcript export:** Add the authentic exported chat/session file(s) to `ai_transcripts/`. Do not put API keys, `.env` files, or credentials in this repository.
- **Prompt leakage:** Keep the task instruction focused on the public interface and business rules; do not include implementation details, bug line numbers, verifier weights, or hidden test construction in the agent-facing instruction. This submission keeps the task instruction separate from the hidden verifier file.

## 8. GitHub Actions

> Provider note: this submission uses **Groq** (spelled with a `q`), not **Grok** from xAI. The selected model is `qwen/qwen3.8-27b` through Groq's Free plan. No paid model or fallback is configured. Keep the account on the Free plan. Its model-specific input/output and daily token limits still apply.


- `Local reward verifier` runs the four local calibration / anti-cheat states on pushes and pull requests. The separate Harbor Docker smoke jobs run `nop` and `oracle`; the latest GitHub Actions run passed both, with reward means `0.00` and `1.00` respectively.
- `Harbor LLM trials (FREE Groq model only)` is manually dispatched after adding `GROQ_API_KEY` as a repository Actions secret. It checks that `qwen/qwen3.8-27b` is listed for the key, then runs three baseline and three ablation `terminus-2` trials sequentially. The model-list check does not make an inference request. The workflow uploads actual `result.json` and `trajectory.json` files and fails the job when a group has exceptions. Groq Free rate limits apply; do not upgrade to the paid Developer tier.

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
