# Vehicle asset scouting — 2026-10-16

Scope: six FlySwarm vehicles. This is an initial source screen and a practical
visual review, not a claim of millimetre-level historical accuracy. A listing's
license, author, format and model statistics are not a substitute for checking
the actual source mesh from useful views.

The acceptance gate is: zero-cost asset; attributable source; license that
allows modification and redistribution in FlySwarm; no commercial-game rips;
recognizable silhouette and key vehicle-specific features; working mechanical
pivots; acceptable performance. Exact factory, month, and production subvariant
are not required unless they change a conspicuous feature. Review front, side,
and top silhouettes and check the characteristic running-gear layout. Do not
reject a usable simplified model for absent rivets, production details, or
unverified minor dimensions. Once a candidate passes this practical visual and
structural screen, move to integration rather than prolonging research.

## Candidate cards

### T-34-85, intended 1944 configuration

- **Lead:** [T-34/85 by Lotnik](https://opengameart.org/content/t-3485), CC0.
- **Evidence:** prior local source inspection recorded 4,113 triangles and 41
  source mesh objects. Hull, turret shell, barrel and left/right track loops
  are distinct; source has UVs on 39 objects but no assigned materials/PBR.
- **Historical variant:** listing does not establish a 1944 factory/version;
  under the updated acceptance gate this is a caveat, not a rejection.
- **Visual review:** existing neutral renders show the sloped hull, rounded
  turret, long gun without a muzzle brake, and five large road wheels per side
  with drive/idler wheels. The same silhouette is legible from front-quarter,
  side, and top views. See `docs/model_validation/t34_85/`.
- **Structure and integration:** source records show separate hull, turret,
  barrel, and track loops. Existing pilot groups these under the live turret
  and gun pivots and retains the existing muzzle/physics contract.
- **Assessment:** passes the revised minimum visual-recognition gate for the
  T-34-85 pilot. It is a simplified, low-poly T-34-85, not a verified Factory
  183 Model 1944 reconstruction. Keep it as the pilot; do not reject or recut
  it solely to establish the exact production batch.

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
- **Disposition:** continue only until one low-cost candidate has a plausible
  silhouette and workable moving parts. Do not spend time proving exact 1944
  subvariant if the visible hull, turret, gun, and IS-family running gear are
  credible. The current candidates still lack inspected source structure.

### Panther Ausf. G

- **Lead A:** [Panther G by brow.wes](https://sketchfab.com/3d-models/panther-g-f76129fb212e4f70b76dbb34d770d823),
  Sketchfab CC BY; listing reports 363.3k triangles and identifies the vehicle
  as Sd.Kfz. 171 / Panther G.
- **Historical variant:** Ausf. G is named, but production sub-variant is not.
- **UV/PBR and hierarchy:** not documented in the listing extract; turret/gun
  pivots and interleaved road-wheel geometry are unknown.
- **Assessment:** named Panther G with a recognizable target, but relatively
  dense and with undocumented structure. Inspect one small preview/source
  first; do not let a missing production subvariant alone disqualify it.
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
  production. The late running-gear appearance still needs a quick check, but
  exact batch documentation is not a gate.
- **UV/PBR and animation:** no PBR/UV statement; separate movable parts are
  described, but no authored animation rig is claimed.
- **Assessment:** best first structural-screen lead because the source is small,
  free and explicitly modular. Candidate only until its silhouette and
  characteristic running gear have been inspected.
- **Disposition:** best small candidate to inspect next. The page describes
  movable separate wheels, turret, and gun and CC0. The free download flow asks
  for an email address, so no account or personal contact detail was supplied;
  obtain the asset only through a normal public download path, or move on.

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

The same pack page also documents 1:1 metre GLBs, embedded PBR and Godot
compatibility, but confirms each tank is a single mesh. It can be revisited only
if a short, reliable segmentation pass proves it can expose the required
mechanical pivots without significant mesh surgery; the 809 MB archive is not a
first-choice download for a single-mesh candidate.

## Current status

The Lotnik T-34-85 pilot passes the revised visual-recognition gate and remains
the only accepted asset in this six-vehicle sourcing pass; its exact year,
track animation, and full GUI validation remain open. Next inspect the small
CC0 Newc42 Tiger through an ordinary zero-cost download if possible. If access
requires contact details, payment, or account circumvention, skip it and select
the next compatible candidate. For the remaining vehicles, stop searching once
a legal, recognizable, mechanically usable source is found; minor production
uncertainty is acceptable. Never use a commercial-game rip or mark a blockout
as an accepted third-party model.
