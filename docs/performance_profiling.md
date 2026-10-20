# FlySwarm performance profiling

`frontend/godot/scripts/app/performance_profile.gd` samples the live Godot
window on macOS using the renderer's frame, process, physics, draw-call,
render-object, primitive, video-memory, and static-memory monitors. It reports
mean, p99, and maximum for each available series, plus logical window size,
root viewport size, screen scale, VSync, renderer, and visible SubViewport count.
The running renderer does not expose a trustworthy GPU-time or CPU/GPU-load
counter through this script; those require a separate Instruments or Activity
Monitor capture.

The optional `--exercise-fire` switch injects a synthetic Open Day click after
the intro, then records frame times that contain a shot or a hit separately.
It measures the firing and impact code paths; it is not a hardware controller
test. `--camera=0` provides a diagnostic comparison with the impact report
hidden in overview mode.

From the repository root, run:

```sh
./tools/run run-profile --mode=menu --seconds=30
./tools/run run-profile --mode=menu --seconds=30 --disable-preview=fly
./tools/run run-profile --mode=menu --seconds=30 --disable-preview=vehicle
./tools/run run-profile --mode=menu --seconds=30 --disable-preview=fly,vehicle
./tools/run run-profile --mode=menu --seconds=30 --preview-rate=0
./tools/run run-profile --mode=battle-rule --seconds=30
./tools/run run-profile --mode=battle-rule --seconds=30 --exercise-fire
./tools/run run-profile --mode=battle-rule --seconds=30 --shadows=off
./tools/run run-profile --mode=battle-rule --seconds=30 --vegetation=0.25
./tools/run run-profile --mode=battle-brain --seconds=30
```

Menu profiles use the Open Day selection screen so both real 3D previews are
present. `battle-rule` measures the same battle scene with both controllers set
to Rule AI; it is a rendering/control baseline and must not be interpreted as a
MaleCNS measurement. `battle-brain` profiles the real Open Day FlyBrain(batch=1)
opponent and includes the latest backend tick in its JSON report. Do not compare
unlike scenes as equivalent workloads.

Godot's root viewport size is the internal logical render target. The reported
screen scale describes macOS display scaling; it does not by itself prove the
physical Metal drawable dimensions. The script leaves VSync unchanged. Reports
are written to `artifacts/performance/` and include the active display backend,
renderer, and Godot version. Editor, normal GUI, and exported-app results must
be recorded separately.
