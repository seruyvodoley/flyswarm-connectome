from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import numpy as np

from flyswarm.marl.env import FlySwarmParallelEnv
from flyswarm.marl.student_code import ManagedStudentReward
from flyswarm.marl.cli import _experiment_label
from flyswarm.marl.experiments import train_sb3_ppo
from flyswarm.marl.cli import main as marl_cli_main


class StudentContractTests(unittest.TestCase):
    def test_student_runs_use_student_experiment_label(self):
        self.assertEqual(_experiment_label("student", 11), "student-agent-seed-11")

    def test_code_check_accepts_team_only_agent_and_extended_reward(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            agent=root/"agent.py"
            reward=root/"reward.py"
            agent.write_text("def act_team(observations, contexts):\n    return [[0, 0, 0, 0, 0, 0] for _ in observations]\n",encoding="utf-8")
            reward.write_text(
                "def calculate_reward(components, observation=None, action=None, next_observation=None, context=None):\n"
                "    assert len(observation) == len(next_observation) == 30\n"
                "    return float(components['objective_capture'] + action[0])\n",
                encoding="utf-8")
            output=StringIO()
            with redirect_stdout(output):
                result=marl_cli_main(["--experiment-dir",str(root/"check"),"check",
                                      "--agent-file",str(agent),"--reward-file",str(reward)])
            self.assertEqual(result,0)
            import json
            progress=json.loads((root/"check"/"progress.json").read_text(encoding="utf-8"))
            self.assertEqual(progress["action_shape"],[[6]]*8)
            self.assertEqual(progress["reward_probe"],1.0)

    def test_8x8_environment_supports_reproducible_swapped_start_sides(self):
        env = FlySwarmParallelEnv(max_steps=2)
        try:
            env.reset(seed=101)
            default_positions = env.pos.copy()
            default_headings = env.heading.copy()
            self.assertEqual(env.active_units_per_team, 8)
            self.assertEqual(env.start_side, "left")
            env.reset(seed=101, options={"swap_sides": True})
            np.testing.assert_allclose(env.pos, -default_positions)
            expected_heading = (default_headings + 2 * np.pi) % (2 * np.pi) - np.pi
            np.testing.assert_allclose(env.heading, expected_heading)
            self.assertEqual(env.start_side, "right")
        finally:
            env.close()

    def test_extended_reward_receives_public_step_context_and_changes_training_reward(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "reward.py"
            source.write_text(
                "SEED = 0\n"
                "def reset(seed=0):\n    global SEED\n    SEED = seed\n"
                "def calculate_reward(components, observation=None, action=None, "
                "next_observation=None, context=None):\n"
                "    assert observation is not None and next_observation is not None\n"
                "    assert len(action) == 6 and context['episode_step'] == 1\n"
                "    return float(action[0] + SEED / 1000 + (0.1 if context['team'] == 'blue' else 0))\n",
                encoding="utf-8",
            )
            reward = ManagedStudentReward(source, timeout_seconds=4)
            env = FlySwarmParallelEnv(max_steps=1, reward_function=reward)
            try:
                env.reset(seed=23)
                actions = {agent_id: np.zeros(6, dtype=np.float32) for agent_id in env.possible_agents}
                actions["blue_0"][0] = 0.5
                _, _, _, _, infos = env.step(actions)
                self.assertAlmostEqual(infos["blue_0"]["training_reward"], 0.623, places=6)
                self.assertAlmostEqual(infos["red_0"]["training_reward"], 0.023, places=6)
                self.assertNotAlmostEqual(infos["blue_0"]["standard_evaluation_reward"], 0.623, places=3)
            finally:
                env.close()

    def test_parameter_sharing_progress_distinguishes_agent_and_world_steps(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "shared-ppo"
            progress = output / "progress.json"
            result = train_sb3_ppo(
                output, timesteps=16, seed=81, max_steps=2,
                progress_path=progress, ppo_architecture="parameter_sharing",
            )
            self.assertEqual(result["timesteps"], 16)
            import json
            state = json.loads(progress.read_text(encoding="utf-8"))
            self.assertEqual(state["ppo_transitions"], 16)
            self.assertEqual(state["agent_transitions"], 16)
            self.assertEqual(state["world_steps"], 2)
            self.assertGreaterEqual(state["ppo_updates"], 1)


if __name__ == "__main__":
    unittest.main()
