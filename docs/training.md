# Training and transfer

Implemented and smoke-tested: **Stage 3 turret-tracking imitation** on the
small training map, using actual dual MaleCNS activity, not random features.
`./tools/run run-training` collects a short dataset, trains a ridge readout,
saves it, reloads it, then evaluates with a held-out brain seed. Policy bytes
are checked unchanged after evaluation. It is deliberately a tiny plumbing
experiment, not evidence of learned vehicle specialization.

Declared training seeds: 100/101/102; held-out seeds: 200/201/202.
Fit rejects test-seed contamination. Feature mode is stored in both dataset
and policy, verified on load. Training/evaluation directories and manifests
are separate. In training range, driving is held still so this is gunnery,
not waypoint learning. Other curriculum stages are listed but not implemented.

Commands (from root, activate .venv or use tools/run):

```bash
./tools/run run-training --seconds 1
PYTHONPATH=src .venv/bin/python -m flyswarm.training.fit DATASET.npz policies/tiger_i/policy.npz --vehicle tiger_i
./tools/run run-brains --seed 200 --policy policies/tiger_i/policy.npz
./tools/run run-battle --training --mirror is2_1944 --seconds 10 --quit
```

Passing one file applies an unchanged shared policy to all chassis, enabling
zero-shot A→B tests with `--mirror`. Passing a directory loads
`<vehicle>/policy.npz` heads. Missing heads fail explicitly. Vehicle-specific
heads share exactly the same frozen connectome architecture. Do not compare
training error with combat accuracy. policy JSON records ridge imitation MSE.

Fine-tuning curves, PPO, mobility curriculum, episode-to-recovery comparisons,
a complete held-out-map evaluation and emergence metrics are TODO. Do not
claim the current fitted head is useful combat AI. The smoke head is only a
saved/reloaded functional example. Full learning is intentionally not run.
