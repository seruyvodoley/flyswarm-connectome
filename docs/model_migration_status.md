# Playable historical vehicle models

Four CC0 tank models are now used by the existing vehicle loader in battles and
previews. `vehicle.gd` loads `res://assets/vehicles/<vehicle-id>.glb`, so each
replacement keeps the same armor, damage, controls, and combat configuration.
The T-34-85 Lotnik pilot was already active; Tiger I, IS-2, and Panther G now use
the selected external assets below.

| Vehicle | Runtime asset | Model source | Mechanical setup |
| --- | --- | --- | --- |
| T-34-85 | `frontend/godot/assets/vehicles/t34_85.glb` | Lotnik, OpenGameArt, CC0 | Separate hull, turret, gun, left/right tracks, and individually named rollers |
| Tiger I | `frontend/godot/assets/vehicles/tiger_i.glb` | Newc42, Low Poly German WWII Tanks, CC0 | Separate hull, turret, barrel, track loops, and 21 wheel meshes |
| IS-2 (1944) | `frontend/godot/assets/vehicles/is2_1944.glb` | MetaWorldOS, WWII Tank Pack, CC0 | Split hull, turret, gun, left/right track belts, and left/right running-gear meshes |
| Panther G | `frontend/godot/assets/vehicles/panther_g.glb` | MetaWorldOS, WWII Tank Pack, CC0 | Split hull, turret, gun, left/right track belts, and left/right running-gear meshes |

All three replacements expose `VehicleModel`, `HullPivot`, `TurretPivot`,
`GunElevationPivot`, and `Muzzle`. They preserve the game's existing vehicle
physics and combat systems. IS-2 and Panther running gear are grouped per side;
their supplied wheels and track belts are visible but do not spin individually.
The Tiger and T-34-85 have separately named wheels and use the existing wheel
rotation behavior. Track marks and ground interaction remain controlled by the
existing simulation.

The MetaWorldOS GLBs were split from single-mesh source files into mechanical
groups, scaled to the model's approximate envelope, and decimated to about
174,000 triangles for IS-2 and 191,000 for Panther G. Source 4K maps were
reduced to 2K for the editable Blender scenes. The runtime GLBs are
approximately 17–18 MB each. These are
visual approximations, not millimeter-accurate reconstructions.

Godot 4.7.2 headless checks passed for asset import, all six Open Day choices
and previews, livery application, turret traverse and gun elevation on the four
requested vehicles, and spawning both active tanks in the real Battle scene
with each of those four IDs. The test used rule controllers and checked scene
loading rather than running a full MaleCNS match. GUI layout and the visual
appearance in a live rendered battle still need manual review.

## Source and license records

- T-34-85: [Lotnik / OpenGameArt, CC0](../assets/models/imported/t34_85/LOTNIK_ATTRIBUTION.md).
- Tiger I: [Newc42 / itch.io, CC0](../assets/models/imported/tiger_i/ATTRIBUTION.md).
- IS-2 and Panther G: [MetaWorldOS / itch.io, CC0](../assets/models/imported/metaworldos/ATTRIBUTION.md).

The Newc42 working and original Blender files are kept under
`assets/models/imported/tiger_i/newc42/`. The MetaWorldOS editable Blender scenes
are under `assets/models/imported/metaworldos/`; the original downloadable GLBs
are large, so their official source links and SHA-256 hashes are recorded in the
attribution file rather than duplicated in the repository.

Jagdpanther and SU-100 remain on their existing assets. No combat physics was
rewritten. This change remains local: it has not been committed, pushed,
installed, or released.
