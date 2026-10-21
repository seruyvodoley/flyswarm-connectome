import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env

from flyswarm.training.combat import (
    ACTION_NAMES, GAME_FEATURES, NEURAL_CHANNELS, SCHEMA, TankCombatEnv,
    _beats_evaluation, prepare_deployment, run_training, stage_for,
)
from flyswarm.bridge.server import combat_features


def _config(output: Path, **overrides):
    values = {
        "training_stage": "pretraining",
        "training_program": "automatic",
        "training_steps": 16,
        "training_time_minutes": 1,
        "training_seconds": 30,
        "training_seed": 31,
        "checkpoint_interval": 64,
        "training_vehicle": "t34_85",
        "resume_checkpoint": "",
    }
    values.update(overrides)
    return values


def test_combat_environment_spaces_features_and_curriculum():
    env = TankCombatEnv(4, malecns=False, max_seconds=30)
    try:
        check_env(env, skip_render_check=True)
        observation, info = env.reset(seed=9)
        assert observation.shape == (22,)
        assert np.all(observation[:6] == 0)
        assert not info["male_cns_active"]
        assert [stage_for(v, 100, "automatic") for v in (0, 20, 40, 55, 70, 90)] == [
            "MOVEMENT", "AIMING", "GUNNERY", "MOVING_TARGET", "TACTICS", "FULL_BATTLE"
        ]
        observation, reward, terminated, truncated, _ = env.step(np.zeros(6, dtype=np.float32))
        assert observation.shape == (22,) and np.isfinite(reward)
        assert not (terminated and truncated)
    finally:
        env.close()


def test_deployment_quality_gate_compares_combat_metrics_not_training_return():
    baseline={"win_rate":.5,"mean_damage":.6,"accuracy":.9,"mean_stuck_recoveries":0,"mean_return":-10}
    worse={"win_rate":0,"mean_damage":0,"accuracy":0,"mean_stuck_recoveries":10,"mean_return":1000}
    tie={**baseline,"mean_return":9999}
    better={**baseline,"win_rate":.6,"mean_return":-9999}
    assert not _beats_evaluation(worse,baseline)
    assert not _beats_evaluation(tie,baseline)
    assert _beats_evaluation(better,baseline)


def test_episode_info_is_only_emitted_for_completed_episode():
    env = TankCombatEnv(4, malecns=False, max_seconds=1)
    try:
        env.reset(seed=9)
        total=0.0
        for _ in range(env.max_steps - 1):
            _, reward, terminated, truncated, info = env.step(np.zeros(6, dtype=np.float32));total+=reward
            assert not terminated and not truncated
            assert "episode" not in info
        _, reward, terminated, truncated, info = env.step(np.zeros(6, dtype=np.float32));total+=reward
        assert truncated and not terminated
        assert info["episode"]["l"] == env.max_steps
        assert info["episode"]["r"] == pytest.approx(total)
        assert set(info["episode"]["reward_components"]) == {
            "distance_progress", "obstacle_collision", "stuck", "aim_alignment",
            "damage_dealt", "missed_shot", "damage_received", "victory", "defeat"}
    finally:
        env.close()


def test_ppo_training_crosses_rollout_after_episode_without_reward_key_error(tmp_path):
    config = _config(
        tmp_path,
        training_steps=512,
        # Complete 1-second episodes before the 384-step logger boundary.
        training_seconds=1,
        checkpoint_interval=10000,
    )
    run_training(config, tmp_path, lambda **values: None, lambda: None)
    progress = json.loads((tmp_path / "progress.json").read_text())
    assert progress["state"] == "complete"
    assert progress["timesteps"] >= 512
    assert progress["episodes"] >= 1


def test_short_ppo_checkpoint_resume_stop_and_deployment(tmp_path):
    checks = []
    config = _config(tmp_path)
    run_training(config, tmp_path, lambda **values: checks.append(values), lambda: None)
    checkpoint = tmp_path / "checkpoints/latest.zip"
    assert checkpoint.is_file()
    metadata = json.loads((tmp_path / "checkpoints/latest.json").read_text())
    assert metadata["schema"] == SCHEMA
    assert metadata["schema_version"] == 2
    assert metadata["features"] == list(NEURAL_CHANNELS) + list(GAME_FEATURES)
    assert metadata["actions"] == list(ACTION_NAMES)
    assert metadata["architecture"] == "MlpPolicy: pi=[128,128], vf=[128,128]"
    assert metadata["independent_evaluation"] == "completed_independent_analytic_evaluation"
    assert len(metadata["sha256"]) == 64
    assert json.loads((tmp_path / "evaluation.json").read_text())["current_policy"]["episodes"]
    first_steps = json.loads((tmp_path / "progress.json").read_text())["timesteps"]

    import torch
    from stable_baselines3 import PPO

    first = PPO.load(str(checkpoint), device="cpu")
    first_weights = [parameter.detach().cpu().clone() for parameter in first.policy.parameters()]
    resume_out = tmp_path / "resume"
    resume_out.mkdir()
    resumed_config = _config(resume_out, resume_checkpoint=str(checkpoint), training_seed=32)
    run_training(resumed_config, resume_out, lambda **values: None, lambda: None)
    second_checkpoint = resume_out / "checkpoints/latest.zip"
    second = PPO.load(str(second_checkpoint), device="cpu")
    assert second.num_timesteps > first_steps
    assert any(not torch.equal(before, after.detach().cpu())
               for before, after in zip(first_weights, second.policy.parameters()))
    assert json.loads((resume_out / "manifest.json").read_text())["resume_checkpoint"] == str(checkpoint)

    deploy = resume_out / "deployment"
    with pytest.raises(ValueError,match="MaleCNS fine-tuning"):
        prepare_deployment(second_checkpoint, deploy)


def test_all_22_training_and_runtime_features_match_for_same_state():
    env=TankCombatEnv(71,malecns=False,max_seconds=30)
    try:
        expected,_=env.reset(seed=16)
        delta=env.target_pos-env.own_pos
        distance=float(np.linalg.norm(delta))
        hull_error=(float(np.arctan2(delta[1],delta[0]))-env.own_heading+np.pi)%(2*np.pi)-np.pi
        turret_error=(hull_error-env.turret+np.pi)%(2*np.pi)-np.pi
        runtime_observation={
            "bearing":turret_error,"visible":env.visible,"target_distance_m":distance,
            "turret_angle_rad":env.turret,"gun_angle_rad":env.elevation,
            "own_health_fraction":env.own_health,"target_health_observed":env.target_health,
            "proprio":[env.own_speed/env.profile["max_speed_m_s"],0.0,
                env.reload/env.profile["reload_s"],env.turret/np.pi,env.elevation,1.0],
        }
        actual=combat_features(np.zeros(6),runtime_observation)
        assert expected.shape==(22,) and actual.shape==(22,)
        np.testing.assert_allclose(actual,expected,rtol=1e-6,atol=1e-6)
    finally:
        env.close()


def test_cancelled_training_still_saves_checkpoint_without_long_evaluation(tmp_path):
    class Cancelled(Exception):
        pass

    calls = 0

    def check():
        nonlocal calls
        calls += 1
        if calls >= 1:
            raise Cancelled()

    run_training(_config(tmp_path), tmp_path, lambda **values: None, check)
    progress = json.loads((tmp_path / "progress.json").read_text())
    report = json.loads((tmp_path / "evaluation.json").read_text())
    assert progress["state"] == "cancelled"
    assert (tmp_path / "checkpoints/latest.zip").is_file()
    assert "evaluation_skipped" in report


def test_supervised_application_job_runs_combat_training(tmp_path):
    output=tmp_path/"job-output"
    output.mkdir()
    config=_config(output, mode="combat_training", combat_action="train",
                   parent_pid=os.getpid(), dataset_path="")
    config["output"] = str(output)
    config_path=tmp_path/"job.json"
    config_path.write_text(json.dumps(config),encoding="utf-8")
    root=Path(__file__).resolve().parents[1]
    env={**os.environ,"PYTHONPATH":str(root/"src")}
    subprocess.run([sys.executable,str(root/"tools/app_job.py"),str(config_path)],
                   cwd=root,env=env,check=True,timeout=30,capture_output=True,text=True)
    progress=json.loads((output/"progress.json").read_text(encoding="utf-8"))
    assert progress["state"]=="complete"
    assert (output/"checkpoints/latest.zip").is_file()
