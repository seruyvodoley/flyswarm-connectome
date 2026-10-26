#!/usr/bin/env python3
"""Open-loop paired MaleCNS counterfactual replay (E0/E1 diagnostic).

The observed Godot sensory/position history is held fixed.  Three passes are
made from the same initial brain seed: reference, exact no-change repeat, and
one directed-message intervention.  No Godot physics state is restored.
Results describe only neural and decoded effects conditional on the fixed
history, NOT closed-loop trajectories, agent choices, or team success.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from flyswarm.brain import DualBrain
from flyswarm.research.causal_comm import CausalCommunication


def load_inputs(path: Path, max_step: int):
    manifest_path = path.parent / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("a complete source run manifest.json is required")
    meta = json.loads(manifest_path.read_text(encoding="utf-8"))
    if meta.get("condition") != "MALECNS_REAL":
        raise ValueError("E0/E1 replay requires unmodified MALECNS_REAL traces")
    mode = meta.get("audio")
    if mode not in ("team_audio", "all_audio"):
        raise ValueError("source run must have real inter-agent communication enabled")
    if meta.get("causal_communication"):
        raise ValueError("source run must be an unmodified communication reference")
    if not path.is_file():
        raise ValueError("source neural_steps.jsonl does not exist")
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.endswith("\n"):
                raise ValueError("incomplete JSONL record")
            row = json.loads(line)
            tick = int(row.get("neural_step_id", -1))
            if tick > max_step:
                break
            if tick != len(rows) + 1:
                raise ValueError("neural input history has missing/duplicate ticks")
            obs = row.get("observations")
            traces = np.asarray(row.get("neural_traces"), dtype=float)
            if not isinstance(obs, list) or len(obs) != 16 or traces.shape != (16, 6):
                raise ValueError(f"invalid neural input/output row at tick {tick}")
            if not np.isfinite(traces).all():
                raise ValueError(f"non-finite recorded traces at tick {tick}")
            rows.append({"tick": tick, "observations": obs, "traces": traces})
    if len(rows) != max_step:
        raise ValueError(f"source has only {len(rows)} steps, expected at least {max_step}")
    return meta, mode, rows


def run_pass(brain: DualBrain, seed: int, rows: list, mode: str, specification: dict):
    brain.configure_causal_communication(specification)
    brain.reset(seed)
    traces = []
    commands = []
    deliveries = []
    applied = []
    for row in rows:
        trace, heard, _ = brain.step(row["observations"], mode)
        traces.append(np.array(trace, copy=True))
        commands.append(np.stack([brain.baseline(t) for t in trace]))
        deliveries.append(np.asarray(heard, dtype=float))
        interventions = brain.last_communication_frame["interventions"]
        if interventions:
            applied.extend(interventions)
    return np.asarray(traces), np.asarray(commands), np.asarray(deliveries), applied


def max_difference(first, second):
    if first.shape != second.shape:
        raise ValueError("shape mismatch in replay results")
    return float(np.max(np.abs(first - second)))


def run(args):
    event = json.loads(args.event)
    specification = {"events": [event]}
    parsed = CausalCommunication(specification).events[0]
    if parsed.tick > args.max_steps:
        raise ValueError("event must occur within max-steps")
    meta, mode, rows = load_inputs(args.neural_steps, args.max_steps)
    seed = int(meta["seed"])
    data_sha = hashlib.sha256(args.neural_steps.read_bytes()).hexdigest()
    brain = DualBrain(seed=seed)
    control = {"events": []}
    ref_traces, ref_commands, ref_heard, ref_applied = run_pass(brain, seed, rows, mode, control)
    repeat_traces, repeat_commands, repeat_heard, _ = run_pass(brain, seed, rows, mode, control)
    tolerance = args.tolerance
    e0 = {
        "neural_max_abs_error": max_difference(ref_traces, repeat_traces),
        "decoder_max_abs_error": max_difference(ref_commands, repeat_commands),
        "heard_max_abs_error": max_difference(ref_heard, repeat_heard),
        "recorded_trace_max_abs_error": max_difference(ref_traces, np.asarray([r["traces"] for r in rows])),
        "tolerance": tolerance,
    }
    # Do not accept a tolerance tuned after looking at these results.
    if any(v > tolerance for k,v in e0.items() if k.endswith("_error")):
        raise RuntimeError("E0 reproducibility validation failed: " + json.dumps(e0))
    treated_traces, treated_commands, treated_heard, applied = run_pass(brain, seed, rows, mode, specification)
    if len(applied) != 1 or applied[0]["tick"] != parsed.tick:
        raise RuntimeError("the prespecified directed intervention was not delivered exactly once")
    receiver = parsed.receiver
    effects = []
    for delta_ticks in (0, 1, 4, 24, 49):
        index = parsed.tick - 1 + delta_ticks
        if index >= len(rows):
            effects.append({"horizon_ms": delta_ticks * 20, "available": False})
            continue
        neutral = ref_traces[index, receiver]
        modified = treated_traces[index, receiver]
        decoded_neutral = ref_commands[index, receiver]
        decoded_modified = treated_commands[index, receiver]
        effects.append({
            "horizon_ms": delta_ticks * 20, "available": True,
            "neural_l2": float(np.linalg.norm(modified - neutral)),
            "decoder_l2": float(np.linalg.norm(decoded_modified - decoded_neutral)),
            "heard_difference": float(treated_heard[index, receiver] - ref_heard[index, receiver]),
            "dnp01_difference_hz": float(modified[4] - neutral[4]),
        })
    result = {
        "schema": "flyswarm.causal.e0e1.open_loop.v1",
        "not_closed_loop": True, "not_team_effect": True,
        "source": str(args.neural_steps), "source_sha256": data_sha,
        "source_run": meta.get("run_id"), "source_commit": meta.get("git",{}),
        "seed": seed, "audio_mode": mode, "event": event,
        "intervention_applied": applied[0],
        "e0": e0, "e1": effects,
        "interpretation": "conditional neural/decoder response with recorded game observations fixed",
    }
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable E0/E1 result: {output}")
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(output), "e0": e0, "e1": effects}, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--neural-steps", type=Path, required=True,
                   help="Validated MALECNS_REAL team_audio run neural_steps.jsonl")
    p.add_argument("--event", required=True,
                   help='JSON: {"tick":40,"sender":0,"receiver":1,"kind":"mute"}')
    p.add_argument("--max-steps", type=int, default=150)
    p.add_argument("--tolerance", type=float, default=1e-9,
                   help="Prespecified maximum absolute E0 repeat/recorded-trace error")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.max_steps < 1 or not np.isfinite(args.tolerance) or args.tolerance < 0:
        p.error("max-steps must be positive and tolerance finite nonnegative")
    run(args)


if __name__ == "__main__":
    main()
