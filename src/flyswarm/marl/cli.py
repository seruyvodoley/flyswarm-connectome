"""Cross-platform CLI for baseline, PPO training, evaluation and comparison."""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import json
import signal
import sys
from pathlib import Path

from .experiments import (
    compare_paired,
    compare_all_policies,
    evaluate_sb3,
    new_experiment_dir,
    run_random_baseline,
    run_student_agent,
    train_sb3_ppo,
)
from .student_code import ManagedStudentAgent, load_reward
from .exporter import export_practical

_ACTIVE_OUTPUT: Path | None = None


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
    train.add_argument("--reward-file", type=Path, help="Student calculate_reward(components) Python file")

    student = sub.add_parser("student", help="Run a student-defined Python policy")
    student.add_argument("--agent-file", type=Path, required=True)
    student.add_argument("--reward-file", type=Path)
    student.add_argument("--episodes", type=int, default=3)
    student.add_argument("--seed", type=int, default=101)
    student.add_argument("--max-steps", type=int, default=600)

    check = sub.add_parser("check", help="Validate student agent/reward files")
    check.add_argument("--agent-file", type=Path, required=True)
    check.add_argument("--reward-file", type=Path)

    export = sub.add_parser("export", help="Export student code and saved experiment results to ZIP")
    export.add_argument("--workspace", type=Path, required=True)
    export.add_argument("--sessions-root", type=Path, required=True)

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
    compare_all = sub.add_parser("compare-all", help="Compare Random, student strategy, standard PPO and custom-reward PPO")
    compare_all.add_argument("--agent-file", type=Path, required=True)
    compare_all.add_argument("--standard-checkpoint", type=Path, required=True)
    compare_all.add_argument("--custom-reward-checkpoint", type=Path, required=True)
    compare_all.add_argument("--episodes", type=int, default=5)
    compare_all.add_argument("--seed", type=int, default=1001)
    compare_all.add_argument("--max-steps", type=int, default=600)
    return parser


def main(argv=None):
    global _ACTIVE_OUTPUT
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
    elif args.command == "check":
        out = make_output("student-code-check")
    elif args.command == "compare-all":
        out = make_output("four-policy-comparison")
    elif args.command == "export":
        out = make_output("practical-export")
    else:
        out = make_output("random-vs-ppo-paired")
    if out.exists():
        raise FileExistsError(f"Experiment output already exists; refusing to overwrite: {out}")
    _ACTIVE_OUTPUT = out
    try:
        if args.command == "check":
            import numpy as np
            out.mkdir(parents=True,exist_ok=True)
            with (out/"execution.log").open("a",encoding="utf-8",buffering=1) as console, redirect_stdout(console), redirect_stderr(console):
                observation=np.zeros(30,dtype=np.float32)
                context={"agent_id":"blue_0","team":"blue","episode_seed":1,"episode_step":0,"team_index":0}
                with ManagedStudentAgent(args.agent_file) as agent:
                    action=agent.act_team([observation],[context])[0]
                reward=load_reward(args.reward_file) if args.reward_file else None
                reward_value=reward({"objective_capture":1.0,"damage_dealt":0.0,"own_death":0.0,
                                     "objective_progress":0.0,"objective_neutralization":0.0,"enemy_kill":0.0,
                                     "ticket_delta":0.0,"battle_win":0.0,"battle_loss":0.0,"role_shaping":0.0}) if reward else None
                (out/"manifest.json").write_text(json.dumps({"kind":"student_code_check","agent_file":str(args.agent_file),
                    "reward_file":str(args.reward_file) if args.reward_file else None},indent=2)+"\n",encoding="utf-8")
                (out/"progress.json").write_text(json.dumps({"state":"complete","message":"Python files are valid.",
                    "action_shape":list(action.shape),"reward_probe":reward_value},indent=2)+"\n",encoding="utf-8")
                print(json.dumps({"valid":True,"action_shape":list(action.shape),"reward_probe":reward_value}))
            return 0
        if args.command == "export":
            out.mkdir(parents=True,exist_ok=True)
            result=export_practical(args.workspace,args.sessions_root,out/"FlySwarm_Practical.zip")
            (out/"manifest.json").write_text(json.dumps({"kind":"practical_export",**result},indent=2)+"\n",encoding="utf-8")
            (out/"progress.json").write_text(json.dumps({"state":"complete","message":f"Exported {result['included_files']} files from {result['sessions']} experiments."},indent=2)+"\n",encoding="utf-8")
            print(json.dumps(result));return 0
        if args.command == "baseline":
            result = run_random_baseline(out, args.episodes, args.seed, args.max_steps, rewards)
        elif args.command == "student":
            out.mkdir(parents=True)
            with (out/"execution.log").open("a",encoding="utf-8",buffering=1) as console, redirect_stdout(console), redirect_stderr(console):
                result = run_student_agent(out,args.agent_file,args.episodes,args.seed,args.max_steps,args.reward_file)
        elif args.command == "compare-all":
            out.mkdir(parents=True)
            with (out/"execution.log").open("a",encoding="utf-8",buffering=1) as console, redirect_stdout(console), redirect_stderr(console):
                result = compare_all_policies(out,args.agent_file,args.standard_checkpoint,
                    args.custom_reward_checkpoint,args.episodes,args.seed,args.max_steps)
        elif args.command == "train":
            out.mkdir(parents=True)
            with (out/"execution.log").open("a",encoding="utf-8",buffering=1) as console, redirect_stdout(console), redirect_stderr(console):
                reward_function=load_reward(args.reward_file) if args.reward_file else None
                result = train_sb3_ppo(out, args.steps, args.seed, args.max_steps,
                                       args.learning_rate, out / "progress.json", rewards,
                                       reward_function=reward_function,reward_file=args.reward_file)
        elif args.command == "evaluate":
            result = evaluate_sb3(args.checkpoint, out, args.episodes, args.seed,
                                  args.max_steps, reward_coefficients=rewards)
        else:
            result = compare_paired(args.checkpoint, out, args.episodes, args.seed,
                                    args.max_steps, rewards)
    except Exception as exc:
        out.mkdir(parents=True, exist_ok=True)
        detail=f"{type(exc).__name__}: {exc}"
        (out / "progress.json").write_text(json.dumps({"state":"error","message":detail},indent=2)+"\n",encoding="utf-8")
        if args.command in {"student","check","train","compare-all"}:
            with (out/"execution.log").open("a",encoding="utf-8") as log:
                import traceback
                log.write(traceback.format_exc()+"\n")
        raise
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    def _graceful_stop(_signum, _frame):
        if _ACTIVE_OUTPUT is not None:
            try:
                (_ACTIVE_OUTPUT / "progress.json").write_text(
                    json.dumps({"state":"cancelled","message":"Stopped by user."},indent=2)+"\n",
                    encoding="utf-8")
            except OSError:
                pass
        raise SystemExit(130)
    signal.signal(signal.SIGTERM, _graceful_stop)
    try:
        raise SystemExit(main())
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError) as exc:
        print(f"flyswarm-marl: {exc}", file=sys.stderr)
        raise SystemExit(2)
