import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
from gymnasium.utils.env_checker import check_env

from flyswarm.training.combat import (
    SCHEMA, TankCombatEnv, prepare_deployment, run_training, stage_for,
)
from flyswarm.bridge.server import combat_features, load_policy


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
        assert [stage_for(v, 100, "automatic") for v in (0, 20, 40, 60, 80)] == [
            "MOVEMENT", "AIMING", "GUNNERY", "TACTICS", "FULL_BATTLE"
        ]
        observation, reward, terminated, truncated, _ = env.step(np.zeros(6, dtype=np.float32))
        assert observation.shape == (22,) and np.isfinite(reward)
        assert not (terminated and truncated)
    finally:
        env.close()


def test_episode_info_is_only_emitted_for_completed_episode():
    env = TankCombatEnv(4, malecns=False, max_seconds=1)
    try:
        env.reset(seed=9)
        for _ in range(env.max_steps - 1):
            _, _, terminated, truncated, info = env.step(np.zeros(6, dtype=np.float32))
            assert not terminated and not truncated
            assert "episode" not in info
        _, _, terminated, truncated, info = env.step(np.zeros(6, dtype=np.float32))
        assert truncated and not terminated
        assert info["episode"]["l"] == env.max_steps
        assert "r" in info["episode"]
    finally:
        env.close()


def test_ppo_training_crosses_rollout_after_episode_without_reward_key_error(tmp_path):
    config = _config(
        tmp_path,
        training_steps=512,
        # Match the failing session's completed episode at timestep 285;
        # the next PPO log boundary is timestep 384.
        training_seconds=57,
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
    manifest = prepare_deployment(second_checkpoint, deploy)
    assert manifest["connectome_modified"] is False
    assert manifest["current_open_day_runtime_compatible"] is True
    assert (deploy / "policy.zip").is_file()
    runtime_policy=load_policy(deploy/"policy.zip")
    runtime_observation={"bearing":.1,"visible":True,"target_distance_m":150.0,
                         "turret_angle_rad":0.0,"gun_angle_rad":0.0,
                         "target_health_observed":1.0,"proprio":[0.2,0.0,0.3,0.0,0.0,1.0],
                         "rl_task":[0.0,0.0,0.8]}
    runtime_features=combat_features(np.zeros(6),runtime_observation)
    action,_=runtime_policy.act(runtime_features)
    assert runtime_features.shape==(22,) and action.shape==(6,)


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
