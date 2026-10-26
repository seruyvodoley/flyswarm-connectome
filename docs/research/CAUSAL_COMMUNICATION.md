# FlySwarm causal communication — pilot implementation (E0/E1)

**Status:** instrumentation and open-loop diagnostics only; **NOT** a validated
closed-loop causal experiment, a complete E0 checkpoint/restore implementation,
an E3/E4 team-behavior experiment, or a finished scientific result.

## Scope and unchanged application behavior

The default Godot/Open Day application and the student branch continue to use
the original `audio_frame` path. New directed interventions are opt-in, only
through a named research backend (`--research-log`, `--experiment-id`,
`--run-id`, and `--causal-config`). The neural model, weights, navigation
controller, and ballistics are unchanged.

The unit of intervention is a sender -> receiver signal injected through
JO-A/JO-B. All inputs are computed from wing-motor activity at the preceding
neural step (20 ms). The physical distance attenuation, gain 0.08, and shared
receiver saturation cap of 0.8 remain unchanged. If a directed signal is
removed, the remaining signals may increase after recomputing the receiver's
saturation cap. This interference is logged explicitly and is part of the
causal definition.

## 1. Acquire a reference trajectory containing real communication

Use a standard Godot 3D research configuration with `audio_mode` set to
`team_audio`, and `MALECNS_REAL` as a condition. This differs deliberately
from older frozen research configurations, which used `no_audio`.

Example `docs/research/configs/causal_neural_reference.json` includes only a
short technical smoke. Its seed count and duration are **not** adequate for
inference. Do not mix the old no-audio research archive with the new study.

Run on a machine with Godot 4.7.2 and verified `brain.npz` / `weights.npz`:

```bash
./tools/run-research collect --config docs/research/configs/causal_neural_reference.json
```

Source and config fingerprints, run identifiers and checksums are retained by
the existing research runner. Report any source mismatch or incomplete run.

## 2. E0/E1 paired open-loop replay

The replay begins from a new `DualBrain(seed)` reset and repeats the same
recorded observations. It compares two no-change continuations and verifies
that the computed neural outputs agree with the original recorded outputs.
Only then does it run a third continuation with one prespecified directed
message changed. This is **conditional** on the recorded sensory/position
history, which is held fixed even when the brain output changes.

```bash
PYTHONPATH=src python tools/causal_neural_replay.py \
  --neural-steps results/research/<experiment-id>/runs/<run-id>/neural_steps.jsonl \
  --event '{"tick":40,"sender":0,"receiver":1,"kind":"mute"}' \
  --max-steps 100 \
  --tolerance 1e-9 \
  --output results/research/causal-e0e1-first-probe.json
```

Specify output path *before* running. Existing output is never overwritten.
E0 fails closed for source mismatch, differing paired repeats, missing rows,
unsupported original conditions, or larger-than-prespecified numerical error.
Pre-register a tolerance and all thresholds before the confirmatory study.

Supported message modifications at the specified 1-based neural tick:

- `mute`: remove only this sender -> receiver contribution.
- `replace`: set its nonnegative source amplitude with `value`.
- `time_shift`: use a recorded past sender amplitude from `lag_steps` earlier.
- `shuffle_sender`: replace it with the signal of a specified
  `substitute_sender` on the same team. This is NOT the existing
  `MALECNS_SHUFFLED` motor-output control.

All modifications act before the intensity cap. A time shift and sender
substitution do not on their own guarantee an intensity-matched surrogate.
Creating statistically matched controls with blinded selection remains work
for E2.

Results record reference SHA256, seed, E0 maximum numerical errors, the exact
intervention, E1 changes in six-channel activity, DNp01, decoder controls and
received signal at 0, 20, 100, 500 and 1000 ms. Missing observation horizons are
explicit. The primary interpretation must **not** claim changes to physical
vehicle trajectories, goal selection or coordinated team outcomes.

## 3. Directed logging in full Godot research runs

A full Godot collection config can additionally specify
`causal_communication` with `enabled_teams` and `events`.
The runner rejects `no_audio` with a causal specification. It emits
`causal_config.json` and the sidecar `causal_neural_steps.jsonl` with
every neural-step link's sender, receiver, distance, source amplitude,
pre-cap signal, baseline and actually delivered signal, and cap scale.
Open Day cannot load such a research-only config.

The sidecar is a diagnostic stream: its SHA256 and schema-aware validation
must be added to the publication protocol before it becomes a definitive
analysis archive. The original Godot game/neural telemetry remains intact.

## Remaining gates for a scientific paper

1. **E0 physical state:** implement and verify Godot + neural checkpoint/restore,
   including velocity/contact state, controllers, RNGs and message histories.
   Fixed-sensory replay above is *not* a substitute for closed-loop E0.
2. **E1:** a sufficient number of independent, prespecified seed blocks and
   events with confidence intervals that account for clustering.
3. **E2:** matched surrogate signal generation and strict message-timing tests.
4. **E3:** paired final-action and physical-behavior interventions with
   unchanged initial game and backend states, tracking auxiliary controllers.
5. **E4:** independently switch each team's channel on/off in a paired 2×2
   Godot design, capture zone coordination and team outcomes.
6. **E5/E6:** directed edge ablations, receiver-context measurements *before*
   intervention, and cluster-aware statistical analysis.

No research-readiness flag or finished article should be inferred from passing
unit tests or from a successful application release.
