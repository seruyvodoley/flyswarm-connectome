# T-34/85 source model

- **Title:** T-34-85 / T-34 Russian tank
- **Creator:** Lotnik
- **Source:** [OpenGameArt listing](https://opengameart.org/content/t-3485)
- **License:** CC0 1.0 Universal, as stated on the listing
- **Original file:** `candidates/Rudy.blend` (Blender 2.59 source scene)

The complete source scene is integrated as supplied: 41 mesh objects and 4,113
triangles. Its hull, turret, barrel, track loops, wheel shapes, and detailing
are retained unchanged. No wheel mesh, material, patch, or replacement part is
added. The only changes are a uniform vehicle-root scale/ground offset and the
`HullPivot`, `TurretPivot`, `GunElevationPivot`, and `Muzzle` nodes needed by the
existing FlySwarm controls. The left and right track objects remain separate.

The source has no prebuilt rig or animation and does not identify a verified
factory/year configuration. Its meshes are separate but do not expose an
animated running gear system. The runtime label remains **T-34-85**.

Rebuild from the included `candidates/Rudy.blend` with Blender 5 and
`tools/blender/build_lotnik_t34_candidate.py`.
