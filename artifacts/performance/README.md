# macOS M2 profiling snapshot

These are local GUI runs on 2026-10-12 using Godot 4.7.2, Apple M2, Metal 4.0
Forward Mobile, 1280 × 800 logical window and root viewport, 2880 × 1800
display, scale factor 2.0. VSync was left at Godot mode 1. The output files
record exact renderer and window metadata. This is a development/editor-runtime
sample; it is not an exported release build measurement. The Godot API used
here does not expose GPU time or reliable CPU/GPU utilization.

The Open Day menu comparison changes only preview render cadence. Both runs
were 10 seconds after a 5-second warm-up:

| Preview cadence | Mean frame | p99 frame | Mean presentation rate | Draw calls/frame |
|---|---:|---:|---:|---:|
| Every rendered frame (`--preview-rate=0`) | 16.66 ms | 20.61 ms | 59.9 FPS | 146 |
| 30 Hz | 6.89 ms | 7.77 ms | 144.6 FPS | 48 |

Repeated always-rendering run p99 was 19.83 ms, so the cadence A/B indicates
less render pressure with the same scene and assets. FPS is uncapped by this
profiler; it is not presented as an end-user target or as an exported-build
result. Existing imported GLB models, livery shaders and preview content were
retained. The GUI vehicle validation continued to render the fly and all three
preview vehicles after the change; screenshots are in this directory.

The arena's baseline and single-variable diagnostics show why further graphics
changes need more evidence:

| Arena condition | Mean frame | p99 frame | Draw calls/frame | Rendered primitives/frame |
|---|---:|---:|---:|---:|
| Full arena, Rule AI | 16.69 ms | 20.38 ms | 2,473 | 5.00 M |
| Environment shadows off | 16.76 ms | 22.34 ms | 1,291 | 1.18 M |
| Vegetation 0.25 | 16.72 ms | 20.83 ms | 1,845 | 1.90 M |

These one-off 10-second A/B samples stayed near the window's observed cadence;
they do not show a frame-time win from either quality reduction. The app retains
the default full vegetation and shadow settings.

With real MaleCNS(batch=1), a 20-second profile sampled 2,345 frames: mean
frame 8.52 ms, p99 18.04 ms, maximum 314.3 ms. Backend tick distribution was
mean 6.24 ms, p99 25.12 ms, maximum 134.66 ms. A bounded one-simulation-second
Open Day functional smoke also passed and measured 5.53 ms for the reported
brain tick. The resulting battle advanced at 0.38 × real time in the sustained
sample, so the neural run is not real-time at this workload. The large maximum
frame spike and tick tail remain unresolved.

Godot reported mean static memory near 319 MB and video memory near 229 MB in
the real-brain run; the Rule AI arena reported about 318 MB and 219 MB. These
are engine counters, not total macOS process resident memory. No 10-minute or
long-run leak test was performed. The rule arena is not a substitute for the
brain workload.

`../open_day_graphics/` contains the earlier visual reference screenshots.
`open_day_validation/` and `open_day_vehicle_validation/` contain new captures.
Preview screenshots were inspected after throttling; tanks remain full imported
3D models and the fly remains the imported model on its vertical yaw pivot.

## Build and release gate

`python tools/package_macos.py --export` now succeeds after installing the
official Godot 4.7.2 macOS export template. It creates `build/FlySwarm.zip`
containing a universal `FlySwarm.app` with the project icon. This is a frontend
export only: it does not include Python, `flybrain`, NumPy/SciPy, the research
job runner, or a dataset setup flow, so it cannot satisfy the standalone Open
Day release requirement. No DMG or GitHub Release was produced. The project
still needs a relocatable backend and an installed-app smoke test before
release. `security find-identity -v -p codesigning` found no Developer ID
signing identity; current build output is unsigned. MaleCNS data remains
outside the repository in the local user data directory.
