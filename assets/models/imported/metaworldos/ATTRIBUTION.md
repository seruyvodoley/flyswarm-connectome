# IS-2 and Panther G source models

- **Creator:** MetaWorldOS.
- **Pack:** [WWII Tank Pack GLB Models](https://metaworldos.itch.io/wwii-tank-pack-glb-models).
- **License:** CC0 1.0, stated by the creator on the pack page.
- **IS-2 source file:** `tank-battle-is-2.glb`; source SHA-256
  `b93a3002f5e03ed54c157deb9c085380d25e133ab8320e5d1609e29f0bbf8be3`.
- **IS-2 FlySwarm GLB SHA-256:**
  `787b0f562ee2554835d0b58259d39e6f972d3b5f9a5c119623531c98e5f24058`.
- **Panther source file:** `tank-battle-panther.glb`; source SHA-256
  `0276b30df384b9ac024378eecb0d16a09151b627190e6d405ee4d379298d92cc`.
- **Panther FlySwarm GLB SHA-256:**
  `2ebfbd91eac1f8643fb107396b99e24c577345e3edfc239b5fa178b0a1211846`.

The project uses the full CC0 source vehicles already imported in the tracked
runtime GLBs. Their complete hull, turret, running gear, tracks, barrel, and
surface materials are retained. This revision removes the temporary FlySwarm
turret substitutions and restores the source GLBs from the project history.
The editable Blender scenes are regenerated from those same GLBs without
changing mesh geometry. The model hierarchy keeps the hull and turret as
separate siblings; the gun-elevation pivot and muzzle are children of the
turret rig. No visual remodelling or new mesh geometry is used.

The creator's pack page describes the delivered GLBs as single-mesh, 1-unit-per-
meter assets with embedded PBR materials, and explicitly grants CC0. FlySwarm
uses the established model names and pivots for combat controls. Source pack
files are not included because the complete downloadable archive is 809 MB.
The model GLBs used here are the project versions of those CC0 sources; this
task changes no source mesh data on either vehicle.
