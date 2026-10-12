"""Cross-platform CLI for baseline, PPO training, evaluation and comparison."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .experiments import (
    compare_paired,
    evaluate_sb3,
    new_experiment_dir,
    run_random_baseline,
    train_sb3_ppo,
)


def _rewards(path):
    if path is None:
        return None
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("reward coefficients must be a JSON object")
    return {str(k): float(v) for k, v in value.items()}


def build_parser():
    parser = argparse.ArgumentParser(prog="flyswarm-marl", description="Reproducible FlySwarm MARL experiments")
    parser.add_argument("--output-root", type=Path, default=Path("results/raw/marl"))
    parser.add_argument("--experiment-dir", type=Path, help="Use this new, non-existing directory")
    parser.add_argument("--reward-coefficients", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)

    baseline = sub.add_parser("baseline", help="Run uniform random policy episodes")
    baseline.add_argument("--episodes", type=int, default=3)
    baseline.add_argument("--seed", type=int, default=101)
    baseline.add_argument("--max-steps", type=int, default=600)

    train = sub.add_parser("train", help="Train Stable-Baselines3 PPO")
    train.add_argument("--steps", type=int, default=10000)
    train.add_argument("--seed", type=int, default=7)
    train.add_argument("--max-steps", type=int, default=600)
    train.add_argument("--learning-rate", type=float, default=3e-4)

    evaluate = sub.add_parser("evaluate", help="Evaluate a saved PPO checkpoint on fresh seeds")
    evaluate.add_argument("checkpoint", type=Path)
    evaluate.add_argument("--episodes", type=int, default=5)
    evaluate.add_argument("--seed", type=int, default=1001)
    evaluate.add_argument("--max-steps", type=int, default=600)

    compare = sub.add_parser("compare", help="Paired Random vs PPO test-seed evaluation")
    compare.add_argument("checkpoint", type=Path)
    compare.add_argument("--episodes", type=int, default=5)
    compare.add_argument("--seed", type=int, default=1001)
    compare.add_argument("--max-steps", type=int, default=600)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    rewards = _rewards(args.reward_coefficients)
    root = args.output_root
    make_output = lambda label: args.experiment_dir or new_experiment_dir(root, label)
    if args.command == "baseline":
        out = make_output(f"random-seed-{args.seed}")
    elif args.command == "train":
        out = make_output(f"ppo-training-seed-{args.seed}")
    elif args.command == "evaluate":
        out = make_output("ppo-evaluation")
    else:
        out = make_output("random-vs-ppo-paired")
    try:
        if args.command == "baseline":
            result = run_random_baseline(out, args.episodes, args.seed, args.max_steps, rewards)
        elif args.command == "train":
            result = train_sb3_ppo(out, args.steps, args.seed, args.max_steps,
                                   args.learning_rate, out / "progress.json", rewards)
        elif args.command == "evaluate":
            result = evaluate_sb3(args.checkpoint, out, args.episodes, args.seed,
                                  args.max_steps, reward_coefficients=rewards)
        else:
            result = compare_paired(args.checkpoint, out, args.episodes, args.seed,
                                    args.max_steps, rewards)
    except Exception as exc:
        out.mkdir(parents=True, exist_ok=True)
        (out / "progress.json").write_text(json.dumps({"state":"error","message":str(exc)},indent=2)+"\n",encoding="utf-8")
        raise
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError) as exc:
        print(f"flyswarm-marl: {exc}", file=sys.stderr)
        raise SystemExit(2)
