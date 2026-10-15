# Community vehicle model import pipeline

Third-party models are kept separate from the current playable GLBs until a
vehicle has passed review. For each candidate, retain the source archive,
license evidence, a per-vehicle configuration, an untouched Blender import,
and a separate working/optimized export. The source archive and working
Blender files are ignored by Git because they can be very large; attribution,
configuration, scripts, and approved optimized assets remain reviewable.

The import helper reads STL, GLB/glTF, and FBX. It reports the source size,
format, bounds, triangle and vertex counts, materials, UV presence, and does
not infer component roles. A reviewed axis/scale entry in the vehicle JSON
enables normalized Blender output. A manual component-region script remains
for future approved candidates, but refuses to process any source marked
`rejected`. The Wei He source is rejected and must not be cut further.

Example on Apple Silicon with Blender installed:

```sh
blender -b --python tools/blender/import_vehicle_asset.py -- \
  --vehicle t34_85 \
  --source assets/models/imported/t34_85/source/extracted/files/T-34-85.STL
```

For the rejected T-34-85 source record, see
[`assets/models/imported/t34_85/ATTRIBUTION.md`](../assets/models/imported/t34_85/ATTRIBUTION.md)
and its `model_config.json`. The selected simplified OpenGameArt pilot has
separate attribution and a measured build report in
[`LOTNIK_ATTRIBUTION.md`](../assets/models/imported/t34_85/LOTNIK_ATTRIBUTION.md)
and [`lotnik_pilot.json`](../assets/models/imported/t34_85/lotnik_pilot.json).
Rebuild it from the locally downloaded `Rudy.blend` with:

```sh
blender -b assets/models/imported/t34_85/candidates/lotnik_opengameart_rudy.blend \
  --python tools/blender/build_lotnik_t34_candidate.py -- \
  --output frontend/godot/assets/vehicles/t34_85.glb \
  --report assets/models/imported/t34_85/lotnik_pilot.json
```

Scouting cards and rejection reasons are in
[`t34_85_candidate_scouting.md`](t34_85_candidate_scouting.md). The source
by Wei He remains rejected and is unsuitable for economical game integration:
3.49 million triangles, fused hull/turret/gun, no UV/PBR textures, and no
verified 1944 configuration. Its separation helper still fails closed and
must not be run against that source. The current T-34/85 runtime GLB is the
Lotnik pilot; the other five runtime models are untouched.
