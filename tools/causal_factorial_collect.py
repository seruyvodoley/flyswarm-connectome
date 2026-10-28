#!/usr/bin/env python3
"""Collect a randomized 2x2 BLUE/RED MaleCNS communication pilot.

Each run has two independent real FlyBrain(batch=8) instances and fixed,
seed-balanced Godot settings. This is an E4 pilot collector, not a claim of
sufficient power or exact closed-loop replay.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import tools.research as research
from flyswarm.research import checksum_archive, validate_archive_checksums

TRANSIENT_GODOT_TIMEOUT = "Brain response timeout; no silent baseline fallback"


def retryable_timeout(run_dir: Path, error: BaseException) -> bool:
    """Only retry a completed Godot process that failed on the explicit bridge guard."""
    log = Path(run_dir) / "godot.log"
    if not isinstance(error, RuntimeError) or not log.is_file():
        return False
    try:
        return TRANSIENT_GODOT_TIMEOUT in log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def canonical_digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_plan(config: dict, *, allow_short: bool = False) -> list[dict]:
    if config.get("schema") != "flyswarm.causal.factorial.v1":
        raise ValueError("unsupported factorial configuration schema")
    if config.get("audio_mode") != "team_audio":
        raise ValueError("the E4 2x2 design requires team_audio")
    seeds = config.get("seeds")
    if not isinstance(seeds, list) or not seeds or any(type(seed) is not int or seed <= 0 for seed in seeds):
        raise ValueError("seeds must be unique positive integers")
    if len(set(seeds)) != len(seeds):
        raise ValueError("duplicate independent seed")
    seconds = config.get("seconds")
    if not isinstance(seconds, (int, float)) or seconds < (3 if allow_short else 30):
        raise ValueError("E4 pilot duration must be at least 30 simulated seconds (3 only for technical smoke)")
    arms = config.get("arms")
    if not isinstance(arms, list) or len(arms) != 4:
        raise ValueError("the 2x2 design must define exactly four arms")
    by_assignment = {}
    for arm in arms:
        if not isinstance(arm, dict) or not isinstance(arm.get("label"), str):
            raise ValueError("each arm needs a readable label")
        comm = arm.get("communication")
        if not isinstance(comm, list) or len(comm) != 2 or any(type(x) is not bool for x in comm):
            raise ValueError("each arm communication must be [BLUE enabled, RED enabled]")
        key = tuple(comm)
        if key in by_assignment:
            raise ValueError("duplicate factorial assignment")
        if arm.get("blue_controller") != "brain" or arm.get("red_controller") != "brain":
            raise ValueError("both teams must use real MaleCNS for E4")
        by_assignment[key] = arm
    if set(by_assignment) != {(True, True), (False, True), (True, False), (False, False)}:
        raise ValueError("all four balanced 2x2 communication assignments are required")
    return arms


def collect(config_path: Path, output: Path, resume: bool = False, technical_smoke: bool = False) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    arms = validate_plan(config, allow_short=technical_smoke)
    seeds = [int(value) for value in config["seeds"]]
    seconds = float(config["seconds"])
    output = output.resolve()
    config_digest = canonical_digest(config)
    source = research.source_fingerprint()
    godot = research.godot_binary()
    if not godot:
        raise RuntimeError("Godot executable unavailable")
    if not research.dataset_preflight().get("ready"):
        raise RuntimeError("MaleCNS dataset or checksums are unavailable")
    if output.exists():
        if not resume:
            raise FileExistsError(f"refusing to overwrite existing study: {output}")
        manifest_path = output / "manifest.json"
        if not manifest_path.is_file():
            raise ValueError("resume folder has no experiment manifest")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("config_sha256") != config_digest:
            raise ValueError("resume configuration differs from the frozen plan")
        if manifest.get("source_fingerprint_sha256") != source["sha256"]:
            raise ValueError("source changed; refusing to combine incompatible implementations")
        if (output / "checksums.sha256").exists():
            raise ValueError("checksummed experiment is immutable")
    else:
        output.mkdir(parents=True, exist_ok=False)
        manifest = {"schema": "flyswarm.causal.factorial.experiment.v1",
                    "experiment_id": output.name, "created_utc": datetime.now(timezone.utc).isoformat(),
                    "state": "running", "config_sha256": config_digest,
                    "source_fingerprint_sha256": source["sha256"], "seed_blocks": seeds,
                    "arms": [arm["label"] for arm in arms],
                    "run_count_expected": len(seeds) * len(arms) * 2}
        (output / "configurations").mkdir()
        (output / "raw/e4").mkdir(parents=True)
        (output / "processed").mkdir()
        (output / "validation").mkdir()
        (output / "logs").mkdir()
        (output / "configurations/pilot.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        protocol = {"schema": "flyswarm.causal.factorial.protocol.v1", "status": "exploratory_pilot",
                    "research_question": "Does enabling each team's artificial team_audio channel change symmetric two-team MaleCNS combat outcomes?",
                    "primary_outcome": config.get("primary_outcome", "difference in normalized objective presence (BLUE minus RED) per 30 s episode"),
                    "experimental_unit": "independent battle seed; side swaps are averaged within seed",
                    "factorial_assignments": [{"label": arm["label"], "communication": arm["communication"]} for arm in arms],
                    "inclusion": "complete synchronized run with valid neural/game/combat logs and both team controllers set to brain",
                    "exclusion": "incomplete or failed integrity validation; retain files but exclude from analysis",
                    "seed_selection": "new seeds declared in configurations/pilot.json before run; arm/side order is randomized with frozen order_seed",
                    "side_balance": "each seed x arm has both physical side assignments; same normalized symmetric vehicles, map and map seed",
                    "confirmatory": False, "minimum_practical_effect": None,
                    "sample_size_note": f"{len(seeds)} independent exploratory seed blocks; this is not a formal power calculation and must not be presented as a powered confirmatory study",
                    "multiplicity": "no confirmatory hypothesis tests in this pilot",
                    "source_fingerprint": source,
                    "created_utc": datetime.now(timezone.utc).isoformat()}
        (output / "PROTOCOL.md").write_text(
            "# Протокол E4 — факторный пилот 2×2\n\n"
            "Пилотный, не подтверждающий сбор. Единица — независимый seed; две перестановки сторон усредняются внутри seed. "
            "Обе команды управляются раздельными реальными MaleCNS/FlyBrain(batch=8). Вмешательство отключает входящий "
            "канал только у указанной команды; остальные настройки симуляции фиксированы.\n\n"
            "Полная замороженная спецификация находится в `configurations/pilot.json`; структурированные критерии — в `protocol.json`.\n",
            encoding="utf-8")
        (output / "protocol.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_root = output / "raw/e4"
    done = set()
    for manifest_path in run_root.glob("*/manifest.json"):
        run_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        result = research.validate_run(manifest_path.parent)
        if result.get("valid"):
            done.add((run_manifest.get("condition"), int(run_manifest.get("seed")), bool(run_manifest.get("side_swap"))))
    schedule = [(arm, seed, swap) for seed in seeds for arm in arms for swap in (False, True)]
    rng = random.Random(int(config.get("order_seed", 582019)))
    rng.shuffle(schedule)
    atomic = lambda path, data: research.atomic_json(path, data)
    try:
        for index, (arm, seed, swap) in enumerate(schedule, 1):
            key = (arm["label"], seed, swap)
            if key in done:
                continue
            arm_spec = {"label": arm["label"], "blue_controller": "brain", "red_controller": "brain",
                        "causal_communication": {"enabled_teams": arm["communication"]}}
            for attempt in range(3):
                run_id = f"e4-{arm['label'].lower()}-s{seed}-swap{int(swap)}-try{attempt+1}-{uuid.uuid4().hex[:6]}"
                run_dir = run_root / run_id
                try:
                    research.run_one(output, run_id, "MALECNS_REAL", seed, swap, seconds, godot,
                                     {"audio_mode": "team_audio", "map_seed": int(config.get("map_seed", 1944))},
                                     expected_source_fingerprint=source["sha256"], arm_spec=arm_spec,
                                     run_subdir="raw/e4")
                    break
                except RuntimeError as exc:
                    if not retryable_timeout(run_dir, exc) or attempt == 2:
                        raise
                    with (output / "logs/retries.jsonl").open("a", encoding="utf-8") as log:
                        log.write(json.dumps({"failed_run_id": run_id, "seed": seed, "arm": arm["label"],
                                              "side_swap": swap, "attempt": attempt + 1,
                                              "reason": TRANSIENT_GODOT_TIMEOUT,
                                              "retry_utc": datetime.now(timezone.utc).isoformat()},
                                             ensure_ascii=False) + "\n")
                    print(f"Retrying exact MaleCNS bridge timeout for {arm['label']} seed={seed} swap={swap} "
                          f"after preserving {run_id}", file=sys.stderr, flush=True)
            done.add(key)
            atomic(output / "progress.json", {"state": "running", "completed": len(done),
                                              "expected": len(schedule), "last_run": run_id})
        if len(done) != len(schedule):
            raise RuntimeError(f"expected {len(schedule)} runs, validated {len(done)}")
        manifest.update({"state": "complete", "completed_utc": datetime.now(timezone.utc).isoformat(),
                         "run_count_valid": len(done), "git": research.git_state()})
        atomic(output / "manifest.json", manifest)
        atomic(output / "progress.json", {"state": "complete", "completed": len(done), "expected": len(schedule)})
        expected_cells = {(arm["label"], seed, swap) for arm, seed, swap in schedule}
        accepted_cells = {}
        excluded_diagnostics = []
        duplicate_valid_cells = []
        for run_manifest in sorted(run_root.glob("*/manifest.json")):
            name = run_manifest.parent.name
            meta = json.loads(run_manifest.read_text(encoding="utf-8"))
            result = research.validate_run(run_manifest.parent)
            cell = (meta.get("condition"), int(meta.get("seed", -1)), bool(meta.get("side_swap")))
            if result.get("valid"):
                if cell in accepted_cells:
                    duplicate_valid_cells.append({"cell": cell, "runs": [accepted_cells[cell], name]})
                else:
                    accepted_cells[cell] = name
            else:
                excluded_diagnostics.append({"run_id": name, "cell": cell,
                                             "reason": "incomplete_or_failed_attempt", "validation": result})
        if duplicate_valid_cells:
            raise RuntimeError(f"duplicate integrity-valid runs for experimental cells: {duplicate_valid_cells}")
        missing_cells = sorted(expected_cells - set(accepted_cells))
        unexpected_cells = sorted(set(accepted_cells) - expected_cells)
        if missing_cells or unexpected_cells or len(accepted_cells) != len(schedule):
            raise RuntimeError(f"factorial cell validation mismatch; missing={missing_cells}, unexpected={unexpected_cells}")
        validation = {"schema": "flyswarm.causal.factorial.collection-validation.v1",
                      "valid_runs": len(accepted_cells), "expected_runs": len(schedule),
                      "all_required_cells_valid": True, "valid_run_ids_by_cell":
                          {f"{cell[0]}|{cell[1]}|swap{int(cell[2])}": run_id for cell, run_id in accepted_cells.items()},
                      "excluded_diagnostic_count": len(excluded_diagnostics),
                      "excluded_diagnostics": excluded_diagnostics,
                      "duplicate_valid_cells": duplicate_valid_cells}
        atomic(output / "validation/collection_validation.json", validation)
        from tools.analyze_causal_factorial import analyze
        result = analyze(output)
        (output / "README.md").write_text(
            "# E4 2×2 causal communication pilot\n\n"
            "This is an exploratory pilot, not a powered confirmatory analysis.\n\n"
            "Reproduce collection (requires configured MaleCNS, Godot and source workspace):\n\n"
            "```sh\npython tools/causal_factorial_collect.py --config configurations/pilot.json --output .\n"
            "python tools/analyze_causal_factorial.py .\n```\n\n"
            "Raw synchronized game/neural data are in `raw/e4/`; analysis tables and figures are in `processed/` and `figures/`.\n",
            encoding="utf-8")
        (output / "RESULTS.md").write_text(
            "# Результаты E4 пилота\n\n"
            f"Валидные запуска: {len(done)}; независимые seed: {len(seeds)}. Статус — exploratory; подтверждающие p-value не рассчитаны.\n\n"
            "Факторные контрасты по seed представлены в `processed/e4_statistics.json`; исходные метрики — `processed/e4_run_metrics.csv` и `processed/e4_seed_level.csv`.\n",
            encoding="utf-8")
        checksum_archive(output)
        if not validate_archive_checksums(output)["valid"]:
            raise RuntimeError("checksum validation failed after collection and analysis")
    except BaseException as exc:
        manifest.update({"state": "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
                         "last_error": f"{type(exc).__name__}: {exc}", "git": research.git_state()})
        atomic(output / "manifest.json", manifest)
        raise
    return {"path": str(output), "state": "complete", "validated_runs": len(done), "seed_blocks": seeds,
            "duration_per_run_s": seconds}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--technical-smoke", action="store_true", help="allow duration below 30 s; never infer E4")
    args = parser.parse_args()
    result = collect(args.config, args.output, args.resume, args.technical_smoke)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
