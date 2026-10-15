# Localization, observer camera and communication debugging

## A. INITIAL FAILURES FOUND

Current uncommitted patch preserved in /tmp/flyswarm-localization-comms-before-debug.patch
and staged counterpart; untracked i18n.gd copied separately. No reset/restore.
Label3D fixed_size was enabled with world-scale pixel sizes (.015 and .08),
producing screen-filling text. Follow camera interpolated from the 1100 m overhead
position. Observer fog reduced map clarity. HUD strings overflowed and initial
vehicle labels overlapped. Optional telemetry accepted malformed arrays/indices;
dead-only links could create an empty ImmediateMesh. Team-specific adapters were
reported as BIOLOGICAL_BASELINE. Several dynamic strings bypassed localization.
Plain compileall also encountered macOS ._* metadata masquerading as Python files.

## B. LOCALIZATION

RU/EN patch retained; invalid persisted language falls back to English. Changes
persist in user://settings.cfg; page replacement is deferred for language callbacks.
Reset defaults preserves language. All semantic format placeholders tested in both
languages. Seven pages rendered in both languages; Russian pages visually inspected.
Dialog/backend prefixes, range instructions and replay display names localized.
Scientific/internal identifiers remain intact. No separate manual keyboard/controller
acceptance or exhaustive screenshot review of every scrolled section was performed.

## C. BATTLEFIELD CAMERA

Autonomous application battle defaults overhead; range defaults follow. Orthographic
height 1600 m, zoom 280–1800 m, WASD pan bounded to terrain; C/button cycles all four
modes. Overhead stays independent of selected tank; looks vertically down. Far clip
4000 m; fog disabled only in overhead. Perspective follow snaps on entry, then smooths.
World-label scale is derived from viewport height and projection (15 px vehicles,
24 px objectives); compact B/R IDs stagger above/below adjacent vehicles. HUD bounded.
Actual Metal frames inspected at 1280×800 and 1920×1080; 1440×900 also captured.

## D. TEAM COMMUNICATION

Previous-step wing output → distance 1/(1+(d/250)^2) → topology → gain .08 →
receiver cap .8 → JO-A/JO-B. Contributions use [receiver,sender]; capped rows scale
proportionally. Neural updates remain 50 Hz, telemetry sample every 10 steps (5 Hz),
threshold .01, strongest 12 events, display history capped at 80. Red/Blue filters
select sender team; All includes both. Lines exclude dead/unavailable actors and
expire after two simulation seconds. Replay sample IDs suppress duplicate history.
No decoded speech or invented messages. Synthetic lines were used only by the
explicit visual fixture, never by normal simulation.

## E. PROTOCOL

Optional communication contains sample, song_out[16], heard_total[16], events and
 delay_steps=1. Version 1/actions unchanged. Real telemetry measured 1520 bytes in
Godot (1678 bytes with Python spaced JSON); complete synthetic result packet 1316
bytes, below 1 MiB. Full real result packet size was not measured. Missing fields
and malformed optional events are safely ignored; old/no-telemetry replay path tested.

## F. TESTS

- .venv/bin/python -m compileall -q src tests tools: FAIL on existing AppleDouble
  metadata files, not source syntax. Repeated with -x '/\._': PASS.
- .venv/bin/python -m unittest discover -s tests -v: initial 18 PASS.
- Godot --headless --path frontend/godot --editor --import: PASS.
- ./tools/run run-tests: final 20 Python PASS; Godot VALIDATION failures=0.
- ./run.sh --headless --script res://scripts/app/validation.gd: PASS, failures=0.
- Same command with -- --real-brains: PASS; real run and offline replay completed.
- ./run.sh --script res://scripts/app/visual_validation.gd: PASS; both languages,
  three resolutions, four cameras, communication filters rendered without errors.
- CLI --camera 0/1 --screenshot captures: both rendered and visually inspected.
- git diff --check: PASS.

## G. REAL MALECNS

Two distinct CPU FlyBrain(batch=8), no shared weights, 2,667,200 neuron states.
One simulation second, Team Audio, five telemetry samples. Final sample had 12
nonzero events with valid indices/nonnegative contribution and distance. Recorded
10 replay frames contained samples -1,1,2,3,4,5; replay completed without backend.
Mean neural tick reported 63.87 ms. Architecture assertions retained.

## H. KNOWN ISSUES

Not a long-run performance benchmark. UI refresh microcheck: closed .00195 ms,
open .02754 ms (two fixture events, 100 calls); real backend dominates runtime.
No full neural battle or training run; no mesh/physics changes in this patch.
Detailed historical model limitations remain as previously documented. Existing
AppleDouble metadata remains ignored and excluded from source compilation.

## I. GIT

Focused commit on feat/historical-3d-tank-simulator; exact SHA/status reported in
completion message. No history rewrite, caches, raw recordings or dataset committed.
