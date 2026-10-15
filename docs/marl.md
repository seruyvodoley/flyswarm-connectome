# Multi-agent reinforcement learning

`FlySwarmParallelEnv` is the canonical PettingZoo `ParallelEnv`: sixteen
simultaneous agents (`blue_0`…`blue_7`, `red_0`…`red_7`) and one six-value
action in this order: `throttle, brake, steering, turret, elevation, fire`.
Values are clipped to `[-1, 1]`; fire activates above `0.5`.

New training defaults use a **28-value role-conditioned observation**. The
first 20 values keep the original `connectome_plus_task` contract; eight
additional values describe the external platform context: vehicle class
(medium/heavy/tank-destroyer one-hot), nation (Germany/USSR one-hot), and
three engineered tactical priors (aggression, objective bias, standoff).
Legacy 20-value PPO checkpoints are still accepted by the live bridge.

The standard 1944 composition is:

- Panther G — `medium_flanker`
- Tiger I — `heavy_anchor`
- Jagdpanther — `td_overwatch`
- T-34-85 — `medium_assault`
- IS-2 Model 1944 — `heavy_breakthrough`
- SU-100 — `td_support`

These labels and country tendencies are **ENGINEERED RESEARCH PRIORS**, not
biological properties of MaleCNS and not claims of a complete historical
national doctrine. MaleCNS remains frozen and never receives role/nation or
objective coordinates through its sensory cells. The external learned policy
is the component that can specialize to a vehicle, class and country context.

The analytical training backend now also uses platform-dependent mobility and
combat parameters from the vehicle catalogue (speed, reverse speed, turn rate,
reload and power-to-weight) plus bounded role-specific engagement priors. A
small `role_shaping` reward supplements, but does not replace, team/objective
reward. Mediums are biased toward capture/maneuver, heavies toward objective
anchoring/contact, and tank destroyers toward stand-off fire support.

The external policy receives task features directly. Objective coordinates are
never injected into MaleCNS sensory cells. The six connectome observation
slots are zero when no real trace provider is attached; callers can supply
measured values with `set_connectome_features((16, 6))`.

The Python backend is labelled `analytical_training` in every info dictionary.
It shares the agent/action contract, objective state transitions, ticket/death
semantics and reward definitions, but it is **DIFFERENT BY DESIGN** from the
authoritative Godot battle: armour geometry, projectile flight, terrain,
tracks and real MaleCNS execution remain Godot/Python-bridge experiments.
Results from both backends must not be pooled without recording this field.

```sh
PYTHONPATH=src .venv/bin/python examples/marl/random_policy.py --episodes 3
PYTHONPATH=src .venv/bin/python examples/marl/train_ppo.py --steps 5000
PYTHONPATH=src .venv/bin/python examples/marl/evaluate.py policies/marl/shared_ppo.npz
```

The included NumPy learner is a small shared-policy PPO/IPPO reference. It
saves and reloads a checkpoint, emits `learning_curve.csv`, and supports
deterministic evaluation. It is suitable for API exercises and smoke tests;
it is not evidence of convergence. Reward components and coefficients are
separate (`objective_progress`, capture, neutralization, damage, kill, death,
ticket delta, result and role shaping). Objective progress rewards only
positive state change; capture/neutralization and dead-target credit are
transition based.

The resulting `.npz` is accepted by the normal **Trained adapter** policy
selector. In a Godot battle, normalized live MaleCNS traces are concatenated
with the engineered task vector and, for a role-conditioned checkpoint, the
same eight platform features. The shared policy then runs deterministically;
its action is recorded separately as `adapter_action`.
