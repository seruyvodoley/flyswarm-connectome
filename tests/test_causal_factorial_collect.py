import unittest
import tempfile
from pathlib import Path

from tools.causal_factorial_collect import validate_plan, retryable_timeout
from flyswarm.research.causal_comm import CausalCommunication
import numpy as np


class FactorialPlanTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "schema": "flyswarm.causal.factorial.v1",
            "audio_mode": "team_audio",
            "seconds": 30,
            "seeds": [93001, 93002],
            "arms": [
                {"label": "BOTH_ON", "blue_controller": "brain", "red_controller": "brain", "communication": [True, True]},
                {"label": "BLUE_OFF", "blue_controller": "brain", "red_controller": "brain", "communication": [False, True]},
                {"label": "RED_OFF", "blue_controller": "brain", "red_controller": "brain", "communication": [True, False]},
                {"label": "BOTH_OFF", "blue_controller": "brain", "red_controller": "brain", "communication": [False, False]},
            ],
        }

    def test_balanced_factorial_requires_two_real_brains(self):
        self.assertEqual(len(validate_plan(self.config)), 4)
        bad = {**self.config, "arms": [dict(arm) for arm in self.config["arms"]]}
        bad["arms"][1]["red_controller"] = "rule"
        with self.assertRaises(ValueError):
            validate_plan(bad)

    def test_pilot_requires_at_least_30_seconds_except_explicit_smoke(self):
        short = {**self.config, "seconds": 3}
        with self.assertRaises(ValueError):
            validate_plan(short)
        self.assertEqual(len(validate_plan(short, allow_short=True)), 4)

    def test_factorial_assignments_are_complete_and_unique(self):
        duplicate = {**self.config, "arms": [*self.config["arms"][:3], dict(self.config["arms"][0]) | {"label": "DUP"}]}
        with self.assertRaises(ValueError):
            validate_plan(duplicate)

    def test_communication_switch_only_changes_receiving_team(self):
        song = np.arange(1, 17, dtype=float)
        positions = np.zeros((16, 3), dtype=float)
        alive = np.ones(16, dtype=bool)
        for enabled, expected_team in (([False, True], 1), ([True, False], 0)):
            model = CausalCommunication({"enabled_teams": enabled})
            heard, links, _, frame = model.step(song, positions, alive, "team_audio", 1)
            off = 1 - expected_team
            self.assertTrue(np.all(heard[off*8:(off+1)*8] == 0))
            self.assertTrue(np.all(links[off*8:(off+1)*8, :] == 0))
            self.assertEqual(frame["enabled_teams"], enabled)

    def test_only_explicit_bridge_timeout_is_retryable_and_partial_run_is_retained(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            log = run / "godot.log"
            error = RuntimeError("Godot exited with code 2")
            self.assertFalse(retryable_timeout(run, error))
            log.write_text("ERROR: Brain response timeout; no silent baseline fallback\n")
            self.assertTrue(retryable_timeout(run, error))
            log.write_text("ERROR: some unrelated script error\n")
            self.assertFalse(retryable_timeout(run, error))


if __name__ == "__main__":
    unittest.main()
