# MaleCNS Combat Training

Combat training is an additional workflow inside the existing **Readout Training** engineering page. The original ridge/readout imitation workflow remains available there, and the separate MARL Laboratory is unchanged.

## Open the training screen

Start FlySwarm from the project, choose **READOUT TRAINING**, and scroll to **MALECNS COMBAT TRAINING**. The app does not start a long run automatically. Choose the data mode, program, PPO step limit, wall-clock limit, episode limit, seed, and checkpoint interval, then start a new run or select a saved checkpoint to continue.

**MaleCNS Training / Fine-tuning** requires the configured MaleCNS reconstruction dataset. It creates one real `FlyBrain(batch=1)`, uses its six measured neural channels as policy inputs, and leaves the connectome frozen. **Gameplay Pretraining · no MaleCNS** explicitly supplies zero neural channels; its results are marked as pretraining and must not be described as MaleCNS training.

The automatic program advances one policy through movement, aiming, gunnery against a moving target, tactics, and full-battle stages. Opponent complexity changes by stage; stage transitions are currently scheduled by training progress, not gated by mastery, so they do not prove that an earlier skill was learned. Full battle can be selected directly. The controlled policy outputs throttle, brake, steering, turret, gun elevation, and fire. No separate neural networks are created for the stages.

## Training controls and saved results

The progress screen shows the current curriculum stage, PPO steps, episodes, elapsed time, steps per second, latest episode reward, and a live reward curve. Reward is a training diagnostic, not evidence that combat skill improved. Use **PAUSE / RESUME**, **SAVE CHECKPOINT NOW**, or **STOP TRAINING** at any time. A stop saves the latest consistent checkpoint and skips the optional evaluation so the app can return promptly.

Each run is stored under `results/raw/app/combat-training-<timestamp>/` (or the app's user-data session directory in a packaged build):

- `checkpoints/latest.zip` and `latest.json` are the resumable PPO policy, optimizer state, schema, and checksum. Periodic, manual, pause, stop, time-limit, and normal-completion saves use the same versioned metadata serializer.
- `checkpoints/best_evaluated.zip` and `best_evaluated.json` are written only after independent analytical evaluation; stopping early never promotes an unevaluated policy.
- `metrics.csv` records episode rewards and curriculum stage.
- `progress.json` is the live state used by the interface.
- `evaluation.json` compares a hand-coded baseline, the current policy, and the previous best on independent seeds. In MaleCNS mode it also evaluates the current policy with neural features ablated.
- `manifest.json` records the algorithm, schema, MaleCNS status, environment approximations, and checkpoint identities.

Use **RESUME / CONTINUE** with an existing checkpoint. Checksum, schema, architecture, feature/action order, training mode, dataset hashes, and version metadata are checked before loading; Stable-Baselines3 restores the policy and optimizer, then training continues with a seeded fresh episode. The original checkpoint is left intact. Schema v1 checkpoints are rejected because their metadata and runtime features are not sufficient to establish compatibility. Gameplay Pretraining → MaleCNS Fine-tuning requires the explicit transfer toggle and records the transfer in metadata; this mode change is not treated as proof that pretraining transfers successfully.

The analytical trainer and the real backend now use one versioned function to build all 22 policy features. The runtime converts the target bearing from turret-relative to hull-relative coordinates, and the test suite compares every feature value against the analytical environment for identical state. Both currently provide zero obstacle-left, obstacle-right, and last-damage channels because those sensor values are not exposed to the policy in Godot.

**EVALUATE MODEL** runs a bounded independent evaluation on the same held-out seeds for the fixed Rule AI and PPO policy. An evaluation is recorded as complete even when PPO loses; only a strict improvement in the ordered combat metrics (win rate, then damage, then accuracy, then fewer stuck recoveries) can qualify it as `best_evaluated`. Training reward is never part of that gate. **PREPARE FOR OPEN DAY** accepts only a MaleCNS-trained checkpoint that beat the fixed baseline, verifies its PPO archive and checksum, then writes `deployment/policy.zip` with the full `metadata.json`. In Open Day, choose **MaleCNS + Trained PPO** and select this deployment ZIP. Backend loading verifies the quality gate along with schema, action order, architecture, checkpoint hash, and MaleCNS mode; on failure the match does not silently fall back to Baseline. The trained PPO is the primary action source and does not receive the baseline's tactical helper.

When continuing a demonstration checkpoint, the default PPO learning rate is reduced to `3e-5`, with a 128-step rollout, batch size 128, and five update epochs. These can be set explicitly with `training_learning_rate`, `training_rollout_steps`, `training_batch_size`, and `training_epochs`. Resuming with a longer rollout rebuilds only the empty rollout buffer; policy weights and optimizer state remain restored.

## Environment and limits

Training is headless and CPU-only. One MaleCNS instance is reused for rollouts and sequential evaluation to limit memory. A training action step and the real FlyBrain neural tick are both 20 ms (50 Hz), matching Godot physics and the connectome's pinned neural step; training does not change the scientific neural timestep. The analytical duel includes inertial movement, hull and turret rotation limits, elevation and reload, a stage-specific stationary/moving/rule opponent mix, a variable obstacle, visibility, projectiles represented by range/aim hit tests, and cumulative vehicle health. Episode returns now sum the complete episode, and metrics retain the component reward totals. The automatic curriculum remains scheduled rather than mastery-gated.

It is an approximation, not Godot's battle simulation: the arena is two-dimensional; armour, internal modules, crew, projectile flight, and obstacle collision are simplified; there is no 3D rendering. A short initial concealment period prevents immediate mutual visibility. Win rate and reward can be noisy, so evaluation uses separate deterministic seeds and is not automatically treated as proof of strength. Final transfer still needs review in Godot/Open Day.

MaleCNS data is neither copied into the project nor bundled. Windows CI remains validation-only under the permanent project policy; this training workflow was exercised on the current macOS development machine, not on a physical Windows system.
