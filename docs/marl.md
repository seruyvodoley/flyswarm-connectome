# Multi-agent reinforcement learning

`FlySwarmParallelEnv` is the canonical PettingZoo `ParallelEnv`: sixteen
simultaneous agents (`blue_0`…`blue_7`, `red_0`…`red_7`), a 20-value
`connectome_plus_task` observation and one six-value action in this order:
`throttle, brake, steering, turret, elevation, fire`. Values are clipped to
`[-1, 1]`; fire activates above `0.5`.

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
ticket delta and result). Objective progress rewards only positive state
change; capture/neutralization and dead-target credit are transition based.

The resulting `.npz` is accepted by the normal **Trained adapter** policy
selector. In a Godot battle, normalized live MaleCNS traces are concatenated
with the engineered task vector and the shared policy runs deterministically;
its action is recorded separately as `adapter_action`.
