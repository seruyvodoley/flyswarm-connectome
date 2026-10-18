"""Fail-closed validation and immutable archive checksums for research runs."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _finite(value, path="$", errors=None):
    errors = errors if errors is not None else []
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return errors
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            errors.append(f"{path}: non-finite numeric value")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _finite(item, f"{path}[{index}]", errors)
    elif isinstance(value, dict):
        for key, item in value.items():
            _finite(item, f"{path}.{key}", errors)
    return errors


def validate_neural_jsonl(path: Path, *, expected_condition: str | None = None,
                          expected_agents: tuple[int, ...] = tuple(range(16))) -> dict:
    """Validate one streamed backend log; never repairs or fills missing rows."""
    path = Path(path)
    errors: list[str] = []
    steps: list[int] = []
    times: list[float] = []
    metadata = None
    experiment_ids = set()
    run_ids = set()
    conditions = set()
    rows = 0
    if not path.is_file():
        return {"valid": False, "rows": 0, "errors": [f"missing file: {path}"]}
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.endswith("\n"):
                errors.append(f"line {line_number}: incomplete final record")
                break
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: invalid JSON ({exc.msg})")
                continue
            rows += 1
            if row.get("schema") != "flyswarm.godot_malecns.neural_step.v1":
                errors.append(f"line {line_number}: unsupported schema")
            step = row.get("neural_step_id")
            sim_time = row.get("simulation_time_s")
            if not isinstance(step, int) or step < 1:
                errors.append(f"line {line_number}: invalid neural_step_id")
            else:
                steps.append(step)
            if not isinstance(sim_time, (int, float)) or not math.isfinite(float(sim_time)):
                errors.append(f"line {line_number}: invalid simulation time")
            else:
                times.append(float(sim_time))
            if expected_condition and row.get("condition") != expected_condition:
                errors.append(f"line {line_number}: condition mismatch")
            conditions.add(row.get("condition"))
            experiment_ids.add(row.get("experiment_id"))
            run_ids.add(row.get("run_id"))
            observations = row.get("observations", [])
            ids = tuple(item.get("id") for item in observations if isinstance(item, dict))
            if ids != expected_agents:
                errors.append(f"line {line_number}: agent IDs/order mismatch")
            dt = row.get("dt_s")
            if not isinstance(dt, (int, float)) or not math.isclose(float(dt), .02, rel_tol=0, abs_tol=1e-9):
                errors.append(f"line {line_number}: unexpected neural timestep")
            sensors = row.get("sensory_inputs", {})
            if not isinstance(sensors, dict) or not all(key in sensors for key in ("lc10_l", "lc10_r", "lc9_l", "lc9_r", "loom", "audio")):
                errors.append(f"line {line_number}: missing sensory population inputs")
            elif any(not isinstance(sensors[key], list) or len(sensors[key]) != len(expected_agents) for key in ("lc10_l", "lc10_r", "lc9_l", "lc9_r", "loom", "audio")):
                errors.append(f"line {line_number}: sensory input agent count mismatch")
            traces = row.get("neural_traces")
            effective = row.get("effective_traces")
            if not isinstance(traces, list) or len(traces) != len(expected_agents):
                errors.append(f"line {line_number}: missing MaleCNS traces")
            if not isinstance(effective, list) or len(effective) != len(expected_agents):
                errors.append(f"line {line_number}: missing effective traces")
            elif any(not isinstance(trace, list) or len(trace) != 6 for trace in effective):
                errors.append(f"line {line_number}: malformed effective trace dimension")
            if isinstance(traces, list) and len(traces) == len(expected_agents) and any(not isinstance(trace, list) or len(trace) != 6 for trace in traces):
                errors.append(f"line {line_number}: malformed raw trace dimension")
            layers = row.get("control_layers")
            actions = row.get("actions")
            if not isinstance(layers, list) or len(layers) != len(expected_agents):
                errors.append(f"line {line_number}: control layer count mismatch")
            if not isinstance(actions, list) or len(actions) != len(expected_agents):
                errors.append(f"line {line_number}: action count mismatch")
            if not row.get("metadata", {}).get("instances_independent", False):
                errors.append(f"line {line_number}: independent real FlyBrain instances not confirmed")
            metadata_row = row.get("metadata", {})
            if metadata_row.get("instance_count") != 2 or metadata_row.get("instance_batches") != [8, 8]:
                errors.append(f"line {line_number}: expected two FlyBrain(batch=8) instances")
            if not metadata_row.get("dataset_sha256") or not metadata_row.get("flybrain_version"):
                errors.append(f"line {line_number}: missing dataset/FlyBrain provenance")
            if row.get("condition") == "MALECNS_ABLATED" and isinstance(traces, list) and isinstance(effective, list):
                channel_ids = {"DNp09_L": 0, "DNp09_R": 1, "DNa02_L": 2, "DNa02_R": 3, "DNp01": 4, "wing": 5}
                for name in metadata_row.get("ablate_channels", []):
                    index = channel_ids.get(name)
                    if index is None or any(float(effective[agent][index]) != 0.0 for agent in range(8)):
                        errors.append(f"line {line_number}: declared ablation was not applied to the tested team")
            if row.get("condition") == "MALECNS_SHUFFLED" and isinstance(traces, list) and isinstance(effective, list):
                if any(row.get("control_layers", [{}]*16)[agent].get("neural_source_agent") == agent for agent in range(8)):
                    errors.append(f"line {line_number}: shuffled condition did not break source-agent pairing")
                if sorted(tuple(trace) for trace in traces[:8]) != sorted(tuple(trace) for trace in effective[:8]):
                    errors.append(f"line {line_number}: shuffled condition changed the team signal distribution")
            errors.extend(f"line {line_number}: {error}" for error in _finite(row))
            metadata = row.get("metadata", metadata)
    if not rows:
        errors.append("no complete records")
    if steps and steps != list(range(steps[0], steps[0] + len(steps))):
        errors.append("missing, duplicated, or out-of-order neural step IDs")
    if times and any(right <= left for left, right in zip(times, times[1:])):
        errors.append("simulation timestamps are not strictly increasing")
    if times and len(times) > 1 and any(not math.isclose(right - left, .02, rel_tol=0, abs_tol=1e-7)
                                         for left, right in zip(times, times[1:])):
        errors.append("MaleCNS research steps are not synchronized to consecutive 20 ms Godot steps")
    if len(experiment_ids) > 1 or len(run_ids) > 1 or len(conditions) > 1:
        errors.append("run identity or condition changes within one log")
    return {"valid": not errors, "rows": rows, "first_step": steps[0] if steps else None,
            "last_step": steps[-1] if steps else None, "metadata": metadata,
            "errors": errors}


def validate_combat_events(path: Path) -> dict:
    """Audit authoritative projectile events and their shot-level references."""
    path = Path(path)
    errors: list[str] = []
    shots: dict[str, dict] = {}
    hits: dict[str, dict] = {}
    armour: dict[str, dict] = {}
    penetrations: set[str] = set()
    damages: set[str] = set()
    kills: set[str] = set()
    kill_targets: dict[str, int] = {}
    dispositions: set[str] = set()
    destroyed_targets: dict[int, dict] = {}
    event_ids: list[int] = []
    counts: dict[str, int] = {}
    vehicle_hits = 0
    identity = None
    last_simulation_time = -math.inf
    if not path.is_file():
        return {"valid": False, "counts": {}, "errors": [f"missing file: {path}"]}
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.endswith("\n"):
                errors.append(f"line {line_number}: incomplete final event")
                break
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: invalid JSON ({exc.msg})")
                continue
            if row.get("schema") != "flyswarm.combat_event.v1":
                errors.append(f"line {line_number}: unsupported event schema")
            current_identity=(row.get("experiment_id"),row.get("run_id"),row.get("condition"),row.get("seed"))
            if identity is None:identity=current_identity
            elif current_identity!=identity:errors.append(f"line {line_number}: run identity changes within the event log")
            simulation_time=row.get("simulation_time_s")
            if not isinstance(simulation_time,(int,float)) or not math.isfinite(float(simulation_time)) or simulation_time<last_simulation_time:
                errors.append(f"line {line_number}: invalid or decreasing simulation time")
            else:last_simulation_time=float(simulation_time)
            event_id = row.get("event_id")
            if not isinstance(event_id, int) or event_id < 1:
                errors.append(f"line {line_number}: invalid event ID")
            else:
                event_ids.append(event_id)
            event = row.get("event")
            counts[event] = counts.get(event, 0) + 1
            errors.extend(f"line {line_number}: {error}" for error in _finite(row))
            shot_id = row.get("shot_id")
            if event == "shot":
                if not shot_id or shot_id in shots:
                    errors.append(f"line {line_number}: missing or duplicate shot ID")
                    continue
                required = ("shooter_id", "projectile", "initial_position", "initial_velocity", "muzzle_velocity_m_s")
                if any(key not in row for key in required):
                    errors.append(f"line {line_number}: shot record is missing launch fields")
                if float(row.get("muzzle_velocity_m_s", 0.0)) <= 0.0:
                    errors.append(f"line {line_number}: invalid muzzle velocity")
                shots[shot_id] = row
            elif event == "hit":
                if shot_id not in shots:
                    errors.append(f"line {line_number}: hit without a known shot")
                elif shot_id in hits:
                    errors.append(f"line {line_number}: duplicate projectile hit")
                else:
                    hits[shot_id] = row
                    dispositions.add(shot_id)
                    if row.get("target_kind") == "vehicle":vehicle_hits+=1
                if not all(key in row for key in ("target_id", "position", "surface_normal", "flight_distance_m")):
                    errors.append(f"line {line_number}: hit record is incomplete")
            elif event == "armour_result":
                if shot_id not in hits or not hits.get(shot_id, {}).get("target_alive", False):
                    errors.append(f"line {line_number}: armour result without a live-vehicle hit")
                if shot_id in armour:
                    errors.append(f"line {line_number}: duplicate armour result")
                armour[shot_id] = row
            elif event == "penetration":
                if shot_id not in armour or not armour[shot_id].get("penetrated", False):
                    errors.append(f"line {line_number}: penetration without successful armour result")
                if shot_id in penetrations:
                    errors.append(f"line {line_number}: duplicate penetration")
                penetrations.add(shot_id)
            elif event == "damage":
                if shot_id not in penetrations:
                    errors.append(f"line {line_number}: damage without penetration")
                if shot_id in damages:errors.append(f"line {line_number}: duplicate damage event for one projectile")
                delta = row.get("module_damage_delta", {})
                if not isinstance(delta, dict) or any(not isinstance(v, (int, float)) or v < 0 for v in delta.values()):
                    errors.append(f"line {line_number}: invalid/negative module damage")
                damages.add(shot_id)
            elif event == "kill":
                if shot_id not in damages:
                    errors.append(f"line {line_number}: projectile kill without recorded damage")
                if shot_id in kills:
                    errors.append(f"line {line_number}: duplicate kill for one projectile")
                kills.add(shot_id)
                kill_targets[shot_id]=row.get("target_id")
            elif event == "vehicle_destroyed":
                target_id=row.get("target_id")
                if not isinstance(target_id,int) or target_id in destroyed_targets:
                    errors.append(f"line {line_number}: invalid or duplicate vehicle destruction")
                else:
                    destroyed_targets[target_id]=row
                if shot_id and shot_id not in shots:
                    errors.append(f"line {line_number}: destruction references an unknown projectile")
            elif event == "projectile_expired":
                if shot_id not in shots:
                    errors.append(f"line {line_number}: expired projectile without a shot")
                if shot_id in dispositions:errors.append(f"line {line_number}: projectile has multiple terminal dispositions")
                dispositions.add(shot_id)
            elif event == "projectile_in_flight_at_end":
                if shot_id not in shots:
                    errors.append(f"line {line_number}: in-flight projectile without a shot")
                if shot_id in dispositions:errors.append(f"line {line_number}: projectile has multiple terminal dispositions")
                dispositions.add(shot_id)
            else:
                errors.append(f"line {line_number}: unknown event type {event!r}")
    if event_ids and event_ids != list(range(1, len(event_ids) + 1)):
        errors.append("event IDs are missing, duplicated, or out of order")
    for shot_id, hit in hits.items():
        if hit.get("target_kind")=="vehicle" and hit.get("target_alive",False) and shot_id not in armour:
            errors.append(f"live vehicle hit for {shot_id} has no armour result")
    for shot_id, result in armour.items():
        if result.get("penetrated",False) and shot_id not in penetrations:
            errors.append(f"penetrating armour result for {shot_id} is missing its penetration event")
    if len(hits)>len(shots) or len(penetrations)>vehicle_hits or len(damages)>len(penetrations) or len(kills)>len(damages):
        errors.append("shot/hit/penetration/damage/kill totals are internally inconsistent")
    if set(shots)-dispositions:
        errors.append(f"{len(set(shots)-dispositions)} shot(s) have no recorded projectile disposition")
    for shot_id in kills:
        if not any(row.get("shot_id")==shot_id and row.get("target_id")==kill_targets.get(shot_id)
                   for row in destroyed_targets.values()):
            errors.append(f"kill event for {shot_id} has no matching vehicle destruction")
    for row in destroyed_targets.values():
        shot_id=row.get("shot_id")
        if shot_id and shot_id not in kills:
            errors.append(f"projectile destruction for {shot_id} has no matching kill event")
    return {"valid": not errors, "shots": len(shots), "hits": len(hits), "vehicle_hits": vehicle_hits,
            "penetrations": len(penetrations), "damaging_shots": len(damages),
            "kills": len(kills), "counts": counts, "errors": errors}


def checksum_archive(root: Path) -> dict:
    """Hash data files in stable path order; reject symlinks and empty archives."""
    root = Path(root).resolve()
    files = sorted(path for path in root.rglob("*")
                   if path.is_file() and path.name != "checksums.sha256" and not path.name.startswith("._"))
    if not files:
        raise ValueError("research archive is empty")
    rows = []
    for path in files:
        if path.is_symlink():
            raise ValueError(f"symlink not allowed in research archive: {path}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        rows.append((digest.hexdigest(), path.relative_to(root).as_posix()))
    target = root / "checksums.sha256"
    if target.exists():
        raise FileExistsError(target)
    target.write_text("".join(f"{value}  {name}\n" for value, name in rows), encoding="utf-8")
    return {"files": len(rows), "path": str(target), "algorithm": "sha256"}


def validate_archive_checksums(root: Path) -> dict:
    """Verify an existing archive manifest without modifying any archive data."""
    root = Path(root).resolve()
    manifest = root / "checksums.sha256"
    if not manifest.is_file():
        return {"valid": False, "checked": 0, "warnings": [], "errors": ["checksums.sha256 absent"]}
    errors: list[str] = []
    warnings: list[str] = []
    listed: set[str] = set()
    checked = 0
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        try:
            digest, relative = line.split("  ", 1)
        except ValueError:
            errors.append(f"checksum line {number}: malformed entry")
            continue
        if relative in listed:
            errors.append(f"checksum line {number}: duplicate path {relative}")
            continue
        listed.add(relative)
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            errors.append(f"checksum line {number}: unsafe path {relative}")
            continue
        target = root / relative
        if not target.is_file() or target.is_symlink():
            errors.append(f"checksum line {number}: missing or symlinked file {relative}")
            continue
        if Path(relative).name.startswith("._"):
            warnings.append("Archive checksum manifest includes macOS AppleDouble metadata files.")
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        checked += 1
        if actual != digest:
            errors.append(f"checksum line {number}: SHA-256 mismatch for {relative}")
    actual_files = {path.relative_to(root).as_posix() for path in root.rglob("*")
                    if path.is_file() and path.name != "checksums.sha256" and not path.name.startswith("._")}
    unlisted = sorted(actual_files - listed)
    if unlisted:
        errors.append(f"archive has {len(unlisted)} unlisted data file(s): {unlisted[:5]}")
    return {"valid": not errors, "checked": checked, "listed": len(listed),
            "warnings": sorted(set(warnings)), "errors": errors}
