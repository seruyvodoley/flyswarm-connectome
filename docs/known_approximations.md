# Known approximations and acceptance status

This is a runnable **research prototype / vertical slice**, not a finished
historically validated simulator. Full P0 acceptance, especially the upgraded
visual-fidelity requirement, is NOT satisfied.

Historically sourced: museum mass/max road speed/gun identity for Panther,
Tiger, Jagdpanther and T-34-85, with variant caveats. Values carry source metadata.
All other parameters default to explicitly marked low-confidence approximations.
IS-2/SU-100 values are provisional until primary-source verification. No copied
game stat tables, ripped assets or historical-performance claims.

Approximate: drivetrain, gear display, soil contact, penetration tables,
ricochet/normalization, panel geometry, module volumes and spall cone. Frozen
experimental neural interface and separate policy training are implemented.
Scenario-only balance controls: composition, objectives/tickets, spawn, side-swap.
Normalized mode is explicit, never a hidden historical nerf/buff.

Current models were generated as simple low-poly blockouts BEFORE the stricter
reference-driven modelling requirement arrived. They fail that requirement:
Tiger turret/hull are insufficiently characteristic; running gear/track geometry
is too coarse; turret and gun proportions and production details are unverified.
They are retained to keep simulation runnable, not labelled finished. See
vehicle_visual_references.md and per-vehicle variant_check.md. Grey renders and
measured dimensions expose the defects. Eighteen Godot comparison views and
42 neutral Blender views are included. No historical 3% tolerance PASS is issued
without independent reference dimensions. No LOD1/LOD2 has been fabricated.

Implemented: Godot-native disconnected battle; six data IDs/GLB blockouts;
terrain/LOS; armour/module damage; three capture zones/tickets; four cameras;
TCP two-brain integration; one real imitation training task; test/launch tools;
pressure/slip-dependent bounded track trails with resistance feedback.

Still incomplete: exact six historical LOD0 meshes/reference packs; validated
ammo tables; full suspension and deformable terrain collision; energy-based
spall; repair; all
validation range scenes; complete performance/behavioral metric suite;
learning curriculum beyond Stage 3; reinforcement learning and fine-tune curves.
Replay is sampled transforms/modules/projectiles, not deterministic input replay;
playback respects recorded sample timestamps; between-sample interpolation and
exact muzzle/impact effect replay still need work.

Scientific interpretation: no outcome here establishes role emergence or
embodiment adaptation. A 1-second training smoke cannot establish either.
