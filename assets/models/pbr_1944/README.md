# Baked vehicle PBR materials

Active GLBs live in `frontend/godot/assets/vehicles/`; this directory contains matching GLBs, editable Blender sources with packed images, and PNG source maps. Geometry comes from `../rebuilt_1944/` without remodeling. Reproduce with Blender background mode and `tools/blender/bake_vehicle_pbr.py`. Each manifest records its deterministic seed.

## Schemes and evidence

| Vehicle | Selected representative scheme |
|---|---|
| T-34-85 (1944) | Matt protective 4BO, subdued green, cast turret microrelief |
| IS-2 (late 1944) | Slightly darker 4BO, independently phased variation, cast turret |
| SU-100 (1944–45) | 4BO, independent variation, rolled casemate and cast mantlet |
| Panther G (late 1944) | Dunkelgelb / Olivgrün / Rotbraun broad sprayed bands; no automatic ambush dots |
| Tiger I (steel-wheel 1944) | Dunkelgelb base with distinct green/brown swept bands |
| Jagdpanther G2 (1945) | Independent longer-scale three-colour bands across the casemate |

These are representative period-compatible schemes, not reproductions of identified individual vehicles. RGB values are visual approximations, not calibrated historical RAL/4BO measurements. No invented unit insignia. Zimmerit is not implemented; the Tiger must not be represented as a fully factory-exact 1944 surface reconstruction.

[The Tank Museum: Watching Paint Dry](https://tankmuseum.org/article/watching-paint-dry/) documents the February 1943 German three-colour system, field application and variability from thinning/application. [The Tigers Repainted](https://tankmuseum.org/article/repainted/) explains the use of archival documents and original paint samples, and cautions by example against treating older museum restorations as authentic schemes. [AMMO's Russian greens reference](https://www.migjimenez.com/img/cms/PDF/russian-greens-leaflet.pdf) identifies 4BO as the wartime protective green; this commercial modelling reference supports the colour family, not an exact RGB specification.

## Texture/material contract

Each vehicle has three 2048² images:

- `albedo.png`: encoded sRGB paint, rubber and steel colours; modest deterministic paint variation, low/upward-facing dust, sparse hatch/fender scuffs, exhaust darkening. No directional shadows or highlights baked into colour.
- `orm.png`: data channels R=short-range structural occlusion, G=roughness, B=metallic. Intact paint is dielectric; exposed steel is metallic; rubber is rough and nonmetallic. AO uses four short rays within each mesh, keeping unrelated moving parts out of the bake. It is an approximation, not a high-sample cavity bake.
- `normal.png`: data, OpenGL tangent-space normals; fine cast relief is stronger than rolled plate relief. The geometry, pivots and wheel origins are unchanged.

UVs are generated and packed across the entire vehicle; colour is evaluated in assembly/rest coordinates before rasterization, so separate mesh origins do not reset the camouflage. Six-pixel edge dilation reduces mip seams. Small details have lower texel density than large plates; this is not a hand-unwrapped hero asset.

The glTF-compatible Principled material exports maps directly. `VehicleAppearance` preserves `FlySwarmPBR_*` materials, including their normal/ORM channels, instead of replacing them with the old procedural shader. A separate darkened material handles destruction and restores cleanly on reset. Existing legacy meshes retain the shader fallback.

Open Day ambient fill was reduced from .86 to .62 to retain surface shading; sun, renderer and overall game lighting style remain in place. Godot Mobile renderer is used; no unsupported SSAO/SSIL added.

Limitations: no exact-unit camouflage claim, Zimmerit absent, no hand-painted localized hatch grease or detailed weld normals; UV packing and short-ray AO remain automated approximations. These limitations should not be confused with missing glTF material channels, which are checked separately.
