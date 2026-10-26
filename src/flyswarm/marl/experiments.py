"""Reproducible team-policy experiments backed by PettingZoo and SB3 PPO."""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

try:
    from stable_baselines3.common.vec_env import VecEnv
except ImportError:
    class VecEnv:  # Allows non-PPO baseline utilities to import without SB3 installed.
        pass

from .env import (ACTION_NAMES, AGENTS, DEFAULT_REWARDS, ENVIRONMENT_SEMANTICS_VERSION, REWARD_SEMANTICS_VERSION,
                  TEAM_REWARD_COMPONENTS, FlySwarmParallelEnv)
from .roles import DEFAULT_COMPOSITION
from .student_code import ManagedStudentAgent, ManagedStudentReward, load_reward

BLUE = tuple(f"blue_{i}" for i in range(8))
RED = tuple(f"red_{i}" for i in range(8))
REPLAY_SCHEMA = "flyswarm.marl.replay.v1"


class FixedRulePolicy:
    """Deterministic objective-seeking control used as the paired opponent."""

    def __init__(self, env: FlySwarmParallelEnv, team: int):
        self.env = env
        self.team = int(team)

    def actions(self) -> dict[str, np.ndarray]:
        result = {}
        offset = self.team * 8
        for local in range(8):
            i = offset + local
            if self.env.health[i] <= 0:
                result[AGENTS[i]] = np.zeros(6, dtype=np.float32)
                continue
            zone_index=local % len(self.env.zones)
            if self.env.curriculum_tier=="A" and self.team==1:zone_index=(zone_index+2)%len(self.env.zones)
            target = self.env.zones[zone_index]
            delta = target - self.env.pos[i]
            desired = float(np.arctan2(delta[1], delta[0]))
            error = float((desired - self.env.heading[i] + np.pi) % (2 * np.pi) - np.pi)
            enemies = np.arange(8, 16) if self.team == 0 else np.arange(0, 8)
            alive = enemies[self.env.health[enemies] > 0]
            turret_control = 0.0
            fire = 0.0
            if len(alive):
                distances = np.linalg.norm(self.env.pos[alive] - self.env.pos[i], axis=1)
                enemy = int(alive[int(np.argmin(distances))])
                enemy_delta = self.env.pos[enemy] - self.env.pos[i]
                enemy_range = float(np.linalg.norm(enemy_delta))
                bearing = float(np.arctan2(enemy_delta[1], enemy_delta[0]))
                hull_error = float((bearing - self.env.heading[i] + np.pi) % (2 * np.pi) - np.pi)
                profile = self.env.profiles[i]
                if profile["turreted"]:
                    aim_error = float((hull_error - self.env.turret_heading[i] + np.pi) % (2 * np.pi) - np.pi)
                    rate = max(1e-6, float(profile["turret_rate_rad_s"]))
                    turret_control = float(np.clip(aim_error / (rate * self.env.dt), -1., 1.))
                else:
                    aim_error = hull_error
                fire = float(enemy_range < float(profile["effective_range_m"])
                             and abs(aim_error) < np.deg2rad(7.))
            result[AGENTS[i]] = np.asarray(
                [0.8, 0.0, np.clip(error / np.pi, -1, 1), turret_control, 0.0, fire],
                dtype=np.float32,
            )
        return result


class TeamGymnasiumEnv(gym.Env):
    """Centralized shared PPO controller for one eight-vehicle team.

    Each policy action contains eight six-value vehicle actions. The other
    team uses the same deterministic rule policy during training and eval.
    Per-step reward is the sum of the eight controlled agents' PettingZoo
    rewards; no second reward or physics model is introduced here.
    """

    metadata = {"render_modes": []}

    def __init__(self, seed: int = 0, max_steps: int = 600, team: int = 0,
                 reward_coefficients: dict[str, float] | None = None, reward_function=None,
                 curriculum_tier: str = "C"):
        super().__init__()
        if team not in (0, 1):
            raise ValueError("team must be 0 (blue) or 1 (red)")
        self.seed_value = int(seed)
        self._episode_seed_rng = np.random.default_rng(self.seed_value)
        self.max_steps = int(max_steps)
        self.team = int(team)
        self.env = FlySwarmParallelEnv(
            max_steps=self.max_steps,
            reward_coefficients=reward_coefficients,
            role_conditioning=True,
            reward_function=reward_function,
            curriculum_tier=curriculum_tier,
        )
        self.observation_space = spaces.Box(
            low=-10, high=10, shape=(8 * self.env.obs_dim,), dtype=np.float32
        )
        self.action_space = spaces.Box(low=-1, high=1, shape=(8, 6), dtype=np.float32)
        self.opponent = FixedRulePolicy(self.env, 1 - self.team)
        self.episode_reward = 0.0
        self.episode_step = 0
        self._last_obs = {}

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        seed = int(self._episode_seed_rng.integers(0, 2**31 - 1)) if seed is None else int(seed)
        self._last_obs, infos = self.env.reset(seed=seed)
        self.episode_reward = 0.0
        self.episode_step = 0
        return self._team_observation(self._last_obs), {"seed": seed, "backend": "analytical_training"}

    def _team_observation(self, observations: dict[str, np.ndarray]) -> np.ndarray:
        members = BLUE if self.team == 0 else RED
        return np.concatenate([observations[a] for a in members]).astype(np.float32)

    def step(self, action):
        value = np.asarray(action, dtype=np.float32).reshape(8, 6)
        members = BLUE if self.team == 0 else RED
        other = RED if self.team == 0 else BLUE
        actions = self.opponent.actions()
        actions.update({a: np.clip(value[i], -1, 1) for i, a in enumerate(members)})
        observations, rewards, terms, truncs, infos = self.env.step(actions)
        self.episode_step += 1
        reward = float(sum(rewards[a] for a in members))
        self.episode_reward += reward
        terminated = bool(any(terms.values()))
        truncated = bool(any(truncs.values()))
        done = terminated or truncated
        snapshot = self.env.snapshot(actions, rewards)
        info = {
            "backend": "analytical_training",
            "team_reward": reward,
            "training_reward": reward,
            "standard_evaluation_reward": float(sum(infos[a]["standard_evaluation_reward"] for a in members)),
            "episode_reward": self.episode_reward,
            "episode_step": self.episode_step,
            "snapshot": snapshot,
            "terminated": terminated,
            "truncated": truncated,
            "winner": self.env.last_outcome.get("winner"),
            "terminal_reason": self.env.last_outcome.get("reason"),
            "reward_component_totals": {
                key: float(sum(infos[a]["reward_components"].get(key, 0.0) for a in members))
                for key in self.env.last_components[0]
            },
        }
        if done:
            info["episode"] = {
                "r": self.episode_reward,
                "l": self.episode_step,
                "tickets": self.env.tickets.tolist(),
                "alive": [int(np.count_nonzero(self.env.health[:8])), int(np.count_nonzero(self.env.health[8:]))],
            }
        self._last_obs = observations
        return self._team_observation(observations), reward, terminated, truncated, info

    def close(self):
        self.env.close() if hasattr(self.env, "close") else None


class SharedAgentVecEnv(VecEnv):
    """One shared PPO policy controls each blue agent in the same battle.

    The eight VecEnv slots are agent views into one synchronized PettingZoo
    world. Each step gathers eight actions before advancing that world once.
    This is parameter-sharing PPO with a local critic, not MAPPO.
    """
    def __init__(self, seed=0, max_steps=600, reward_coefficients=None,
                 reward_function=None, curriculum_tier="C"):
        self.tier=str(curriculum_tier).upper()
        self.world=FlySwarmParallelEnv(max_steps=max_steps,reward_coefficients=reward_coefficients,
            role_conditioning=True,reward_function=reward_function,curriculum_tier=self.tier)
        self.world.render_mode=None
        self.agent_count=self.world.active_units_per_team
        self.base_seed=int(seed);self.episode_index=0;self.episode_steps=0
        self.episode_rewards=np.zeros(self.agent_count,dtype=np.float64)
        self._pending_actions=None;self._observations=None
        self._closed=False
        super().__init__(self.agent_count,self.world.observation_space("blue_0"),self.world.action_space("blue_0"))

    def _seed_for_episode(self):
        value=self.base_seed+self.episode_index;self.episode_index+=1;return value

    def reset(self):
        seed=self._seed_for_episode()
        observations,infos=self.world.reset(seed=seed)
        self._observations=np.stack([observations[f"blue_{i}"] for i in range(self.agent_count)])
        self.reset_infos=[{"seed":seed,"backend":"analytical_training","curriculum_tier":self.tier}
                          for _ in range(self.agent_count)]
        self.episode_steps=0;self.episode_rewards.fill(0.)
        self._reset_seeds();self._reset_options()
        return self._observations.copy()

    def step_async(self,actions):self._pending_actions=np.asarray(actions,dtype=np.float32).reshape(self.agent_count,6)

    def step_wait(self):
        if self._pending_actions is None:raise RuntimeError("step_async must be called before step_wait")
        actions=FixedRulePolicy(self.world,1).actions()
        actions.update({f"blue_{i}":np.clip(self._pending_actions[i],-1,1) for i in range(self.agent_count)})
        observations,rewards,terms,truncs,infos=self.world.step(actions);self.episode_steps+=1
        reward_array=np.asarray([rewards[f"blue_{i}"] for i in range(self.agent_count)],dtype=np.float32)
        self.episode_rewards+=reward_array
        done=bool(any(terms.values()) or any(truncs.values()))
        info_rows=[]
        for i in range(self.agent_count):
            info=dict(infos[f"blue_{i}"]);info["TimeLimit.truncated"]=bool(truncs[f"blue_{i}"] and not terms[f"blue_{i}"])
            info["reward_component_totals"]=dict(info.get("reward_components",{}))
            if done:
                info["terminal_observation"]=observations[f"blue_{i}"].copy()
                if i==0:info["episode"]={"r":float(np.mean(self.episode_rewards)),"l":int(self.episode_steps)}
            info_rows.append(info)
        dones=np.full(self.agent_count,done,dtype=bool)
        if done:
            self._observations=self.reset()
        else:self._observations=np.stack([observations[f"blue_{i}"] for i in range(self.agent_count)])
        self._pending_actions=None
        return self._observations.copy(),reward_array,dones,info_rows

    def close(self):
        if not self._closed:self.world.close();self._closed=True

    def get_attr(self,attr_name,indices=None):
        if not hasattr(self.world,attr_name):raise AttributeError(attr_name)
        return [getattr(self.world,attr_name) for _ in self._get_indices(indices)]
    def set_attr(self,attr_name,value,indices=None):setattr(self.world,attr_name,value)
    def env_method(self,method_name,*method_args,indices=None,**method_kwargs):
        method=getattr(self.world,method_name);return [method(*method_args,**method_kwargs) for _ in self._get_indices(indices)]
    def env_is_wrapped(self,wrapper_class,indices=None):return [False for _ in self._get_indices(indices)]


def new_experiment_dir(root: Path, label: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    safe = "".join(c.lower() if c.isalnum() else "-" for c in label).strip("-") or "experiment"
    path = root / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{safe}-{uuid.uuid4().hex[:8]}"
    return path


def _prepare_output(output: Path) -> None:
    output = Path(output)
    if output.exists():
        unexpected = [path.name for path in output.iterdir()
                      if path.name != "execution.log" and not path.name.startswith("._")]
        if unexpected:
            raise FileExistsError(f"Experiment output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    # Godot polls progress.json while the backend is training. Windows can
    # briefly reject replacing the target while its reader still has it open.
    for attempt in range(8):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.01 * (attempt + 1))


def _source_metadata() -> dict[str, str | None]:
    root = Path(__file__).resolve().parents[3]
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    try:
        version = subprocess.check_output(["git", "describe", "--tags", "--exact-match"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        version = None
    fingerprint=hashlib.sha256()
    for relative in ("src/flyswarm/marl/env.py","src/flyswarm/marl/roles.py",
                     "src/flyswarm/marl/experiments.py","src/flyswarm/marl/cli.py",
                     "src/flyswarm/marl/student_code.py","src/flyswarm/marl/exporter.py",
                     "src/flyswarm/bridge/server.py"):
        source=root/relative
        if source.is_file():
            fingerprint.update(relative.encode("utf-8"));fingerprint.update(source.read_bytes())
    return {"commit_sha": commit, "project_version": version,
            "experiment_code_sha256":fingerprint.hexdigest()}


def _effective_rewards(reward_coefficients):
    return DEFAULT_REWARDS | {"battle_draw": 0.} | dict(reward_coefficients or {})


def append_replay(path: Path, seed: int, frame: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"schema": REPLAY_SCHEMA, "seed": int(seed), **frame}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n")


def start_replay(path: Path, env: FlySwarmParallelEnv, seed: int, policy_id: str) -> None:
    if path.exists():
        raise FileExistsError(path)
    append_replay(path, seed, {
        "kind": "header", "backend": "analytical_training",
        "policy_id": policy_id, "dt": env.dt,
        "observation_dim": env.obs_dim, "agent_ids": list(AGENTS),
        "action_order": list(ACTION_NAMES),
        "state_authority": "FlySwarmParallelEnv",
        "visual_effects_authority": "none; playback may render recorded events only",
        "curriculum_tier":env.curriculum_tier,"active_units_per_team":env.active_units_per_team,
        "start_side":env.start_side,
        "combat_enabled":env.combat_enabled,"fire_rate_multiplier":env.fire_rate_multiplier,
        "environment_semantics_version":ENVIRONMENT_SEMANTICS_VERSION,
        "reward_semantics_version":REWARD_SEMANTICS_VERSION,
    })
    append_replay(path, seed, env.snapshot({}, {}, kind="frame"))


def _step_episode(env: FlySwarmParallelEnv, observations: dict[str, np.ndarray],
                  seed: int, policy_id: str, run_id: str, replay_path: Path | None = None,
                  ppo_model=None, rng: np.random.Generator | None = None,
                  deterministic: bool = False, student_agent=None,
                  ppo_architecture: str="centralized",rule_agent:bool=False,
                  step_callback=None) -> dict[str, Any]:
    members = BLUE
    rule_red = FixedRulePolicy(env, 1).actions
    total_reward = 0.0
    captures = kills = deaths = 0
    standard_evaluation_reward = 0.0
    episode_steps = 0
    reward_component_totals: dict[str, float] = {}
    standard_component_totals: dict[str, float] = {}
    while env.agents:
        actions = rule_red()
        if ppo_model is not None:
            if ppo_architecture=="parameter_sharing":
                for agent_id in members[:env.active_units_per_team]:
                    action,_=ppo_model.predict(observations[agent_id],deterministic=deterministic)
                    actions[agent_id]=np.asarray(action,dtype=np.float32).reshape(6)
            else:
                team_obs=np.concatenate([observations[a] for a in members]).astype(np.float32)
                action,_=ppo_model.predict(team_obs,deterministic=deterministic)
                actions.update({a:np.asarray(action).reshape(8,6)[i] for i,a in enumerate(BLUE)})
        elif student_agent is not None:
            if episode_steps == 0 and getattr(student_agent, "reset", None):
                student_agent.reset(seed=int(seed))
            contexts = [{"agent_id": a, "team": "blue", "episode_seed": int(seed),
                         "episode_step": int(episode_steps), "team_index": int(local_index)}
                        for local_index, a in enumerate(members)]
            if hasattr(student_agent, "act_team"):
                team_actions = student_agent.act_team([observations[a] for a in members], contexts)
                actions.update({a: action for a, action in zip(members, team_actions)})
            else:
                actions.update({a: student_agent(observations[a], context)
                                for a, context in zip(members, contexts)})
        elif rule_agent:
            actions.update(FixedRulePolicy(env,0).actions())
        else:
            for a in members:
                actions[a] = rng.uniform(-1, 1, size=6).astype(np.float32)
        old_health = env.health.copy()
        old_owners = env.zones_owner.copy()
        observations, rewards, terms, truncs, infos = env.step(actions)
        team_step_reward = float(sum(rewards[a] for a in members))
        total_reward += team_step_reward
        standard_evaluation_reward += float(sum(infos[a]["standard_evaluation_reward"] for a in members))
        for key in infos[members[0]]["reward_components"]:
            value=float(sum(infos[a]["reward_components"].get(key,0.0) for a in members))
            reward_component_totals[key]=reward_component_totals.get(key,0.0)+value
            standard_component_totals[key]=standard_component_totals.get(key,0.0)+value*DEFAULT_REWARDS.get(key,0.0)
        episode_steps += 1
        if step_callback is not None:
            step_callback(episode_steps)
        captures += int(np.count_nonzero((old_owners != 0) & (env.zones_owner == 0)))
        kills += int(np.count_nonzero((old_health[8:] > 0) & (env.health[8:] <= 0)))
        deaths += int(np.count_nonzero((old_health[:8] > 0) & (env.health[:8] <= 0)))
        if replay_path is not None:
            append_replay(replay_path, seed, env.snapshot(actions, rewards, run_id=run_id))
        if any(terms.values()) or any(truncs.values()):
            break
    tickets = env.tickets.tolist()
    if replay_path is not None:
        write_json(replay_path.with_suffix(".final_state.json"),
                   {"schema":REPLAY_SCHEMA,"seed":int(seed),**env.snapshot(actions,rewards,run_id=run_id)})
    winner = env.last_outcome.get("winner") or "draw"
    return {
        "seed": seed, "policy_id": policy_id, "run_id": run_id,
        "team_reward": total_reward, "training_reward": total_reward,
        "standard_evaluation_reward": standard_evaluation_reward,
        "episode_steps": episode_steps,
        "episode_seconds": episode_steps * env.dt, "captures": captures,
        "kills": kills, "deaths": deaths, "winner": winner,
        "blue_tickets": tickets[0], "red_tickets": tickets[1],
        "blue_alive": int(np.count_nonzero(env.health[:8])),
        "red_alive": int(np.count_nonzero(env.health[8:])),
        "terminal_reason": env.last_outcome.get("reason"),
        "reward_component_totals":reward_component_totals,
        "standard_component_contributions":standard_component_totals,
    }


def run_student_agent(output: Path, agent_file: Path, episodes: int = 3,
                      seed: int = 101, max_steps: int = 300,
                      reward_file: Path | None = None,curriculum_tier: str="C",
                      progress_path: Path | None = None) -> dict[str, Any]:
    """Run a student's real Python strategy in the analytical PettingZoo env."""
    agent_file = Path(agent_file).expanduser().resolve()
    reward_file = Path(reward_file).expanduser().resolve() if reward_file else None
    _prepare_output(output)
    (output / "student_code").mkdir()
    shutil.copy2(agent_file, output / "student_code/agent.py")
    if reward_file:
        shutil.copy2(reward_file, output / "student_code/reward.py")
    progress_path = Path(progress_path) if progress_path else output / "progress.json"
    started = time.monotonic()
    episode_total = max(1, int(episodes))
    max_steps = max(1, int(max_steps))
    completed_world_steps = 0
    write_json(progress_path, {
        "state": "starting", "phase": "initializing", "command": "student",
        "completed": 0, "total": episode_total, "episodes": 0,
        "elapsed_seconds": 0.0, "eta_seconds": None,
        "message": "Preparing the student strategy evaluation.",
    })
    rows=[]
    agent = ManagedStudentAgent(agent_file)
    reward_function = ManagedStudentReward(reward_file) if reward_file else None
    env=None
    try:
        env=FlySwarmParallelEnv(max_steps=max_steps,reward_function=reward_function,curriculum_tier=curriculum_tier)
        for episode in range(int(episodes)):
            episode_seed=int(seed+episode)

            def report_step(step: int) -> None:
                if int(step) % 10 != 0 and int(step) < max_steps:
                    return
                elapsed = time.monotonic() - started
                progress_units = episode + min(float(step) / max_steps, 0.99)
                rate = progress_units / elapsed if elapsed > 0 else 0.0
                write_json(progress_path, {
                    "state": "running", "phase": "evaluation",
                    "command": "student", "episodes": episode,
                    "completed": progress_units, "total": episode_total,
                    "world_steps": completed_world_steps + int(step),
                    "elapsed_seconds": round(elapsed, 2),
                    "eta_seconds": round((episode_total - progress_units) / rate, 2) if rate > 0 else None,
                    "message": f"Evaluating student strategy · episode {episode + 1}/{int(episodes)}",
                })

            write_json(progress_path, {
                "state": "running", "phase": "evaluation", "command": "student",
                "episodes": episode, "completed": float(episode), "total": episode_total,
                "world_steps": completed_world_steps, "elapsed_seconds": round(time.monotonic() - started, 2),
                "eta_seconds": None,
                "message": f"Evaluating student strategy · episode {episode + 1}/{int(episodes)}",
            })
            observations,_=env.reset(seed=episode_seed)
            replay=output/"replays"/f"student-seed-{episode_seed}.jsonl"
            start_replay(replay,env,episode_seed,"student_python_agent")
            row=_step_episode(env,observations,episode_seed,"student_python_agent",
                              f"student-{episode_seed}",replay,student_agent=agent,
                              step_callback=report_step)
            rows.append(row)
            completed_world_steps += int(row["episode_steps"])
            elapsed = time.monotonic() - started
            progress_units = float(episode + 1)
            rate = progress_units / elapsed if elapsed > 0 else 0.0
            write_json(progress_path, {
                "state": "running", "phase": "evaluation", "command": "student",
                "episodes": episode + 1, "completed": progress_units, "total": episode_total,
                "world_steps": completed_world_steps, "elapsed_seconds": round(elapsed, 2),
                "eta_seconds": round((episode_total - progress_units) / rate, 2) if rate > 0 else None,
                "message": f"Completed episode {episode + 1}/{int(episodes)}",
            })
    finally:
        if env is not None:env.close()
        elif reward_function is not None:reward_function.close()
        agent.close()
    write_json(progress_path, {
        "state": "finalizing", "phase": "saving", "command": "student",
        "episodes": len(rows), "completed": episode_total, "total": episode_total,
        "world_steps": completed_world_steps,
        "elapsed_seconds": round(time.monotonic() - started, 2), "eta_seconds": 0.0,
        "message": "Saving student evaluation results.",
    })
    _write_run_outputs(output,rows,"student_python_agent",seed,max_steps)
    manifest=json.loads((output/"manifest.json").read_text(encoding="utf-8"))
    manifest.update({"agent_file_sha256":hashlib.sha256(agent_file.read_bytes()).hexdigest(),
                     "reward_file_sha256":hashlib.sha256(reward_file.read_bytes()).hexdigest() if reward_file else None,
                     "student_code_directory":"student_code",
                     "security_note":"Student Python ran in the separate backend process with current-user permissions; this is not a sandbox."})
    write_json(output/"manifest.json",manifest)
    write_json(output/"summary.json",{
        "backend":"analytical_training","experiment":"student_python_agent",
        "episodes":len(rows),"mean_training_reward":_mean(rows,"training_reward"),
        "mean_standard_evaluation_reward":_mean(rows,"standard_evaluation_reward"),
        "mean_captures":_mean(rows,"captures"),"mean_kills":_mean(rows,"kills"),
        "blue_win_rate":_win_rate(rows),"runs":rows,
    })
    write_json(progress_path, {
        "state": "complete", "phase": "complete", "command": "student",
        "episodes": len(rows), "completed": episode_total, "total": episode_total,
        "world_steps": completed_world_steps,
        "elapsed_seconds": round(time.monotonic() - started, 2), "eta_seconds": 0.0,
        "message": "Student strategy evaluation and results are complete.",
    })
    return {"experiment_dir":str(output),"runs":rows,
            "mean_training_reward":_mean(rows,"training_reward"),
            "mean_standard_evaluation_reward":_mean(rows,"standard_evaluation_reward")}


def run_random_baseline(output: Path, episodes: int = 3, seed: int = 101,
                        max_steps: int = 300, reward_coefficients=None,
                        curriculum_tier: str = "C") -> dict[str, Any]:
    """Run uniform random blue actions against the fixed rule opponent."""
    _prepare_output(output)
    rows = []
    for episode in range(int(episodes)):
        episode_seed = int(seed + episode)
        rng = np.random.default_rng(episode_seed)
        env = FlySwarmParallelEnv(max_steps=max_steps, reward_coefficients=reward_coefficients,curriculum_tier=curriculum_tier)
        observations, _ = env.reset(seed=episode_seed)
        replay = output / "replays" / f"random-seed-{episode_seed}.jsonl"
        start_replay(replay, env, episode_seed, "uniform_random")
        rows.append(_step_episode(env, observations, episode_seed, "uniform_random",
                                  f"random-{episode_seed}", replay, rng=rng))
    _write_run_outputs(output, rows, "random_baseline", seed, max_steps, reward_coefficients)
    manifest=json.loads((output/"manifest.json").read_text());manifest.update({"curriculum_tier":curriculum_tier,"reward_semantics_version":REWARD_SEMANTICS_VERSION});write_json(output/"manifest.json",manifest)
    return {"experiment_dir": str(output), "runs": rows, "mean_team_reward": _mean(rows, "team_reward")}


def evaluate_rule_ai(output:Path,episodes:int=5,seed:int=1001,max_steps:int=300,
                     curriculum_tier:str="C"):
    """Independent fixed Rule AI control, scored by the standard metric."""
    _prepare_output(output);rows=[]
    for offset in range(int(episodes)):
        episode_seed=int(seed+offset);env=FlySwarmParallelEnv(max_steps=max_steps,curriculum_tier=curriculum_tier)
        try:
            observations,_=env.reset(seed=episode_seed)
            replay=output/"replays"/f"rule-ai-seed-{episode_seed}.jsonl"
            start_replay(replay,env,episode_seed,"fixed_rule_ai")
            rows.append(_step_episode(env,observations,episode_seed,"fixed_rule_ai",f"rule-ai-{episode_seed}",
                replay,rule_agent=True))
        finally:env.close()
    _write_run_outputs(output,rows,"rule_ai_evaluation",seed,max_steps)
    manifest=json.loads((output/"manifest.json").read_text());manifest.update({"curriculum_tier":curriculum_tier,
        "reward_semantics_version":REWARD_SEMANTICS_VERSION,
        "environment_semantics_version":ENVIRONMENT_SEMANTICS_VERSION,
        "control":"fixed objective and aim aware policy"})
    write_json(output/"manifest.json",manifest)
    write_json(output/"summary.json",{"protocol":"independent fixed Rule AI control","curriculum_tier":curriculum_tier,
        "episodes":len(rows),"mean_standard_evaluation_reward":_mean(rows,"standard_evaluation_reward"),
        "std_standard_evaluation_reward":float(np.std([r["standard_evaluation_reward"] for r in rows],ddof=1)) if len(rows)>1 else 0.,
        "win_rate":_win_rate(rows),"mean_captures":_mean(rows,"captures"),"mean_kills":_mean(rows,"kills"),
        "mean_losses":_mean(rows,"deaths"),"runs":rows})
    return {"experiment_dir":str(output),"runs":rows,"mean_standard_evaluation_reward":_mean(rows,"standard_evaluation_reward")}


def _mean(rows, field):
    return float(np.mean([float(row[field]) for row in rows])) if rows else 0.0


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        fields=[]
        for row in rows:
            for key in row:
                if key not in fields:fields.append(key)
        writer = csv.DictWriter(stream, fieldnames=fields,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_run_outputs(output: Path, rows: list[dict[str, Any]], backend: str,
                       seed: int, max_steps: int, reward_coefficients=None) -> None:
    _write_csv(output / "evaluation.csv", rows)
    if backend == "random_baseline":
        _write_csv(output / "baseline.csv", rows)
    write_json(output / "summary.json", {
        "backend": "analytical_training", "experiment": backend,
        "seed": int(seed), "episodes": len(rows), "max_steps": int(max_steps),
        "team_reward_definition": "sum of the eight controlled blue agents' per-step rewards across the episode",
        "mean_team_reward": _mean(rows, "team_reward"),
        "mean_captures": _mean(rows, "captures"), "mean_kills": _mean(rows, "kills"),
        "mean_episode_steps": _mean(rows, "episode_steps"),
        "blue_win_rate": float(np.mean([r["winner"] == "blue" for r in rows])) if rows else 0.0,
        "runs": rows,
    })
    manifest = {
        "backend": "analytical_training", "runtime": "PettingZoo ParallelEnv",
        **_source_metadata(),
        "reward_semantics_version": REWARD_SEMANTICS_VERSION,
        "environment_semantics_version": ENVIRONMENT_SEMANTICS_VERSION,
        "python": platform.python_version(), "platform": platform.platform(),
        "seed": int(seed), "episode_length_limit": int(max_steps),
        "reward_coefficients": _effective_rewards(reward_coefficients),
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(output / "config.json", {
        "seed": int(seed), "max_steps": int(max_steps), "dt_seconds": .1,
        "episodes": len(rows), "reward_coefficients": _effective_rewards(reward_coefficients),
        "vehicle_ids": list(DEFAULT_COMPOSITION),
        "opponent": "fixed objective-seeking and aim-aware rule policy",
    })
    write_json(output / "manifest.json", manifest)


def train_sb3_ppo(output: Path, timesteps: int = 10000, seed: int = 7,
                  max_steps: int = 300, learning_rate: float = 3e-4,
                  progress_path: Path | None = None, reward_coefficients=None,
                  reward_function=None, reward_file: Path | None = None,
                  curriculum_tier: str = "C", continue_from: Path | None = None,
                  checkpoint_interval: int = 1024,ppo_architecture: str="centralized") -> dict[str, Any]:
    """Train centralized joint-action PPO with safe pause, stop, and resume."""
    started = time.monotonic()
    _prepare_output(output)
    progress_path = progress_path or output / "progress.json"
    curve_path = output / "training.csv"
    if int(timesteps) < 1: raise ValueError("steps must be positive")
    tier=str(curriculum_tier).upper()
    if tier not in {"A","B","C"}:raise ValueError("curriculum tier must be A, B, or C")
    ppo_architecture=str(ppo_architecture)
    if ppo_architecture not in {"centralized","parameter_sharing"}:raise ValueError("unknown PPO architecture")
    reward_values=_effective_rewards(reward_coefficients)
    reward_file_hash=hashlib.sha256(Path(reward_file).read_bytes()).hexdigest() if reward_file else None
    from .roles import ROLE_FEATURE_DIM
    contract={"checkpoint_schema":"flyswarm.sb3_ppo.v2",
        "observation_shape":[(22+ROLE_FEATURE_DIM) if ppo_architecture=="parameter_sharing" else 8*(22+ROLE_FEATURE_DIM)],
        "action_shape":[6] if ppo_architecture=="parameter_sharing" else [8,6],
        "architecture":"parameter_sharing_mlp_128x2" if ppo_architecture=="parameter_sharing" else "centralized_joint_mlp_128x2",
        "curriculum_tier":tier,
        "active_units_per_team":{"A":1,"B":4,"C":8}[tier],"combat_enabled":tier!="A",
        "fire_rate_multiplier":{"A":1.,"B":2.,"C":1.}[tier],
        "max_steps":int(max_steps),"environment_semantics_version":ENVIRONMENT_SEMANTICS_VERSION,
        "reward_semantics_version":REWARD_SEMANTICS_VERSION,
        "reward_coefficients":reward_values,"custom_reward_sha256":reward_file_hash}
    checkpoint=output/"checkpoint"/"ppo_team";checkpoint.parent.mkdir(parents=True,exist_ok=True)
    zipped=checkpoint.with_suffix(".zip");metadata_path=checkpoint.parent/"ppo_team.metadata.json"
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.callbacks import BaseCallback
    except ImportError as exc:
        raise RuntimeError("PPO training requires stable-baselines3; install requirements-marl.txt") from exc

    if reward_file and not callable(getattr(reward_function,"calculate_batch",None)):
        reward_function=ManagedStudentReward(reward_file)

    try:
        env=(SharedAgentVecEnv(seed=seed,max_steps=max_steps,reward_coefficients=reward_coefficients,
                               reward_function=reward_function,curriculum_tier=tier)
             if ppo_architecture=="parameter_sharing" else
             TeamGymnasiumEnv(seed=seed,max_steps=max_steps,reward_coefficients=reward_coefficients,
                              reward_function=reward_function,curriculum_tier=tier))
    except BaseException:
        close=getattr(reward_function,"close",None)
        if callable(close):close()
        raise
    def save_checkpoint(model,kind):
        model.save(str(checkpoint))
        write_json(metadata_path,{**contract,"seed":int(seed),"num_timesteps":int(model.num_timesteps),
            "ppo_hyperparameters":{"learning_rate":float(model.learning_rate),"n_steps":int(model.n_steps),
                "batch_size":int(model.batch_size),"n_epochs":int(model.n_epochs),"gamma":float(model.gamma),
                "gae_lambda":float(model.gae_lambda),"clip_range":float(model.clip_range(1.) if callable(model.clip_range) else model.clip_range),
                "policy_network":{"pi":[128,128],"vf":[128,128]}},
            "saved_as":kind,"created_utc":datetime.now(timezone.utc).isoformat(),
            "checkpoint_sha256":hashlib.sha256(zipped.read_bytes()).hexdigest()})

    initial_timesteps=0
    if continue_from is not None:
        continue_from=Path(continue_from).expanduser().resolve()
        sidecar=continue_from.parent/(continue_from.stem+".metadata.json")
        if not continue_from.is_file() or not sidecar.is_file():
            env.close();raise ValueError("Checkpoint is missing compatibility metadata; start a new training run.")
        saved=json.loads(sidecar.read_text(encoding="utf-8"))
        if saved.get("checkpoint_sha256")!=hashlib.sha256(continue_from.read_bytes()).hexdigest():
            env.close();raise ValueError("Checkpoint checksum does not match its metadata.")
        mismatches=[key for key,value in contract.items() if saved.get(key)!=value]
        if mismatches:
            env.close();raise ValueError("Checkpoint is incompatible with this training setup: "+", ".join(mismatches))
        model=PPO.load(str(continue_from),env=env,device="cpu")
        initial_timesteps=int(model.num_timesteps)
    else:
        vector_count=env.num_envs if hasattr(env,"num_envs") else 1
        n_steps=(min(64,max(2,(int(timesteps)+vector_count-1)//vector_count))
                 if ppo_architecture=="parameter_sharing" else min(256,max(16,int(timesteps))))
        rollout_size=n_steps*vector_count
        batch_size=min(128 if ppo_architecture=="parameter_sharing" else 64,rollout_size)
        model=PPO("MlpPolicy",env,learning_rate=float(learning_rate),n_steps=n_steps,
            batch_size=max(2,batch_size),n_epochs=5,gamma=.99,gae_lambda=.95,
            clip_range=.2,seed=int(seed),device="cpu",verbose=0,
            policy_kwargs={"net_arch":{"pi":[128,128],"vf":[128,128]}})

    write_json(progress_path,{"state":"initializing","phase":"model","timesteps":initial_timesteps,
        "target_timesteps":int(timesteps),"episodes":0,"elapsed_seconds":0.0,"latest_episode_reward":None,
        "message":"Continuing the compatible checkpoint." if continue_from else "Constructing the PPO policy network."})

    class Progress(BaseCallback):
        def __init__(self):
            super().__init__()
            self.rows=[];self.episode_count=0;self.last_logged_steps=0;self.last_checkpoint_steps=initial_timesteps
            self.last_metrics_steps=-1;self.latest_metrics={};self.stopped_by_user=False
            self.component_totals={};self.component_steps=0

        def _status(self,state="training",message="PPO rollouts are running."):
            elapsed=max(.001,time.monotonic()-started);current=int(self.num_timesteps)
            vector_count=max(1,int(getattr(self.training_env,"num_envs",1)))
            world_steps=current//vector_count
            agent_transitions=world_steps*int(contract["active_units_per_team"])
            local_completed=max(0,current-initial_timesteps)
            local_world_steps=local_completed//vector_count
            world_speed=local_world_steps/elapsed
            agent_speed=local_world_steps*int(contract["active_units_per_team"])/elapsed
            remaining=max(0,int(timesteps)-local_completed)
            speed=local_completed/elapsed
            write_json(progress_path,{"state":state,"phase":"rollouts","timesteps":current,
                "ppo_transitions":current,"agent_transitions":agent_transitions,
                "world_steps":world_steps,"ppo_updates":int(getattr(self.model,"_n_updates",0)),
                "transitions_per_world_step":int(contract["active_units_per_team"]),
                "architecture":ppo_architecture,
                "target_timesteps":initial_timesteps+int(timesteps),"episodes":self.episode_count,
                "elapsed_seconds":round(elapsed,2),"steps_per_second":round(speed,2),
                "world_steps_per_second":round(world_speed,2),
                "agent_transitions_per_second":round(agent_speed,2),
                "eta_seconds":round(remaining/speed,2) if speed else None,
                "latest_episode_reward":self.rows[-1]["mean_team_reward"] if self.rows else None,
                "ppo_metrics":self.latest_metrics,"reward_component_totals":self.component_totals,
                "checkpoint":str(zipped) if zipped.exists() else None,
                "message":message})

        def _on_training_start(self):
            self._status()

        def _on_step(self):
            step_infos=self.locals.get("infos", [])
            component_rows=[info.get("reward_component_totals",{}) for info in step_infos if isinstance(info,dict)]
            if any(component_rows):self.component_steps+=1
            for components in component_rows:
                if components:
                    for key,value in components.items():self.component_totals[key]=self.component_totals.get(key,0.)+float(value)
            for info in step_infos:
                ep = info.get("episode") if isinstance(info, dict) else None
                if ep:
                    self.episode_count += 1
                    self.rows.append({
                        "timesteps": int(self.num_timesteps),
                        "episodes": self.episode_count,
                        "mean_team_reward": float(ep["r"]),
                        "episode_steps": int(ep["l"]),
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                    })
                    _write_csv(curve_path, self.rows)
            log_interval=max(16,int(getattr(self.model,"n_steps",16))*max(1,int(getattr(self.training_env,"num_envs",1)))//4)
            if self.num_timesteps - self.last_logged_steps >= log_interval or self.num_timesteps >= timesteps:
                self.last_logged_steps = self.num_timesteps
                self._status()
            values=getattr(self.model.logger,"name_to_value",{})
            aliases={"policy_loss":"train/policy_gradient_loss","value_loss":"train/value_loss",
                "entropy":"train/entropy_loss","approx_kl":"train/approx_kl",
                "clip_fraction":"train/clip_fraction","explained_variance":"train/explained_variance"}
            if self.num_timesteps-self.last_metrics_steps>=max(1,int(self.model.n_steps)):
                self.latest_metrics={k:float(values[v]) for k,v in aliases.items()
                    if v in values and np.isfinite(float(values[v]))}
                if self.latest_metrics:
                    metric_path=output/"ppo_metrics.csv";metric_rows=_read_csv(metric_path)
                    metric_rows.append({"timesteps":int(self.num_timesteps),"elapsed_seconds":round(time.monotonic()-started,3),**self.latest_metrics})
                    _write_csv(metric_path,metric_rows)
                self.last_metrics_steps=self.num_timesteps
            if (output/"pause").exists() and not (output/"cancel").exists():
                save_checkpoint(self.model,"paused_checkpoint");self._status("paused","Training paused; checkpoint saved.")
                while (output/"pause").exists() and not (output/"cancel").exists():time.sleep(.2)
                if not (output/"cancel").exists():self._status("training","Training resumed.")
            if self.num_timesteps-self.last_checkpoint_steps>=max(1,int(checkpoint_interval)):
                save_checkpoint(self.model,"periodic_checkpoint");self.last_checkpoint_steps=self.num_timesteps
            if (output/"cancel").exists():self.stopped_by_user=True;return False
            return True

        def _on_training_end(self):save_checkpoint(self.model,"final_checkpoint")

    try:
        callback=Progress()
        model.learn(total_timesteps=int(timesteps),callback=callback,progress_bar=False,
                    reset_num_timesteps=continue_from is None)
        training_rows = _read_csv(curve_path)
        write_json(progress_path, {
            "state": "finalizing", "phase": "artifacts",
            "timesteps": int(model.num_timesteps), "target_timesteps": int(timesteps),
            "episodes": len(training_rows),
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "latest_episode_reward": float(training_rows[-1]["mean_team_reward"]) if training_rows else None,
            "message": "Training finished; saving checkpoint and learning curve.",
        })
    finally:
        env.close()
    digest = hashlib.sha256(zipped.read_bytes()).hexdigest()
    write_json(output / "manifest.json", {
        **_source_metadata(),
        "backend": "analytical_training", "algorithm": "Stable-Baselines3 PPO",
        "algorithm_version": _sb3_version(), "framework": "PettingZoo ParallelEnv + Gymnasium team adapter",
        "control_mode": "shared per-agent policy, 6 continuous controls" if ppo_architecture=="parameter_sharing" else "centralized joint action, 8 agents x 6 continuous controls",
        "architecture":"parameter-sharing PPO with local critic; not MAPPO" if ppo_architecture=="parameter_sharing" else "centralized PPO; not MAPPO or parameter-sharing PPO",
        "curriculum_tier":tier,"active_units_per_team":contract["active_units_per_team"],
        "combat_enabled":contract["combat_enabled"],"environment_semantics_version":ENVIRONMENT_SEMANTICS_VERSION,
        "reward_semantics_version":REWARD_SEMANTICS_VERSION,
        "fire_rate_multiplier":contract["fire_rate_multiplier"],
        "continued_from":str(continue_from) if continue_from else None,"initial_timesteps":initial_timesteps,
        "ppo_metrics_file":"ppo_metrics.csv",
        "seed": int(seed), "target_timesteps": int(timesteps),
        "actual_timesteps": int(model.num_timesteps), "episode_length_limit": int(max_steps),
        "ppo_transition_unit":"one vector-env sample; parameter-sharing has one per active agent, centralized has one joint-team sample",
        "transitions_per_world_step":int(contract["active_units_per_team"]),
        "actual_world_steps":int(model.num_timesteps)//max(1,int(getattr(model.get_env(),"num_envs",1))),
        "actual_agent_transitions":(int(model.num_timesteps)//max(1,int(getattr(model.get_env(),"num_envs",1))))*int(contract["active_units_per_team"]),
        "ppo_updates":int(getattr(model,"_n_updates",0)),
        "learning_rate": float(model.learning_rate),"n_steps":int(model.n_steps),"batch_size":int(model.batch_size),
        "n_epochs":int(model.n_epochs),"gamma":float(model.gamma),"gae_lambda":float(model.gae_lambda),
        "clip_range":float(model.clip_range(1.) if callable(model.clip_range) else model.clip_range),
        "policy_network":{"pi":[128,128],"vf":[128,128]},"checkpoint": str(zipped),
        "checkpoint_sha256": digest, "elapsed_seconds": round(time.monotonic() - started, 3),
        "reward_coefficients": _effective_rewards(reward_coefficients),
        "custom_reward": bool(reward_function),
        "reward_file_sha256": reward_file_hash,
        "created_utc": datetime.now(timezone.utc).isoformat(),
    })
    training_rows=_read_csv(curve_path)
    write_json(output / "summary.json", {
        "backend":"analytical_training","algorithm":"Stable-Baselines3 PPO",
        "target_timesteps":int(timesteps),"actual_timesteps":int(model.num_timesteps),
        "episodes":len(training_rows),
        "mean_training_team_reward":float(np.mean([float(row["mean_team_reward"]) for row in training_rows])) if training_rows else None,
        "checkpoint":str(zipped),"checkpoint_sha256":digest,
        "training_curve_is_not_independent_evaluation":True,
        "initial_timesteps":initial_timesteps,"curriculum_tier":tier,
        "ppo_architecture":ppo_architecture,
    })
    write_json(output/"reward_components.json",{
        "schema":"flyswarm.reward_diagnostics.v1","semantics_version":REWARD_SEMANTICS_VERSION,
        "training_world_steps":callback.component_steps,"custom_reward":bool(reward_function),
        "raw_component_totals":callback.component_totals,
        "raw_component_means_per_world_step":{key:value/max(1,callback.component_steps) for key,value in callback.component_totals.items()},
        "standard_coefficient_contributions":None if reward_function else {
            key:value*reward_values.get(key,0.) for key,value in callback.component_totals.items()},
        "note":"For custom reward.py, raw components are reported; arbitrary student code cannot be decomposed additively without changing its semantics."})
    write_json(output / "config.json", {
        "algorithm":"Stable-Baselines3 PPO","seed":int(seed),"timesteps":int(timesteps),
        "ppo_transition_unit":"one vector-env sample; parameter-sharing has one per active agent, centralized has one joint-team sample",
        "transitions_per_world_step":int(contract["active_units_per_team"]),
        "max_steps":int(max_steps),"learning_rate":float(learning_rate),
        "reward_coefficients":_effective_rewards(reward_coefficients),
        "vehicle_ids":list(DEFAULT_COMPOSITION),"opponent":"fixed objective-seeking and aim-aware rule policy",
        "custom_reward":bool(reward_function),
        "curriculum_tier":tier,"active_units_per_team":contract["active_units_per_team"],
        "fire_rate_multiplier":contract["fire_rate_multiplier"],
        "reward_semantics_version":REWARD_SEMANTICS_VERSION,
        "ppo_architecture":ppo_architecture,
    })
    if reward_file:
        (output/"student_code").mkdir(exist_ok=True)
        shutil.copy2(reward_file,output/"student_code/reward.py")
    plot_error = None
    try:
        _plot_learning_curve(curve_path, output / "plots" / "learning_curve.png")
        _plot_ppo_diagnostics(output/"ppo_metrics.csv",output/"plots"/"ppo_diagnostics.png")
    except Exception as exc:  # A chart is supplemental; preserve a valid checkpoint and results.
        plot_error = str(exc)
    current = json.loads(progress_path.read_text()) if progress_path.exists() else {}
    vector_count=max(1,int(getattr(model.get_env(),"num_envs",1)))
    final_world_steps=int(model.num_timesteps)//vector_count
    current.update({
        "state": "cancelled" if callback.stopped_by_user else "complete",
        "phase": "saved" if callback.stopped_by_user else "complete", "timesteps": int(model.num_timesteps),
        "ppo_transitions":int(model.num_timesteps),
        "agent_transitions":final_world_steps*int(contract["active_units_per_team"]),
        "world_steps":final_world_steps,"ppo_updates":int(getattr(model,"_n_updates",0)),
        "transitions_per_world_step":int(contract["active_units_per_team"]),
        "architecture":ppo_architecture,
        "checkpoint": str(zipped), "checkpoint_sha256": digest,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "message": "Stopped by user; the last consistent checkpoint was saved." if callback.stopped_by_user else
                   "Training and checkpoint are ready." if plot_error is None else
                   f"Training and checkpoint are ready; learning curve could not be rendered: {plot_error}",
    })
    write_json(progress_path, current)
    return {"checkpoint": str(zipped), "checkpoint_sha256": digest,
            "timesteps": int(model.num_timesteps), "episodes": len(_read_csv(curve_path)),
            "initial_timesteps":initial_timesteps,"curriculum_tier":tier,"experiment_dir": str(output)}


def _sb3_version():
    try:
        from importlib.metadata import version
        return version("stable-baselines3")
    except Exception:
        return "unknown"


def _checkpoint_metadata(path: Path) -> dict[str, Any]:
    path=Path(path).expanduser().resolve()
    sidecar=path.parent/(path.stem+".metadata.json")
    if not sidecar.is_file():return {"architecture":"centralized_joint_mlp_128x2","curriculum_tier":"C"}
    metadata=json.loads(sidecar.read_text(encoding="utf-8"))
    if metadata.get("checkpoint_sha256")!=hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError(f"Checkpoint checksum mismatch: {path}")
    return metadata


def _read_csv(path: Path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _plot_learning_curve(csv_path: Path, png_path: Path) -> None:
    rows = _read_csv(csv_path)
    if not rows:
        return
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        steps = [int(row["timesteps"]) for row in rows]
        rewards = [float(row["mean_team_reward"]) for row in rows]
        window=max(1,min(10,len(rewards)))
        rolling=[float(np.mean(rewards[max(0,index-window+1):index+1])) for index in range(len(rewards))]
        png_path.parent.mkdir(parents=True, exist_ok=True)
        figure, axis = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
        axis.plot(steps, rewards, marker=".", linewidth=1, alpha=.45,label="Episode return")
        axis.plot(steps, rolling, linewidth=2,label=f"Rolling mean ({window})")
        axis.set(xlabel="PPO transitions", ylabel="Episode return", title="FlySwarm PPO training reward")
        axis.legend()
        axis.grid(alpha=.25)
        figure.savefig(png_path, dpi=150)
        plt.close(figure)
    except ImportError:
        return


def _plot_ppo_diagnostics(csv_path:Path,png_path:Path)->None:
    rows=_read_csv(csv_path)
    if not rows:return
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fields=[("policy_loss","Policy gradient loss"),("value_loss","Value loss"),
                ("entropy","Entropy loss"),("approx_kl","Approximate KL"),
                ("clip_fraction","Clip fraction"),("explained_variance","Explained variance")]
        figure,axes=plt.subplots(3,2,figsize=(10,9),constrained_layout=True)
        for axis,(field,title) in zip(axes.flat,fields):
            pairs=[(int(row["timesteps"]),float(row[field])) for row in rows if field in row and row[field]!=""]
            if pairs:
                axis.plot([x for x,_ in pairs],[y for _,y in pairs],linewidth=1.5)
                axis.set_title(title);axis.set_xlabel("PPO transitions");axis.grid(alpha=.25)
            else:axis.set_visible(False)
        png_path.parent.mkdir(parents=True,exist_ok=True);figure.savefig(png_path,dpi=150);plt.close(figure)
    except ImportError:return


def evaluate_sb3(checkpoint: Path, output: Path, episodes: int = 5,
                 seed: int = 1001, max_steps: int = 300, deterministic=True,
                 reward_coefficients=None,curriculum_tier: str="C") -> dict[str, Any]:
    try:
        from stable_baselines3 import PPO
    except ImportError as exc:
        raise RuntimeError("Evaluation requires stable-baselines3; install requirements-marl.txt") from exc
    output.mkdir(parents=True, exist_ok=False)
    metadata=_checkpoint_metadata(checkpoint)
    if metadata.get("curriculum_tier","C")!=str(curriculum_tier).upper():
        raise ValueError("Checkpoint curriculum tier does not match the selected evaluation tier.")
    architecture="parameter_sharing" if metadata.get("architecture")=="parameter_sharing_mlp_128x2" else "centralized"
    model = PPO.load(str(checkpoint), device="cpu")
    rows = []
    for index in range(int(episodes)):
        episode_seed = seed + index
        env = FlySwarmParallelEnv(max_steps=max_steps, reward_coefficients=reward_coefficients,curriculum_tier=curriculum_tier)
        observations, _ = env.reset(seed=episode_seed)
        replay = output / "replays" / f"trained-seed-{episode_seed}.jsonl"
        start_replay(replay, env, episode_seed, "stable_baselines3_ppo")
        rows.append(_step_episode(env, observations, episode_seed, "stable_baselines3_ppo",
                                  f"trained-{episode_seed}", replay, ppo_model=model,
                                  deterministic=deterministic,ppo_architecture=architecture))
    _write_run_outputs(output, rows, "ppo_evaluation", seed, max_steps, reward_coefficients)
    manifest=json.loads((output/"manifest.json").read_text());manifest.update({"curriculum_tier":curriculum_tier,"reward_semantics_version":REWARD_SEMANTICS_VERSION});write_json(output/"manifest.json",manifest)
    _plot_evaluation(rows, output / "plots" / "evaluation.png")
    return {"experiment_dir": str(output), "runs": rows, "mean_team_reward": _mean(rows, "team_reward")}


def compare_paired(checkpoint: Path, output: Path, episodes: int = 5,
                   seed: int = 1001, max_steps: int = 300,
                   reward_coefficients=None,curriculum_tier: str="C") -> dict[str, Any]:
    """Evaluate random and PPO on the same seeds and fixed rule opponents."""
    try:
        from stable_baselines3 import PPO
    except ImportError as exc:
        raise RuntimeError("Paired comparison requires stable-baselines3; install requirements-marl.txt") from exc
    output.mkdir(parents=True, exist_ok=False)
    metadata=_checkpoint_metadata(checkpoint)
    if metadata.get("curriculum_tier","C")!=str(curriculum_tier).upper():
        raise ValueError("Checkpoint curriculum tier does not match the selected comparison tier.")
    architecture="parameter_sharing" if metadata.get("architecture")=="parameter_sharing_mlp_128x2" else "centralized"
    model = PPO.load(str(checkpoint), device="cpu")
    rows = []
    for index in range(int(episodes)):
        episode_seed = seed + index
        for policy_id in ("uniform_random", "stable_baselines3_ppo"):
            env = FlySwarmParallelEnv(max_steps=max_steps, reward_coefficients=reward_coefficients,curriculum_tier=curriculum_tier)
            observations, _ = env.reset(seed=episode_seed)
            replay_path = output / "replays" / f"{policy_id}-seed-{episode_seed}.jsonl"
            start_replay(replay_path, env, episode_seed, policy_id)
            rng = np.random.default_rng(episode_seed)
            rows.append(_step_episode(
                env, observations, episode_seed, policy_id, f"{policy_id}-{episode_seed}",
                replay_path, ppo_model=model if policy_id == "stable_baselines3_ppo" else None,
                rng=rng, deterministic=True,ppo_architecture=architecture,
            ))
    grouped = {policy: [row for row in rows if row["policy_id"] == policy]
               for policy in ("uniform_random", "stable_baselines3_ppo")}
    summary = {
        "backend": "analytical_training", "protocol": "paired common test seeds, same rule opponent",
        "curriculum_tier":curriculum_tier,"reward_semantics_version":REWARD_SEMANTICS_VERSION,
        "seeds": list(range(seed, seed + episodes)), "episodes_per_policy": int(episodes),
        "team_reward_definition": "sum of the eight controlled blue agents' per-step rewards across the episode",
        "random_mean_team_reward": _mean(grouped["uniform_random"], "team_reward"),
        "ppo_mean_team_reward": _mean(grouped["stable_baselines3_ppo"], "team_reward"),
        "random_blue_win_rate": _win_rate(grouped["uniform_random"]),
        "ppo_blue_win_rate": _win_rate(grouped["stable_baselines3_ppo"]),
        "random_mean_captures": _mean(grouped["uniform_random"], "captures"),
        "ppo_mean_captures": _mean(grouped["stable_baselines3_ppo"], "captures"),
        "random_mean_kills": _mean(grouped["uniform_random"], "kills"),
        "ppo_mean_kills": _mean(grouped["stable_baselines3_ppo"], "kills"),
        "caveat": "Same initial seed and opponent do not force identical trajectories after policy actions diverge.",
        "runs": rows,
    }
    _write_csv(output / "comparison.csv", rows)
    _write_csv(output / "evaluation.csv", rows)
    write_json(output / "summary.json", summary)
    write_json(output / "config.json", {
        "algorithm":"paired Random vs Stable-Baselines3 PPO","seeds":summary["seeds"],
        "episodes_per_policy":int(episodes),"max_steps":int(max_steps),
        "reward_coefficients":_effective_rewards(reward_coefficients),
        "vehicle_ids":list(DEFAULT_COMPOSITION),"opponent":"fixed objective-seeking and aim-aware rule policy",
    })
    write_json(output / "manifest.json", {
        **_source_metadata(),
        "backend": "analytical_training", "algorithm": "Stable-Baselines3 PPO",
        "checkpoint": str(checkpoint), "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "seeds": summary["seeds"], "episode_length_limit": max_steps,
        "reward_coefficients": _effective_rewards(reward_coefficients),
        "opponent": "same deterministic objective-seeking rule policy for both runs",
    })
    _plot_comparison(grouped, output / "plots" / "random_vs_ppo.png")
    return {"experiment_dir": str(output), **{k: v for k, v in summary.items() if k != "runs"}, "runs": rows}


def compare_all_policies(output: Path, agent_file: Path, standard_checkpoint: Path,
                         custom_reward_checkpoint: Path, episodes: int = 5,
                         seed: int = 1001, max_steps: int = 300,curriculum_tier: str="C") -> dict[str, Any]:
    """Compare four policies under one unchanged, standard evaluation protocol."""
    try:
        from stable_baselines3 import PPO
    except ImportError as exc:
        raise RuntimeError("Four-way comparison requires stable-baselines3") from exc
    standard_meta=_checkpoint_metadata(standard_checkpoint);custom_meta=_checkpoint_metadata(custom_reward_checkpoint)
    if any(meta.get("curriculum_tier","C")!=str(curriculum_tier).upper() for meta in (standard_meta,custom_meta)):
        raise ValueError("Both PPO checkpoints must match the selected curriculum tier.")
    standard_arch="parameter_sharing" if standard_meta.get("architecture")=="parameter_sharing_mlp_128x2" else "centralized"
    custom_arch="parameter_sharing" if custom_meta.get("architecture")=="parameter_sharing_mlp_128x2" else "centralized"
    standard_model=PPO.load(str(standard_checkpoint),device="cpu")
    custom_model=PPO.load(str(custom_reward_checkpoint),device="cpu")
    policies=("uniform_random","student_python_agent","ppo_standard_reward","ppo_custom_reward")
    _prepare_output(output)
    rows=[]
    agent=ManagedStudentAgent(agent_file)
    try:
        for episode in range(int(episodes)):
            episode_seed=int(seed+episode)
            for swap_sides in (False,True):
              for policy_id in policies:
                env=FlySwarmParallelEnv(max_steps=max_steps,curriculum_tier=curriculum_tier)
                try:
                    observations,_=env.reset(seed=episode_seed,options={"swap_sides":swap_sides})
                    condition="swapped_sides" if swap_sides else "default_sides"
                    replay=output/"replays"/f"{policy_id}-{condition}-seed-{episode_seed}.jsonl"
                    start_replay(replay,env,episode_seed,policy_id)
                    kwargs={}
                    rng=None
                    if policy_id=="student_python_agent":
                        kwargs["student_agent"]=agent
                    elif policy_id=="ppo_standard_reward":
                        kwargs["ppo_model"]=standard_model;kwargs["deterministic"]=True;kwargs["ppo_architecture"]=standard_arch
                    elif policy_id=="ppo_custom_reward":
                        kwargs["ppo_model"]=custom_model;kwargs["deterministic"]=True;kwargs["ppo_architecture"]=custom_arch
                    else:
                        rng=np.random.default_rng(episode_seed)
                    row=_step_episode(env,observations,episode_seed,policy_id,
                                      f"{policy_id}-{condition}-{episode_seed}",replay,rng=rng,**kwargs)
                    row["start_condition"]=condition
                    row["evaluation_protocol"]="standard_default_reward_same_seed_fixed_opponent"
                    row["curriculum_tier"]=curriculum_tier
                    rows.append(row)
                finally:
                    env.close()
    finally:
        agent.close()
    groups={policy:[r for r in rows if r["policy_id"]==policy and r["start_condition"]=="default_sides"] for policy in policies}
    condition_groups={condition:{policy:[r for r in rows if r["policy_id"]==policy and r["start_condition"]==condition]
                                 for policy in policies}
                      for condition in ("default_sides","swapped_sides")}
    _write_csv(output/"comparison.csv",rows)
    _write_csv(output/"evaluation.csv",rows)
    summary={"backend":"analytical_training","protocol":"same independent seeds and fixed opponent; starting sides reported separately; default standard reward",
             "curriculum_tier":curriculum_tier,"reward_semantics_version":REWARD_SEMANTICS_VERSION,
             "training_reward_is_not_used_for_ranking":True,"seeds":list(range(seed,seed+episodes)),
             "episodes_per_policy":int(episodes),"policies":{
                 name:{"mean_standard_evaluation_reward":_mean(group,"standard_evaluation_reward"),
                       "std_standard_evaluation_reward":float(np.std([r["standard_evaluation_reward"] for r in group],ddof=1)) if len(group)>1 else 0.,
                       "median_standard_evaluation_reward":float(np.median([r["standard_evaluation_reward"] for r in group])) if group else 0.,
                       "win_rate":_win_rate(group),"mean_captures":_mean(group,"captures"),
                       "mean_kills":_mean(group,"kills"),"mean_losses":_mean(group,"deaths")}
                 for name,group in groups.items()},
             "conditions":{
                 condition:{name:{"mean_standard_evaluation_reward":_mean(group,"standard_evaluation_reward"),
                       "std_standard_evaluation_reward":float(np.std([r["standard_evaluation_reward"] for r in group],ddof=1)) if len(group)>1 else 0.,
                       "median_standard_evaluation_reward":float(np.median([r["standard_evaluation_reward"] for r in group])) if group else 0.,
                       "win_rate":_win_rate(group),"mean_captures":_mean(group,"captures"),
                       "mean_kills":_mean(group,"kills"),"mean_losses":_mean(group,"deaths")}
                 for name,group in policy_groups.items()}
                 for condition,policy_groups in condition_groups.items()},
             "runs":rows}
    write_json(output/"summary.json",summary)
    write_json(output/"config.json",{"protocol":summary["protocol"],"seeds":summary["seeds"],
                 "episodes_per_policy":int(episodes),"max_steps":int(max_steps),
                 "reward":"unchanged DEFAULT_REWARDS evaluation metric"})
    write_json(output/"manifest.json",{**_source_metadata(),"agent_file_sha256":hashlib.sha256(Path(agent_file).read_bytes()).hexdigest(),
                 "standard_checkpoint_sha256":hashlib.sha256(Path(standard_checkpoint).read_bytes()).hexdigest(),
                 "custom_reward_checkpoint_sha256":hashlib.sha256(Path(custom_reward_checkpoint).read_bytes()).hexdigest(),
                 "security_note":"Student code runs with current-user permissions; not a sandbox."})
    _plot_comparison({name:group for name,group in groups.items()},output/"plots/comparison.png")
    return {"experiment_dir":str(output),"policies":summary["policies"],"conditions":summary["conditions"],"seeds":summary["seeds"]}


def _win_rate(rows):
    return float(np.mean([row["winner"] == "blue" for row in rows])) if rows else 0.0


def _plot_evaluation(rows, path):
    _plot_comparison({"evaluation": rows}, path)


def _plot_comparison(groups, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        names = list(groups)
        values = [[r["team_reward"] for r in groups[n]] for n in names]
        path.parent.mkdir(parents=True, exist_ok=True)
        figure, axis = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
        axis.boxplot(values, tick_labels=names, showmeans=True)
        axis.set(ylabel="Episode team reward", title="Paired FlySwarm policy evaluation")
        axis.grid(axis="y", alpha=.25)
        figure.savefig(path, dpi=150)
        plt.close(figure)
    except ImportError:
        return
