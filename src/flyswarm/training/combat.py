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
import math
import os
import random
import time
from pathlib import Path

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from flyswarm.brain.demo import DemoBrain
from flyswarm.marl.roles import vehicle_profile

SCHEMA = "flyswarm_malecns_combat_v1"
ACTION_NAMES = ("throttle", "brake", "steering", "turret", "elevation", "fire")
NEURAL_CHANNELS = ("DNp09_L", "DNp09_R", "DNa02_L", "DNa02_R", "DNp01", "wing_song")
GAME_FEATURES = (
    "speed_fraction", "distance_fraction", "target_bearing_sin", "target_bearing_cos",
    "hull_error_sin", "hull_error_cos", "turret_error_sin", "turret_error_cos",
    "gun_elevation", "reload_fraction", "own_health", "target_health",
    "target_visible", "obstacle_left", "obstacle_right", "last_damage",
)


def _wrap(angle: float) -> float:
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def stage_for(step: int, total: int, program: str) -> str:
    if program == "full_battle":
        return "FULL_BATTLE"
    fraction = min(1.0, max(0.0, step / max(1, total)))
    return ("MOVEMENT" if fraction < .16 else "AIMING" if fraction < .34
            else "GUNNERY" if fraction < .54 else "TACTICS" if fraction < .74
            else "FULL_BATTLE")


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
        self.max_steps = max(1, int(max_seconds * 5))
        self.dt = .2
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
        self.own_pos = np.zeros(2, dtype=np.float64)
        angle = float(self.rng.uniform(-math.pi, math.pi))
        distance = float(self.rng.uniform(125.0, 310.0))
        self.target_pos = np.array([math.cos(angle), math.sin(angle)]) * distance
        self.own_heading = float(self.rng.uniform(-math.pi, math.pi))
        self.target_heading = _wrap(angle + math.pi + float(self.rng.uniform(-.5, .5)))
        self.target_type = str(self.rng.choice(["stationary", "moving", "rule", "aggressive"]))
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
        game = np.array([
            self.own_speed / max(1.0, speed), min(distance / 500.0, 2.0),
            math.sin(bearing), math.cos(bearing), math.sin(hull_error), math.cos(hull_error),
            math.sin(turret_error), math.cos(turret_error), self.elevation / .5,
            self.reload / max(.1, float(self.profile["reload_s"])), self.own_health,
            self.target_health if visible else 1.0, float(visible), 0.0, 0.0, 0.0,
        ], dtype=np.float32)
        return np.concatenate([self._neural(bearing, distance, visible), game]).astype(np.float32)

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
        if self.program == "automatic":
            stage = stage_for(self.training_step, self.training_total, self.program)
        else:
            stage = "FULL_BATTLE"
        if stage in ("MOVEMENT", "TACTICS", "FULL_BATTLE"):
            reward += float(np.clip(previous_distance - distance, -2.0, 2.0)) * (.008 if stage == "MOVEMENT" else .003)
            if collision: reward -= .12
            if self.stuck_steps > 15: reward -= .08
        if visible and stage in ("AIMING", "GUNNERY", "TACTICS", "FULL_BATTLE"):
            reward += max(0.0, 1.0 - abs(gun_error) / .6) * .012
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
                reward += damage * (3.0 if stage in ("GUNNERY", "FULL_BATTLE") else .3)
            elif stage in ("GUNNERY", "FULL_BATTLE"):
                reward -= .015
        # Opponent periodically engages after spotting the player.
        if visible and distance < 420.0 and int(self.elapsed * 5) % 22 == 0:
            enemy_error = abs(_wrap(math.atan2(float(self.own_pos[1]-self.target_pos[1]), float(self.own_pos[0]-self.target_pos[0])) - self.target_heading))
            if enemy_error < .35:
                self.own_health = max(0.0, self.own_health - (.10 if self.target_type == "aggressive" else .05))
                self.last_damage = 1.0 - self.own_health
                reward -= self.last_damage * (2.0 if stage == "FULL_BATTLE" else .25)
        terminated = self.target_health <= 0.0 or self.own_health <= 0.0
        truncated = self.steps >= self.max_steps
        if self.target_health <= 0.0: reward += 4.0
        if self.own_health <= 0.0: reward -= 4.0
        obs = self._observation()
        info = {"stage": stage, "male_cns_active": self.use_malecns,
                "shots": int(self.shots), "hits": int(self.hits),
                "damage": float(self.damage_dealt), "distance_m": float(self.distance_travelled),
                "stuck": self.stuck_steps > 15, "stuck_recoveries": self.stuck_recoveries,
                "own_health": self.own_health,
                "target_health": self.target_health, "target_type": self.target_type,
                "visible": visible, "episode": {"r": float(reward), "l": self.steps} if terminated or truncated else {}}
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


def _verified_checkpoint_metadata(path: Path) -> dict:
    sidecar=path.with_suffix(".json")
    if not sidecar.exists():sidecar=path.parent/"metadata.json"
    if not sidecar.is_file():raise ValueError("Checkpoint metadata is missing; only FlySwarm combat checkpoints can be resumed or deployed.")
    metadata=json.loads(sidecar.read_text(encoding="utf-8"))
    if metadata.get("schema")!=SCHEMA:raise ValueError("Checkpoint feature schema is incompatible")
    features=metadata.get("features",metadata.get("feature_schema"))
    actions=metadata.get("actions",metadata.get("action_schema"))
    if features!=list(NEURAL_CHANNELS)+list(GAME_FEATURES):raise ValueError("Checkpoint feature layout is incompatible")
    if actions!=list(ACTION_NAMES):raise ValueError("Checkpoint action layout is incompatible")
    expected=metadata.get("sha256",metadata.get("checkpoint_sha256"))
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    if expected!=actual:raise ValueError("Checkpoint checksum mismatch")
    return metadata


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


def run_training(config: dict, output: Path, status, check):
    """Create/resume PPO training; always checkpoint on normal stop or cancel."""
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback

    malecns = config.get("training_stage", "malecns") == "malecns"
    if malecns:
        from flybrain.data import has_data
        if not has_data():
            raise RuntimeError("MaleCNS training requires the configured reconstruction dataset; use GAMEPLAY PRETRAINING explicitly to train without it.")
    seed = int(config.get("training_seed", 7))
    steps = int(config.get("training_steps", 512))
    max_seconds = int(config.get("training_seconds", 180))
    checkpoint_interval = int(config.get("checkpoint_interval", 256))
    time_limit = max(1, int(config.get("training_time_minutes", 60))) * 60.0
    program = str(config.get("training_program", "automatic"))
    vehicle = str(config.get("training_vehicle", "t34_85"))
    checkpoint_dir = output / "checkpoints"
    latest_path = checkpoint_dir / "latest.zip"
    best_path = checkpoint_dir / "best.zip"
    resume = str(config.get("resume_checkpoint", ""))
    resume_path = Path(resume) if resume else None
    if resume_path and not resume_path.is_file():
        raise FileNotFoundError(f"Resume checkpoint not found: {resume_path}")
    if resume_path:_verified_checkpoint_metadata(resume_path)

    env = TankCombatEnv(seed, vehicle, malecns, max_seconds, program)
    n_steps = max(16, min(128, steps))
    if resume_path:
        model = PPO.load(str(resume_path), env=env, device="cpu")
        model.set_random_seed(seed)
        model.set_env(env)
        model._total_timesteps = int(model.num_timesteps) + steps
    else:
        model = PPO("MlpPolicy", env, learning_rate=3e-4, n_steps=n_steps,
                    batch_size=max(8, min(64, n_steps)), n_epochs=5,
                    gamma=.99, gae_lambda=.95, clip_range=.2, seed=seed,
                    device="cpu", verbose=0,
                    policy_kwargs={"net_arch":{"pi":[128,128],"vf":[128,128]}})
    start_step=int(model.num_timesteps)
    schedule_total=start_step+steps
    env.set_schedule(start_step,schedule_total)
    started = time.monotonic()
    status(state="training",timesteps=start_step,target_timesteps=schedule_total,
           episodes=0,stage=stage_for(start_step,schedule_total,program),male_cns_active=malecns,
           steps_per_second=0.0,message="PPO initialized; collecting combat rollouts")
    curve_path = output / "metrics.csv"
    rows=[]
    if curve_path.exists():
        with curve_path.open(newline="",encoding="utf-8") as f: rows=list(csv.DictReader(f))

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
                    _atomic_json(checkpoint_dir/"latest.json",{"sha256":digest,"schema":SCHEMA,
                        "steps":step,"seed":seed,"training_stage":"malecns" if malecns else "gameplay_pretraining",
                        "features":list(NEURAL_CHANNELS)+list(GAME_FEATURES),"actions":list(ACTION_NAMES)})
                time.sleep(.25)
            if (output/"save_checkpoint").exists():
                digest=_atomic_model(self.model,latest_path);(output/"save_checkpoint").unlink(missing_ok=True)
                _atomic_json(checkpoint_dir/"latest.json",{"sha256":digest,"schema":SCHEMA,
                    "steps":step,"seed":seed,"training_stage":"malecns" if malecns else "gameplay_pretraining",
                    "features":list(NEURAL_CHANNELS)+list(GAME_FEATURES),"actions":list(ACTION_NAMES)})
            infos=self.locals.get("infos",[])
            for info in infos:
                ep=info.get("episode") if isinstance(info,dict) else None
                if ep:
                    self.episodes+=1
                    row={"timesteps":step,"episodes":self.episodes,"stage":stage_for(step,schedule_total,program),
                         "episode_reward":float(ep.get("r",0)),"episode_steps":int(ep.get("l",0)),
                         "elapsed_seconds":round(time.monotonic()-started,3),
                         "male_cns_active":int(malecns)}
                    self.episode_rows.append(row);rows.append(row)
                    with curve_path.open("w",newline="",encoding="utf-8") as f:
                        writer=csv.DictWriter(f,fieldnames=list(row));writer.writeheader();writer.writerows(rows)
            if step-self.last_save>=checkpoint_interval:
                digest=_atomic_model(self.model,latest_path);self.last_save=step
                _atomic_json(checkpoint_dir/"latest.json",{"sha256":digest,"schema":SCHEMA,
                    "steps":step,"seed":seed,"stage":stage_for(step,schedule_total,program),
                    "training_stage":"malecns" if malecns else "gameplay_pretraining"})
                _atomic_json(output/"progress.json",{"state":"training","timesteps":step,
                    "target_timesteps":int(self.model._total_timesteps),"episodes":self.episodes,
                    "elapsed_seconds":round(time.monotonic()-started,2),
                    "stage":stage_for(step,schedule_total,program),"male_cns_active":malecns,
                    "steps_per_second":round(step/max(.001,time.monotonic()-started),2),
                    "latest_episode_reward":self.episode_rows[-1]["episode_reward"] if self.episode_rows else None,
                    "checkpoint":str(latest_path)})
            if step-self.last_report>=16:
                rate=step/max(.001,time.monotonic()-started)
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
        _atomic_json(checkpoint_dir/"latest.json",{"sha256":digest,"schema":SCHEMA,
            "steps":int(model.num_timesteps),"seed":seed,"training_stage":"malecns" if malecns else "gameplay_pretraining",
            "features":list(NEURAL_CHANNELS)+list(GAME_FEATURES),"actions":list(ACTION_NAMES),
            "optimizer_state":"included by Stable-Baselines3 PPO archive"})
        # Independent evaluation reuses one MaleCNS instance sequentially to stay within RAM limits.
        if monitor.cancelled:
            if not best_path.exists():
                temp=best_path.with_name("best.pending.zip");temp.write_bytes(latest_path.read_bytes());os.replace(temp,best_path)
            best_digest=hashlib.sha256(best_path.read_bytes()).hexdigest()
            _atomic_json(checkpoint_dir/"best.json",{"sha256":best_digest,"schema":SCHEMA,
                "steps":int(model.num_timesteps),"seed":seed,"training_stage":"malecns" if malecns else "gameplay_pretraining",
                "features":list(NEURAL_CHANNELS)+list(GAME_FEATURES),"actions":list(ACTION_NAMES)})
            evaluation={"schema":SCHEMA,"independent_seeds":True,"male_cns_active":malecns,
                        "evaluation_skipped":"user stopped training; run Evaluate Model when ready",
                        "best_checkpoint_sha256":best_digest}
        else:
            # Keep evaluation bounded even when training episodes are configured for hours.
            env.max_steps=min(env.max_steps,225)
            evaluation_seed=seed+10000
            baseline=_evaluate(None,env,evaluation_seed,3)
            trained=_evaluate(model,env,evaluation_seed,3)
            if malecns:
                trained["neural_feature_ablation"]=_evaluate(model,env,evaluation_seed,3,ablate_neural=True)
            previous_best=None
            if best_path.exists():
                try: previous_best=PPO.load(str(best_path),device="cpu")
                except Exception: previous_best=None
            best_eval=_evaluate(previous_best or model,env,evaluation_seed,3)
            current_score=(trained["win_rate"],trained["mean_damage"],trained["accuracy"])
            best_score=(best_eval["win_rate"],best_eval["mean_damage"],best_eval["accuracy"])
            selected=model if current_score >= best_score else previous_best
            if selected is model:
                best_digest=_atomic_model(model,best_path)
                _atomic_json(checkpoint_dir/"best.json",{"sha256":best_digest,"schema":SCHEMA,
                    "steps":int(model.num_timesteps),"seed":seed,"training_stage":"malecns" if malecns else "gameplay_pretraining",
                    "features":list(NEURAL_CHANNELS)+list(GAME_FEATURES),"actions":list(ACTION_NAMES)})
            else: best_digest=hashlib.sha256(best_path.read_bytes()).hexdigest()
            evaluation={"schema":SCHEMA,"independent_seeds":True,"male_cns_active":malecns,
                        "baseline_rule":baseline,"current_policy":trained,"previous_best":best_eval,
                        "selected_best":"current_policy" if selected is model else "previous_best",
                        "best_checkpoint_sha256":best_digest}
        _atomic_json(output/"evaluation.json",evaluation)
        meta={"schema":SCHEMA,"algorithm":"Stable-Baselines3 PPO","controller":"external policy; MaleCNS connectome frozen",
              "training_stage":"malecns_finetuning" if malecns else "gameplay_pretraining",
              "male_cns_active":malecns,"male_cns_dataset_loaded":malecns,
              "feature_schema":list(NEURAL_CHANNELS)+list(GAME_FEATURES),"action_schema":list(ACTION_NAMES),
              "vehicle":vehicle,"program":program,"seed":seed,"requested_steps":steps,
              "actual_steps":int(model.num_timesteps),"resume_checkpoint":str(resume_path or ""),
              "checkpoint":str(latest_path),"checkpoint_sha256":digest,
              "best_checkpoint":str(best_path),"environment":"analytical_tank_duel_v1",
              "approximations":["two-dimensional arena","simplified armor and module damage","circle obstacle affects transitions but is not directly observed","simplified rule opponents","not Godot physics"],
              "reward_is_not_quality_proof":True}
        _atomic_json(output/"manifest.json",meta)
        _atomic_json(output/"deployment_policy.json",{"schema":SCHEMA,"checkpoint":str(best_path),
            "checkpoint_sha256":best_digest,"feature_schema":meta["feature_schema"],
            "action_schema":list(ACTION_NAMES),"male_cns_required":malecns,
            "connectome_modified":False,"loadable_by_current_open_day":True})
        state="cancelled" if monitor.cancelled or (output/"cancel").exists() else "complete"
        _atomic_json(output/"progress.json",{"state":state,"timesteps":int(model.num_timesteps),
            "target_timesteps":int(model._total_timesteps),"episodes":len(rows),
            "elapsed_seconds":round(time.monotonic()-started,2),"stage":"SAVED",
            "male_cns_active":malecns,"steps_per_second":round(int(model.num_timesteps)/max(.001,time.monotonic()-started),2),
            "checkpoint":str(latest_path),"best_checkpoint":str(best_path),
            "message":"Checkpoint and independent evaluation saved."})
        return {"checkpoint":str(latest_path),"best_checkpoint":str(best_path),"evaluation":evaluation}
    finally:
        env.close()


def prepare_deployment(checkpoint: Path, output: Path) -> dict:
    """Validate schema/hash and create a self-describing deployment copy."""
    from stable_baselines3 import PPO
    if not checkpoint.is_file(): raise FileNotFoundError(checkpoint)
    metadata=_verified_checkpoint_metadata(checkpoint)
    digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    PPO.load(str(checkpoint),device="cpu")
    output.mkdir(parents=True,exist_ok=False)
    target=output/"policy.zip";target.write_bytes(checkpoint.read_bytes())
    male_cns_required=bool(metadata.get("male_cns_required",metadata.get("training_stage") in ("malecns","malecns_finetuning")))
    manifest={"schema":SCHEMA,"checkpoint_sha256":digest,"policy":str(target),
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
        from flybrain.data import has_data
        if not has_data():raise RuntimeError("Evaluation requires the configured MaleCNS dataset.")
    env=TankCombatEnv(int(config.get("training_seed",7)),str(config.get("training_vehicle","t34_85")),
                      malecns,int(config.get("training_seconds",180)),str(config.get("training_program","automatic")))
    try:
        model=PPO.load(str(checkpoint),device="cpu")
        evaluation_seed=int(config.get("training_seed",7))+10000
        result={"schema":SCHEMA,"male_cns_active":malecns,"baseline_rule":_evaluate(None,env,evaluation_seed,3),
                "current_policy":_evaluate(model,env,evaluation_seed,3)}
        if malecns:result["current_policy"]["neural_feature_ablation"]=_evaluate(model,env,evaluation_seed,3,ablate_neural=True)
        best=checkpoint.parent/"best.zip"
        if best.is_file():result["best_policy"]=_evaluate(PPO.load(str(best),device="cpu"),env,evaluation_seed,3)
        else:result["best_policy"]=result["current_policy"]
        _atomic_json(output/"evaluation.json",result)
        return result
    finally:env.close()
