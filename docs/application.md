# FlySwarm desktop application

Normal entry: `./run.sh` from the repository. This opens Bootstrap → MainMenu.
No brain is loaded for the menu, Rule AI or manual test range. Existing CLI
research commands in tools/run remain compatible through --legacy-battle.

AppState owns scene routing, SessionConfig, local settings, processes and job
status. Battle.tscn remains the existing physics/combat world. SessionConfig is
passed to each battle instance; legacy CLI arguments remain available only for
CLI jobs. No source experiment is executed on import by the menu.

## Implemented flows

- MainMenu → HistoricalBattleSetup → staged Loading → 8v8 → Results → Menu.
  Per-team Rule AI/MaleCNS/readout selectors, seeds, audio, side swap and recording.
- MainMenu → TestRangeSetup → manual vehicle/target at 100/500/1000/1500 metres,
  target angle, drive/gunnery/armour/module modes → ESC → Menu. Mobility adds a
  proving-ground slope; gunnery targets remain stationary. Armour/modules enable
  the impact debug view. Damage physics remains approximate.
- ResearchLab → supervised sequential condition jobs → measured results path.
  Audio comparisons use real two-brain simulation; all-Rule audio comparison is
  rejected. Embodiment, mirror, side swap, policy evaluation, unchanged transfer,
  and trained/baseline conditions use existing backend/scene functions.
- TrainingMenu → real Stage 3 teacher imitation → small ridge readout fit/save/
  reload → frozen validation. Vehicle-specific/shared readouts supported.
  Other curriculum tasks are disabled. Reward/success metrics are not invented.
- ReplayBrowser recursively scans results/raw/app, plays recorded world state
  without brains; delete moves the selected recording to Trash after confirmation.
- Settings save to Godot user://settings.cfg. Presets change shadows, vegetation
  and effects; window mode/resolution and imported-mesh LOD bias are functional.

Controls in range: W/S drive, A/D steer, Q/E turret, R/F elevation, Space/left
mouse fire, right mouse drag aim, C camera, F1 debug, ESC pause. Free camera
uses WASD/QE/arrows, suspending manual driving while that camera is selected.

Pause offers resume/debug/save replay/menu/exit. With recording off, the most
recent 10 minutes of state are buffered; Save Replay starts persistent recording
and writes the buffer. Interrupted sessions preserve measured summaries.

## Process ownership and failure behavior

Neural battles start `.venv/bin/python -m flyswarm.bridge.server` on demand.
Actual callbacks identify BLUE loading, RED loading, warm-up and READY. Every
neural backend creates two distinct CPU FlyBrain(batch=8) objects and verifies
separate weight memory. No batch16/fake backend is used. Mixed-team Rule AI is
explicitly chosen; it does not silently replace a missing brain controller.

Startup errors show Retry / Use Rule AI / Cancel. Disconnect pauses the world;
Reconnect starts fresh neural state and is explicitly not a continuous scientific
episode. Return/exit terminate the owned backend. Research/training use
`tools/app_job.py`, which owns and reaps each child Godot/backend, observes a
cancel file and parent liveness, and reports stage/condition/seed/run/time.
The job writes results incrementally; cancellation does not discard completed runs.

Localhost only is supported. A custom remote host produces an explanatory error;
no unauthenticated remote control service is opened. Python dependencies and the
MaleCNS dataset must already exist for neural modes. No automatic downloads.

## Validation and limits

`./run.sh --headless --script res://scripts/app/validation.gd`
checks menu resources, manual Tiger movement, pause/return, Rule 8v8/results,
replay completion and missing-backend recovery. Add `-- --real-brains` to run an
actual bounded neural session. Existing `./tools/run run-tests` remains available.

The GUI exposes only Stage 3 training; the rest of the curriculum is visibly
unavailable. Research reports measured values, not scientific conclusions.
Replay remains sampled state playback, without exact effect or rut reproduction.
No sound playback. Vehicle historical fidelity remains a separate failing gate;
see model_validation/README.md and reference manifests.
