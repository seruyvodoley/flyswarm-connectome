# FlySwarm MARL Python API

The MARL Laboratory runs student policies in the existing analytical `FlySwarmParallelEnv` used by Random and PPO. Godot displays recorded replays; it does not recompute their physics or outcomes. The installed app supplies Python and NumPy, so a student does not need a separate Python installation.

## `agent.py`

Implement `act(observation)`; an optional second parameter receives public episode context. The function is called once for each of the eight blue agents at every step. Return exactly six finite numbers in `[-1, 1]`:

| Index | Action | Meaning |
|---:|---|---|
| 0 | throttle | forward/reverse drive input |
| 1 | brake | braking input |
| 2 | steering | hull rotation input |
| 3 | turret | turret rotation input; ignored for fixed-gun vehicles |
| 4 | elevation | gun elevation input |
| 5 | fire | values above 0.5 request a shot |

```python
import numpy as np

def act(observation, context=None):
    action = np.zeros(6, dtype=np.float32)
    action[0] = 0.5
    return action
```

The current default observation has 30 float32 values (22 public base features and eight optional role-conditioning features). Indices 0–5 are connectome-signal features; 6–11 are normalized speed, reload, health, alive, turret heading, and gun elevation; 12–20 describe the assigned objective, its direction/distance/owner/progress, team and enemy tickets, and nearest visible enemy bearing/distance; index 21 is a bias feature. Indices 22–29 are one-hot vehicle class (medium/heavy/destroyer), one-hot country, aggression prior, objective prior, and standoff distance. If role conditioning is disabled by a programmatic caller, the observation contains only the first 22 values. Observation contents are the public API; no hidden opponent state is passed to `act`.

Optional context contains `agent_id`, `team` (`"blue"`), `episode_seed`, `episode_step`, and `team_index` (0–7). A module-level `reset(seed=...)` function may reset strategy state at each episode. Do not rely on filesystem state or execution order between agents.

## `reward.py`

`calculate_reward(components)` returns one finite number. This function is called in the backend during every environment step and its return value is the actual PPO training reward. If the file is absent, PPO uses the standard reward coefficients. PPO evaluations and four-way comparisons always calculate their ranking metrics with the unchanged default reward.

The component values have these meanings and signs:

| Key | Value | Sign / scale |
|---|---|---|
| `objective_progress` | positive progress toward an objective, divided by 100 | non-negative normalized increment |
| `objective_capture` | newly captured objective count | non-negative event count |
| `objective_neutralization` | objectives returned to neutral ownership | non-negative event count |
| `damage_dealt` | enemy health removed this step, summed for team | non-negative health amount |
| `enemy_kill` | enemies eliminated this step | non-negative event count |
| `own_death` | controlled vehicle losses this step | non-negative event count; apply a negative weight yourself |
| `ticket_delta` | enemy tickets lost minus own tickets lost | signed difference |
| `battle_win` | 1 when the team wins at episode end | non-negative indicator |
| `battle_loss` | 1 when the team loses at episode end | non-negative indicator; apply a negative weight yourself |
| `role_shaping` | engineered role shaping value | signed value clipped to `[-1, 1]` |

Components are raw values, not pre-weighted rewards. For example:

```python
def calculate_reward(c):
    return (3.0 * c["objective_capture"]
            + 0.01 * c["damage_dealt"]
            - 4.0 * c["own_death"]
            - 10.0 * c["battle_loss"])
```

Avoid applying a negative sign twice: `own_death` and `battle_loss` arrive as positive indicators. Components are the same for each teammate on a given team step; PPO's team reward is the sum across eight agents.

## Running and interpreting experiments

Use the Python tab to save or import `agent.py` and `reward.py`, check them, run the strategy, train PPO, evaluate on fresh seeds, compare policies, inspect replay, or export a ZIP. Each experiment gets its own timestamped directory and stores source copies and hashes, configuration, seeds, summary, tables, and replay; PPO runs also save a checkpoint and training curve. Results are not overwritten.

A custom training reward is not an effectiveness score. Compare Random, the student policy, standard-reward PPO, and custom-reward PPO on the same independent test seeds and use the standard evaluation reward, win rate, captures, kills, and losses. Same initial seed and opponent do not force identical trajectories once actions differ.

The runner uses a long-lived separate Python process for `agent.py`, with a per-call timeout and action validation. Custom `reward.py` runs in the backend process to avoid expensive IPC on every PPO step; cancelling the backend stops a stuck training job. This is process separation, not a security sandbox: Python code has the current user's permissions. Run only source you trust. The application does not claim isolation from filesystem or process access.

The practical ZIP contains the current student files and actual saved result files with hashes. It excludes research archives, MaleCNS datasets, and unrelated user files. Do not treat analytical replay as a high-fidelity Godot battle.
