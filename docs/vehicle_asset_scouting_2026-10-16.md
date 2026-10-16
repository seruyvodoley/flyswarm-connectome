# Vehicle asset scouting — 2026-10-16

Scope: six FlySwarm vehicles. This is an initial source screen, not model
approval. No third-party vehicle files were downloaded or integrated in this
pass. A listing's license, author, format and model statistics are not a
substitute for inspecting the actual source mesh from multiple views.

The acceptance gate is: zero-cost download; attributable author/source; license
that allows modification and use in FlySwarm; no ripped commercial-game art;
recognizable and historically plausible silhouette; separated or cheaply
separable chassis, turret and gun where applicable; running gear that can meet
the vehicle-specific wheel/track layout. Preserve the current runtime model
until a replacement passes import, articulation, geometry and performance
checks.

## Candidate cards

### T-34-85, intended 1944 configuration

- **Lead:** [T-34/85 by Lotnik](https://opengameart.org/content/t-3485), CC0.
- **Evidence:** prior local source inspection recorded 4,113 triangles and 41
  source mesh objects. Hull, turret shell, barrel and left/right track loops
  are distinct; source has UVs on 39 objects but no assigned materials/PBR.
- **Historical variant:** listing does not establish a 1944 factory/version.
- **Running gear:** source pilot added seven simple rollers per side. That
  geometry does not meet this task's five-large-road-wheel requirement and
  must not be carried over as approved geometry.
- **Assessment:** promising low-cost source for a new pilot after exact
  silhouette and running-gear review; the current evidence does not qualify it
  as the requested 1944 model.
- **Disposition:** keep as a lead; no source copied from another worktree.

### IS-2, Model 1944

- **Lead A:** [IS2 Soviet WWII Tank by ShaposhnikovG](https://sketchfab.com/3d-models/is2-soviet-wwii-tank-7efb256211eb423cb3f479e96bcb08fc),
  Sketchfab CC BY; listing reports 6.6k triangles / 4k vertices and tags 1944.
- **Historical variant:** the title and tags do not establish the 1944 hull
  configuration.
- **UV/PBR and hierarchy:** not stated on the available listing extract;
  turret/gun separation and wheel/track structure remain unknown.
- **Assessment:** low-poly and potentially useful, but no structural acceptance
  yet. Sketchfab states model downloads require an authenticated account
  ([download guidance](https://sketchfab.com/developers/download-api/guidelines));
  no credentials were requested or entered.
- **Lead B:** [IS2 Heavy Tank by adrielcz](https://sketchfab.com/3d-models/is2-heavy-tank-4ecb3d27eb5d491ba76a4c3ceeeb5895),
  CC BY; listing reports 461.9k triangles and says UVs were not authored by
  the model creator. Mesh structure and moving parts are unknown.
- **Disposition:** neither candidate is approved for download/integration until
  the source structure and required 1944 hull are verified.

### Panther Ausf. G

- **Lead A:** [Panther G by brow.wes](https://sketchfab.com/3d-models/panther-g-f76129fb212e4f70b76dbb34d770d823),
  Sketchfab CC BY; listing reports 363.3k triangles and identifies the vehicle
  as Sd.Kfz. 171 / Panther G.
- **Historical variant:** Ausf. G is named, but production sub-variant is not.
- **UV/PBR and hierarchy:** not documented in the listing extract; turret/gun
  pivots and interleaved road-wheel geometry are unknown.
- **Assessment:** the triangle count is high for a candidate advertised without
  game-asset details. Structure must be inspected before any download effort.
- **Lead B:** [low-poly Panther G on Free3D](https://free3d.com/3d-model/panther-pzkpfw-ausf-g-low-poly-model-97333.html)
  reports 4,026 polygons, but is explicitly under a Personal Use License;
  that does not satisfy redistribution in FlySwarm.
- **Disposition:** A remains unverified; B rejected on license.

### Tiger I, late production

- **Lead:** [Low Poly German WWII Tanks by Newc42](https://newc-42.itch.io/german-low-poly-wwii-tanks),
  CC0 1.0, free/name-your-price. Author reports 5,175 vertices for the Tiger I,
  a shared palette texture, and states wheels, turret and guns are separate
  movable objects. Available source formats are Blender and FBX.
- **Historical variant:** page says Pz-VI-Tiger, but does not specify late
  production or the 16-wheel steel-rimmed layout.
- **UV/PBR and animation:** no PBR/UV statement; separate movable parts are
  described, but no authored animation rig is claimed.
- **Assessment:** best first structural-screen lead because the source is small,
  free and explicitly modular. Still not approved as a late Tiger until the
  downloaded source proves the correct late running gear and silhouette.
- **Disposition:** eligible for a small source inspection after visual preview;
  no runtime replacement yet.

### Jagdpanther G1

- **Lead:** [Jagdpanther G1 by KojfDiscord](https://sketchfab.com/3d-models/jagdpanther-g1-war-thunder-b56ac9d5efe4402a8122183723fde281),
  Sketchfab CC BY, 151.9k triangles.
- **Historical variant:** G1 is named, but the author explicitly labels it a
  War Thunder model extraction.
- **Disposition:** rejected. The permissive page license does not make a
  commercial-game rip acceptable under this task. A separate, clean source has
  not yet been found.

### SU-100

- **Lead A:** [SU-100 (Victory Day) by 42manako](https://sketchfab.com/3d-models/su-100-victory-day-eae3337d22a74f11bb5143b7071c426e),
  Sketchfab CC BY, 4k triangles; description says it is a retexture of an SU-100
  from Theatre of War 2.
- **Disposition:** rejected as a game rip; pivot/material hierarchy is also
  undocumented.
- **Lead B:** [SU-100 winter-camouflage model by Majorfatal](https://www.cgtrader.com/free-3d-models/military/military-vehicle/su-100-tank-destroyer-soviet-winter-camo)
  lists moving tracks/wheels, gun movement, UV/PBR and Blender/GLTF/FBX. The
  listing gives a 1.49 GB Blender source and 724 MB GLTF. Its CGTrader Royalty
  Free terms permit incorporation only when end users cannot retrieve the
  source asset; the terms require reasonable safeguards
  ([official license terms](https://help.cgtrader.com/hc/en-us/articles/360015124437-Royalty-Free-License)).
  FlySwarm's ordinary Godot resources are extractable, and no protective asset
  packaging was verified for this work.
- **Disposition:** not downloaded. Size and redistribution conditions make it
  unsuitable for the current asset pipeline unless the author provides a
  compatible explicit license and the project can satisfy the protection
  clause.

## Other screened lead

[WWII Tank Pack by MetaWorldOS](https://metaworldos.itch.io/wwii-tank-pack-glb-models)
states CC0 1.0, and contains a Panther and an IS-2. The page says each tank is
a single mesh per file; the pack is 809 MB. Since no mechanical submeshes or
pivots are documented, it does not meet the first-pass articulation gate and
was not downloaded.

## Current status

No candidate has yet passed every licensing, source-structure and historical
variant check. No models in the runtime roster were changed. The next useful
action is to visually inspect and, if still suitable, obtain only the small
CC0 Newc42 Tiger source and confirm its wheel arrangement; in parallel, seek
clean, non-game-ripped modular candidates for Panther G, Jagdpanther G1 and
SU-100. Do not promote any of the unverified leads above to a final model.
