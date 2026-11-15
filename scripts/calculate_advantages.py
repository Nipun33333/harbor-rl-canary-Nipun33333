#!/usr/bin/env python3
"""Calculate group means and per-trial advantages from real Harbor rewards."""

import argparse


def summarize(label, rewards):
    mean = sum(rewards) / len(rewards)
    advantages = [value - mean for value in rewards]
    print(f"{label}:")
    print("  rewards:    " + ", ".join(f"{value:.2f}" for value in rewards))
    print(f"  group mean: {mean:.4f}")
    print("  advantages:" + ", ".join(f" {value:+.4f}" for value in advantages))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", nargs=3, type=float, required=True, metavar=("T1", "T2", "T3"))
    parser.add_argument("--ablation", nargs=3, type=float, required=True, metavar=("T1", "T2", "T3"))
    args = parser.parse_args()
    for name, values in (("Baseline", args.baseline), ("Ablation", args.ablation)):
        if any(value < 0 or value > 1 for value in values):
            parser.error("all rewards must be between 0.0 and 1.0")
        summarize(name, values)


if __name__ == "__main__":
    main()
