# Tiger I model attribution

- **Creator:** Newc42.
- **Model pack:** [Low Poly German WWII Tanks](https://newc-42.itch.io/german-low-poly-wwii-tanks).
- **License:** CC0 1.0 Universal, as stated by the creator on the pack page.
- **Selected asset:** `Pz-VI-Tiger` (the Tiger I shown in the earlier source review).
- **Source SHA-256:** `3301a0bea43211398c34194e344e4c48bc7354cd6af36818886ef1b6292a1980`.
- **Runtime GLB SHA-256:** `a033c8ea8a8457346d2dcb580e90a3d4a3a50deb3bd147cdd4b611b1b4087b77`.

The source Blender scene already separates hull, turret, barrel, tracks, and
wheel geometry. The FlySwarm scene adds the standard `VehicleModel`,
`HullPivot`, `TurretPivot`, `GunElevationPivot`, and `Muzzle` nodes while
preserving the artist's wheel and track hierarchy. The converted GLB contains
26 mesh nodes, including 21 wheel meshes. The working Blender scene packs its
color atlas. The original source and atlas are retained in `newc42/`.

The pack's asset is a low-poly visual model, not a certified production-series
reconstruction. The current game label remains Tiger I.
