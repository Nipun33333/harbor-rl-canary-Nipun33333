# Diagnostic Baseline Attempt — 16/17 November 2026

**Status: NOT ACCEPTED as the final baseline group.** This is a transparent record of the incomplete diagnostic run, not a replacement for the required six clean trials.

- Workflow: [Harbor LLM trials (Groq Free only), run #18](https://github.com/Nipun33333/harbor-rl-canary-Nipun33333/actions/runs/43958484922)
- Full Harbor artifact: download the ZIP from the run page. It includes the actual `result.json` and `agent/trajectory.json` files.
- Planned experiment: 3 baseline trials followed by 3 ablation trials.
- Actual outcome: baseline validation failed; the ablation job was skipped.

## Baseline observations

| Trial | Binary reward recorded | Exception status | Acceptance |
|---|---:|---|---|
| `reconcile-bug__dwFyLaa` | 1.00 | No exception | Individual trial usable for forensic review |
| `reconcile-bug__pWb5A3f` | 0.00 | No exception | Individual trial usable for forensic review |
| `reconcile-bug__42NsA2t` | 1.00 | Groq `RateLimitError` (TPD) | Invalid under the zero-exception rule |

The rejected trial's error reported a 200,000-token daily limit, 196,020 tokens already used, and 5,754 requested. Because the trial ended with an exception, its recorded reward must not be treated as a valid benchmark result.

## Trajectory forensics

In `reconcile-bug__pWb5A3f/agent/trajectory.json`, the model successfully ran:

```bash
python3 -m py_compile /app/reconcile.py
```

It then ran:

```bash
python3 /app/reconcile.py /tmp/t.csv
```

The program raised:

```text
ValueError: too many values to unpack (expected 2)
```

The generated implementation stored a tuple with more than two fields in the `latest` mapping, then attempted to unpack each stored value into only two variables. This is a concrete example of why syntax compilation alone does not prove runtime correctness.

## Experiment boundary

- Do not enter `[1.00, 1.00, 0.00]` as a valid final Baseline group.
- Do not calculate or report final Baseline advantages from this incomplete group.
- The Ablation arm did not start, so there are no Run 2 rewards or trajectories and no measured ablation effect.
- Run a fresh, exception-free Baseline and Ablation experiment, then copy the six real result and trajectory files into `jobs_summary/`.
