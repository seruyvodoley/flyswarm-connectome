# T-34-85 model candidate scouting

Screening date: 2026-10-16. Candidates were checked for license, downloadable
source, mesh structure, and historical claims before investing in conversion.
After the user relaxed the art gate to allow simplified models with separated
modules and recognizable silhouettes, Lotnik's OpenGameArt model passed as a
minimal local pilot. Its exact production year remains unverified.

## Wei He / Xdhsqj — rejected; preserve only

- [Thingiverse source](https://www.thingiverse.com/thing:4326802), archived at
  [Archive.org](https://archive.org/details/thingiverse-4326802); CC BY 4.0.
- Historical variant: listed only as “T-34 85 Detailed”; Model 1944 not
  confirmed.
- Source STL: 3,491,836 triangles; 1.74 million vertices; no UV or PBR maps.
- One principal mesh fuses hull, turret, and gun; 133 loose pieces have not
  been identified. No usable running-gear animation was established.
- Adaptation: very high; requires retopology plus major manual reconstruction
  of mechanical separation. Rejected per user direction. Keep the archive and
  imports as evidence; do not cut or repair this source.

## Lotnik — OpenGameArt; selected for the low-poly pilot

- [OpenGameArt listing](https://opengameart.org/content/t-3485); author
  Lotnik; CC0. The public direct file `Rudy.blend` was available and downloaded
  locally for a brief check (704,628 bytes; Blender 2.59).
- Historical variant: listing says “t-34/85” and its preview caption says
  “T-34 Russian tank”; factory/year details are absent, so Model 1944 is not
  confirmed.
- Blender 5.0.1 import: 4,113 triangles, 41 mesh objects. 39 objects have UV
  layers; none has assigned materials or PBR images.
- The model has a simplified but recognizable T-34/85 silhouette. Its hull
  shell, turret shell, gun barrel, and both track loops are separate source
  objects. The source has no authored pivots or articulated running gear.
- Adaptation: low to moderate. The existing geometry was preserved and grouped
  under FlySwarm hull, turret, and gun pivots; no mesh cutting was needed. The
  local GLB adds fourteen simple cylindrical rollers (seven per side), keeps
  both tracks as separate meshes, and reuses the existing wheel-spin behavior.
  Godot checks passed for import, livery, turret traverse, gun elevation, and
  muzzle movement. Track belts themselves remain static.
- The integrated pilot replaces only the T-34/85 runtime GLB. It is not a
  historically verified 1944 factory variant and is not a final running-gear
  pass. See [`LOTNIK_ATTRIBUTION.md`](../assets/models/imported/t34_85/LOTNIK_ATTRIBUTION.md)
  and [`lotnik_pilot.json`](../assets/models/imported/t34_85/lotnik_pilot.json).
- [Preview rendered from the exported GLB](../artifacts/models/t34_85_lotnik_pilot_preview.png)
  shows the low-poly silhouette, track loops, and simple wheel rollers; it is
  not a screenshot from the running Godot interface.

## KLGaming — Sketchfab; promising metadata, download gated

- [Sketchfab model](https://sketchfab.com/3d-models/t-34-85-tank-f344bd94aa8b4daf9761207a12fa6ae4);
  author KLGaming; CC BY 4.0.
- Historical variant: T-34-85 in general; exact 1944 production setup not
  stated.
- Listing reports 35.1k triangles / 18.4k vertices and three 2K PBR maps.
- Author says the objects are separated for customization and animation, but
  does not enumerate the turret, gun, track, or wheel hierarchy; no rig is
  included. Running-gear animation is unknown.
- Adaptation: potentially low to medium if the hierarchy is suitable. The
  public download control opened a Sketchfab sign-in prompt, so the source
  structure cannot be verified without account access. Skip under the current
  instruction to move on when the source cannot be obtained; no credentials
  were requested or entered.

## SamTT7 — BlendSwap; account-gated and structure unclear

- [BlendSwap listing](https://blendswap.com/blend/20012); author SamTT7;
  CC BY-SA. Blender 2.7 file listed at 23.1 MB.
- Historical variant: titled T-34-85; exact factory/year setup not stated.
- Triangle count, UVs, and PBR maps are not reported. The description lists a
  “single object model”, a separate suspension object, right/left tracks, and
  track guides; that does not establish separately pivoted turret and gun.
- Running gear appears to have parts but no confirmed animation rig.
- Adaptation: high until the Blender file confirms the hierarchy. Site requires
  login to download, so not obtained or tested. Skip.

## Other screened candidates

| Candidate | Listing evidence | Decision |
| --- | --- | --- |
| Ilya_1392, [Sketchfab](https://sketchfab.com/3d-models/t-34-85-soviet-tank-ebfb39f734aa4c3dae10eae4243b796a) | CC Attribution shown in search metadata; 88.8k triangles; described as a low-poly game model. No UV/PBR or component hierarchy in the listing; no download control surfaced on the page. | Skip: identity and mechanical structure cannot be verified from the available source. |
| Mr_Hmob, [Sketchfab](https://sketchfab.com/3d-models/t34-85-abac846f33da494a87d07db84ba5956a) | CC Attribution; 388.2k triangles; raw modeling practice mesh; author says lower hull/suspension details are missing. | Reject: missing vehicle geometry and no game-ready articulation. |
| Neo_minigan, [Sketchfab](https://sketchfab.com/3d-models/t-34-85-71442c66ad92427c98a14ddd7206cc91) | CC Attribution; 1.4M triangles; photogrammetry. | Reject: scan-scale mesh and no evidence of separable mechanical parts. |
| magistral075, [CGTrader](https://www.cgtrader.com/3d-models/military/military-vehicle/t-34-85mm) | Listing reports 3,445 triangles, PBR/UVs, rigged/animated, separated turret, gun mount, tracks, and wheels. Royalty Free, $15; page states the model is unavailable. | Reject: source cannot be downloaded and its license is not an open redistribution license. |
| aegcfo, [CGTrader](https://www.cgtrader.com/free-3d-models/military/armor/t-34-85-sov-medium-tank) | 270,646 polygons; 88.7 MB Blender 3.3; listing flags animated, rigged, PBR, and textures. Exact variant and hierarchy are not described. | Reject: Royalty Free license only permits incorporated products where the raw model cannot be retrieved; not a suitable open source asset for this project. |
| Vsevolod, [ArtStation](https://www.artstation.com/marketplace/p/Xkemv/t-34) | Author calls it a T-34, says about 400k triangles, not optimized for games, with poor UVs; author text offers free commercial use with attribution. | Reject: not identified as T-34-85; page also displays a conflicting Standard Use License. |
| Ahadul Hasan, [ArtStation](https://www.artstation.com/marketplace/p/k1rPR/tank-t-34-3d-model-soviet-medium-tank-world-war-weapon-3d-model) | Description claims T-34-85 Model 1944, PBR/4K, and unique named parts, but reports 1,198,747 quad faces and asks $50 under Standard Use License. | Reject for this pilot: very high geometry cost and non-open marketplace license; no source downloaded. |
| Agustank 3D, [BlendKit](https://www.blendkit.com/asset-gallery-detail/a89c0228-0e8a-4525-a71f-ffdf206c7380/) | “Toy Tank: T-34-85”; 2,443 polygons; rigged/basic videogame animation. License is not visible in the listing extract. | Reject: explicitly toy-styled and no verified redistribution license. |

CGTrader Royalty Free terms require a model to be incorporated so that the raw
asset cannot be retrieved, and prohibit redistribution in the downloaded
standalone form; see the [official license explanation](https://help.cgtrader.com/hc/en-us/articles/360015124437-Royalty-Free-License).
ArtStation Standard Use licenses are limited to the listed project/sales
limits; these are not open asset licenses for this pilot.

Searches covered Sketchfab, GitHub repository results, BlendSwap, OpenGameArt,
Wikimedia Commons, BlenderKit/BlendKit, CGTrader, ArtStation, Free3D, and other
free-model indexes. GitHub results did not surface a verifiable T-34-85 source
asset; Wikimedia searches surfaced no rigged game-ready model. Game-ripped
assets, personal-use-only downloads, and unclear licenses were excluded.

## Next selection gate

Keep the current pilot local while reviewing its in-game silhouette and the
existing damage/collider alignment. If a more accurate T-34/85 source is
considered later, require a verifiable redistribution license and inspect the
source structure before full download or adaptation. Do not touch the other
five vehicle models during this pilot.
