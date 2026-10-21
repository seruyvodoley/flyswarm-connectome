"""Resumable PPO training for an external MaleCNS combat controller.

The connectome is always frozen. In MaleCNS mode the real FlyBrain(batch=1)
produces sensory motor features consumed by PPO; in gameplay pretraining those
six explicitly unavailable channels are zero and are never labelled biological.
The environment is a small deterministic analytical tank duel, not Godot.
"""
from __future__ import annotations

import csv
import hashlib
import json
import importlib.metadata
import math
import os
import platform
import random
import time
from pathlib import Path

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from flyswarm.brain.demo import DemoBrain
from flyswarm.marl.roles import vehicle_profile

SCHEMA = "flyswarm_malecns_combat_v2"
ACTION_NAMES = ("throttle", "brake", "steering", "turret", "elevation", "fire")
NEURAL_CHANNELS = ("DNp09_L", "DNp09_R", "DNa02_L", "DNa02_R", "DNp01", "wing_song")
GAME_FEATURES = (
    "speed_fraction", "distance_fraction", "target_bearing_sin", "target_bearing_cos",
    "hull_error_sin", "hull_error_cos", "turret_error_sin", "turret_error_cos",
    "gun_elevation", "reload_fraction", "own_health", "target_health",
    "target_visible", "obstacle_left", "obstacle_right", "last_damage",
)
REWARD_COMPONENTS = ("distance_progress", "obstacle_collision", "stuck", "aim_alignment",
                     "damage_dealt", "missed_shot", "damage_received", "victory", "defeat")


def _wrap(angle: float) -> float:
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def combat_feature_vector(neural_trace, state: dict) -> np.ndarray:
    """Build the versioned 22-value PPO observation from canonical world state.

    ``target_bearing_rad`` and ``hull_error_rad`` are both hull-relative in the
    current simulator (the former is retained for schema compatibility).
    Runtime ``bearing_rad`` is turret-relative and is converted by adding the
    turret angle before calling this function.
    """
    neural = np.log1p(np.maximum(0.0, np.asarray(neural_trace, dtype=np.float32))) / 5.0
    if neural.shape != (len(NEURAL_CHANNELS),):
        raise ValueError(f"Expected {len(NEURAL_CHANNELS)} neural inputs, got {neural.shape}")
    game = np.asarray([
        float(state["speed_fraction"]), min(max(0.0, float(state["distance_m"])) / 500.0, 2.0),
        math.sin(float(state["target_bearing_rad"])), math.cos(float(state["target_bearing_rad"])),
        math.sin(float(state["hull_error_rad"])), math.cos(float(state["hull_error_rad"])),
        math.sin(float(state["turret_error_rad"])), math.cos(float(state["turret_error_rad"])),
        float(state["gun_elevation_rad"]) / .5, float(state["reload_fraction"]),
        float(state["own_health"]), float(state["target_health"] if state["visible"] else 1.0),
        float(bool(state["visible"])), float(state.get("obstacle_left", 0.0)),
        float(state.get("obstacle_right", 0.0)), float(state.get("last_damage", 0.0)),
    ], dtype=np.float32)
    return np.concatenate((neural, game)).astype(np.float32, copy=False)


def stage_for(step: int, total: int, program: str) -> str:
    if program == "full_battle":
        return "FULL_BATTLE"
    fraction = min(1.0, max(0.0, step / max(1, total)))
    return ("MOVEMENT" if fraction < .14 else "AIMING" if fraction < .28
            else "GUNNERY" if fraction < .44 else "MOVING_TARGET" if fraction < .60
            else "TACTICS" if fraction < .80 else "FULL_BATTLE")


class TankCombatEnv(gym.Env):
    """One-vs-one tank-control approximation with optional real MaleCNS input."""
    metadata = {"render_modes": []}

    def __init__(self, seed: int, vehicle: str = "t34_85", malecns: bool = True,
                 max_seconds: int = 180, program: str = "automatic"):
        super().__init__()
        self.seed_value = int(seed)
        self.profile = vehicle_profile(vehicle)
        self.vehicle_id = vehicle
        self.use_malecns = bool(malecns)
        # Match Godot's 50 Hz physics and DemoBrain's pinned 20 ms neural tick.
        # A PPO action is held for one real controller tick, not 200 ms.
        self.dt = .02
        self.max_steps = max(1, int(max_seconds * 50))
        self.program = program
        self.training_step = 0
        self.training_total = 1
        self.brain = DemoBrain(seed=seed) if self.use_malecns else None
        self.action_space = spaces.Box(-1.0, 1.0, (6,), dtype=np.float32)
        self.observation_space = spaces.Box(-10.0, 10.0, (len(NEURAL_CHANNELS) + len(GAME_FEATURES),), dtype=np.float32)
        self.rng = np.random.default_rng(seed)
        self.reset(seed=seed)

    def set_schedule(self, step: int, total: int) -> None:
        self.training_step = int(step)
        self.training_total = int(total)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self.rng = np.random.default_rng(int(seed))
            self.seed_value = int(seed)
        self.steps = 0
        self.elapsed = 0.0
        self.episode_reward = 0.0
        self.reward_totals = {}
        self.own_pos = np.zeros(2, dtype=np.float64)
        angle = float(self.rng.uniform(-math.pi, math.pi))
        distance = float(self.rng.uniform(125.0, 310.0))
        self.target_pos = np.array([math.cos(angle), math.sin(angle)]) * distance
        self.own_heading = float(self.rng.uniform(-math.pi, math.pi))
        self.target_heading = _wrap(angle + math.pi + float(self.rng.uniform(-.5, .5)))
        stage=stage_for(self.training_step,self.training_total,self.program)
        stage_opponents={
            "MOVEMENT":["stationary"],"AIMING":["stationary"],"GUNNERY":["stationary"],
            "MOVING_TARGET":["moving"],"TACTICS":["moving","rule"],
            "FULL_BATTLE":["stationary","moving","rule","aggressive"],
        }
        self.target_type = str(self.rng.choice(stage_opponents.get(stage,["stationary","moving","rule","aggressive"])))
        self.target_speed = 0.0
        self.own_speed = 0.0
        self.own_health = 1.0
        self.target_health = 1.0
        self.reload = 0.0
        self.turret = 0.0
        self.elevation = 0.0
        self.obstacle_angle = float(self.rng.uniform(-math.pi, math.pi))
        self.obstacle_radius = float(self.rng.uniform(28.0, 65.0))
        self.obstacle_offset = float(self.rng.uniform(-.35, .35))
        self.last_damage = 0.0
        self.shots = self.hits = self.damage_dealt = self.distance_travelled = 0.0
        self.stuck_steps = 0
        self.stuck_recoveries = 0
        self.visible = False
        if self.brain is not None:
            self.brain.reset(self.seed_value)
        return self._observation(), {"stage": stage_for(self.training_step, self.training_total, self.program),
                                     "male_cns_active": self.use_malecns}

    def _relative(self):
        delta = self.target_pos - self.own_pos
        distance = float(np.linalg.norm(delta))
        bearing = _wrap(math.atan2(float(delta[1]), float(delta[0])) - self.own_heading)
        visible = distance > self.obstacle_radius + 9.0 and abs(_wrap(math.atan2(float(delta[1]), float(delta[0])) - self.obstacle_angle)) > self.obstacle_offset
        # A deterministic ten-second concealment window gives training varied approach conditions.
        visible = visible and self.elapsed >= 10.0
        return delta, distance, bearing, visible

    def _neural(self, bearing: float, distance: float, visible: bool):
        if self.brain is None:
            return np.zeros(len(NEURAL_CHANNELS), dtype=np.float32)
        target = {"alive": self.target_health > 0, "position": [float(self.target_pos[0]), 0.0, float(self.target_pos[1])],
                  "bearing": float(bearing), "visible": bool(visible),
                  "looming": max(0.0, float(np.dot(self.target_pos - self.own_pos,
                      np.array([math.cos(self.target_heading), math.sin(self.target_heading)]))) / max(distance, 1.0))}
        observations = [{"alive": False, "position": [0.0, 0.0, 0.0]} for _ in range(16)]
        observations[0] = {"alive": self.target_health > 0, "position": target["position"]}
        observations[8] = target
        traces, _heard, _elapsed_ms = self.brain.step(observations, "no_audio")
        # Log scaling keeps spike-rate features numerically comparable with state inputs.
        return np.log1p(np.maximum(0.0, traces[8])).astype(np.float32) / 5.0

    def _observation(self):
        delta, distance, bearing, visible = self._relative()
        self.visible = visible
        world_bearing = math.atan2(float(delta[1]), float(delta[0]))
        hull_error = _wrap(world_bearing - self.own_heading)
        turret_error = _wrap(hull_error - self.turret)
        speed = float(self.profile["max_speed_m_s"])
        return combat_feature_vector(self._neural(bearing, distance, visible), {
            "speed_fraction": self.own_speed / max(1.0, speed), "distance_m": distance,
            "target_bearing_rad": bearing, "hull_error_rad": hull_error,
            "turret_error_rad": turret_error, "gun_elevation_rad": self.elevation,
            "reload_fraction": self.reload / max(.1, float(self.profile["reload_s"])),
            "own_health": self.own_health, "target_health": self.target_health,
            "visible": visible,
        })

    def step(self, action):
        action = np.clip(np.asarray(action, dtype=np.float32), -1.0, 1.0)
        previous_distance = float(np.linalg.norm(self.target_pos - self.own_pos))
        self.steps += 1
        self.elapsed += self.dt
        p = self.profile
        self.own_heading = _wrap(self.own_heading + float(action[2]) * float(p["turn_rate_rad_s"]) * self.dt)
        self.turret = float(np.clip(self.turret + float(action[3]) * float(p["turret_rate_rad_s"]) * self.dt,
                                    -float(p["traverse_limit_rad"]), float(p["traverse_limit_rad"])))
        self.elevation = float(np.clip(self.elevation + float(action[4]) * float(p["gun_rate_rad_s"]) * self.dt,
                                       float(p["elevation_min_rad"]), float(p["elevation_max_rad"])))
        accel = float(p["accel_m_s2"])
        self.own_speed += (float(action[0]) * accel - max(0.0, float(action[1])) * 8.0 - self.own_speed * .32) * self.dt
        self.own_speed = float(np.clip(self.own_speed, -float(p["reverse_m_s"]), float(p["max_speed_m_s"])))
        direction = np.array([math.cos(self.own_heading), math.sin(self.own_heading)])
        move = direction * self.own_speed * self.dt
        next_pos = self.own_pos + move
        # A soft circular obstacle models collision, route choice and getting unstuck.
        obstacle = np.array([math.cos(self.obstacle_angle), math.sin(self.obstacle_angle)]) * self.obstacle_radius
        collision = float(np.linalg.norm(next_pos - obstacle)) < 15.0
        if collision:
            self.own_speed *= -.18
            self.stuck_steps += 1
            self.stuck_recoveries += 1
        else:
            self.own_pos = next_pos
            self.distance_travelled += float(np.linalg.norm(move))
            self.stuck_steps = max(0, self.stuck_steps - 1)
        self.target_heading = _wrap(self.target_heading + float(self.rng.normal(0, .08)))
        if self.target_type == "moving":
            self.target_speed = 3.0
        elif self.target_type in ("rule", "aggressive"):
            self.target_speed = 2.2 if self.target_type == "rule" else 4.5
            toward = math.atan2(float(self.own_pos[1] - self.target_pos[1]), float(self.own_pos[0] - self.target_pos[0]))
            self.target_heading = _wrap(self.target_heading + np.clip(_wrap(toward - self.target_heading), -.5, .5) * .25)
        self.target_pos += np.array([math.cos(self.target_heading), math.sin(self.target_heading)]) * self.target_speed * self.dt
        self.reload = max(0.0, self.reload - self.dt)
        delta, distance, bearing, visible = self._relative()
        world_bearing = math.atan2(float(delta[1]), float(delta[0]))
        gun_error = _wrap(world_bearing - self.own_heading - self.turret)
        reward = 0.0
        reward_components = {}
        def add_reward(name: str, amount: float) -> None:
            nonlocal reward
            value=float(amount)
            reward += value
            reward_components[name]=reward_components.get(name,0.0)+value
        if self.program == "automatic":
            stage = stage_for(self.training_step, self.training_total, self.program)
        else:
            stage = "FULL_BATTLE"
        if stage in ("MOVEMENT", "TACTICS", "FULL_BATTLE"):
            add_reward("distance_progress",float(np.clip(previous_distance - distance, -2.0, 2.0)) * (.0002 if stage == "MOVEMENT" else .00005))
            if collision: add_reward("obstacle_collision",-.12)
            if self.stuck_steps > 15: add_reward("stuck",-.016)
        if visible and stage in ("AIMING", "GUNNERY", "MOVING_TARGET", "TACTICS", "FULL_BATTLE"):
            add_reward("aim_alignment",max(0.0, 1.0 - abs(gun_error) / .6) * .0002)
        self.last_damage = 0.0
        if action[5] > .5 and self.reload <= 0.0:
            self.shots += 1.0
            self.reload = float(p["reload_s"])
            if visible and distance < float(p["effective_range_m"]) and abs(gun_error) < .14 and abs(self.elevation) < .22:
                damage = min(self.target_health, float(p["damage_per_hit"]))
                self.target_health -= damage
                self.last_damage = damage
                self.damage_dealt += damage
                self.hits += 1.0
                add_reward("damage_dealt",damage * (5.0 if stage in ("GUNNERY", "MOVING_TARGET", "TACTICS", "FULL_BATTLE") else .5))
            elif stage in ("GUNNERY", "MOVING_TARGET", "TACTICS", "FULL_BATTLE"):
                add_reward("missed_shot",-.05)
        # Opponent periodically engages after spotting the player.
        if visible and distance < 420.0 and int(self.elapsed * 5) % 22 == 0:
            enemy_error = abs(_wrap(math.atan2(float(self.own_pos[1]-self.target_pos[1]), float(self.own_pos[0]-self.target_pos[0])) - self.target_heading))
            if enemy_error < .35:
                self.own_health = max(0.0, self.own_health - (.10 if self.target_type == "aggressive" else .05))
                self.last_damage = 1.0 - self.own_health
                add_reward("damage_received",-self.last_damage * (5.0 if stage == "FULL_BATTLE" else 1.0))
        terminated = self.target_health <= 0.0 or self.own_health <= 0.0
        truncated = self.steps >= self.max_steps
        if self.target_health <= 0.0: add_reward("victory",20.0)
        if self.own_health <= 0.0: add_reward("defeat",-20.0)
        self.episode_reward += reward
        for name in REWARD_COMPONENTS:
            self.reward_totals[name]=self.reward_totals.get(name,0.0)+reward_components.get(name,0.0)
        obs = self._observation()
        info = {"stage": stage, "male_cns_active": self.use_malecns,
                "shots": int(self.shots), "hits": int(self.hits),
                "damage": float(self.damage_dealt), "distance_m": float(self.distance_travelled),
                "stuck": self.stuck_steps > 15, "stuck_recoveries": self.stuck_recoveries,
                "own_health": self.own_health,
                "target_health": self.target_health, "target_type": self.target_type,
                "visible": visible}
        # Gymnasium/SB3 reserve the "episode" info key for completed Monitor
        # summaries. An empty dict on every ordinary step is still interpreted
        # as a completed episode by SB3 and later causes KeyError("r") while
        # the rollout logger reads episode rewards.
        if terminated or truncated:
            info["episode"] = {"r": float(self.episode_reward), "l": self.steps,
                                "reward_components": {key:round(value,6) for key,value in self.reward_totals.items()}}
        return obs, float(reward), terminated, truncated, info

    def close(self):
        # FlyBrain owns its arrays; dropping the sole instance releases resources.
        self.brain = None


def _atomic_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _atomic_model(model, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.stem + ".pending.zip")
    model.save(str(temp))
    os.replace(temp, path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_malecns_dataset() -> dict:
    """Read-only validation against FlyBrain's pinned release hashes."""
    from flybrain.data import DATA, FILES, has_data
    root=Path(os.environ.get("FLY_DATA",DATA))
    if not has_data(root):
        raise RuntimeError(f"MaleCNS training requires brain.npz and weights.npz in {root}")
    hashes={}
    for name,expected in FILES.items():
        digest=hashlib.sha256()
        with (root/name).open("rb") as source:
            for block in iter(lambda:source.read(1 << 20),b""):digest.update(block)
        actual=digest.hexdigest()
        if actual!=expected:raise RuntimeError(f"MaleCNS file checksum mismatch: {root/name}")
        hashes[name]=actual
    return {"path":str(root),"sha256":hashes}


def _verified_checkpoint_metadata(path: Path) -> dict:
    sidecar=path.with_suffix(".json")
    if not sidecar.exists():sidecar=path.parent/"metadata.json"
    if not sidecar.is_file():raise ValueError("Checkpoint metadata is missing; only FlySwarm combat checkpoints can be resumed or deployed.")
    metadata=json.loads(sidecar.read_text(encoding="utf-8"))
    if metadata.get("schema")!=SCHEMA or metadata.get("schema_version")!=2:raise ValueError("Checkpoint feature schema is incompatible; legacy combat checkpoints require explicit retraining/export")
    features=metadata.get("features",metadata.get("feature_schema"))
    actions=metadata.get("actions",metadata.get("action_schema"))
    if features!=list(NEURAL_CHANNELS)+list(GAME_FEATURES):raise ValueError("Checkpoint feature layout is incompatible")
    if actions!=list(ACTION_NAMES):raise ValueError("Checkpoint action layout is incompatible")
    if metadata.get("architecture") != "MlpPolicy: pi=[128,128], vf=[128,128]":
        raise ValueError("Checkpoint PPO architecture is missing or incompatible")
    if metadata.get("male_cns_required") not in (True, False):
        raise ValueError("Checkpoint MaleCNS/pretraining provenance is missing")
    expected=metadata.get("sha256",metadata.get("checkpoint_sha256"))
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    if expected!=actual:raise ValueError("Checkpoint checksum mismatch")
    return metadata


def _checkpoint_metadata(model, *, digest: str, seed: int, malecns: bool,
                         vehicle: str, program: str, requested_steps: int,
                         resume_path: Path | None, evaluation_status: str,
                         resume_source_mode: str = "", dataset_metadata: dict | None = None,
                         imitation_metadata: dict | None = None) -> dict:
    return {
        "schema": SCHEMA, "schema_version": 2,
        "algorithm": "Stable-Baselines3 PPO",
        "architecture": "MlpPolicy: pi=[128,128], vf=[128,128]",
        "features": list(NEURAL_CHANNELS) + list(GAME_FEATURES),
        "actions": list(ACTION_NAMES),
        "training_stage": "malecns_finetuning" if malecns else "gameplay_pretraining",
        "male_cns_required": bool(malecns), "connectome_modified": False,
        "male_cns_dataset": dataset_metadata,
        "imitation_pretraining": imitation_metadata or {"used":False,"samples":0,"epochs":0},
        "vehicle": vehicle, "program": program, "seed": int(seed),
        "steps": int(model.num_timesteps), "requested_steps": int(requested_steps),
        "environment": "analytical_tank_duel_v1",
        "hyperparameters": {"learning_rate": float(model.learning_rate) if isinstance(model.learning_rate, (int, float)) else None,
            "n_steps": int(model.n_steps),
            "batch_size": int(model.batch_size), "n_epochs": int(model.n_epochs),
            "gamma": float(model.gamma), "gae_lambda": float(model.gae_lambda),
            "clip_range": float(model.clip_range(1.0) if callable(model.clip_range) else model.clip_range),
            "ent_coef": float(model.ent_coef), "vf_coef": float(model.vf_coef),
            "max_grad_norm": float(model.max_grad_norm),
            "normalize_advantage": bool(model.normalize_advantage)},
        "versions": {"python": platform.python_version(),
            "stable_baselines3": importlib.metadata.version("stable-baselines3"),
            "gymnasium": importlib.metadata.version("gymnasium"),
            "numpy": np.__version__},
        "resumed_from": str(resume_path or ""),
        "resume_source_mode": resume_source_mode,
        "pretraining_to_malecns_finetuning": resume_source_mode == "gameplay_pretraining" and malecns,
        "optimizer_state": "included by Stable-Baselines3 PPO archive",
        "independent_evaluation": evaluation_status,
        "sha256": digest,
    }


def _rule_action(observation):
    game=observation[len(NEURAL_CHANNELS):]
    distance=float(game[1])*500.0
    hull_error=math.atan2(float(game[4]),float(game[5]))
    turret_error=math.atan2(float(game[6]),float(game[7]))
    speed=float(game[0]);visible=bool(game[12]);reload=float(game[9])
    return np.asarray([np.clip((distance-70.0)/160.0,0.0,.72),0.0,
                       np.clip(hull_error*1.3,-.8,.8),np.clip(turret_error*1.5,-1.0,1.0),
                       np.clip(-float(game[8])*.6,-.5,.5),
                       1.0 if visible and reload<.08 and abs(turret_error)<.09 else -1.0],dtype=np.float32)


def _evaluate(model, env, seed: int, episodes: int = 3, ablate_neural: bool = False):
    rows=[]
    for i in range(episodes):
        obs,_=env.reset(seed=seed+i*997)
        total=0.0;steps=0;info={}
        while steps<env.max_steps:
            policy_obs=obs.copy()
            if ablate_neural:policy_obs[:len(NEURAL_CHANNELS)]=0.0
            action=_rule_action(policy_obs) if model is None else model.predict(policy_obs, deterministic=True)[0]
            obs,reward,terminated,truncated,info=env.step(action);total+=reward;steps+=1
            if terminated or truncated:break
        rows.append({"seed":seed+i*997,"return":round(total,4),"win":bool(info.get("target_health",1.0)<=0),
                     "shots":info.get("shots",0),"hits":info.get("hits",0),"damage":round(float(info.get("damage",0)),4),
                     "duration_s":round(steps*env.dt,2),"distance_m":round(float(info.get("distance_m",0)),2),
                     "stuck":bool(info.get("stuck",False)),"stuck_recoveries":int(info.get("stuck_recoveries",0))})
    return {"episodes":rows,"win_rate":float(np.mean([r["win"] for r in rows])),
            "accuracy":float(sum(r["hits"] for r in rows)/max(1,sum(r["shots"] for r in rows))),
            "mean_damage":float(np.mean([r["damage"] for r in rows])),
            "mean_shots":float(np.mean([r["shots"] for r in rows])),
            "mean_duration_s":float(np.mean([r["duration_s"] for r in rows])),
            "mean_distance_m":float(np.mean([r["distance_m"] for r in rows])),
            "mean_stuck_recoveries":float(np.mean([r["stuck_recoveries"] for r in rows])),
            "mean_return":float(np.mean([r["return"] for r in rows]))}


def _evaluation_score(metrics: dict) -> tuple[float, float, float, float]:
    """Order evaluation outcomes by combat results, never by training reward."""
    return (float(metrics.get("win_rate", 0.0)), float(metrics.get("mean_damage", 0.0)),
            float(metrics.get("accuracy", 0.0)), -float(metrics.get("mean_stuck_recoveries", 0.0)))


def _beats_evaluation(candidate: dict, reference: dict) -> bool:
    """Require a strict independent improvement over the fixed Rule AI baseline."""
    return _evaluation_score(candidate) > _evaluation_score(reference)


def _behavior_clone_rule(model, env: TankCombatEnv, samples: int, seed: int,
                         epochs: int, status, check) -> dict:
    """Optional, explicitly labelled Rule-AI imitation initialization for PPO."""
    import torch
    from torch.nn.utils import clip_grad_norm_
    count=max(0,int(samples))
    if count==0:return {"used":False,"samples":0,"epochs":0}
    env.program="full_battle"
    previous_max_steps=env.max_steps
    # Demonstrations must cover visibility, aiming, reload and multiple target
    # layouts. A single long episode often ends before enough firing states are
    # collected, leaving the fire output trained on one accidental example.
    demo_max_steps=min(previous_max_steps,max(1,int(20.0/env.dt)))
    env.max_steps=demo_max_steps
    observations=np.empty((count,22),dtype=np.float32)
    actions=np.empty((count,6),dtype=np.float32)
    obs,_=env.reset(seed=seed+300_000)
    demo_episodes=1
    for index in range(count):
        if index%512==0:
            check()
            status(state="imitation_pretraining",samples=index,target_samples=count,
                   male_cns_active=env.use_malecns,
                   message="Collecting Rule AI demonstrations; this is not PPO training")
        action=_rule_action(obs)
        observations[index]=obs
        actions[index]=action
        obs,_,terminated,truncated,_=env.step(action)
        if terminated or truncated:
            demo_episodes+=1
            obs,_=env.reset(seed=seed+300_001+index)
    env.max_steps=previous_max_steps
    x=torch.as_tensor(observations,dtype=torch.float32)
    y=torch.as_tensor(actions,dtype=torch.float32)
    fire_targets=(y[:,5]>0.0).to(torch.float32)
    positive_count=int(fire_targets.sum().item())
    fire_positive_weight=min(300.0,(count-positive_count)/max(1,positive_count))
    fire_loss=torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor(fire_positive_weight))
    generator=torch.Generator(device="cpu");generator.manual_seed(seed+300_002)
    batch_size=256
    for epoch in range(max(1,int(epochs))):
        check()
        indices=torch.randperm(count,generator=generator)
        for start in range(0,count,batch_size):
            batch=indices[start:start+batch_size]
            distribution=model.policy.get_distribution(x[batch])
            mean=distribution.distribution.mean.clamp(-1.0,1.0)
            target=y[batch]
            motor_loss=torch.nn.functional.mse_loss(mean[:,:5],target[:,:5])
            firing_loss=fire_loss(mean[:,5],fire_targets[batch])
            loss=motor_loss+firing_loss
            model.policy.optimizer.zero_grad()
            loss.backward()
            clip_grad_norm_(model.policy.parameters(),model.max_grad_norm)
            model.policy.optimizer.step()
    with torch.no_grad():
        prediction=model.policy.get_distribution(x).distribution.mean.clamp(-1.0,1.0)
        mse=float(torch.nn.functional.mse_loss(prediction[:,:5],y[:,:5]).item())
    return {"used":True,"samples":count,"epochs":max(1,int(epochs)),"training_mse":mse,
            "fire_positive_samples":positive_count,"fire_positive_fraction":positive_count/count,
            "fire_positive_loss_weight":fire_positive_weight,
            "demo_episodes":demo_episodes,"demo_episode_limit_seconds":round(demo_max_steps*env.dt,2),
            "teacher":"rule_action","method":"behavior_cloning_before_PPO"}


def run_training(config: dict, output: Path, status, check):
    """Create/resume PPO training; always checkpoint on normal stop or cancel."""
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback
    from stable_baselines3.common.buffers import RolloutBuffer
    from stable_baselines3.common.utils import ConstantSchedule

    malecns = config.get("training_stage", "malecns") == "malecns"
    dataset_metadata=_verify_malecns_dataset() if malecns else None
    seed = int(config.get("training_seed", 7))
    steps = int(config.get("training_steps", 512))
    max_seconds = int(config.get("training_seconds", 180))
    checkpoint_interval = int(config.get("checkpoint_interval", 256))
    time_limit = max(1, int(config.get("training_time_minutes", 60))) * 60.0
    program = str(config.get("training_program", "automatic"))
    vehicle = str(config.get("training_vehicle", "t34_85"))
    checkpoint_dir = output / "checkpoints"
    latest_path = checkpoint_dir / "latest.zip"
    best_path = checkpoint_dir / "best_evaluated.zip"
    resume = str(config.get("resume_checkpoint", ""))
    resume_path = Path(resume) if resume else None
    if resume_path and not resume_path.is_file():
        raise FileNotFoundError(f"Resume checkpoint not found: {resume_path}")
    resume_metadata = _verified_checkpoint_metadata(resume_path) if resume_path else {}
    resume_source_mode=str(resume_metadata.get("training_stage", ""))
    source_malecns=bool(resume_metadata.get("male_cns_required",False))
    if resume_path and source_malecns!=malecns:
        permitted=(not source_malecns and malecns and bool(config.get("allow_pretraining_to_malecns",False)))
        if not permitted:
            raise ValueError("Checkpoint input mode differs; explicitly enable Gameplay Pretraining → MaleCNS Fine-tuning to continue this model")
    if resume_path and malecns and source_malecns and resume_metadata.get("male_cns_dataset",{}).get("sha256") != dataset_metadata.get("sha256"):
        raise ValueError("MaleCNS dataset checksum differs from the checkpoint; refusing incompatible continuation")

    env = TankCombatEnv(seed, vehicle, malecns, max_seconds, program)
    n_steps = max(16, min(512, int(config.get("training_rollout_steps", 128))))
    batch_size = max(8, min(n_steps, int(config.get("training_batch_size", min(128, n_steps)))))
    n_epochs = max(1, int(config.get("training_epochs", 5)))
    learning_rate = max(1e-7, float(config.get("training_learning_rate", 3e-5 if resume_path else 3e-4)))
    if resume_path:
        model = PPO.load(str(resume_path), env=env, device="cpu")
        model.set_random_seed(seed)
        model.set_env(env)
        # Preserve the learned weights and optimizer moments while replacing
        # very short demonstration rollouts with a useful PPO horizon.
        if int(model.n_steps) != n_steps:
            model.n_steps = n_steps
            model.rollout_buffer = model.rollout_buffer_class(
                buffer_size=model.n_steps, observation_space=model.observation_space,
                action_space=model.action_space, device=model.device, gamma=model.gamma,
                gae_lambda=model.gae_lambda, n_envs=model.n_envs, **model.rollout_buffer_kwargs)
        model.batch_size = batch_size
        model.n_epochs = n_epochs
        model.learning_rate = learning_rate
        model.lr_schedule = ConstantSchedule(learning_rate)
    else:
        model = PPO("MlpPolicy", env, learning_rate=learning_rate, n_steps=n_steps,
                    batch_size=batch_size, n_epochs=n_epochs,
                    gamma=.99, gae_lambda=.95, clip_range=.2, seed=seed,
                    device="cpu", verbose=0,
                    policy_kwargs={"net_arch":{"pi":[128,128],"vf":[128,128]}})
    imitation_metadata=resume_metadata.get("imitation_pretraining",{"used":False,"samples":0,"epochs":0})
    if not resume_path and config.get("training_stage","malecns")=="pretraining":
        try:
            imitation_metadata=_behavior_clone_rule(model,env,
                int(config.get("imitation_samples",0)),seed,
                int(config.get("imitation_epochs",15)),status,check)
        except Exception:
            env.close()
            raise
    start_step=int(model.num_timesteps)
    schedule_total=start_step+steps
    env.set_schedule(start_step,schedule_total)
    started = time.monotonic()
    report_interval=max(256,min(2048,int(model.n_steps)*8))
    status(state="training",timesteps=start_step,target_timesteps=schedule_total,
           episodes=0,stage=stage_for(start_step,schedule_total,program),male_cns_active=malecns,
           steps_per_second=0.0,message="PPO initialized; collecting combat rollouts")
    curve_path = output / "metrics.csv"
    rows=[]
    if curve_path.exists():
        with curve_path.open(newline="",encoding="utf-8") as f: rows=list(csv.DictReader(f))

    def checkpoint_metadata(digest: str, evaluation_status: str = "not_evaluated") -> dict:
        return _checkpoint_metadata(model, digest=digest, seed=seed, malecns=malecns,
            vehicle=vehicle, program=program, requested_steps=steps,
            resume_path=resume_path, evaluation_status=evaluation_status,
            resume_source_mode=resume_source_mode,dataset_metadata=dataset_metadata,
            imitation_metadata=imitation_metadata)

    class Monitor(BaseCallback):
        def __init__(self):
            super().__init__(); self.last_save=0; self.last_report=0; self.episodes=len(rows); self.episode_rows=[]; self.cancelled=False
        def _on_step(self):
            step=int(self.num_timesteps); env.set_schedule(step, max(1,schedule_total))
            if time.monotonic()-started>=time_limit:
                self.stop_training=True
                return False
            try: check()
            except Exception as exc:
                if exc.__class__.__name__!="Cancelled":raise
                self.cancelled=True;self.stop_training=True
                return False
            pause=output/"pause"
            while pause.exists():
                status(state="paused",timesteps=step,target_timesteps=step+steps,
                       episodes=self.episodes,stage=stage_for(step,schedule_total,program),
                       male_cns_active=malecns,message="Paused; waiting for Resume")
                try:check()
                except Exception as exc:
                    if exc.__class__.__name__!="Cancelled":raise
                    self.cancelled=True;self.stop_training=True
                    return False
                if (output/"save_checkpoint").exists():
                    digest=_atomic_model(self.model,latest_path)
                    (output/"save_checkpoint").unlink(missing_ok=True)
                    _atomic_json(checkpoint_dir/"latest.json",checkpoint_metadata(digest))
                time.sleep(.25)
            if (output/"save_checkpoint").exists():
                digest=_atomic_model(self.model,latest_path);(output/"save_checkpoint").unlink(missing_ok=True)
                _atomic_json(checkpoint_dir/"latest.json",checkpoint_metadata(digest))
            infos=self.locals.get("infos",[])
            for info in infos:
                ep=info.get("episode") if isinstance(info,dict) else None
                if ep:
                    self.episodes+=1
                    row={"timesteps":step,"episodes":self.episodes,"stage":stage_for(step,schedule_total,program),
                         "episode_reward":float(ep.get("r",0)),"episode_steps":int(ep.get("l",0)),
                         "elapsed_seconds":round(time.monotonic()-started,3),
                         "male_cns_active":int(malecns)}
                    row.update({"reward_"+name:float(ep.get("reward_components",{}).get(name,0.0)) for name in REWARD_COMPONENTS})
                    self.episode_rows.append(row);rows.append(row)
                    with curve_path.open("w",newline="",encoding="utf-8") as f:
                        writer=csv.DictWriter(f,fieldnames=list(row));writer.writeheader();writer.writerows(rows)
            if step-self.last_save>=checkpoint_interval:
                digest=_atomic_model(self.model,latest_path);self.last_save=step
                _atomic_json(checkpoint_dir/"latest.json",checkpoint_metadata(digest))
                _atomic_json(output/"progress.json",{"state":"training","timesteps":step,
                    "target_timesteps":int(self.model._total_timesteps),"episodes":self.episodes,
                    "elapsed_seconds":round(time.monotonic()-started,2),
                    "stage":stage_for(step,schedule_total,program),"male_cns_active":malecns,
                    "steps_per_second":round(step/max(.001,time.monotonic()-started),2),
                    "latest_episode_reward":self.episode_rows[-1]["episode_reward"] if self.episode_rows else None,
                    "checkpoint":str(latest_path)})
            if step-self.last_report>=report_interval:
                elapsed=max(.001,time.monotonic()-started)
                rate=(step-start_step)/elapsed
                status(state="training",timesteps=step,target_timesteps=int(self.model._total_timesteps),
                       episodes=self.episodes,elapsed_seconds=round(time.monotonic()-started,2),
                       stage=stage_for(step,schedule_total,program),male_cns_active=malecns,
                       steps_per_second=round(rate,2),
                       eta_seconds=round(max(0,int(self.model._total_timesteps)-step)/max(.001,rate),1),
                       latest_episode_reward=self.episode_rows[-1]["episode_reward"] if self.episode_rows else None,
                       checkpoint=str(latest_path) if latest_path.exists() else "",
                       message="Training reward is a progress metric, not independent quality evidence")
                self.last_report=step
            return True

    monitor=Monitor()
    try:
        model.learn(total_timesteps=steps, callback=monitor, reset_num_timesteps=not bool(resume_path),
                    progress_bar=False)
        # Also flush a consistent checkpoint if user stopped before save interval.
        digest=_atomic_model(model,latest_path)
        _atomic_json(checkpoint_dir/"latest.json",checkpoint_metadata(digest))
        # Independent evaluation reuses one MaleCNS instance sequentially to stay within RAM limits.
        if monitor.cancelled:
            evaluation={"schema":SCHEMA,"independent_seeds":True,"male_cns_active":malecns,
                        "evaluation_skipped":"user stopped training; run Evaluate Model when ready",
                        "best_evaluated_checkpoint":str(best_path) if best_path.exists() else None}
        else:
            # Keep evaluation bounded even when training episodes are configured for hours.
            env.max_steps=min(env.max_steps,2250)
            evaluation_seed=seed+10000
            evaluation_episodes=max(3,int(config.get("evaluation_episodes",3)))
            status(state="evaluating_baseline",evaluation_episodes=evaluation_episodes,
                   male_cns_active=malecns,message="Evaluating the fixed Rule AI baseline on held-out seeds")
            baseline=_evaluate(None,env,evaluation_seed,evaluation_episodes)
            status(state="evaluating_policy",evaluation_episodes=evaluation_episodes,
                   male_cns_active=malecns,message="Evaluating the trained policy on the same held-out seeds")
            trained=_evaluate(model,env,evaluation_seed,evaluation_episodes)
            if malecns:
                status(state="evaluating_ablation",evaluation_episodes=evaluation_episodes,
                       male_cns_active=malecns,message="Repeating with neural features ablated")
                trained["neural_feature_ablation"]=_evaluate(model,env,evaluation_seed,evaluation_episodes,ablate_neural=True)
            previous_best=None
            if best_path.exists():
                try:
                    old_meta=_verified_checkpoint_metadata(best_path)
                    old_eval=old_meta.get("evaluation_metrics",{})
                    if (old_meta.get("independent_evaluation")=="passed_independent_analytic_evaluation"
                            and _beats_evaluation(old_eval.get("policy",{}),old_eval.get("baseline_rule",{}))):
                        previous_best=PPO.load(str(best_path),device="cpu")
                except Exception: previous_best=None
            best_eval=_evaluate(previous_best,env,evaluation_seed,evaluation_episodes) if previous_best is not None else None
            current_passes_baseline=_beats_evaluation(trained,baseline)
            previous_passes_baseline=previous_best is not None and _beats_evaluation(best_eval,baseline)
            selected=(model if current_passes_baseline and
                      (not previous_passes_baseline or _evaluation_score(trained)>_evaluation_score(best_eval))
                      else (previous_best if previous_passes_baseline else None))
            if selected is model:
                best_digest=_atomic_model(model,best_path)
                best_metadata=checkpoint_metadata(best_digest, "passed_independent_analytic_evaluation")
                best_metadata["evaluation_metrics"]={"baseline_rule":baseline,"policy":trained}
                _atomic_json(checkpoint_dir/"best_evaluated.json",best_metadata)
            elif previous_best is not None:
                best_digest=hashlib.sha256(best_path.read_bytes()).hexdigest()
            else:
                best_digest=""
            evaluation={"schema":SCHEMA,"independent_seeds":True,"male_cns_active":malecns,
                        "baseline_rule":baseline,"current_policy":trained,"previous_best":best_eval,
                        "selected_best":"current_policy" if selected is model else ("previous_best" if previous_best is not None else None),
                        "candidate_beats_rule_baseline":current_passes_baseline,
                        "best_checkpoint_sha256":best_digest}
        _atomic_json(output/"evaluation.json",evaluation)
        meta={"schema":SCHEMA,"algorithm":"Stable-Baselines3 PPO","controller":"external policy; MaleCNS connectome frozen",
              "training_stage":"malecns_finetuning" if malecns else "gameplay_pretraining",
              "male_cns_active":malecns,"male_cns_dataset_loaded":malecns,
              "male_cns_dataset":dataset_metadata,
              "feature_schema":list(NEURAL_CHANNELS)+list(GAME_FEATURES),"action_schema":list(ACTION_NAMES),
              "vehicle":vehicle,"program":program,"seed":seed,"requested_steps":steps,
              "actual_steps":int(model.num_timesteps),"resume_checkpoint":str(resume_path or ""),
              "checkpoint":str(latest_path),"checkpoint_sha256":digest,
              "imitation_pretraining":imitation_metadata,
              "best_checkpoint":str(best_path),"environment":"analytical_tank_duel_v1",
              "approximations":["two-dimensional arena","simplified armor and module damage","circle obstacle affects transitions but is not directly observed","simplified rule opponents","not Godot physics"],
              "reward_is_not_quality_proof":True}
        _atomic_json(output/"manifest.json",meta)
        best_metadata_path=checkpoint_dir/"best_evaluated.json"
        best_is_valid=False
        if best_path.is_file() and best_metadata_path.is_file():
            try:
                best_meta=_verified_checkpoint_metadata(best_path)
                best_eval=best_meta.get("evaluation_metrics",{})
                best_is_valid=(best_meta.get("independent_evaluation")=="passed_independent_analytic_evaluation"
                    and _beats_evaluation(best_eval.get("policy",{}),best_eval.get("baseline_rule",{})))
            except Exception:
                best_is_valid=False
        if best_is_valid:
            _atomic_json(output/"deployment_policy.json",{"schema":SCHEMA,"checkpoint":str(best_path),
                "checkpoint_sha256":best_digest,"features":meta["feature_schema"],
                "actions":list(ACTION_NAMES),"male_cns_required":malecns,
                "connectome_modified":False,"loadable_by_current_open_day":True})
        if not monitor.cancelled:
            latest_meta=checkpoint_metadata(digest, "completed_independent_analytic_evaluation")
            _atomic_json(checkpoint_dir/"latest.json",latest_meta)
        state="cancelled" if monitor.cancelled or (output/"cancel").exists() else "complete"
        _atomic_json(output/"progress.json",{"state":state,"timesteps":int(model.num_timesteps),
            "target_timesteps":int(model._total_timesteps),"episodes":len(rows),
            "elapsed_seconds":round(time.monotonic()-started,2),"stage":"SAVED",
            "male_cns_active":malecns,"steps_per_second":round((int(model.num_timesteps)-start_step)/max(.001,time.monotonic()-started),2),
            "checkpoint":str(latest_path),"best_checkpoint":str(best_path) if best_is_valid else "",
            "message":"Checkpoint and independent evaluation saved."})
        return {"checkpoint":str(latest_path),"best_checkpoint":str(best_path) if best_is_valid else "","evaluation":evaluation}
    finally:
        env.close()


def prepare_deployment(checkpoint: Path, output: Path) -> dict:
    """Validate schema/hash and create a self-describing deployment copy."""
    from stable_baselines3 import PPO
    if not checkpoint.is_file(): raise FileNotFoundError(checkpoint)
    metadata=_verified_checkpoint_metadata(checkpoint)
    if not metadata.get("male_cns_required"):
        raise ValueError("Open Day MaleCNS deployment requires MaleCNS fine-tuning; gameplay pretraining alone is not deployable")
    if metadata.get("independent_evaluation") != "passed_independent_analytic_evaluation":
        raise ValueError("Checkpoint must beat the fixed Rule AI baseline in independent evaluation before Open Day deployment")
    evaluation_metrics=metadata.get("evaluation_metrics",{})
    if not _beats_evaluation(evaluation_metrics.get("policy",{}),evaluation_metrics.get("baseline_rule",{})):
        raise ValueError("Checkpoint evaluation does not show a strict combat improvement over the fixed Rule AI baseline")
    digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    PPO.load(str(checkpoint),device="cpu")
    output.mkdir(parents=True,exist_ok=False)
    target=output/"policy.zip";target.write_bytes(checkpoint.read_bytes())
    male_cns_required=bool(metadata.get("male_cns_required",metadata.get("training_stage") in ("malecns","malecns_finetuning")))
    manifest={**metadata,"schema":SCHEMA,"checkpoint_sha256":digest,"sha256":digest,"policy":str(target),
              "features":list(NEURAL_CHANNELS)+list(GAME_FEATURES),"actions":list(ACTION_NAMES),
              "male_cns_required":male_cns_required,
              "connectome_modified":False,"current_open_day_runtime_compatible":True}
    _atomic_json(output/"metadata.json",manifest)
    return manifest


def evaluate_checkpoint(checkpoint: Path, config: dict, output: Path) -> dict:
    """Evaluate baseline, supplied policy and best policy on independent seeds."""
    from stable_baselines3 import PPO
    checkpoint_metadata=_verified_checkpoint_metadata(checkpoint)
    malecns=bool(checkpoint_metadata.get("male_cns_required",checkpoint_metadata.get("training_stage") in ("malecns","malecns_finetuning")))
    if malecns:
        _verify_malecns_dataset()
    env=TankCombatEnv(int(config.get("training_seed",7)),str(config.get("training_vehicle","t34_85")),
                      malecns,int(config.get("training_seconds",180)),str(config.get("training_program","automatic")))
    try:
        model=PPO.load(str(checkpoint),device="cpu")
        evaluation_seed=int(config.get("training_seed",7))+10000
        evaluation_episodes=max(3,int(config.get("evaluation_episodes",3)))
        baseline=_evaluate(None,env,evaluation_seed,evaluation_episodes)
        trained=_evaluate(model,env,evaluation_seed,evaluation_episodes)
        result={"schema":SCHEMA,"male_cns_active":malecns,"baseline_rule":baseline,
                "current_policy":trained,"candidate_beats_rule_baseline":_beats_evaluation(trained,baseline)}
        if malecns:result["current_policy"]["neural_feature_ablation"]=_evaluate(model,env,evaluation_seed,evaluation_episodes,ablate_neural=True)
        best=checkpoint.parent/"best_evaluated.zip"
        if best.is_file():result["best_policy"]=_evaluate(PPO.load(str(best),device="cpu"),env,evaluation_seed,evaluation_episodes)
        else:result["best_policy"]=result["current_policy"]
        _atomic_json(output/"evaluation.json",result)
        sidecar=checkpoint.with_suffix(".json")
        checkpoint_metadata["independent_evaluation"]=("passed_independent_analytic_evaluation"
            if result["candidate_beats_rule_baseline"] else "completed_independent_analytic_evaluation")
        checkpoint_metadata["evaluation_metrics"]={"baseline_rule":baseline,"policy":trained}
        checkpoint_metadata["evaluation_path"]=str(output/"evaluation.json")
        _atomic_json(sidecar,checkpoint_metadata)
        return result
    finally:env.close()
