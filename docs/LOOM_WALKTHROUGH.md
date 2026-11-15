# Five-minute Loom walkthrough script

Record one continuous, unedited screen capture with microphone audio. Keep your terminal, task files, hidden verifier file, and actual Harbor job folders ready before starting. This is a speaking/display guide; use your real run outputs.

## 0:00–1:45 — Reward mutation and anti-cheat proof

1. Show `tasks/reconcile-bug/solution/solve.sh` and identify the UTC normalization line.
2. Temporarily replace `return parsed.astimezone(dt.timezone.utc)` with `return parsed.replace(tzinfo=dt.timezone.utc)` in the embedded Python source. Explain: “The CLI and status rules are correct, but this treats local wall-clock time as UTC, so duplicate ordering can be wrong when records use different offsets.”
3. Run `harbor run -p ./tasks/reconcile-bug -a oracle`. State the predicted score: `0.50` (CLI `0.20` + status `0.30`; UTC deduplication `0.00`). Show the actual output.
4. Restore the correct line, run oracle again, and show `1.000`.
5. Open `solution/hack.sh`, explain that it returns the memorized summary `42.00 / 1 / 0` instead of reading the CSV. Swap it in as `solve.sh` using the four commands in `docs/SETUP_AND_SUBMISSION.md`; show the hardened verifier returns `0.000`. Restore the real solution immediately.

## 1:45–3:15 — Trajectory forensics

1. Open a real failed `trajectory.json` from Run 1.
2. Point to the exact command where the agent made the relevant mistake (for example, where it stopped after a shallow sample test, mishandled an invocation, or did not test timezone offsets). Read the actual command and explain why it missed the hidden rule.
3. Open `instruction.ablation.md` and explain the one controlled change: a concrete CLI invocation/output example. Compare the corresponding real Run 2 trajectory and score. Do not claim the ablation helped unless the observed trajectory supports it.

## 3:15–5:00 — Dense reward and RL reasoning

1. Show `tests/test.sh` and the `0.20 / 0.30 / 0.50` weights.
2. Show the README results table. Choose one real trial and calculate both its binary advantage and dense advantage using that run's group mean.
3. Explain the local-optimum risk: the two easier checks account for half the reward, so a model may stop before attempting the UTC edge case. Describe the proposed `0.15 / 0.25 / 0.60` reweighting as a possible follow-up, not a change already tested.
4. Explain one remaining adaptive-cheating risk and the need for isolated verifier permissions, hidden test inputs, and independent randomized cases.

## Final check

Keep the entire recording under five minutes, do not pause or cut, and set link visibility to “Anyone with the link can view”. Replace the placeholder video URL in the root README with the verified share link.
