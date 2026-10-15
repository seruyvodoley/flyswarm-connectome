# T-34/85 pilot model attribution

- **Title:** T-34-85 / T-34 Russian tank
- **Creator:** Lotnik
- **Source:** [OpenGameArt listing](https://opengameart.org/content/t-3485)
- **License:** CC0 1.0 Universal, as stated on the listing
**Downloaded file:** `Rudy.blend` (704,628 bytes; Blender 2.59 source scene)

The source was screened before use. Blender 5.0.1 reports 41 mesh objects and
4,113 triangles; 39 meshes have UV layers, but the scene has no assigned
materials or PBR texture maps. Existing source meshes include the hull shell,
turret shell, gun barrel, and left/right track loops as separate objects. The
source does not provide named pivots, a rig, animated running gear, or a
verified factory/year configuration.

For the local FlySwarm pilot, no source mesh was cut, rebuilt, or decimated.
Existing objects were grouped below `HullPivot`, `TurretPivot`, and
`GunElevationPivot`; the gun muzzle marker follows elevation. The model was
uniformly scaled and centered at the ground plane. Two static track meshes
remain separate. Fourteen simple cylindrical rollers (seven on each side) were
added as separate nodes for the existing wheel-spin animation. The current
T-34/85 livery shader supplies runtime coloring.

The runtime GLB contains 4,953 triangles across 55 mesh nodes and is 256,732
bytes. The 4,113 source triangles are unchanged; the rest are the simple wheel
rollers. Godot applies the T-34/85 livery to all 55 surfaces.

The game label remains **T-34/85**; do not describe this as a verified 1944
factory configuration. The source scene is kept locally under the ignored
`assets/models/imported/t34_85/candidates/` directory; the generated game GLB,
this attribution, and `lotnik_pilot.json` are included in the repository.
