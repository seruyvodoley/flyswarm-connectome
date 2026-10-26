#!/usr/bin/env python3
"""Fail-closed runner for paired Godot 3D + real MaleCNS research experiments."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from flyswarm.research import checksum_archive, validate_archive_checksums, validate_combat_events, validate_neural_jsonl
from flyswarm.research.analysis import analyze


def godot_binary() -> str | None:
    candidate = os.environ.get("GODOT") or shutil.which("godot") or shutil.which("godot4")
    if candidate:
        return candidate
    for path in (Path.home() / "Applications/Godot.app/Contents/MacOS/Godot",
                 Path("/Applications/Godot.app/Contents/MacOS/Godot")):
        if path.is_file():
            return str(path)
    return None


def git_state() -> dict:
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    try:
        commit = git("rev-parse", "HEAD")
        status = git("status", "--porcelain")
        branch = git("branch", "--show-current")
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "branch": None, "dirty": None}
    return {"commit": commit, "branch": branch, "dirty": bool(status), "status_porcelain": status.splitlines()}


def source_fingerprint() -> dict:
    """Capture source and assets that can change the research environment."""
    candidates = [ROOT / "frontend/godot/project.godot", ROOT / "data/scenarios/krasny_valley.json"]
    for pattern in ("frontend/godot/scripts/**/*.gd", "frontend/godot/scenes/**/*.tscn",
                    "frontend/godot/assets/vehicles/*.glb", "src/flyswarm/**/*.py",
                    "tools/research.py", "docs/research/configs/*.json"):
        candidates.extend(ROOT.glob(pattern))
    rows = []
    for path in sorted(set(path for path in candidates if path.is_file())):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append({"path": path.relative_to(ROOT).as_posix(), "sha256": digest})
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return {"sha256": hashlib.sha256(encoded).hexdigest(), "files": rows}


def software_metadata(godot: str | None = None) -> dict:
    packages = {}
    for name in ("flybrain", "numpy", "scipy", "matplotlib", "gymnasium", "stable-baselines3"):
        try: packages[name] = __import__("importlib.metadata", fromlist=["version"]).version(name)
        except Exception: packages[name] = None
    godot_version = None
    if godot:
        result = subprocess.run([godot, "--headless", "--path", str(ROOT / "frontend/godot"), "--version"],
                                cwd=ROOT, text=True, capture_output=True, timeout=30, check=False)
        if result.returncode == 0: godot_version = (result.stdout or result.stderr).strip().splitlines()[:1]
    return {"python": sys.version, "packages": packages, "godot_version": godot_version,
            "platform": platform.platform(), "machine": platform.machine(), "processor": platform.processor(),
            "cpu_count": os.cpu_count()}


def dataset_preflight() -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    data_dir = Path(env.get("FLY_DATA", Path.home() / "fly-data"))
    result = subprocess.run([sys.executable, "-m", "flyswarm.bridge.server", "--check-data", "--data-dir", str(data_dir)],
                           cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    try:
        details = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        details = {"ready": False, "error": (result.stdout + result.stderr)[-2000:]}
    return details


def preflight() -> dict:
    godot = godot_binary()
    data = dataset_preflight()
    brain_probe = {"ready": False, "error": "dataset unavailable"}
    if data.get("ready"):
        try:
            from flyswarm.brain import DualBrain
            brain = DualBrain(seed=271828)
            observations = [{"id": i, "alive": True, "position": [float(i), 0.0, float(i % 3)],
                             "bearing": 0.0, "elevation": 0.0, "looming": 0.0,
                             "visible": i != 0, "proprio": [0.0] * 6, "teacher": [0.0] * 6,
                             "vehicle": "t34_85"} for i in range(16)]
            traces, heard, tick_ms = brain.step(observations, "no_audio")
            mutable_arrays = [name for name, value in vars(brain.blue).items()
                              if isinstance(value, np.ndarray) and isinstance(getattr(brain.red, name, None), np.ndarray)]
            aliasing = [name for name in mutable_arrays if np.shares_memory(getattr(brain.blue, name), getattr(brain.red, name))]
            brain_probe = {"ready": bool(len(brain.brains) == 2 and all(b.batch == 8 for b in brain.brains)
                           and not aliasing and traces.shape == (16, 6) and heard.shape == (16,)
                           and np.isfinite(traces).all() and np.isfinite(heard).all()),
                           "flybrain_version": __import__("importlib.metadata", fromlist=["version"]).version("flybrain"),
                           "batches": [b.batch for b in brain.brains], "neurons_per_brain": [b.n for b in brain.brains],
                           "neural_dt_s": brain.blue.dt, "shared_mutable_arrays": aliasing,
                           "response_shape": list(traces.shape), "response_finite": bool(np.isfinite(traces).all()),
                           "one_real_neural_step_ms": tick_ms}
            if not brain_probe["ready"]:
                brain_probe["error"] = "real two-brain response or instance-isolation check failed"
        except Exception as exc:
            brain_probe = {"ready": False, "error": f"{type(exc).__name__}: {exc}"}
    evidence = research_evidence()
    checks = {"godot_binary": bool(godot), "MaleCNS_dataset_checksums": bool(data.get("ready")),
              "dual_batch8_real_brain_step": bool(brain_probe.get("ready")),
              "non_neural_trained_checkpoint": evidence["non_neural_checkpoint"],
              "real_multi_seed_pilot_completed": evidence["multi_seed_pilot"],
              "end_to_end_game_and_neural_sync_validated": evidence["game_neural_sync"],
              "repeat_reproducibility_validated": evidence["repeat_reproducibility"],
              "long_duration_real_combat_pilot": evidence["long_duration_pilot"],
              "long_duration_repeatability": evidence["long_duration_reproducibility"],
              "complete_scientific_ready": False}
    godot_version = None
    if godot:
        probe = subprocess.run([godot, "--headless", "--path", str(ROOT / "frontend/godot"), "--version"],
                              cwd=ROOT, text=True, capture_output=True, timeout=30, check=False)
        godot_version = (probe.stdout or probe.stderr).strip().splitlines()[:1]
        checks["godot_binary"] = probe.returncode == 0
    checks["complete_scientific_ready"] = bool(not evidence["blockers"] and checks["godot_binary"]
                                                 and checks["MaleCNS_dataset_checksums"]
                                                 and checks["dual_batch8_real_brain_step"])
    neural_ready = checks["MaleCNS_dataset_checksums"] and checks["dual_batch8_real_brain_step"]
    simulator_ready = checks["godot_binary"] and evidence["controlled_combat_integration"]
    controls_ready = evidence["multi_seed_pilot"] and evidence["non_neural_checkpoint"]
    registration_ready = evidence["long_duration_event_audit"] and checks["end_to_end_game_and_neural_sync_validated"]
    statistics_ready = evidence["analysis_outputs_valid"]
    reproducibility_ready = evidence["repeat_reproducibility"] and evidence["long_duration_reproducibility"]
    recovery_ready = evidence["end_to_end_recovery_verified"]
    study_protocol_ready = evidence["preregistered_study_protocol"]
    categories = {
        "neural_infrastructure": {"ready": bool(neural_ready), "reasons": [] if neural_ready else [
            *([] if checks["MaleCNS_dataset_checksums"] else ["MaleCNS dataset is unavailable or its checksums do not match."]),
            *([] if checks["dual_batch8_real_brain_step"] else ["Two independent real FlyBrain(batch=8) instances failed the finite-step probe."])]},
        "simulator": {"ready": bool(simulator_ready), "reasons": [] if simulator_ready else [
            *([] if checks["godot_binary"] else ["Godot executable/version probe failed."]),
            *([] if evidence["controlled_combat_integration"] else ["Controlled real-projectile integration scenarios A–D have not all passed."])]},
        "controls": {"ready": bool(controls_ready), "reasons": [] if controls_ready else [
            *([] if evidence["multi_seed_pilot"] else ["Validated REAL/ABLATED/SHUFFLED/RULE multi-seed runs are missing."]),
            *([] if evidence["non_neural_checkpoint"] else ["A held-out, task-matched NON_NEURAL_TRAINED checkpoint is missing; existing ridge model imitates Rule AI."])]},
        "registration": {"ready": bool(registration_ready), "reasons": [] if registration_ready else [
            *([] if evidence["long_duration_event_audit"] else ["Long-pilot event stream audit is missing or invalid."]),
            *([] if checks["end_to_end_game_and_neural_sync_validated"] else ["Validated game/neural frame synchronization evidence is missing."])]},
        "statistical_processing": {"ready": bool(statistics_ready), "reasons": [] if statistics_ready else ["Validated run/seed tables, statistics, numeric plot data, and PNG plus SVG/PDF outputs are incomplete."]},
        "reproducibility": {"ready": bool(reproducibility_ready), "reasons": [] if reproducibility_ready else [
            *([] if evidence["repeat_reproducibility"] else ["No same-source, same-config run pair has reproduced raw traces."]),
            *([] if evidence["long_duration_reproducibility"] else ["The 30-second-or-longer MaleCNS trace has not been repeated on the same source fingerprint."])]},
        "failure_recovery": {"ready": bool(recovery_ready), "reasons": [] if recovery_ready else ["Real end-to-end stop/resume, backend-process failure, and MaleCNS disconnect/recovery checks are incomplete."]},
        "study_protocol": {"ready": bool(study_protocol_ready), "reasons": [] if study_protocol_ready else ["No preregistered final protocol with primary metric, control set, power/sample-size rationale, exclusions, analysis plan, and frozen collection config is available."]},
    }
    platform_ready = all(categories[key]["ready"] for key in ("neural_infrastructure", "simulator", "controls", "registration", "statistical_processing", "reproducibility", "failure_recovery"))
    study_ready = platform_ready and categories["study_protocol"]["ready"]
    result = {"status": "READY" if study_ready else "NOT_READY",
              "platform_status": "PLATFORM_READY" if platform_ready else "NOT_READY",
              "study_status": "STUDY_READY" if study_ready else "NOT_READY",
              "readiness_categories": categories, "checks": checks, "evidence": evidence, "implemented_capabilities": {
                  "paired_side_swap_runner": True, "streamed_neural_and_game_step_formats": True,
                  "fail_closed_integrity_validator": True, "pair_aware_analysis_and_figures": True,
                  "resume_after_interruption": True, "discrete_event_export_and_audit": True},
              "dataset": data, "real_backend_probe": brain_probe,
              "godot": godot, "godot_version": godot_version,
              "software": software_metadata(godot), "source_fingerprint": source_fingerprint(),
              "git": git_state(), "python": sys.version, "platform": platform.platform(),
              "blockers": evidence["blockers"]}
    return result


def controlled_combat_integration_valid(root: Path | None = None) -> bool:
    root = root or (ROOT / "results/research")
    required = {"A_stationary_vs_stationary", "B_stationary_vs_moving_target",
                "C_moving_shooter_vs_stationary", "D_mutual_engagement"}
    for report_path in sorted(root.glob("controlled-combat-validation-*.json"), reverse=True):
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not report.get("overall_passed") or report.get("scientific_sample") is not False or report.get("synthetic_hits") is not False:
            continue
        cases = {case.get("case"): case for case in report.get("cases", [])}
        if not required.issubset(cases) or not all(cases[name].get("passed") for name in required):
            continue
        if any(not cases[name].get("impact", {}).get("shot_id")
               or not cases[name].get("impact", {}).get("zone")
               or not cases[name].get("impact", {}).get("penetrated")
               for name in required - {"D_mutual_engagement"}):
            continue
        mutual = cases["D_mutual_engagement"]
        if not mutual.get("first_impact", {}).get("shot_id") or not mutual.get("second_impact", {}).get("shot_id"):
            continue
        return True
    return False


def analysis_outputs_valid(experiments: list[dict]) -> bool:
    required_csv = ("neural_motor_timeseries.csv", "behavior_timeseries.csv", "agent_trajectories.csv")
    for item in experiments:
        path = Path(item["path"])
        processed = path / "processed"
        figures = path / "figures"
        if not all((processed / name).is_file() for name in ("analysis.json", "run_level.csv", "seed_level.csv")):
            continue
        if not all((figures / name).is_file() and (figures / name).stat().st_size > 0 for name in required_csv):
            continue
        if list(figures.glob("*.png")) and list(figures.glob("*.svg")) and list(figures.glob("*.pdf")):
            return True
    return False


def preregistered_protocol_valid() -> bool:
    path = ROOT / "docs/research/preregistration.json"
    if not path.is_file():
        return False
    try:
        protocol = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    required = ("research_question", "primary_metric", "experimental_unit", "conditions",
                "minimum_meaningful_effect", "alpha", "power_target", "sample_size", "exclusions",
                "analysis_plan", "final_config")
    if not all(protocol.get(key) not in (None, "", [], {}) for key in required):
        return False
    config_path = ROOT / str(protocol["final_config"])
    return config_path.is_file() and protocol.get("status") == "preregistered"


def research_evidence() -> dict:
    """Summarize validated local evidence without upgrading a pilot to science-ready."""
    def experiment_config(path: Path, manifest: dict) -> dict:
        # New archives keep the immutable protocol in protocol.json. Older
        # archives may have copied the config directly into manifest.json.
        protocol_path = path / "protocol.json"
        if protocol_path.is_file():
            try:
                protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
                if isinstance(protocol.get("config"), dict):
                    return protocol["config"]
            except (OSError, json.JSONDecodeError):
                pass
        return manifest.get("config", {}) if isinstance(manifest.get("config"), dict) else {}

    def is_matched_non_neural_checkpoint(training_manifest: dict) -> bool:
        # A checkpoint file or a RULE-AI imitation model is not sufficient.
        # Require explicit provenance and disjoint train/validation seeds.
        train = set(training_manifest.get("training_seeds", []))
        validation = set(training_manifest.get("validation_seeds", []))
        return bool(
            training_manifest.get("baseline_type") == "NON_NEURAL_TRAINED"
            and training_manifest.get("feature_schema")
            and training_manifest.get("architecture")
            and training_manifest.get("training_budget_sim_seconds")
            and train and validation and train.isdisjoint(validation)
            and training_manifest.get("heldout_task_evaluation") is True
        )

    root = ROOT / "results/research"
    completed = []
    if root.is_dir():
        for path in sorted(root.glob("experiment-*")):
            manifest_path = path / "manifest.json"
            if not manifest_path.is_file(): continue
            try: manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError): continue
            if manifest.get("state") != "complete": continue
            validation = validate_archive_checksums(path)
            if not validation["valid"]: continue
            runs = [child for child in (path / "runs").iterdir() if child.is_dir() and not child.name.startswith("._")]
            if not runs or not all(validate_run(run)["valid"] for run in runs): continue
            conditions = set(manifest.get("conditions", []))
            seeds = set(manifest.get("seeds", []))
            completed.append({"path": str(path), "manifest": manifest,
                              "config": experiment_config(path, manifest),
                              "conditions": conditions, "seeds": seeds,
                              "runs": len(runs), "valid": True})
    multi_seed = [item for item in completed if len(item["seeds"]) >= 2
                  and {"RULE_BASED", "MALECNS_REAL", "MALECNS_ABLATED", "MALECNS_SHUFFLED"}.issubset(item["conditions"])]
    current_source_fingerprint = source_fingerprint()["sha256"]
    long_duration = [item for item in completed if float(item["config"].get("seconds", 0.0)) >= 30.0
                     and len(item["seeds"]) >= 2 and {"RULE_BASED", "MALECNS_REAL"}.issubset(item["conditions"])
                     and item["manifest"].get("source_fingerprint_sha256") == current_source_fingerprint]
    for item in long_duration:
        run_paths = [manifest_path.parent for manifest_path in (Path(item["path"]) / "runs").glob("*/manifest.json")]
        item["event_audit_valid"] = bool(run_paths) and all(
            (run_path / "validation.json").is_file()
            and json.loads((run_path / "validation.json").read_text(encoding="utf-8")).get("combat_events", {}).get("valid", False)
            for run_path in run_paths)
    repeated = False
    long_repeated = False
    for index, first in enumerate(multi_seed):
        for second in multi_seed[index + 1:]:
            if first["manifest"].get("config_sha256") != second["manifest"].get("config_sha256"):
                continue
            fingerprint = first["manifest"].get("source_fingerprint_sha256")
            if not fingerprint or fingerprint != second["manifest"].get("source_fingerprint_sha256"):
                continue
            repeated = compare_experiments(Path(first["path"]), Path(second["path"]))
            if repeated and float(first["config"].get("seconds", 0.0)) >= 30.0:
                long_repeated = True
            if repeated: break
        if repeated: break
    checkpoint = False
    if root.is_dir():
        for metadata_path in root.glob("**/training_manifest.json"):
            if metadata_path.parent.name.startswith("."):
                continue
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if is_matched_non_neural_checkpoint(metadata):
                checkpoint = True
                break
    blockers = []
    if not checkpoint: blockers.append("No non-neural trained-controller checkpoint with held-out seeds is available.")
    if not multi_seed: blockers.append("No validated multi-seed pilot archive with MALECNS_REAL, ABLATED, SHUFFLED, and RULE_BASED conditions was found.")
    if not long_duration: blockers.append("No completed 30-second-or-longer paired pilot with real MaleCNS, Rule-based control, two seeds, and both side assignments was found.")
    if long_duration and not all(item.get("event_audit_valid", False) for item in long_duration):
        blockers.append("The long-duration pilot is missing a valid event audit for one or more runs.")
    if not repeated: blockers.append("A repeated configuration has not reproduced the same raw simulation traces.")
    if long_duration and not long_repeated: blockers.append("Long-duration (30 seconds or more) MaleCNS runs have not yet been exactly reproduced.")
    blockers.extend(["Interruption/resume, backend crash, and backend disconnect have not all been verified end to end against a real interrupted collection.",
                     "The available non-neural ridge model remains a Rule-AI imitation baseline, not an architecture- and budget-matched trained controller.",
                     "The preregistered scientific sample size and power target are not set; pilot data are insufficient for confirmatory inference."])
    return {"validated_experiment_archives": [{"path": item["path"], "runs": item["runs"],
             "seeds": sorted(item["seeds"]), "conditions": sorted(item["conditions"])} for item in completed],
            "multi_seed_pilot": bool(multi_seed), "game_neural_sync": bool(multi_seed),
            "long_duration_pilot": bool(long_duration), "long_duration_reproducibility": long_repeated,
            "long_duration_event_audit": bool(long_duration) and all(item.get("event_audit_valid", False) for item in long_duration),
            "repeat_reproducibility": repeated, "non_neural_checkpoint": checkpoint,
            "controlled_combat_integration": controlled_combat_integration_valid(root),
            "analysis_outputs_valid": analysis_outputs_valid(long_duration),
            "end_to_end_recovery_verified": False,
            "preregistered_study_protocol": preregistered_protocol_valid(),
            "blockers": blockers}


def compare_experiments(first: Path, second: Path) -> bool:
    def keyed(path):
        result = {}
        for manifest_path in (path / "runs").glob("*/manifest.json"):
            meta = json.loads(manifest_path.read_text(encoding="utf-8"))
            result[(meta.get("condition"), int(meta.get("seed", -1)), bool(meta.get("side_swap")))] = manifest_path.parent
        return result
    left, right = keyed(first), keyed(second)
    if not left or left.keys() != right.keys(): return False
    for key in left:
        a, b = left[key], right[key]
        for filename, fields in (("neural_steps.jsonl", ("neural_step_id", "simulation_time_s", "sensory_inputs", "observations", "neural_traces", "effective_traces", "actions")),
                                 ("game_steps.jsonl", ("game_step_id", "physics_step_id", "simulation_time_s", "neural_step_id", "new_neural_response", "tickets", "zones", "projectiles", "agents")),
                                 ("combat_events.jsonl", ("event_id", "event", "shot_id", "shooter_id", "target_id", "position", "penetrated", "module_damage_delta", "outcome"))):
            try:
                rows_a = [json.loads(line) for line in (a / filename).read_text(encoding="utf-8").splitlines()]
                rows_b = [json.loads(line) for line in (b / filename).read_text(encoding="utf-8").splitlines()]
            except (OSError, json.JSONDecodeError): return False
            if len(rows_a) != len(rows_b): return False
            if any(any(row_a.get(field) != row_b.get(field) for field in fields)
                   for row_a, row_b in zip(rows_a, rows_b)):
                return False
    return True


def atomic_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def derive_events(game_log: Path, output: Path) -> dict:
    """Reconstruct explicit events from authoritative 50 Hz Godot state rows."""
    prior_agents = {}
    prior_zones = {}
    count = 0
    with Path(output).open("x", encoding="utf-8", buffering=1) as out:
        with Path(game_log).open(encoding="utf-8") as source:
            for line in source:
                frame = json.loads(line)
                common = {key: frame.get(key) for key in ("experiment_id", "run_id", "condition", "seed", "neural_step_id", "simulation_time_s", "wall_time_unix_s")}
                for agent in frame.get("agents", []):
                    agent_id = int(agent["agent_id"])
                    previous = prior_agents.get(agent_id)
                    if previous is not None:
                        before_metrics = previous.get("metrics", {})
                        after_metrics = agent.get("metrics", {})
                        for key, event_type in (("shots", "shot"), ("penetrations", "penetration"), ("kills", "kill")):
                            delta = int(after_metrics.get(key, 0)) - int(before_metrics.get(key, 0))
                            if delta > 0:
                                out.write(json.dumps(common | {"event": event_type, "agent_id": agent_id, "count": delta}, separators=(",", ":"), allow_nan=False) + "\n"); count += 1
                        if previous.get("visible") != agent.get("visible"):
                            out.write(json.dumps(common | {"event": "target_detected" if agent.get("visible") else "target_lost", "agent_id": agent_id, "target_agent_id": agent.get("target_agent_id")}, separators=(",", ":"), allow_nan=False) + "\n"); count += 1
                        if previous.get("alive") and not agent.get("alive"):
                            out.write(json.dumps(common | {"event": "vehicle_destroyed", "agent_id": agent_id, "last_impact": agent.get("impact", {})}, separators=(",", ":"), allow_nan=False) + "\n"); count += 1
                        old_modules = previous.get("modules", {})
                        new_modules = agent.get("modules", {})
                        disabled = sorted(key for key, value in new_modules.items() if value is False and old_modules.get(key, True))
                        if disabled:
                            out.write(json.dumps(common | {"event": "module_disabled", "agent_id": agent_id, "modules": disabled, "module_damage": agent.get("module_damage", {})}, separators=(",", ":"), allow_nan=False) + "\n"); count += 1
                        old_damage = previous.get("module_damage", {})
                        new_damage = agent.get("module_damage", {})
                        damage_delta = {key: float(value) - float(old_damage.get(key, 0.0)) for key, value in new_damage.items()
                                        if float(value) - float(old_damage.get(key, 0.0)) > 1e-9}
                        if damage_delta:
                            out.write(json.dumps(common | {"event": "module_damage", "agent_id": agent_id, "damage_delta": damage_delta}, separators=(",", ":"), allow_nan=False) + "\n"); count += 1
                        old_impact = previous.get("impact", {})
                        new_impact = agent.get("impact", {})
                        if new_impact and new_impact.get("shot_number", 0) > old_impact.get("shot_number", 0):
                            out.write(json.dumps(common | {"event": "impact", "agent_id": agent_id, "impact": new_impact}, separators=(",", ":"), allow_nan=False) + "\n"); count += 1
                    prior_agents[agent_id] = agent
                for index, zone in enumerate(frame.get("zones", [])):
                    owner = zone.get("owner")
                    if index in prior_zones and prior_zones[index] != owner:
                        out.write(json.dumps(common | {"event": "objective_owner_changed", "zone_id": index, "old_owner": prior_zones[index], "new_owner": owner}, separators=(",", ":"), allow_nan=False) + "\n"); count += 1
                    prior_zones[index] = owner
        out.flush()
    return {"events": count, "path": str(output)}


def summarize_interventions(game_log: Path, output: Path) -> dict:
    totals = {"decoder_to_applied_l1": 0.0, "objective_aux_l1": 0.0,
              "gunnery_aux_l1": 0.0, "adapter_to_applied_l1": 0.0}
    counts = {key: 0 for key in totals}
    channel_totals = [0.0] * 6
    with Path(game_log).open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            for agent in row.get("agents", []):
                layers = agent.get("control_layers", {})
                final = layers.get("final_action", agent.get("final_action"))
                decoder = layers.get("decoder_action")
                adapter = layers.get("adapter_action")
                if isinstance(final, list) and isinstance(decoder, list) and len(final) == len(decoder) == 6:
                    for index, (actual, decoded) in enumerate(zip(final, decoder)):
                        difference = abs(float(actual) - float(decoded))
                        totals["decoder_to_applied_l1"] += difference
                        channel_totals[index] += difference
                    counts["decoder_to_applied_l1"] += 1
                for key in ("objective_aux_action", "gunnery_aux_action"):
                    values = layers.get(key)
                    if isinstance(values, list) and len(values) == 6:
                        totals[key.replace("_action", "_l1")] += sum(abs(float(value)) for value in values)
                        counts[key.replace("_action", "_l1")] += 1
                if isinstance(final, list) and isinstance(adapter, list) and len(final) == len(adapter) == 6:
                    totals["adapter_to_applied_l1"] += sum(abs(float(a) - float(b)) for a, b in zip(final, adapter))
                    counts["adapter_to_applied_l1"] += 1
    means = {key: totals[key] / counts[key] if counts[key] else None for key in totals}
    result = {"schema": "flyswarm.research.intervention.v1", "agent_frame_counts": counts,
              "mean_l1_per_agent_frame": means,
              "decoder_to_applied_mean_abs_by_action": [value / counts["decoder_to_applied_l1"] if counts["decoder_to_applied_l1"] else None for value in channel_totals]}
    atomic_json(output, result)
    return result


def run_one(experiment: Path, run_id: str, condition: str, seed: int, swap: bool,
            seconds: float, godot: str, config: dict, collect_nonneural: Path | None = None,
            expected_source_fingerprint: str | None = None):
    run_dir = experiment / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    run_source_fingerprint=source_fingerprint()["sha256"]
    if expected_source_fingerprint and run_source_fingerprint!=expected_source_fingerprint:
        raise RuntimeError("Research source changed after the experiment protocol was written; refusing mixed-source data")
    if condition == "NON_NEURAL_TRAINED":
        checkpoint = config.get("non_neural_checkpoint")
        if not checkpoint or not Path(checkpoint).is_file():
            raise RuntimeError("NON_NEURAL_TRAINED requires a separately trained checkpoint; refusing substitution")
    audio_mode = config.get("audio_mode", "no_audio")
    if audio_mode not in ("no_audio", "team_audio", "all_audio"):
        raise ValueError("audio_mode must be no_audio, team_audio, or all_audio")
    causal_spec = config.get("causal_communication")
    if causal_spec is not None:
        from flyswarm.research.causal_comm import CausalCommunication
        CausalCommunication(causal_spec)  # Fail before launching backend/Godot.
        if condition == "RULE_BASED":
            raise ValueError("causal_communication requires the MaleCNS backend")
        if audio_mode == "no_audio":
            raise ValueError("causal_communication cannot intervene when audio_mode=no_audio")
        atomic_json(run_dir / "causal_config.json", causal_spec)
    port_socket = socket.socket()
    port_socket.bind(("127.0.0.1", 0))
    port = port_socket.getsockname()[1]
    port_socket.close()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    condition_name = condition
    backend = None
    backend_log = (run_dir / "backend.log").open("x", encoding="utf-8")
    try:
        if condition != "RULE_BASED":
            backend_status = run_dir / "backend-status.json"
            backend_args = [sys.executable, "-m", "flyswarm.bridge.server", "--port", str(port), "--seed", str(seed),
                            "--status-file", str(backend_status), "--parent-pid", str(os.getpid()),
                            "--blue-controller", "brain", "--red-controller", "rule",
                            "--condition", condition, "--experiment-id", experiment.name, "--run-id", run_id]
            if condition == "NON_NEURAL_TRAINED":
                backend_args += ["--non-neural-policy", str(config["non_neural_checkpoint"])]
            if condition == "MALECNS_ABLATED":
                channels = config.get("ablate_channels", ["DNp09_L", "DNp09_R", "DNa02_L", "DNa02_R", "DNp01"])
                backend_args += ["--ablate-channels", ",".join(channels)]
            if causal_spec is not None:
                backend_args += ["--causal-config", str(run_dir / "causal_config.json"),
                                 "--research-log", str(run_dir / "causal_neural_steps.jsonl")]
            if collect_nonneural:
                backend_args += ["--collect-nonneural", str(collect_nonneural)]
            backend = subprocess.Popen(backend_args, cwd=ROOT, env=env, stdout=backend_log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 180
            while True:
                if backend.poll() is not None:
                    raise RuntimeError(f"MaleCNS backend exited before READY; inspect {run_dir / 'backend.log'}")
                if backend_status.exists():
                    state = json.loads(backend_status.read_text(encoding="utf-8"))
                    if state.get("stage") == "READY":
                        break
                    if state.get("stage") == "ERROR":
                        raise RuntimeError(state.get("error", "MaleCNS startup failed"))
                if time.monotonic() >= deadline:
                    raise TimeoutError("MaleCNS backend startup exceeded 180 seconds")
                time.sleep(.2)
        manifest = {"schema": "flyswarm.research.run.v1", "experiment_id": experiment.name, "run_id": run_id,
                    "condition": condition_name, "seed": seed, "side_swap": swap, "pair_id": f"{condition_name}:{seed}",
                    "duration_s": seconds, "map": "Krasny Valley", "map_seed": int(config.get("map_seed", 1944)),
                    "vehicle_composition": "normalized symmetric t34_85 mirror", "normalized": True,
                    "audio": audio_mode, "causal_communication": causal_spec,
                    "blue_controller": condition_name, "red_controller": "RULE_BASED",
                    "git": git_state(), "godot": godot, "source_fingerprint": run_source_fingerprint,
                    "combat_event_schema": "flyswarm.combat_event.v1",
                    "step_semantics": "blocking_one_response_per_physics_step" if condition != "RULE_BASED" else "fixed_50hz_rule_step"}
        atomic_json(run_dir / "manifest.json", manifest)
        cmd = [godot, "--headless", "--path", str(ROOT / "frontend/godot"), "--",
               "--normalized", "--mirror", "t34_85", "--seed", str(int(config.get("map_seed", 1944))),
               "--battle-seed", str(seed), "--seconds", str(seconds), "--quit", "--audio", audio_mode,
               "--record", str(run_dir), "--research-record", str(run_dir / "game_steps.jsonl"),
               "--experiment-id", experiment.name, "--run-id", run_id, "--condition", condition_name]
        if swap:
            cmd.append("--swap")
        if backend:
            cmd += ["--connect", "--port", str(port)]
        else:
            cmd.append("--legacy-battle")
        godot_log = (run_dir / "godot.log").open("x", encoding="utf-8")
        try:
            result = subprocess.run(cmd, cwd=ROOT, env=env, stdout=godot_log, stderr=subprocess.STDOUT,
                                    timeout=max(180, seconds * 35), check=False)
        finally:
            godot_log.close()
        if result.returncode != 0:
            raise RuntimeError(f"Godot exited with code {result.returncode}; inspect {run_dir / 'godot.log'}")
        if source_fingerprint()["sha256"]!=run_source_fingerprint:
            raise RuntimeError("Research source changed during this run; preserving it as an invalid diagnostic run")
        log_text = (run_dir / "godot.log").read_text(errors="replace")
        if "SCRIPT ERROR" in log_text or "ERROR:" in log_text:
            raise RuntimeError(f"Godot log contains errors; inspect {run_dir / 'godot.log'}")
        summary_path = run_dir / "summary.json"
        if not summary_path.is_file():
            raise RuntimeError("Godot did not write summary.json")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        godot_manifest_path = run_dir / "manifest.json"
        godot_manifest = json.loads(godot_manifest_path.read_text(encoding="utf-8")) if godot_manifest_path.exists() else {}
        manifest.update({"godot_manifest": godot_manifest, "git_state": manifest["git"],
                         "condition": condition_name, "seed": seed, "side_swap": swap,
                         "experiment_id": experiment.name, "run_id": run_id})
        atomic_json(godot_manifest_path, godot_manifest | manifest)
        event_summary = derive_events(run_dir / "game_steps.jsonl", run_dir / "events.jsonl")
        combat_event_audit = validate_combat_events(run_dir / "combat_events.jsonl")
        intervention_summary = summarize_interventions(run_dir / "game_steps.jsonl", run_dir / "control_interventions.json")
        if backend:
            with (run_dir / "neural_steps.jsonl").open(encoding="utf-8") as stream:
                neural_ids = [json.loads(line)["neural_step_id"] for line in stream if line.strip()]
            with (run_dir / "game_steps.jsonl").open(encoding="utf-8") as stream:
                game_rows = [json.loads(line) for line in stream if line.strip()]
            applied_ids = [row["neural_step_id"] for row in game_rows if row.get("new_neural_response")]
            if neural_ids != applied_ids:
                atomic_json(run_dir / "step_sync_error.json", {"neural_step_ids": neural_ids, "applied_neural_step_ids": applied_ids})
                raise RuntimeError("Neural responses were not applied exactly once in the Godot game stream")
            neural_by_id = {json.loads(line)["neural_step_id"]: json.loads(line) for line in (run_dir / "neural_steps.jsonl").open(encoding="utf-8") if line.strip()}
            for row in game_rows:
                if row.get("new_neural_response"):
                    source = neural_by_id[row["neural_step_id"]]
                    if abs(float(source["simulation_time_s"]) - float(row["request_simulation_time_s"])) > 1e-8:
                        raise RuntimeError("Godot input observation time does not match the recorded MaleCNS step")
        validation = {"valid": True, "checks": ["summary_present", "no_godot_errors"]}
        if backend:
            neural_validation = validate_neural_jsonl(run_dir / "neural_steps.jsonl", expected_condition=condition)
            game_path = run_dir / "game_steps.jsonl"
            game_count = sum(1 for line in game_path.open(encoding="utf-8") if line.strip()) if game_path.exists() else 0
            if not neural_validation["valid"]:
                validation["valid"] = False
                validation["neural"] = neural_validation
            if game_count < 1:
                validation["valid"] = False
                validation.setdefault("errors", []).append("missing synchronized Godot game-state rows")
            validation["neural"] = neural_validation
            validation["game_state_rows"] = game_count
        validation["derived_event_count"] = event_summary["events"]
        validation["combat_events"] = combat_event_audit
        validation["control_intervention_samples"] = intervention_summary["agent_frame_counts"]
        atomic_json(run_dir / "validation.json", validation)
        run_validation=validate_run(run_dir)
        validation["run_validation"]=run_validation
        validation["valid"]=bool(validation["valid"] and run_validation["valid"])
        atomic_json(run_dir / "validation.json", validation)
        if not validation["valid"]:
            raise RuntimeError(f"Research run failed data-quality validation: {run_id}")
        return {"run_id": run_id, "condition": condition, "seed": seed, "side_swap": swap,
                "summary": summary, "validation": validation}
    finally:
        if backend and backend.poll() is None:
            backend.terminate()
            try:
                backend.wait(timeout=10)
            except subprocess.TimeoutExpired:
                backend.kill(); backend.wait()
        backend_log.close()


def collect(args, resume_path: Path | None = None):
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if config.get("schema") != "flyswarm.research.config.v1":
        raise ValueError("Unsupported research config schema")
    if not dataset_preflight().get("ready"):
        raise RuntimeError("The verified MaleCNS dataset is unavailable")
    godot = godot_binary()
    if not godot:
        raise RuntimeError("Godot executable unavailable; set GODOT")
    seeds = [int(seed) for seed in config["seeds"]]
    if any(seed <= 0 for seed in seeds):
        raise ValueError("research seeds must be positive nonzero integers (Godot seed 0 is nondeterministic)")
    if len(seeds) != len(set(seeds)):
        raise ValueError("duplicate seeds in one collection config")
    conditions = list(config["conditions"])
    allowed = {"MALECNS_REAL", "MALECNS_ABLATED", "MALECNS_SHUFFLED", "NON_NEURAL_TRAINED", "RULE_BASED"}
    if not conditions or set(conditions) - allowed:
        raise ValueError(f"unsupported or empty condition list: {conditions}")
    if "NON_NEURAL_TRAINED" in conditions:
        checkpoint = Path(config.get("non_neural_checkpoint", ""))
        if not checkpoint.is_file():
            raise ValueError("NON_NEURAL_TRAINED requires a checkpoint created by `tools/run-research train-control`")
        with np.load(checkpoint, allow_pickle=False) as data:
            checkpoint_metadata = json.loads(str(data["metadata"]))
        overlap = set(seeds) & set(checkpoint_metadata.get("training_seeds", []))
        overlap |= set(seeds) & set(checkpoint_metadata.get("validation_seeds", []))
        if overlap:
            raise ValueError(f"training/validation seeds overlap the evaluation seeds: {sorted(overlap)}")
    config_digest = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    initial_source_fingerprint=source_fingerprint()
    root = Path(config.get("output_root", ROOT / "results/research"))
    if not root.is_absolute():root=ROOT/root
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if resume_path:
        experiment = Path(resume_path).resolve()
        current = json.loads((experiment / "manifest.json").read_text(encoding="utf-8"))
        if current.get("state") == "complete":raise ValueError("This experiment is already complete")
        if current.get("config_sha256") != config_digest:raise ValueError("Resume config does not match the archived configuration")
        if current.get("source_fingerprint_sha256")!=initial_source_fingerprint["sha256"]:
            raise ValueError("Source code/assets changed since this experiment began; refusing to combine results from different implementations")
        if (experiment / "checksums.sha256").exists():raise ValueError("Checksummed archive is immutable and cannot be resumed")
        experiment_id = current["experiment_id"]
        protocol = json.loads((experiment / "protocol.json").read_text(encoding="utf-8"))
    else:
        experiment_id = datetime.now(timezone.utc).strftime("experiment-%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
        experiment = root / experiment_id
        experiment.mkdir(exist_ok=False)
        protocol = {"schema": "flyswarm.research.protocol.v1", "created_utc": datetime.now(timezone.utc).isoformat(),
                    "config": config, "config_sha256": config_digest, "git": git_state(), "dataset": dataset_preflight(),
                    "source_fingerprint": initial_source_fingerprint, "software": software_metadata(godot),
                    "pairing": "same seed, map seed, symmetric t34_85 setup, and physical-side assignment across conditions; each run has normal and swapped sides",
                    "randomness": "battle seed and map seed are recorded separately; no unverified claim of common internal RNG streams",
                    "primary_metric": "terminal_ticket_balance=(BLUE tickets-RED tickets)/600; per-seed mean across the two side assignments",
                    "secondary_metrics": ["terminal_alive_balance", "duration_s", "realtime_factor", "neural_tick_ms_mean", "neural_tick_ms_p99"]}
        atomic_json(experiment / "protocol.json", protocol)
        current = {"schema": "flyswarm.research.experiment.v1", "experiment_id": experiment_id,
                   "created_utc": protocol["created_utc"], "state": "running", "config_sha256": config_digest,
                   "source_fingerprint_sha256": initial_source_fingerprint["sha256"],
                   "seeds": seeds, "conditions": conditions, "run_count_expected": len(seeds)*len(conditions)*2}
        atomic_json(experiment / "manifest.json", current)
    runs_root = experiment / "runs"
    runs_root.mkdir(exist_ok=True)
    completed_pairs = set()
    for run_dir in runs_root.iterdir():
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():continue
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("condition") in conditions and existing.get("seed") in seeds:
            if validate_run(run_dir)["valid"]:
                completed_pairs.add((existing["condition"], int(existing["seed"]), bool(existing["side_swap"])))
    expected = len(seeds)*len(conditions)*2
    try:
        current["state"] = "running"
        atomic_json(experiment / "manifest.json", current)
        for seed in seeds:
            for condition in conditions:
                for swap in (False, True):
                    key = (condition, seed, swap)
                    if key in completed_pairs:continue
                    run_id = f"{len(completed_pairs)+1:04d}-{condition.lower()}-s{seed}-swap{int(swap)}-{uuid.uuid4().hex[:6]}"
                    item = run_one(experiment, run_id, condition, seed, swap, float(config["seconds"]), godot, config,
                                   expected_source_fingerprint=initial_source_fingerprint["sha256"])
                    completed_pairs.add(key)
                    atomic_json(experiment / "progress.json", {"completed": len(completed_pairs), "expected": expected,
                                                                 "last_run": run_id, "state": "running"})
        if len(completed_pairs) != expected:
            raise RuntimeError(f"Expected {expected} complete pairs of runs, found {len(completed_pairs)}")
        current.update({"state": "processing", "completed_utc": datetime.now(timezone.utc).isoformat(),
                        "run_count_valid": len(completed_pairs), "git": git_state()})
        atomic_json(experiment / "manifest.json", current)
        if not (experiment / "processed/analysis.json").is_file():
            analyze(experiment, reference=config.get("reference_condition", "RULE_BASED"))
        current["state"] = "complete"
        atomic_json(experiment / "manifest.json", current)
        checksum_archive(experiment)
    except BaseException as exc:
        current.update({"state": "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
                        "last_error": f"{type(exc).__name__}: {exc}", "git": git_state()})
        atomic_json(experiment / "manifest.json", current)
        raise
    print(json.dumps({"experiment_id": experiment_id, "path": str(experiment), "runs": len(completed_pairs), "state": "complete"}, indent=2))


def validate_run(path: Path):
    path = Path(path)
    manifest_path = path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    neural = path / "neural_steps.jsonl"
    if manifest.get("condition") == "RULE_BASED":
        result = {"valid": True, "not_applicable": True, "rows": 0}
    elif neural.exists():
        result = validate_neural_jsonl(neural)
    else:
        result = {"valid": False, "errors": ["neural_steps.jsonl absent"]}
    game_path = path / "game_steps.jsonl"
    game_rows = 0
    game_errors = []
    if game_path.exists():
        last_step = 0
        last_neural = 0
        last_simulation_time = -1.0
        game_new_response_ids=[]
        last_neural_response_applied=0
        with game_path.open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                try:
                    if not line.endswith("\n"):
                        game_errors.append(f"line {number}: incomplete record")
                    row = json.loads(line)
                    step = int(row.get("game_step_id", -1))
                    if step != last_step + 1:
                        game_errors.append(f"line {number}: missing, duplicated, or out-of-order game step")
                    last_step = step
                    neural_step = int(row.get("neural_step_id", -1))
                    if neural_step < last_neural:
                        game_errors.append(f"line {number}: neural step moved backwards")
                    last_neural = neural_step
                    simulation_time = row.get("simulation_time_s")
                    if not isinstance(simulation_time, (int, float)) or not np.isfinite(simulation_time):
                        game_errors.append(f"line {number}: invalid simulation timestamp")
                    elif simulation_time <= last_simulation_time:
                        game_errors.append(f"line {number}: simulation timestamps are not strictly increasing")
                    else:
                        last_simulation_time = float(simulation_time)
                    if int(row.get("physics_step_id", -1)) != step - 1:
                        game_errors.append(f"line {number}: physics/game step ID mismatch")
                    request_time = row.get("request_simulation_time_s")
                    if request_time is not None and (not isinstance(request_time, (int, float)) or not np.isfinite(request_time)):
                        game_errors.append(f"line {number}: invalid request timestamp")
                    lag = row.get("response_simulation_lag_s")
                    if lag is not None and (not isinstance(lag, (int, float)) or not np.isfinite(lag) or lag < -1e-9):
                        game_errors.append(f"line {number}: invalid/negative neural response lag")
                    if row.get("new_neural_response"):
                        game_new_response_ids.append(neural_step)
                    if manifest.get("step_semantics") == "blocking_one_response_per_physics_step":
                        if not row.get("new_neural_response"):
                            game_errors.append(f"line {number}: research physics advanced without a fresh MaleCNS response")
                        if neural_step != last_neural_response_applied + 1:
                            game_errors.append(f"line {number}: stale, skipped, or duplicated MaleCNS command")
                        last_neural_response_applied=neural_step
                    if len(row.get("agents", [])) != 16:
                        game_errors.append(f"line {number}: expected 16 game agents")
                    if row.get("new_neural_response") and neural_step < 1:
                        game_errors.append(f"line {number}: marked response without a neural step ID")
                    if manifest.get("condition") != "RULE_BASED" and not row.get("new_neural_response") and neural_step < 1:
                        game_errors.append(f"line {number}: game frame has no corresponding MaleCNS output yet")
                    game_rows += 1
                except (ValueError, json.JSONDecodeError):
                    game_errors.append(f"line {number}: invalid game-state JSON")
    else:
        game_errors.append("game_steps.jsonl absent")
    summary_path = path / "summary.json"
    saved_validation_path = path / "validation.json"
    saved_validation = json.loads(saved_validation_path.read_text(encoding="utf-8")) if saved_validation_path.exists() else {"valid": False}
    run_complete = False
    if summary_path.exists():
        try:run_complete = json.loads(summary_path.read_text(encoding="utf-8")).get("completion") == "complete"
        except json.JSONDecodeError:pass
    if run_complete:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if int(summary.get("physics_steps", -1)) != game_rows:
            game_errors.append("game-state frame count differs from Godot physics step count")
        if manifest.get("condition") != "RULE_BASED" and neural.exists():
            with neural.open(encoding="utf-8") as stream:
                neural_ids = [json.loads(line)["neural_step_id"] for line in stream if line.strip()]
            if neural_ids != game_new_response_ids:
                game_errors.append("applied neural response IDs do not match neural telemetry IDs")
    if not (path / "events.jsonl").is_file():game_errors.append("events.jsonl absent")
    if manifest.get("combat_event_schema"):
        event_audit=validate_combat_events(path / "combat_events.jsonl")
        if not event_audit["valid"]:game_errors.extend(event_audit["errors"])
        if not saved_validation.get("combat_events",{}).get("valid",False):
            game_errors.append("combat-event audit was not saved as valid")
    if not (path / "control_interventions.json").is_file():game_errors.append("control intervention summary absent")
    checksum_result = validate_archive_checksums(path) if (path / "checksums.sha256").exists() else None
    if checksum_result and not checksum_result["valid"]:
        game_errors.extend(checksum_result["errors"])
    return {"valid": bool(result.get("valid") and game_rows and not game_errors and run_complete and saved_validation.get("valid")),
            "complete_summary": run_complete,
            "neural": result, "game_rows": game_rows, "game_errors": game_errors,
            "archive_checksums": checksum_result}


def train_control(args):
    train_seeds = [int(value) for value in args.train_seeds.split(",") if value.strip()]
    validation_seeds = [int(value) for value in args.validation_seeds.split(",") if value.strip()]
    if not train_seeds or not validation_seeds or set(train_seeds) & set(validation_seeds):
        raise ValueError("training and validation require nonempty, disjoint seed lists")
    godot = godot_binary()
    if not godot:
        raise RuntimeError("Godot executable unavailable; set GODOT")
    root = Path(args.output)
    if not root.is_absolute():root=ROOT/root
    root = root.resolve()
    root.parent.mkdir(parents=True,exist_ok=True)
    root.mkdir(parents=True, exist_ok=False)
    experiment = root / "collection"
    experiment.mkdir()
    config = {"schema": "flyswarm.research.config.v1", "map_seed": args.map_seed,
              "ablate_channels": [], "non_neural_checkpoint": None}
    datasets = []
    for seed in train_seeds + validation_seeds:
        target = root / f"samples-seed-{seed}.npz"
        run_id = f"collect-{seed}-{uuid.uuid4().hex[:8]}"
        run_one(experiment, run_id, "MALECNS_REAL", seed, False, args.seconds, godot, config, collect_nonneural=target)
        datasets.append((seed, target))
    train_x=[];train_y=[];valid_x=[];valid_y=[]
    for seed,path in datasets:
        with np.load(path,allow_pickle=False) as data:
            if str(data["feature_schema"])!="game_proprioception_v1":
                raise ValueError(f"unexpected feature schema in {path}")
            x=np.asarray(data["x"],dtype=np.float64);y=np.asarray(data["y"],dtype=np.float64)
            if x.ndim!=2 or x.shape[1]!=22 or y.shape!=(len(x),6) or not np.isfinite(x).all() or not np.isfinite(y).all():
                raise ValueError(f"invalid samples in {path}")
            (train_x if seed in train_seeds else valid_x).append(x)
            (train_y if seed in train_seeds else valid_y).append(y)
    x=np.concatenate(train_x);y=np.concatenate(train_y)
    validation_x=np.concatenate(valid_x);validation_y=np.concatenate(valid_y)
    design=np.column_stack([x,np.ones(len(x))])
    weights=np.linalg.solve(design.T@design+np.eye(23)*args.ridge,design.T@y)
    prediction=np.clip(np.column_stack([validation_x,np.ones(len(validation_x))])@weights,-1,1)
    validation_mse=float(np.mean((prediction-validation_y)**2))
    metadata={"feature_schema":"game_proprioception_v1","feature_names":[f"proprio_{i}" for i in range(6)]+[f"rl_task_{i}" for i in range(16)],
              "training_seeds":train_seeds,"validation_seeds":validation_seeds,"training_samples":len(x),
              "validation_samples":len(validation_x),"ridge_alpha":args.ridge,"validation_mse":validation_mse,
              "training_seconds_per_seed":args.seconds,"training_budget_sim_seconds":args.seconds*len(train_seeds),
              "target":"existing teacher action; this is a distilled rule-policy baseline, not an independent biological controller",
              "git":git_state(),"dataset":dataset_preflight(),"software":software_metadata(godot),
              "source_fingerprint":source_fingerprint(),"created_utc":datetime.now(timezone.utc).isoformat()}
    checkpoint=root/"non_neural_policy.npz"
    np.savez(checkpoint,weights=weights,metadata=json.dumps(metadata,sort_keys=True))
    atomic_json(root/"training_manifest.json",metadata|{"checkpoint":str(checkpoint),
                "checkpoint_sha256":hashlib.sha256(checkpoint.read_bytes()).hexdigest()})
    checksums=checksum_archive(root)
    print(json.dumps({"checkpoint":str(checkpoint),"training_samples":len(x),"validation_samples":len(validation_x),
                      "validation_mse":validation_mse,"training_seeds":train_seeds,"validation_seeds":validation_seeds,
                      "checksums":checksums},indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight", help="Check local Godot, MaleCNS data, and readiness blockers")
    pilot = sub.add_parser("pilot", help="Run a small paired real-data pilot using a config")
    pilot.add_argument("--config", default=str(ROOT / "docs/research/configs/pilot.json"))
    collect_parser = sub.add_parser("collect", help="Run a configured multi-seed paired series")
    collect_parser.add_argument("--config", required=True)
    resume_parser = sub.add_parser("resume", help="Resume incomplete collection without reusing completed run IDs")
    resume_parser.add_argument("--config", required=True)
    resume_parser.add_argument("--run", required=True)
    validate = sub.add_parser("validate", help="Validate a run folder or all runs in an experiment")
    validate.add_argument("--run", required=True)
    analysis = sub.add_parser("analyze", help="Analyze only valid completed runs")
    analysis.add_argument("--run", required=True)
    analysis.add_argument("--reference", default="RULE_BASED")
    report = sub.add_parser("report", help="Print the saved statistical report")
    report.add_argument("--run", required=True)
    checksums = sub.add_parser("checksum", help="Create non-overwriting SHA-256 archive checksums")
    checksums.add_argument("--run", required=True)
    training = sub.add_parser("train-control", help="Collect disjoint 3D teacher data and fit the non-neural adapter")
    training.add_argument("--train-seeds", required=True, help="Comma-separated train seeds")
    training.add_argument("--validation-seeds", required=True, help="Comma-separated held-out validation seeds")
    training.add_argument("--seconds", type=float, default=20)
    training.add_argument("--map-seed", type=int, default=1944)
    training.add_argument("--ridge", type=float, default=.1)
    training.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "preflight":
        result = preflight(); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if result["checks"]["complete_scientific_ready"] else 2
    if args.command in {"pilot", "collect"}:
        args.config = args.config
        collect(args); return 0
    if args.command == "resume":
        collect(args, Path(args.run)); return 0
    if args.command == "train-control":
        train_control(args); return 0
    path = Path(args.run).resolve()
    if args.command == "validate":
        if (path / "runs").is_dir():
            results = {child.name: validate_run(child) for child in sorted((path / "runs").iterdir()) if child.is_dir()}
            archive_checksums = validate_archive_checksums(path) if (path / "checksums.sha256").exists() else None
            output = {"valid": bool(results) and all(row["valid"] for row in results.values())
                      and (archive_checksums is None or archive_checksums["valid"]),
                      "runs": results, "archive_checksums": archive_checksums}
        else: output = validate_run(path)
        print(json.dumps(output, indent=2)); return 0 if output["valid"] else 2
    if args.command == "analyze":
        print(json.dumps(analyze(path, args.reference), indent=2)); return 0
    if args.command == "report":
        print((path / "processed/analysis.json").read_text(encoding="utf-8")); return 0
    if args.command == "checksum":
        print(json.dumps(checksum_archive(path), indent=2)); return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
