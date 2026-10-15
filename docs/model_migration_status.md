# Historical vehicle model migration status

This is a local, single-vehicle pilot. The T-34/85 runtime model has been
replaced locally for validation; the other five vehicle models remain unchanged.

| Vehicle | Status | Source and license | Runtime replacement |
| --- | --- | --- | --- |
| T-34-85 | LOW-POLY PILOT INTEGRATED / GODOT CHECKS PASS | Lotnik, OpenGameArt, CC0; 4,113 source triangles; 41 source meshes plus 14 simple rollers | Yes, local GLB |
| Panther G, late 1944 | BLOCKED / not started | No verified, downloadable, correctly licensed source selected | No |
| Tiger I, late | BLOCKED / not started | No verified, downloadable, correctly licensed source selected | No |
| IS-2, Model 1944 | BLOCKED / not started | No verified, downloadable, correctly licensed source selected | No |
| Jagdpanther G1 | BLOCKED / not started | No verified, downloadable, correctly licensed source selected | No |
| SU-100, 1944–45 | BLOCKED / not started | No verified, downloadable, correctly licensed source selected | No |

## Rejected Wei He candidate evidence

- Archive integrity passes and SHA-256 is
  `6991e9f8f4bf3f322306c7446af01205c3d8fa3e6d7126958b50aa486146315d`.
- The STL is 174,659,284 bytes and imports as 3,491,836 triangles, with one
  connected principal mesh and 133 loose components.
- It has no UV maps or PBR textures. Its title and available source record do
  not establish the requested 1944 production configuration.
- The main mesh fuses hull, turret, and gun. The candidate is rejected; no
  further cuts or geometry repair are allowed. A prior exploratory cut remains
  as a diagnostic artifact only and must not be used.
- No geometry from this rejected source is integrated.

## Selected Lotnik pilot

- The game now loads Lotnik's OpenGameArt CC0 model for the T-34/85. The source
  has 4,113 triangles in 41 objects and UV layers on 39 objects, with no
  materials or PBR textures. Its listing does not confirm a production year.
- Existing source meshes were grouped under hull, turret, and gun pivots. The
  muzzle follows gun elevation, and left/right track loops remain separate
  static meshes. Fourteen simple wheel rollers use existing wheel-spin
  behavior. T-34/85 livery applies to all 55 runtime mesh surfaces.
- Godot 4.7.2 headless validation passed for import, node hierarchy, all 55
  mesh nodes, livery, turret traverse, gun elevation, and muzzle movement. The
  full Open Day headless validation also passed, including its firing and
  control checks; a DualSense was connected. Track-belt animation, LOD,
  collider/damage-zone alignment, and full GUI visual review remain unverified.
- This is the only vehicle asset changed. Combat physics was not rewritten.

The downloaded source scene and review renders are local and ignored by Git;
the runtime GLB, build script, measurement report, attribution, and status are
reviewable. The reusable first-stage importer supports STL, GLB/glTF, and FBX.
See [candidate scouting](t34_85_candidate_scouting.md) for alternatives and
[the import pipeline](model_import_pipeline.md) for tooling.

## Release and integration gate

Before treating the pilot as final, visually review it in the game and check
the sight, muzzle, collider, and damage-zone alignment. Measure performance if
the art is accepted. This work remains local; no merge, push, tag, installation,
or release is part of the current task.
