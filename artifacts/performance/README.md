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

Before the scheduler change, the same synchronous physics/request cycle could
advance world time only after a backend reply; a 20-second sample measured
about 0.38 × realtime with a reported tick mean of 6.24 ms, p99 25.12 ms and
maximum 134.66 ms. The Open Day path now advances physics at the configured
50 Hz regardless of backend readiness, begins with neutral input, and holds
the last validated motor command between replies. It permits one in-flight
request, validates increasing response sequence numbers and applies neural
trace/audio telemetry only on a new accepted response. Research and training
keep their synchronous response-before-step path and their two batch=8 brains.

After the change, three comparable GUI samples used MaleCNS(batch=1), the same
T-34-85 Open Day scenario, 1280 × 800 window, VSync and five seconds of warm-up:

| Run | Sim / wall | xRT | Physics steps | Fresh MaleCNS responses | Tick mean / p99 / max | IPC mean / p99 | FPS mean / p99 frame |
|---|---:|---:|---:|---:|---:|---:|---:|
| `04-12-50` | 15.02 / 15.00 s | 1.001× | 751 | 749 (49.92 Hz) | 5.07 / 11.16 / 18.79 ms | 18.72 / 26.12 ms | 120.1 / 12.75 ms |
| `04-13-32` | 15.00 / 15.02 s | 0.999× | 750 | 750 (49.94 Hz) | 4.44 / 5.89 / 7.11 ms | 18.69 / 32.50 ms | 59.9 / 20.49 ms |
| `04-24-20` | 15.00 / 15.00 s | 1.000× | 750 | 671 (44.72 Hz) | 7.63 / 38.48 / 162.75 ms | 20.87 / 68.12 ms | 104.2 / 26.18 ms |

A longer real-brain battle ran until the match ended: the measured active window
advanced 88.82 simulated seconds in 88.83 wall seconds (0.9999×), taking 4,441
physics steps and accepting 4,096 fresh replies (46.11 Hz). Mean frame time was
9.98 ms, p99 21.18 ms, and presentation rate 99.8 FPS. Tick mean/p99/max was
6.73/42.32/349.82 ms; IPC mean/p99/max was 20.38/58.25/403.29 ms. The world
clock stayed at 50 Hz while slower replies caused command holds; these outlier
latencies remain visible in the diagnostics instead of dropping physics time.
The fight ended at 88.82 sample seconds, so this run verifies a long, nearly
90-second battle but did not run all the way to the 90-second timeout.

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

The supported build is `.venv/bin/python tools/package_macos.py --build
--version 0.2.0-beta.1`. It combines the Godot app and an arm64 PyInstaller
onedir backend with FlyBrain, NumPy, SciPy, Numba and llvmlite, runtime source
for packaged research jobs, and third-party license notices. The external
MaleCNS data is SHA-256 checked through Settings and is not included. The
installed-app and release gate results are tracked in the release notes and
`docs/macos_packaging.md`; do not use the legacy frontend-only ZIP as a release.
