# MaleCNS Combat Training

Combat training is an additional workflow inside the existing **Readout Training** engineering page. The original ridge/readout imitation workflow remains available there, and the separate MARL Laboratory is unchanged.

## Open the training screen

Start FlySwarm from the project, choose **READOUT TRAINING**, and scroll to **MALECNS COMBAT TRAINING**. The app does not start a long run automatically. Choose the data mode, program, PPO step limit, wall-clock limit, episode limit, seed, and checkpoint interval, then start a new run or select a saved checkpoint to continue.

**MaleCNS Training / Fine-tuning** requires the configured MaleCNS reconstruction dataset. It creates one real `FlyBrain(batch=1)`, uses its six measured neural channels as policy inputs, and leaves the connectome frozen. **Gameplay Pretraining · no MaleCNS** explicitly supplies zero neural channels; its results are marked as pretraining and must not be described as MaleCNS training.

The automatic program advances one policy through movement, aiming, gunnery, tactics, and full-battle reward stages. Full battle can be selected directly. The controlled policy outputs throttle, brake, steering, turret, gun elevation, and fire. No separate neural networks are created for the stages.

## Training controls and saved results

The progress screen shows the current curriculum stage, PPO steps, episodes, elapsed time, steps per second, latest episode reward, and a live reward curve. Reward is a training diagnostic, not evidence that combat skill improved. Use **PAUSE / RESUME**, **SAVE CHECKPOINT NOW**, or **STOP TRAINING** at any time. A stop saves the latest consistent checkpoint and skips the optional evaluation so the app can return promptly.

Each run is stored under `results/raw/app/combat-training-<timestamp>/` (or the app's user-data session directory in a packaged build):

- `checkpoints/latest.zip` and `latest.json` are the resumable PPO policy, optimizer state, schema, and checksum.
- `checkpoints/best.zip` and `best.json` retain the best policy found by independent evaluation.
- `metrics.csv` records episode rewards and curriculum stage.
- `progress.json` is the live state used by the interface.
- `evaluation.json` compares a hand-coded baseline, the current policy, and the previous best on independent seeds. In MaleCNS mode it also evaluates the current policy with neural features ablated.
- `manifest.json` records the algorithm, schema, MaleCNS status, environment approximations, and checkpoint identities.

Use **RESUME / CONTINUE** with an existing checkpoint. Checksum and schema metadata are checked before loading; Stable-Baselines3 restores the policy and optimizer, then training continues with a seeded fresh episode. The original checkpoint is left intact.

**EVALUATE MODEL** runs a bounded independent evaluation. **PREPARE FOR OPEN DAY** validates the selected checkpoint and writes `deployment/policy.zip` with its `metadata.json`; the packaged policy is accepted by the existing Python backend as a trained adapter, but FlySwarm does not select it as the default Open Day opponent. Select the deployment ZIP in a battle's trained-adapter field when you want to test it.

## Environment and limits

Training is headless and CPU-only. One MaleCNS instance is reused for rollouts and sequential evaluation to limit memory. The analytical duel includes inertial movement, hull and turret rotation limits, elevation and reload, a moving/stationary/rule opponent mix, a variable obstacle, visibility, projectiles represented by range/aim hit tests, and cumulative vehicle health.

It is an approximation, not Godot's battle simulation: the arena is two-dimensional; armour, internal modules, crew, projectile flight, and obstacle collision are simplified; there is no 3D rendering. A short initial concealment period prevents immediate mutual visibility. Win rate and reward can be noisy, so evaluation uses separate deterministic seeds and is not automatically treated as proof of strength. Final transfer still needs review in Godot/Open Day.

MaleCNS data is neither copied into the project nor bundled. Windows CI remains validation-only under the permanent project policy; this training workflow was exercised on the current macOS development machine, not on a physical Windows system.
