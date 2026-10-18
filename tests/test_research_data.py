import json
import tempfile
import unittest
from pathlib import Path

from flyswarm.research.integrity import checksum_archive, validate_archive_checksums, validate_combat_events, validate_neural_jsonl
from flyswarm.research.analysis import paired_effect
from flyswarm.bridge.server import NonNeuralAdapter


def row(step, condition="MALECNS_REAL"):
    observations = [{"id": i} for i in range(16)]
    return {
        "schema": "flyswarm.godot_malecns.neural_step.v1",
        "experiment_id": "e1", "run_id": "r1", "condition": condition,
        "seed": 7, "neural_step_id": step, "simulation_time_s": (step - 1) * .02,
        "dt_s": .02, "observations": observations,
        "neural_traces": [[0.] * 6 for _ in range(16)],
        "effective_traces": [[0.] * 6 for _ in range(16)],
        "control_layers": [{} for _ in range(16)], "actions": [[0.] * 6 for _ in range(16)],
        "sensory_inputs": {key: [0.] * 16 for key in ("lc10_l", "lc10_r", "lc9_l", "lc9_r", "loom", "audio")},
        "metadata": {"instances_independent": True, "instance_count": 2, "instance_batches": [8, 8],
                     "dataset_sha256": {"brain.npz": "abc"}, "flybrain_version": "0.1.0"},
    }


class ResearchDataTests(unittest.TestCase):
    def test_combat_event_audit_checks_projectile_lifecycle_and_damage(self):
        events = [
            {"event": "shot", "shot_id": "r:1", "shooter_id": 2, "projectile": "ap", "initial_position": [0, 1, 0], "initial_velocity": [0, 0, 300], "muzzle_velocity_m_s": 300},
            {"event": "hit", "shot_id": "r:1", "shooter_id": 2, "target_id": 9, "target_alive": True, "target_kind": "vehicle", "position": [0, 1, 10], "surface_normal": [0, 0, -1], "flight_distance_m": 10},
            {"event": "vehicle_destroyed", "shot_id": "r:1", "killer_id": 2, "target_id": 9, "cause": "ammo_rack"},
            {"event": "armour_result", "shot_id": "r:1", "target_id": 9, "penetrated": True, "outcome": "critical"},
            {"event": "penetration", "shot_id": "r:1", "target_id": 9},
            {"event": "damage", "shot_id": "r:1", "target_id": 9, "module_damage_delta": {"gunner": 1.2}, "disabled_modules": ["gunner"]},
            {"event": "kill", "shot_id": "r:1", "shooter_id": 2, "target_id": 9, "reason": "crew_knockout"},
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "combat.jsonl"
            rows = [{"schema": "flyswarm.combat_event.v1", "event_id": i, "run_id": "r", "condition": "MALECNS_REAL", "simulation_time_s": i * .02, **event}
                    for i, event in enumerate(events, 1)]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            result = validate_combat_events(path)
            self.assertTrue(result["valid"], result["errors"])
            self.assertEqual((result["shots"], result["hits"], result["penetrations"], result["damaging_shots"], result["kills"]), (1, 1, 1, 1, 1))
            self.assertEqual(result["counts"]["vehicle_destroyed"],1)

    def test_combat_event_audit_rejects_orphan_penetration_duplicate_hit_and_negative_damage(self):
        events = [
            {"event": "shot", "shot_id": "r:1", "shooter_id": 2, "projectile": "ap", "initial_position": [0, 1, 0], "initial_velocity": [0, 0, 300], "muzzle_velocity_m_s": 300},
            {"event": "hit", "shot_id": "r:1", "target_id": 9, "target_alive": True, "position": [0, 1, 10], "surface_normal": [0, 0, -1], "flight_distance_m": 10},
            {"event": "hit", "shot_id": "r:1", "target_id": 9, "target_alive": True, "position": [0, 1, 10], "surface_normal": [0, 0, -1], "flight_distance_m": 10},
            {"event": "penetration", "shot_id": "missing", "target_id": 9},
            {"event": "damage", "shot_id": "r:1", "module_damage_delta": {"gunner": -1.0}},
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "combat.jsonl"
            rows = [{"schema": "flyswarm.combat_event.v1", "event_id": i, "run_id": "r", "condition": "MALECNS_REAL", "simulation_time_s": i * .02, **event}
                    for i, event in enumerate(events, 1)]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            result = validate_combat_events(path)
            self.assertFalse(result["valid"])
            self.assertTrue(any("duplicate projectile hit" in error for error in result["errors"]))
            self.assertTrue(any("without successful armour result" in error for error in result["errors"]))
            self.assertTrue(any("negative module damage" in error for error in result["errors"]))

    def test_neural_stream_accepts_complete_monotonic_records(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "steps.jsonl"
            path.write_text("".join(json.dumps(row(i), allow_nan=False) + "\n" for i in (1, 2)))
            result = validate_neural_jsonl(path, expected_condition="MALECNS_REAL")
            self.assertTrue(result["valid"], result["errors"])
            self.assertEqual(result["rows"], 2)

    def test_neural_stream_rejects_gap_condition_change_and_missing_independence(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "steps.jsonl"
            first = row(1)
            second = row(3, "MALECNS_ABLATED")
            second["metadata"]["instances_independent"] = False
            path.write_text(json.dumps(first) + "\n" + json.dumps(second) + "\n")
            result = validate_neural_jsonl(path, expected_condition="MALECNS_REAL")
            self.assertFalse(result["valid"])
            self.assertTrue(any("step IDs" in error for error in result["errors"]))
            self.assertTrue(any("condition mismatch" in error for error in result["errors"]))
            self.assertTrue(any("independent" in error for error in result["errors"]))

    def test_neural_stream_rejects_simulation_step_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "steps.jsonl"
            first, second = row(1), row(2)
            second["simulation_time_s"] = .04
            path.write_text(json.dumps(first) + "\n" + json.dumps(second) + "\n", encoding="utf-8")
            result = validate_neural_jsonl(path)
            self.assertFalse(result["valid"])
            self.assertTrue(any("synchronized" in error for error in result["errors"]))

    def test_neural_stream_rejects_nan(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "steps.jsonl"
            item = row(1)
            item["tick_ms"] = float("nan")
            path.write_text(json.dumps(item) + "\n")
            result = validate_neural_jsonl(path)
            self.assertFalse(result["valid"])
            self.assertTrue(any("non-finite" in error for error in result["errors"]))

    def test_archive_checksums_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data.json").write_text("{}\n")
            self.assertEqual(checksum_archive(root)["files"], 1)
            with self.assertRaises(FileExistsError):
                checksum_archive(root)

    def test_archive_checksum_validation_detects_changes_and_ignores_appledouble(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sample.json").write_text("{}\n", encoding="utf-8")
            checksum_archive(root)
            self.assertTrue(validate_archive_checksums(root)["valid"])
            (root / "._sample.json").write_bytes(b"AppleDouble metadata")
            self.assertTrue(validate_archive_checksums(root)["valid"])
            (root / "sample.json").write_text("corrupt\n", encoding="utf-8")
            result = validate_archive_checksums(root)
            self.assertFalse(result["valid"])
            self.assertTrue(any("mismatch" in error for error in result["errors"]))

    def test_pair_effect_uses_independent_seed_count(self):
        result = paired_effect([.2, .4, .1], [0., .1, -.1])
        self.assertEqual(result["n_independent_seeds"], 3)
        self.assertAlmostEqual(result["mean_difference"], .2333333333)
        self.assertEqual(len(result["bootstrap_ci95_seed_resampling"]), 2)

    def test_non_neural_checkpoint_rejects_neural_feature_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "policy.npz"
            metadata = {"feature_schema": "game_proprioception_v1", "training_seeds": [1],
                        "validation_seeds": [2], "training_samples": 32}
            import numpy as np
            np.savez(path, weights=np.zeros((23, 6)), metadata=json.dumps(metadata))
            policy = NonNeuralAdapter(path)
            self.assertEqual(policy.predict(np.zeros(22)).shape, (6,))
            metadata["feature_schema"] = "connectome_only"
            np.savez(path, weights=np.zeros((23, 6)), metadata=json.dumps(metadata))
            with self.assertRaises(ValueError):
                NonNeuralAdapter(path)


if __name__ == "__main__":
    unittest.main()
