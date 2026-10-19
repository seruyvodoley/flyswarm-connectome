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

from .env import ACTION_NAMES, AGENTS, DEFAULT_REWARDS, FlySwarmParallelEnv
from .roles import DEFAULT_COMPOSITION
from .student_code import ManagedStudentAgent, load_reward

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
            target = self.env.zones[local % len(self.env.zones)]
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
                 reward_coefficients: dict[str, float] | None = None, reward_function=None):
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
    temporary.replace(path)


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
    return DEFAULT_REWARDS | dict(reward_coefficients or {})


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
    })
    append_replay(path, seed, env.snapshot({}, {}, kind="frame"))


def _step_episode(env: FlySwarmParallelEnv, observations: dict[str, np.ndarray],
                  seed: int, policy_id: str, run_id: str, replay_path: Path | None = None,
                  ppo_model=None, rng: np.random.Generator | None = None,
                  deterministic: bool = False, student_agent=None) -> dict[str, Any]:
    members = BLUE
    rule_red = FixedRulePolicy(env, 1).actions
    total_reward = 0.0
    captures = kills = deaths = 0
    standard_evaluation_reward = 0.0
    episode_steps = 0
    while env.agents:
        actions = rule_red()
        if ppo_model is not None:
            team_obs = np.concatenate([observations[a] for a in members]).astype(np.float32)
            action, _ = ppo_model.predict(team_obs, deterministic=deterministic)
            actions.update({a: np.asarray(action).reshape(8, 6)[i] for i, a in enumerate(BLUE)})
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
        else:
            for a in members:
                actions[a] = rng.uniform(-1, 1, size=6).astype(np.float32)
        old_health = env.health.copy()
        old_owners = env.zones_owner.copy()
        observations, rewards, terms, truncs, infos = env.step(actions)
        team_step_reward = float(sum(rewards[a] for a in members))
        total_reward += team_step_reward
        standard_evaluation_reward += float(sum(infos[a]["standard_evaluation_reward"] for a in members))
        episode_steps += 1
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
    winner = "blue" if tickets[0] > tickets[1] else ("red" if tickets[1] > tickets[0] else "draw")
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
    }


def run_student_agent(output: Path, agent_file: Path, episodes: int = 3,
                      seed: int = 101, max_steps: int = 300,
                      reward_file: Path | None = None) -> dict[str, Any]:
    """Run a student's real Python strategy in the analytical PettingZoo env."""
    agent_file = Path(agent_file).expanduser().resolve()
    reward_file = Path(reward_file).expanduser().resolve() if reward_file else None
    reward_function = load_reward(reward_file) if reward_file else None
    _prepare_output(output)
    (output / "student_code").mkdir()
    shutil.copy2(agent_file, output / "student_code/agent.py")
    if reward_file:
        shutil.copy2(reward_file, output / "student_code/reward.py")
    rows=[]
    agent = ManagedStudentAgent(agent_file)
    try:
        for episode in range(int(episodes)):
            episode_seed=int(seed+episode)
            env=FlySwarmParallelEnv(max_steps=max_steps,reward_function=reward_function)
            try:
                observations,_=env.reset(seed=episode_seed)
                replay=output/"replays"/f"student-seed-{episode_seed}.jsonl"
                start_replay(replay,env,episode_seed,"student_python_agent")
                rows.append(_step_episode(env,observations,episode_seed,"student_python_agent",
                                          f"student-{episode_seed}",replay,student_agent=agent))
            finally:
                env.close()
    finally:
        agent.close()
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
    return {"experiment_dir":str(output),"runs":rows,
            "mean_training_reward":_mean(rows,"training_reward"),
            "mean_standard_evaluation_reward":_mean(rows,"standard_evaluation_reward")}


def run_random_baseline(output: Path, episodes: int = 3, seed: int = 101,
                        max_steps: int = 300, reward_coefficients=None) -> dict[str, Any]:
    """Run uniform random blue actions against the fixed rule opponent."""
    _prepare_output(output)
    rows = []
    for episode in range(int(episodes)):
        episode_seed = int(seed + episode)
        rng = np.random.default_rng(episode_seed)
        env = FlySwarmParallelEnv(max_steps=max_steps, reward_coefficients=reward_coefficients)
        observations, _ = env.reset(seed=episode_seed)
        replay = output / "replays" / f"random-seed-{episode_seed}.jsonl"
        start_replay(replay, env, episode_seed, "uniform_random")
        rows.append(_step_episode(env, observations, episode_seed, "uniform_random",
                                  f"random-{episode_seed}", replay, rng=rng))
    _write_run_outputs(output, rows, "random_baseline", seed, max_steps, reward_coefficients)
    return {"experiment_dir": str(output), "runs": rows, "mean_team_reward": _mean(rows, "team_reward")}


def _mean(rows, field):
    return float(np.mean([float(row[field]) for row in rows])) if rows else 0.0


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
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
                  reward_function=None, reward_file: Path | None = None) -> dict[str, Any]:
    """Train the real Stable-Baselines3 PPO implementation on the team wrapper."""
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.callbacks import BaseCallback
    except ImportError as exc:
        raise RuntimeError("PPO training requires stable-baselines3; install requirements-marl.txt") from exc

    _prepare_output(output)
    progress_path = progress_path or output / "progress.json"
    curve_path = output / "training.csv"

    class Progress(BaseCallback):
        def __init__(self):
            super().__init__()
            self.started = time.monotonic()
            self.rows = []
            self.episode_count = 0
            self.last_logged_steps = 0

        def _on_step(self):
            for info in self.locals.get("infos", []):
                ep = info.get("episode") if isinstance(info, dict) else None
                if ep:
                    self.episode_count += 1
                    self.rows.append({
                        "timesteps": int(self.num_timesteps),
                        "episodes": self.episode_count,
                        "mean_team_reward": float(ep["r"]),
                        "episode_steps": int(ep["l"]),
                        "elapsed_seconds": round(time.monotonic() - self.started, 3),
                    })
                    _write_csv(curve_path, self.rows)
            if self.num_timesteps - self.last_logged_steps >= 16 or self.num_timesteps >= timesteps:
                self.last_logged_steps = self.num_timesteps
                write_json(progress_path, {
                    "state": "training", "timesteps": int(self.num_timesteps),
                    "target_timesteps": int(timesteps), "episodes": self.episode_count,
                    "elapsed_seconds": round(time.monotonic() - self.started, 2),
                    "latest_episode_reward": self.rows[-1]["mean_team_reward"] if self.rows else None,
                })
            return not (output / "cancel").exists()

    env = TeamGymnasiumEnv(seed=seed, max_steps=max_steps, reward_coefficients=reward_coefficients,
                           reward_function=reward_function)
    n_steps = min(256, max(16, int(timesteps)))
    model = PPO(
        "MlpPolicy", env, learning_rate=float(learning_rate), n_steps=n_steps,
        batch_size=min(64, max(8, n_steps)), n_epochs=5, gamma=.99, gae_lambda=.95,
        clip_range=.2, seed=int(seed), device="cpu", verbose=0,
        policy_kwargs={"net_arch": {"pi": [128, 128], "vf": [128, 128]}},
    )
    started = time.monotonic()
    try:
        model.learn(total_timesteps=int(timesteps), callback=Progress(), progress_bar=False)
        checkpoint = output / "checkpoint" / "ppo_team"
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        model.save(str(checkpoint))
    finally:
        env.close()
    zipped = checkpoint.with_suffix(".zip")
    digest = hashlib.sha256(zipped.read_bytes()).hexdigest()
    write_json(output / "manifest.json", {
        **_source_metadata(),
        "backend": "analytical_training", "algorithm": "Stable-Baselines3 PPO",
        "algorithm_version": _sb3_version(), "framework": "PettingZoo ParallelEnv + Gymnasium team adapter",
        "control_mode": "centralized joint action, 8 agents x 6 continuous controls",
        "seed": int(seed), "target_timesteps": int(timesteps),
        "actual_timesteps": int(model.num_timesteps), "episode_length_limit": int(max_steps),
        "learning_rate": float(learning_rate), "checkpoint": str(zipped),
        "checkpoint_sha256": digest, "elapsed_seconds": round(time.monotonic() - started, 3),
        "reward_coefficients": _effective_rewards(reward_coefficients),
        "custom_reward": bool(reward_function),
        "reward_file_sha256": hashlib.sha256(Path(reward_file).read_bytes()).hexdigest() if reward_file else None,
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
    })
    write_json(output / "config.json", {
        "algorithm":"Stable-Baselines3 PPO","seed":int(seed),"timesteps":int(timesteps),
        "max_steps":int(max_steps),"learning_rate":float(learning_rate),
        "reward_coefficients":_effective_rewards(reward_coefficients),
        "vehicle_ids":list(DEFAULT_COMPOSITION),"opponent":"fixed objective-seeking and aim-aware rule policy",
        "custom_reward":bool(reward_function),
    })
    if reward_file:
        (output/"student_code").mkdir(exist_ok=True)
        shutil.copy2(reward_file,output/"student_code/reward.py")
    current = json.loads(progress_path.read_text()) if progress_path.exists() else {}
    current.update({"state": "complete", "timesteps": int(model.num_timesteps), "checkpoint": str(zipped), "checkpoint_sha256": digest})
    write_json(progress_path, current)
    _plot_learning_curve(curve_path, output / "plots" / "learning_curve.png")
    return {"checkpoint": str(zipped), "checkpoint_sha256": digest,
            "timesteps": int(model.num_timesteps), "episodes": len(_read_csv(curve_path)),
            "experiment_dir": str(output)}


def _sb3_version():
    try:
        from importlib.metadata import version
        return version("stable-baselines3")
    except Exception:
        return "unknown"


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
        png_path.parent.mkdir(parents=True, exist_ok=True)
        figure, axis = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
        axis.plot(steps, rewards, marker=".", linewidth=1.5)
        axis.set(xlabel="Joint environment steps", ylabel="Episode team reward", title="FlySwarm PPO learning curve")
        axis.grid(alpha=.25)
        figure.savefig(png_path, dpi=150)
        plt.close(figure)
    except ImportError:
        return


def evaluate_sb3(checkpoint: Path, output: Path, episodes: int = 5,
                 seed: int = 1001, max_steps: int = 300, deterministic=True,
                 reward_coefficients=None) -> dict[str, Any]:
    try:
        from stable_baselines3 import PPO
    except ImportError as exc:
        raise RuntimeError("Evaluation requires stable-baselines3; install requirements-marl.txt") from exc
    output.mkdir(parents=True, exist_ok=False)
    model = PPO.load(str(checkpoint), device="cpu")
    rows = []
    for index in range(int(episodes)):
        episode_seed = seed + index
        env = FlySwarmParallelEnv(max_steps=max_steps, reward_coefficients=reward_coefficients)
        observations, _ = env.reset(seed=episode_seed)
        replay = output / "replays" / f"trained-seed-{episode_seed}.jsonl"
        start_replay(replay, env, episode_seed, "stable_baselines3_ppo")
        rows.append(_step_episode(env, observations, episode_seed, "stable_baselines3_ppo",
                                  f"trained-{episode_seed}", replay, ppo_model=model,
                                  deterministic=deterministic))
    _write_run_outputs(output, rows, "ppo_evaluation", seed, max_steps, reward_coefficients)
    _plot_evaluation(rows, output / "plots" / "evaluation.png")
    return {"experiment_dir": str(output), "runs": rows, "mean_team_reward": _mean(rows, "team_reward")}


def compare_paired(checkpoint: Path, output: Path, episodes: int = 5,
                   seed: int = 1001, max_steps: int = 300,
                   reward_coefficients=None) -> dict[str, Any]:
    """Evaluate random and PPO on the same seeds and fixed rule opponents."""
    try:
        from stable_baselines3 import PPO
    except ImportError as exc:
        raise RuntimeError("Paired comparison requires stable-baselines3; install requirements-marl.txt") from exc
    output.mkdir(parents=True, exist_ok=False)
    model = PPO.load(str(checkpoint), device="cpu")
    rows = []
    for index in range(int(episodes)):
        episode_seed = seed + index
        for policy_id in ("uniform_random", "stable_baselines3_ppo"):
            env = FlySwarmParallelEnv(max_steps=max_steps, reward_coefficients=reward_coefficients)
            observations, _ = env.reset(seed=episode_seed)
            replay_path = output / "replays" / f"{policy_id}-seed-{episode_seed}.jsonl"
            start_replay(replay_path, env, episode_seed, policy_id)
            rng = np.random.default_rng(episode_seed)
            rows.append(_step_episode(
                env, observations, episode_seed, policy_id, f"{policy_id}-{episode_seed}",
                replay_path, ppo_model=model if policy_id == "stable_baselines3_ppo" else None,
                rng=rng, deterministic=True,
            ))
    grouped = {policy: [row for row in rows if row["policy_id"] == policy]
               for policy in ("uniform_random", "stable_baselines3_ppo")}
    summary = {
        "backend": "analytical_training", "protocol": "paired common test seeds, same rule opponent",
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
                         seed: int = 1001, max_steps: int = 300) -> dict[str, Any]:
    """Compare four policies under one unchanged, standard evaluation protocol."""
    try:
        from stable_baselines3 import PPO
    except ImportError as exc:
        raise RuntimeError("Four-way comparison requires stable-baselines3") from exc
    standard_model=PPO.load(str(standard_checkpoint),device="cpu")
    custom_model=PPO.load(str(custom_reward_checkpoint),device="cpu")
    policies=("uniform_random","student_python_agent","ppo_standard_reward","ppo_custom_reward")
    _prepare_output(output)
    rows=[]
    agent=ManagedStudentAgent(agent_file)
    try:
        for episode in range(int(episodes)):
            episode_seed=int(seed+episode)
            for policy_id in policies:
                env=FlySwarmParallelEnv(max_steps=max_steps)
                try:
                    observations,_=env.reset(seed=episode_seed)
                    replay=output/"replays"/f"{policy_id}-seed-{episode_seed}.jsonl"
                    start_replay(replay,env,episode_seed,policy_id)
                    kwargs={}
                    rng=None
                    if policy_id=="student_python_agent":
                        kwargs["student_agent"]=agent
                    elif policy_id=="ppo_standard_reward":
                        kwargs["ppo_model"]=standard_model;kwargs["deterministic"]=True
                    elif policy_id=="ppo_custom_reward":
                        kwargs["ppo_model"]=custom_model;kwargs["deterministic"]=True
                    else:
                        rng=np.random.default_rng(episode_seed)
                    row=_step_episode(env,observations,episode_seed,policy_id,
                                      f"{policy_id}-{episode_seed}",replay,rng=rng,**kwargs)
                    row["evaluation_protocol"]="standard_default_reward_same_seed_fixed_opponent"
                    rows.append(row)
                finally:
                    env.close()
    finally:
        agent.close()
    groups={policy:[r for r in rows if r["policy_id"]==policy] for policy in policies}
    _write_csv(output/"comparison.csv",rows)
    _write_csv(output/"evaluation.csv",rows)
    summary={"backend":"analytical_training","protocol":"same independent seeds, fixed opponent, default standard reward",
             "training_reward_is_not_used_for_ranking":True,"seeds":list(range(seed,seed+episodes)),
             "episodes_per_policy":int(episodes),"policies":{
                 name:{"mean_standard_evaluation_reward":_mean(group,"standard_evaluation_reward"),
                       "win_rate":_win_rate(group),"mean_captures":_mean(group,"captures"),
                       "mean_kills":_mean(group,"kills"),"mean_losses":_mean(group,"deaths")}
                 for name,group in groups.items()},"runs":rows}
    write_json(output/"summary.json",summary)
    write_json(output/"config.json",{"protocol":summary["protocol"],"seeds":summary["seeds"],
                 "episodes_per_policy":int(episodes),"max_steps":int(max_steps),
                 "reward":"unchanged DEFAULT_REWARDS evaluation metric"})
    write_json(output/"manifest.json",{**_source_metadata(),"agent_file_sha256":hashlib.sha256(Path(agent_file).read_bytes()).hexdigest(),
                 "standard_checkpoint_sha256":hashlib.sha256(Path(standard_checkpoint).read_bytes()).hexdigest(),
                 "custom_reward_checkpoint_sha256":hashlib.sha256(Path(custom_reward_checkpoint).read_bytes()).hexdigest(),
                 "security_note":"Student code runs with current-user permissions; not a sandbox."})
    _plot_comparison({name:group for name,group in groups.items()},output/"plots/comparison.png")
    return {"experiment_dir":str(output),"policies":summary["policies"],"seeds":summary["seeds"]}


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
