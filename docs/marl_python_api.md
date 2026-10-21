# FlySwarm MARL Python API

The MARL Laboratory runs student policies in the existing analytical `FlySwarmParallelEnv` used by Random and PPO. Godot displays recorded replays; it does not recompute their physics or outcomes. The installed app supplies Python and NumPy, so a student does not need a separate Python installation.

## `agent.py`

Choose any control algorithm that fits the public API and available compute: rules, state machines, search, coordination, optimization, or a neural policy are all valid. FlySwarm does not assign a tactic or require a particular algorithm. Every student experiment uses the same full 8-versus-8 battle.

The individual interface is `act(observation, context=None)`. FlySwarm calls it once for each active blue vehicle at every synchronized world step. Return exactly six finite numbers in `[-1, 1]`:

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

Optional context contains `agent_id`, `team` (`"blue"`), `episode_seed`, `episode_step`, and `team_index` (0–7). Module-level state remains alive between steps. Define `reset(seed=...)` to initialize it at the start of each episode; `reset(seed)` is also accepted.

For centralized team logic, you may define `act_team(observations, contexts)`. It is called once per synchronized world step and receives one observation and context for each active blue vehicle, in `blue_0` through `blue_7` order. Return exactly one six-number action per input observation. If `act_team()` exists, it takes priority over `act()`; otherwise FlySwarm calls `act()` once per vehicle. The environment does not call the command function more than once for a world step. In the full 8×8 student environment all eight blue vehicles are active. Contexts and observations contain public data only.

Normal Python functions, classes, helper modules beside `agent.py`, NumPy, `random`, and the standard library are available. Other packages depend on what is installed in the bundled Python environment; arbitrary `pip` packages are not guaranteed. Agents have a per-world-step time limit. Bad shapes, non-numeric values, NaN/Infinity, out-of-range controls, exceptions, and timeouts stop that run with a traceback in its execution log.

## `reward.py`

`calculate_reward(components, observation=None, action=None, next_observation=None, context=None)` returns one finite number. The original one-argument form remains supported. During PPO training the returned value is the actual training reward. If no `reward.py` is supplied, PPO uses the standard reward coefficients. Independent evaluations and four-way comparisons always use the same standard metrics, regardless of the custom training reward.

The optional values are supplied together for the same agent and transition: the read-only current and next public observation arrays, the six applied actions, and `context`. Context contains the public agent/team IDs, episode seed and step, terminal flags and reason, winner, and events involving that agent. It does not contain hidden opponent positions or full simulator state. Reward is computed after the world step and objective updates, once per active agent transition. Components still describe that same transition; team-level events are divided across active teammates.

Reward module state persists between world steps. An optional `reset(seed)` is called at each episode start. The runner uses one long-lived worker and sends the batch for all agents in one message per synchronized world step. A slow reward function times out; returned values must be numeric finite scalars. A custom reward changes PPO's training signal only; it does not change the independent evaluation formula.

The component values have these meanings and signs:

| Key | Value | Sign / scale |
|---|---|---|
| `objective_progress` | positive progress toward an objective, divided by 100 | non-negative normalized increment |
| `objective_approach` | net movement toward the vehicle's assigned objective, divided by 100 m | signed per-agent distance delta clipped to `[-0.05, 0.05]` per step; moving back reverses reward, standing still adds zero |
| `objective_capture` | newly captured objective count | non-negative event count |
| `objective_neutralization` | objectives returned to neutral ownership | non-negative event count |
| `damage_dealt` | enemy health removed this step, summed for team | non-negative health amount |
| `enemy_kill` | enemies eliminated this step | non-negative event count |
| `own_death` | controlled vehicle losses this step | non-negative event count; apply a negative weight yourself |
| `ticket_delta` | enemy tickets lost minus own tickets lost | signed difference |
| `battle_win` | 1 when the team wins at episode end | non-negative indicator |
| `battle_loss` | 1 when the team loses at episode end | non-negative indicator; apply a negative weight yourself |
| `role_shaping` | small role-weighted change in distance to the assigned objective | signed distance delta, normalized to 1 km and clipped to `[-0.05, 0.05]`; moving away reverses the contribution, standing still adds zero |
| `battle_draw` | 1 when a completed episode is a draw | non-negative indicator; default coefficient is zero |

Components are raw values, not pre-weighted rewards. For example:

```python
def calculate_reward(c):
    return (3.0 * c["objective_capture"]
            + 0.01 * c["damage_dealt"]
            - 4.0 * c["own_death"]
            - 10.0 * c["battle_loss"])
```

Avoid applying a negative sign twice: `own_death` and `battle_loss` arrive as positive indicators. Team-wide components are divided equally among the active teammates, so summing per-agent rewards counts a capture, team damage, ticket change, or terminal result once. `own_death` is local to the affected agent; role shaping is individual.

## Episode outcomes and learning tasks

One outcome resolver is used for training, evaluation and replay metadata:

- When only one side has surviving vehicles, that side wins. If both sides are eliminated on the same step, the result is a draw.
- If tickets are exhausted, the side with tickets remaining wins. Simultaneous exhaustion is a draw.
- At the time limit, compare tickets, then the number of held objectives; an exact tie is a draw.

Win, loss and draw components are mutually exclusive terminal indicators. Existing experiment files and old checkpoints remain untouched. Checkpoints without the new compatibility sidecar can be evaluated with the legacy centralized model, but cannot be continued as new training because their reward and task semantics are unknown.

The student-facing laboratory uses one 8×8 configuration for Random, student Python, PPO, evaluation, and comparisons. Internal diagnostic configurations may remain available to developers, but are not student assignments and their results must not be mixed with full 8×8 results.

PPO is a separate learning mechanism from `agent.py`: editing an agent does not alter Stable-Baselines3 PPO's network or weights. PPO architecture can be selected explicitly. Centralized PPO maps all eight observations to one 48-value joint action. Parameter-sharing PPO maps each vehicle observation to six actions using one shared policy across the team; it collects eight individual transitions and advances the shared world once. It has a local value function and is not MAPPO. Architecture, 8×8 environment, reward source, and task metadata are checked before resuming a checkpoint.

PPO checkpoints include SB3 model and optimizer state plus a SHA-256 checked metadata sidecar. Pause writes a consistent checkpoint and waits; Stop returns from the rollout callback, saves the current checkpoint, then exits. Continue requires compatible architecture, environment, step limit, reward coefficients, and custom reward source. `progress.json` distinguishes PPO transitions, individual agent transitions, synchronized world steps, completed episodes, and optimizer updates. Training CSVs record episode returns; `ppo_metrics.csv` records value/policy loss, entropy, approximate KL, clip fraction, and explained variance when SB3 has logged them. `reward_components.json` reports raw component sums and, for standard reward training, coefficient-weighted contributions.

## Running and interpreting experiments

Use the Python tab to save or import `agent.py` and `reward.py`, check them, run the strategy, train PPO, evaluate on fresh seeds, compare policies, inspect replay, or export a ZIP. Each experiment gets its own timestamped directory and stores source copies and hashes, configuration, seeds, summary, tables, and replay; PPO runs also save a checkpoint and training curve. Results are not overwritten.

A custom training reward is not an effectiveness score. Compare Random, the student policy, standard-reward PPO, and custom-reward PPO on the same independent test seeds and use the standard evaluation reward, win rate, captures, kills, and losses. Same initial seed and opponent do not force identical trajectories once actions differ.

The runner uses long-lived separate Python worker processes for `agent.py` and custom `reward.py`, with time limits, batch messages, action/reward validation, and worker cleanup. This is process separation, not a security sandbox: Python code has the current user's permissions and may access files or start processes. Run only source you trust. The app does not claim OS-level sandboxing. Errors include the student file and traceback in the experiment console.

The practical ZIP contains the current student files and actual saved result files with hashes. It excludes research archives, MaleCNS datasets, and unrelated user files. Do not treat analytical replay as a high-fidelity Godot battle.
