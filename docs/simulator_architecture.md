# Simulator architecture — implemented vertical slice

Godot 4.7.2 owns positions, terrain, contact/vehicle dynamics, LOS, flight,
armour-zone collision, module damage and objectives. It runs independently:
`./tools/run run-demo`. It never substitutes a fake brain for MaleCNS.

`battle.gd` orchestrates `terrain.gd`, `vehicle.gd`, `combat.gd`, `tracks.gd`,
`catalog.gd` and `bridge.gd`. JSON definitions live in data/ outside the engine
project, loaded relative to the repository. Run from checkout; a standalone
export needs a packaging step that includes data/ (not implemented).

Python owns the biological encoder, two FlyBrain instances, recurrent activity
traces, wing-song coupling, readouts and training. NDJSON over localhost TCP
uses one request in flight. Godot rendering continues while simulation waits;
no neural tick is skipped and the world advances 20 ms per reply. Physics is
50 Hz, rendering independent. A backend-required run waits instead of silently
switching to conventional AI. The disconnected demo does not contact Python.

Vehicle actions: throttle [-1,1], brake [0,1], steer [-1,1], traverse [-1,1],
elevate [-1,1], fire [0,1]. Negative throttle means reverse. Same actor indices
throughout: BLUE 0..7, RED 8..15. Data-driven compositions are 4 medium, 2 heavy,
2 tank destroyers per team. Policy gets no role label or historical stats.

Camera: C cycles strategic/follow/gunner/free; TAB selects another actor.
Free flight: WASD/QE and arrows. F1 shows module/impact diagnostics and selected
vision/LOS lines. SPACE pauses. Default is follow camera. Labels are gameplay
HUD, never a substitute for model recognition validation.

Modes: HISTORICAL (default, *provisional* data model), NORMALIZED (`--normalized`,
all physics/armour/guns use T-34 parameters; original meshes retained), mirror
(`--mirror t34_85`), side-swap (`--swap`), training range (`--training`).
No secret national stat multipliers. Scenario pressure is tickets and zones.

Data flow is tested end-to-end, but the complete acceptance brief is NOT met:
see known_approximations.md and vehicle_visual_references.md. Models remain
blockouts and many historical parameters need primary-source verification.
