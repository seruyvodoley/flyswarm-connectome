# IS-2 and Panther G model attribution

- **Creator:** MetaWorldOS.
- **Pack:** [WWII Tank Pack GLB Models](https://metaworldos.itch.io/wwii-tank-pack-glb-models).
- **License:** CC0 1.0 Universal, as stated by the creator on the pack page.
- **IS-2 source file:** `tank-battle-is-2.glb`; source SHA-256
  `b93a3002f5e03ed54c157deb9c085380d25e133ab8320e5d1609e29f0bbf8be3`.
- **IS-2 FlySwarm GLB SHA-256:**
  `787b0f562ee2554835d0b58259d39e6f972d3b5f9a5c119623531c98e5f24058`.
- **Panther source file:** `tank-battle-panther.glb`; source SHA-256
  `0276b30df384b9ac024378eecb0d16a09151b627190e6d405ee4d379298d92cc`.
- **Panther FlySwarm GLB SHA-256:**
  `2ebfbd91eac1f8643fb107396b99e24c577345e3edfc239b5fa178b0a1211846`.

The source files are each a single mesh with embedded PBR maps. They were
downloaded from the creator's public pack and split into hull, turret, gun,
left/right track belts, and left/right running-gear meshes. Each scene exposes
the standard FlySwarm hull, turret, gun-elevation, and muzzle pivots. The
resulting models contain approximately 174k triangles for IS-2 and 191k for
Panther G; 4K source maps were reduced to 2K in the editable Blender scenes.
The official source files are not copied into this repository because they are
large; the optimized editable scenes and their source hashes are retained.

These are visual approximations. The conversion preserves the source silhouette
and materials while supplying mechanical pivots; it does not claim factory-level
historical accuracy.
