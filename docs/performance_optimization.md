# FlySwarm performance audit — 2026-10-21

## Environment and method

- Mac with Apple M2; Godot 4.7.2; Metal Forward Mobile renderer.
- Logical game window: 1280 × 800; Retina display: 2880 × 1800 at scale 2.
- VSync remained enabled. The captures observed different presentation cadence, so frame-rate comparisons are indicative rather than a controlled benchmark.
- Battle samples used the existing `battle-rule` Open Day scene. A separate `--exercise-fire` run injected synthetic clicks; it is a profiling stimulus, not a gamepad test.
- Godot exposes no reliable GPU-time or CPU/GPU-load counter for this renderer. The report uses frame duration, physics duration, draw calls, primitives, and memory monitors.

## Findings and changes

1. A selected vehicle damage schematic was rebuilt and queued for redraw on every rendered frame. It now refreshes at 10 Hz, with immediate refresh when camera, selected vehicle, or hit-report visibility changes.
2. Shots and impacts allocated shell, flash, and particle nodes during the combat tick. Shells and short-lived effects now reuse bounded pools. The pools are prepared in small batches during battle startup.
3. The first selected hit report loaded and instantiated a vehicle model and built its x-ray scene during the hit tick. Active enemy models and one representative hit visualization are prepared in the report viewport during battle startup and reused for later hits.
4. MARL and supervised-job progress JSON files were read every frame. Polling now runs at 5 Hz while the UI continues to present progress.
5. The MaleCNS folder checksum check previously waited synchronously on the UI thread. It now runs in a worker thread and shows an indeterminate progress bar with a completion or error state.
6. Fresh installs now use the existing reset default for vegetation density (0.6 instead of 1.0). Existing saved settings are preserved. A 15-second profile at density 0.6 measured 7,000 mean draw calls, 3.30 million mean primitives, 16.68 ms mean frame time, 24.56 ms p99, and 48.57 ms maximum. The matching pre-change default-density profile measured 7,351 mean draw calls, 6.17 million mean primitives, 19.72 ms mean frame time, 86.64 ms p99, and 589.14 ms maximum. These runs were on the same M2 and viewport, but occurred at different observed presentation cadence and the code changes were cumulative; do not read them as an isolated vegetation-only effect.

## Shot and impact measurements

The profiling harness was extended to measure frames containing a shot or hit. In a 30-second synthetic-fire capture after warming the hit-report view, it recorded 9 shot frames (16.16 ms mean, 18.57 ms max) and 1 hit frame (17.48 ms). Earlier diagnostic captures recorded 2 hit frames with a 187.89 ms maximum before report-view prewarming, then 2 hit frames with a 90.58 ms maximum after model prewarming. A camera-overview control capture recorded 3 hit frames with an 8.18 ms maximum while the impact report was hidden.

The small hit sample is not enough to guarantee every first hit stays below the display refresh budget. It does identify and remove the synchronous model setup from the hit path, and the final measured hit frame was comparable to the ordinary shot frames. The total battle scene can still produce long frames under the full-detail profile; the measured p99 in the separate 30-second default profile was 59.06 ms and the maximum was 421.27 ms. Instruments-level attribution and a physical controller run remain outstanding.

## Status indicators checked

- Session preparation: indeterminate loading progress bar plus current stage text.
- MARL Laboratory: determinate or indeterminate experiment progress bar, state, and details.
- Supervised training/research jobs: progress bar, run/step counts, elapsed time, and worker status.
- Open Day battle: player and fly health bars plus match clock.
- MaleCNS dataset validation: new indeterminate bar while checksums run, followed by ready/error text.
- Static selection, replay browsing, and settings screens have no long-running operation requiring a progress bar.

## Validation

- `tools/run run-tests`: 45 Python tests passed; Godot ballistics, environment physics, field environment, bridge protocol, controlled projectile cases A–D, and Open Day validation passed.
- App validation: all application checks passed, including asynchronous invalid-dataset handling and progress-bar presence.
- `open_day_vehicle_validation.gd`: previously passed with failures=0; the latest performance changes do not modify the fly model.
- Godot headless exits print a renderer dummy-shader RID leak warning. Test validations still report zero failures; this warning was present before/through the changes and is not treated as a gameplay pass/fail result.
- Physical DualSense, packaged app, and real MaleCNS dataset startup were not part of this performance run.

Profiles are stored outside the repository on the RisingSail SSD under `FlySwarm-Build/performance-qa-before/` and `FlySwarm-Build/performance-qa-after/`.
