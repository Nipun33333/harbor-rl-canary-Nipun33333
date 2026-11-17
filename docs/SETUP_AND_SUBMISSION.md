# Setup, Harbor runs, and submission (Windows + WSL2)

The internship instructions require Docker, Python 3.12/3.13, `uv`, Harbor, one model API key, six real model trials, exported coding-agent transcripts, and a Loom recording. This repository is configured to use the Groq Free plan only; do not enable pay-as-you-go billing or upgrade to the Developer plan. The coding task and verifier are prepared. You can run the six model trials either in WSL2 or with the included GitHub Actions workflow after adding the model API key as a repository secret.

## 1. Prepare Windows

1. Install Docker Desktop and enable its WSL2 backend.
2. Install Ubuntu 22.04 or newer in WSL2.
3. Open Ubuntu and confirm `docker info` works. If it fails, start Docker Desktop and enable integration for that Ubuntu distribution.
4. Install Git, `uv`, and Harbor in the Ubuntu shell:

```bash
sudo apt-get update
sudo apt-get install -y git curl
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
uv tool install harbor
uv tool update-shell
harbor --help
```

5. Install the official Harbor examples repository and run its built-in sanity tasks before spending model API calls:

```bash
git clone --depth 1 https://github.com/harbor-framework/harbor.git /tmp/harbor-examples
harbor run -p /tmp/harbor-examples/examples/tasks/hello-world -a nop
harbor run -p /tmp/harbor-examples/examples/tasks/hello-world -a oracle
```

Expected: `nop` should be zero and `oracle` should be one.

## 2. Put this project in WSL

Extract the downloaded ZIP somewhere inside the WSL Linux filesystem (for example, `~/work/harbor-rl-canary-submission`). Avoid running Docker bind mounts from a slow Windows-mounted directory if possible.

```bash
cd ~/work/harbor-rl-canary-submission
bash scripts/run_local_validation.sh
```

The local validation does not need Harbor or an API key. It should report starter `0.00`, full solution `1.00`, and cheat `0.00`.

## 3. Get a model API key

Create a Groq API key at https://console.groq.com/keys while remaining on the Free plan. Do not add a payment method, upgrade to Developer, or enable pay-as-you-go billing.

For Groq:

```bash
export GROQ_API_KEY="PASTE_YOUR_KEY_HERE"
```

The GitHub Actions workflow is configured only for `groq/qwen/qwen3.8-27b` using the Groq Free plan. No paid model or paid-provider fallback is configured.

Never paste the key into source code or commit it to GitHub. Do not add a `.env` file to this submission.

## 4. Run the baseline group (3 trials)

Before the first LLM trial, switch the active Harbor verifier to binary mode:

```bash
bash scripts/use_binary_verifier.sh
```

This keeps the dense verifier backup as `tests/test_dense.sh` and installs the binary wrapper as `tests/test.sh`. From the project root:

```bash
harbor run -p ./tasks/reconcile-bug \
  -a terminus-2 \
  --model groq/qwen/qwen3.8-27b \
  -k 3 -n 1
```


Always keep `-n 1` to run one container at a time. Save the resulting job folder. If all three baseline trials score `1.00` under the binary verifier required by the initial calibration step, follow the assignment's instruction to make the third bug harder and rerun before continuing. Do not silently change the task after observing the results; document the exact change.

## 5. Run the one-change ablation group (3 trials)

Keep the binary verifier active for this run as well. The planned ablation is a single instruction-only change: add an explicit CLI invocation/output example. After the baseline results are saved:

```bash
cp tasks/reconcile-bug/instruction.ablation.md tasks/reconcile-bug/instruction.md
harbor run -p ./tasks/reconcile-bug \
  -a terminus-2 \
  --model groq/qwen/qwen3.8-27b \
  -k 3 -n 1
```

Use the same model and concurrency as Run 1. The ablation can only be evaluated after comparing actual trajectories and result files. Restore the baseline version if you need to reproduce Run 1:

```bash
cp tasks/reconcile-bug/instruction.baseline.md tasks/reconcile-bug/instruction.md
```

## 6. Dense reward and anti-cheat checks

After both three-trial LLM runs are complete, restore the final dense verifier:

```bash
bash scripts/use_dense_verifier.sh
```

The final hardened dense verifier is now `tasks/reconcile-bug/tests/test.sh`. It gives each independent check weights `0.20`, `0.30`, and `0.50` and writes the result to `/logs/verifier/reward.txt`.

The cheat proof should be performed only after the full solution calibration:

```bash
cp tasks/reconcile-bug/solution/solve.sh /tmp/solve.sh.bak
cp tasks/reconcile-bug/solution/hack.sh tasks/reconcile-bug/solution/solve.sh
harbor run -p ./tasks/reconcile-bug -a oracle
mv /tmp/solve.sh.bak tasks/reconcile-bug/solution/solve.sh
```

The cheat run must score `0.000`. Then run oracle once more with the restored full solution and confirm `1.000`.

For the partial-credit Loom demonstration, make a temporary copy of `solution/solve.sh` and change this line inside its embedded Python source:

```python
return parsed.astimezone(dt.timezone.utc)
```

to:

```python
return parsed.replace(tzinfo=dt.timezone.utc)
```

This intentionally breaks UTC offset handling while leaving the CLI and status logic fixed, so the expected reward is `0.50`. Run oracle, show the score, restore the original `solve.sh`, and run oracle again to show `1.00`. Do not commit the mutated partial version.

## 7. Calculate advantages from actual results

After the six runs, copy the three reward values from each run's actual `result.json`. Use:

```bash
python scripts/calculate_advantages.py --baseline 0.0 0.0 0.0 --ablation 0.0 0.0 0.0
```

Replace the example zeros with the six actual dense rewards. For each run, also calculate the binary rewards (`1.0` only if all three checks pass, else `0.0`). Fill the README table using the helper output. Inspect at least one failed Run 1 trajectory and one Run 2 trajectory, and cite their exact command steps in the analysis.

## 8. Save job artifacts and transcripts

From the submission root, create the summary folder and copy actual files while preserving their folder names. Example:

```bash
mkdir -p jobs_summary ai_transcripts
find jobs -type f \( -name 'result.json' -o -name 'trajectory.json' \) -print0 \
  | tar --null -cf - --files-from - \
  | tar -xf - -C jobs_summary
```

Export the real session history using the export command for the AI coding tool actually used (Codex, Gemini CLI, Claude Code, Cursor, Windsurf, etc.). Put the exported file(s) in `ai_transcripts/`. Do not invent or handwrite a fake transcript.

## 9. Record the Loom walkthrough

Follow [`LOOM_WALKTHROUGH.md`](LOOM_WALKTHROUGH.md). The video must be one unedited recording under five minutes, with the microphone on. Verify the link works in an incognito browser before pasting it into the submission README.

## 10. GitHub Actions API secret and Harbor trials

Before manually starting the six-trial workflow, create one repository Actions secret in GitHub:

- Add only Groq `GROQ_API_KEY`. The workflow uses `groq/qwen/qwen3.8-27b` and checks model availability before any trial starts.

Open **Settings → Secrets and variables → Actions → New repository secret**. Never paste the key into chat, source files, or commits. The `Harbor LLM trials (FREE Groq model only)` workflow is manually dispatched after the secret is configured. It runs six `terminus-2` trials: three baseline and three ablation, sequentially. It uploads the real Harbor `jobs/` directory as a workflow artifact, including `result.json` and `trajectory.json`. The workflow can also be rerun from the Actions tab.

The separate `Local reward verifier` workflow runs on pushes and pull requests without an API key.

## 11. GitHub repository

The project is published to `https://github.com/Nipun33333/harbor-rl-canary-Nipun33333`. The repository is configured to preserve the source tree and workflows. Submit that GitHub URL in the Internshala chat before the deadline.
