# Vehicle art reference pass — 1944–45 (work in progress)

This is an **art-direction and evidence log**, not a declaration that the supplied
GLBs meet historical drawing tolerances. The six existing in-house Blender/GLB
models are retained. No third-party tank geometry or drawing files are bundled.

## Sources and reuse

A published web page is **not** automatically an open-source drawing. In
particular, paid publications (e.g. Panzer Tracts) and drawings on reference
aggregator sites must not be copied into the repository just because a preview
is freely visible. The links below distinguish public-domain / CC0 **visual
references**, independently published **technical descriptions**, and schematic
drawings. Use measurements from independently corroborated, variant-specific
evidence before setting `verified: true` in a dimension sheet.

| Vehicle | Open visual / profile reference | Variant check |
| --- | --- | --- |
| T-34-85 (1944) | [T-34-85 at Kubinka (photograph; author-released public domain)](https://commons.wikimedia.org/wiki/File:T-34-85_in_the_Kubinka_Tank_Museum_outside.JPG); [additional public-domain photo](https://commons.wikimedia.org/wiki/File:T_34-85.jpg) | [Tank Encyclopedia's 1944 specifications and variants](https://tanks-encyclopedia.com/ww2/soviet/soviet_t34-85/). Do **not** use the freely licensed [NVA T-34-85/D-5T silhouette](https://commons.wikimedia.org/wiki/File:T-34-85_nva.svg) as a dimensionally validated drawing of a 1944 Factory 183 ZiS-S-53 tank. |
| Panther Ausf. G (late 1944) | [public-domain Panther G vector side profile](https://commons.wikimedia.org/wiki/File:Panzer_V_panther.svg); [public-domain museum photograph](https://commons.wikimedia.org/wiki/File:Panther_Ausf._G_pic1.JPG) | Silhouette is a **profile**, not a fully dimensioned manufacturer drawing; confirm G hull shape, cupola and mantlet from variant-specific references. |
| Tiger I (late production) | [public-domain vector profile](https://commons.wikimedia.org/wiki/File:Panzer_VI_tiger.svg); [British wartime technical side view (UK Crown Copyright expired)](https://commons.wikimedia.org/wiki/File:Tiger_Side_View_Left.png); [originally licensed public-domain museum photograph](https://commons.wikimedia.org/wiki/File:%D0%9D%D0%B5%D0%BC%D0%B5%D1%86%D0%BA%D0%B8%D0%B9_%D1%82%D1%8F%D0%B6%D1%91%D0%BB%D1%8B%D0%B9_%D1%82%D0%B0%D0%BD%D0%BA_Pz.VI_(Tiger_I).JPG) | Existing model has [component measurement sources](references/tiger_i/dimension_sheet.json); do not confuse the early-production and late-production running gear. |
| IS-2 Model 1944 | [public-domain museum photograph](https://commons.wikimedia.org/wiki/File:%D0%A2%D1%8F%D0%B6%D0%B5%D0%BB%D1%8B%D0%B9_%D1%82%D0%B0%D0%BD%D0%BA_%D0%98%D0%A1-2_pic1.JPG) | Preserve the **straightened 1944 glacis**, cast turret shape, 122-mm gun and IS running gear. Photo is *not* a calibrated drawing. |
| Jagdpanther G1 (1944) | [public-domain museum photograph at Sinsheim](https://commons.wikimedia.org/wiki/File:Panzerkampfwagen_V_Jagdpanther,_Technik_Museum_Sinsheim.jpg); [CC0 photograph at Saumur](https://commons.wikimedia.org/wiki/File:Jagdpanther_Saumur_1.JPG) | Preserve Panther-family running gear and continuous sloped superstructure, gun mounting and casemate-limited traverse; G1 ≠ G2. |
| SU-100 (1944–45) | [public-domain museum photograph](https://commons.wikimedia.org/wiki/File:SU-100,_Artillery_museum,_Saint-Petersburg_pic1.JPG); [US DoD public-domain reference](https://commons.wikimedia.org/wiki/File:Su-100_Panzer.jpg) | SU-100 is **not** a T-34-85 with turret removed: check continuous casemate, 100-mm gun, mantlet, roof and commander cupola. |

Many Commons photos show **restored museum vehicles** with potentially
non-original paint or postwar fittings. Use them for shapes and components,
not as proof of wartime camouflage or exact manufacturer dimensions.

## 1944–45 camouflage treatment

Primary technical colour context: [AFV Colors and Camouflage —
Wehrmacht/Bundeswehr](https://www.theworldwars.net/resources/file.php?r=camo_heer)
(RAL 7028 Dunkelgelb, RAL 6003 Olivgrün and RAL 8017 Rotbraun).
Its colour swatches and the Godot palette are **visual approximations**, not
measured period paint standards or spectrophotometric RAL matches.

| Vehicle | In-game interpretation | Rationale / limit |
| --- | --- | --- |
| T-34-85 | Muted 4BO-inspired protective green; no compulsory multicolour patches | A single-colour wartime Soviet vehicle is an appropriate conservative default. An exact 4BO pigment/sRGB match is **not** asserted. |
| IS-2 (1944) | Muted olive protective green | Same conservative wartime-family scheme; factory, front and markings intentionally unspecified. |
| SU-100 | Protective green, with dusty tracks and painted road-wheel centres | No invented factory or unit-specific disruptive pattern. |
| Panther G | German three-colour late-1944, with small contrast-colour spots; *Hinterhalt-inspired* | A **representative scheme**, not a verified MAN/Daimler-Benz/MNH production batch or vehicle serial number. |
| Tiger I late | German three-colour with broader, soft field-applied bands **without Panther-style dots** | No unsupported claim that the particular late Tiger had factory Hinterhalt. |
| Jagdpanther G1 | German broad, field-applied three-colour breakup | No unsupported claim of one particular manufacturer's exact painted pattern. |

Colour palette and camouflage pattern scale are tuned per vehicle in
`frontend/godot/scripts/vehicles/vehicle_appearance.gd` and rendered by
`frontend/godot/shaders/vehicle_livery.gdshader`.

The paint shader now keeps low-amplitude texture detail where a source albedo
texture exists and distinguishes painted road-wheel faces, rubber tyres, steel
tracks and mechanical recesses. The GLBs retain their existing physically
animated gun/turret/muzzle hierarchy.

## Geometry correction checklist (NOT YET VERIFIED OR REBUILT)

The current files in `assets/models/` and `frontend/godot/assets/vehicles/`
remain in place. Prior geometry passes are provisional (see
`docs/references/pass03_audit.md`). Their visual resemblance is not evidence
of manufacturer-level accuracy. Each item below needs front/side/top
comparison and Blender/Godot re-export; **do not make unverified dimension
edits based solely on a photo or a nominal overall length**.

- **T-34-85**: select the exact 1944 turret subvariant; confirm rounded
  two-piece cast turret contour, cupola position, five-wheel spacing, rear
  engine deck and ZiS-S-53 barrel/mantlet. Avoid D-5T-specific features.
- **Panther G**: check glacis and single-piece upper hull profile,
  Schürzen mounts, interleaved road-wheel rows, grille layout, rear deck and
  turret/mantlet. Compare exact late-production fittings, not an A/D hybrid.
- **Tiger I late**: verify late production road-wheel style, front/rear plate
  dimensions, cupola, turret asymmetry, gun/muzzle brake and rear fixtures.
  Existing verified *component* numbers are not sufficient to approve full GLB.
- **IS-2 1944**: inspect straightened glacis junction, broad cast turret,
  distinct road wheels, commander cupola, gun shield and large D-25T barrel.
- **Jagdpanther G1**: confirm glacis-casemate blend, gun axis/mantlet, engine
  deck, Panther-derived gear and superstructure hatch locations.
- **SU-100**: check continuous front casemate, mantlet and barrel axis, roof
  sight/cupola, T-34-derived running gear and hull front.

For every geometry pass retain the following node/pivot contracts:
`TurretPivot`, `GunElevationPivot`, `Muzzle`, and wheels; do not disturb
armour collision zones or introduce a false visual muzzle position.

## Validation still required

- Open the actual Godot 4.7.2 project and confirm shader compilation.
- Capture consistent previews under identical lighting, including the
  undersides and separate running-gear materials.
- Test original/destroyed livery, six vehicle previews, 1v1 and 8v8.
- Compare geometry silhouette at 3 orthographic views per variant.
- Check muzzle alignment with physical shells after any GLB re-export.
- Measure FPS on M2 8 GB before shipping.
- Do not mark strict historical validation PASS until the variant-specific
  dimension sheets have genuine independently checked values.

**Status:** paint code and research checklist drafted; Godot screenshots,
GLB regeneration, geometry corrections, visual acceptance and release checks
are **NOT** completed in this branch.
