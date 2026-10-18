# Battlefield environment profiles

Krasny Valley and Training Range use the shared CC0 field assets from
`frontend/godot/assets/environment/`. The default scenario profile is
`enhanced_visual`; Open Day keeps its dedicated compact arena and its existing
destruction behavior.

`enhanced_visual` adds detailed, repeatable PBR ground, more terrain triangles
sampled from the same legacy height function, CC0 tree and shrub meshes, farm
buildings, fences, stones, and grass. It does not add obstacle collision bodies
or alter the legacy forest visibility test. Training Range keeps the target
axis clear and its configured firing distances unchanged.

`enhanced_physical` adds gentle deterministic ground undulation, grades the
three dirt roads into the ground, and enables matching forest visibility,
tree-trunk collision, destructible masonry, wood fences, and stone obstacles.
It is an explicit experiment condition because it changes movement and line of
sight. Run a battle with `--environment-profile enhanced_physical` to select it.

`legacy` retains the prior procedural scenery and is the fallback for old
recordings without an environment profile. Select it with
`--environment-profile legacy`. Replay manifests now record the profile,
generator version, destruction state, seed, and source hashes so results from
different environment conditions stay distinguishable.

## Rendering and measured costs

Field assets use material-grouped `ArrayMesh`/`MultiMesh` batches. This avoids
creating one draw batch per imported leaf or prop mesh. In the repeatable
headless construction check at 35% vegetation density, the default Krasny
visual profile built 37 MultiMesh batches and 1,338 instances in about 1.3–2.8 s;
the physical profile built 22 batches and 1,862 instances in about 0.8–1.9 s;
the Training Range built 4 batches and 390 instances in about 0.3–0.4 s. The first
implementation created about 1,200 batches for the visual battlefield; grouped
mesh surfaces and cached terrain samples cut that to 37 while preserving the
same placements and terrain heights. These are scene-construction timings on
this Apple M2 machine, not GPU frame-time results.
The Metal gallery check renders at 1440×900 and confirms the map views; a
repeatable in-battle p99 frame-time comparison has not yet been recorded.

The 1K Poly Haven terrain maps now import mipmaps and use trilinear mip
sampling, which removes the strong high-frequency shimmer visible in the first
overhead capture. Tree and prop batches have finite visibility ranges; grass
does not cast shadows. Open Day keeps its existing, denser close-range layout
and destruction system.

The new field layouts use only assets already distributed in the project.
Their sources and licenses are recorded in
`frontend/godot/assets/environment/ASSET_SOURCES.md`: CC0 Poly Haven ground
maps, CC0 Innerscene trees, and CC0 3D Assets foliage, rocks, cottages, walls,
and fences. The existing cottages are generic rural props rather than
museum-grade Eastern European reconstructions.
