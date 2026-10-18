# In-engine PBR comparison

`before/` and `after/` contain matching actual Godot Mobile/Metal captures for every vehicle: front, side, top, quarter, turret/casemate and running gear. `after/` adds three alternate light azimuths, ambient-only shade and distant views. `all-six.png` shows all models together. Camera, geometry and lighting match between comparison phases; both use the revised .62 ambient fill.

`validation.json` records the renderer/device, failures, draw calls, texture memory and 120 CPU-observed frame intervals after 30 warm-up frames per phase. This is a controlled six-model scene using battle lighting values, not a full MaleCNS battle benchmark. Timing order/cache effects mean an improvement here must not be advertised as a guaranteed gameplay FPS gain. Texture memory is renderer-reported, including cached resources.

Run `vehicle_material_validation.gd` graphically. Its temporary baseline resources are copies of `assets/models/rebuilt_1944/*.glb` into `frontend/godot/assets/vehicle_pbr_baseline/`; import these first and remove this temporary directory before application packaging. Baseline uses the previous livery shader. The test asserts imported albedo, normal, roughness, metallic and AO channels, and captures the images.

See `../../assets/models/pbr_1944/README.md` for sources, schemes, textures and limitations.
