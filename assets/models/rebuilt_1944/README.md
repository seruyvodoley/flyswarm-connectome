# Integrated 1944 vehicle models

These are untextured geometry sources. The active battle/preview GLBs now come from `../pbr_1944/`, which adds UVs and baked PBR maps without remodeling. Each editable `.blend` is saved before glTF export. Reproduction: Blender background mode with `tools/blender/rebuild_1944.py -- <id>` (first three vehicles) or `tools/blender/rebuild_remaining_1944.py -- <id>` (remaining three).

| Vehicle | Configuration and geometry | Road wheels per side |
|---|---|---|
| T-34-85 | 1944-style cast turret, sloping hull, smaller raised end wheels, unbraked 85 mm barrel | Five paired stations |
| IS-2 | Late 1944 straight glacis, broad cast turret, D-25T-style brake, return rollers | Six paired stations |
| Panther G | Late G-style chin mantlet, angular turret moved aft, staggered wheel pairs | Eight paired stations |
| Tiger I | Late steel-wheel configuration; retained Newc42 hull/turret, replaced running gear/barrel, removed early smoke-launcher clusters | Eight paired stations |
| Jagdpanther | G2-style extended engine deck, fixed sloped casemate and bolted collar, limited gun traverse | Eight paired stations |
| SU-100 | Fixed sloping casemate, projecting right commander's bay/cupola, D-10S-style barrel without brake | Five paired stations |

The Tiger hull/turret derive from Newc42's CC0 [German Low Poly WWII Tanks](https://newc-42.itch.io/german-low-poly-wwii-tanks). Its pre-rebuild GLB is preserved at `../imported/tiger_i/newc42/tiger_i_pre_rebuild.glb`. Other meshes in this directory were constructed in the project by the accompanying generators. Historical drawings were used as visual references, not redistributed or embedded textures. Archived imported candidates elsewhere in the repository are not these runtime assets.

Reference plates: [T-34-85](https://man.fas.org/dod-101/sys/land/row/t34-85-line.gif), [IS-2](https://www.onwar.com/wwii/tanks/ussr/su005is2mp.html), [Panther G](https://onwar.com/wwii/tanks/germany/ge026pantherg.jpg), [Tiger I](https://onwar.com/wwii/tanks/germany/ge067tiger1p.html), [Jagdpanther G2](https://www.onwar.com/wwii/tanks/germany/ge011jagdpantherp2.html), [SU-100](https://www.onwar.com/wwii/tanks/ussr/su021su100p.html).

## Mechanical contract

`VehicleModel` contains fixed `HullPivot`, independently driven `TurretPivot`, its `GunElevationPivot`, and `Muzzle`. For the two casemate vehicles, the traverse pivot carries only the moving gun assembly. Wheel mesh origins lie on their axles; left/right tracks retain the existing animation interface. Existing physics, armor, damage, AI and input code are unchanged. Existing wheel rotation/belt animation is supported; articulated suspension and individually moving track links are not implemented.

These are simplified game models with reference-based silhouettes, not certified dimensional replicas. Small fittings, cast contours and suspension details remain approximations. Automated rig checks do not establish historical accuracy; the rendered gallery is provided for visual review.
