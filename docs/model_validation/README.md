# Historical model acceptance report — 2026-09-16

**All six assets remain BLOCKOUT / NOT ACCEPTED.** No historically accurate
finished variant is claimed. The named variants below are targets, not achieved
production-detail matches. Independent dimension sheets remain incomplete;
strict validation exits 2. This is an intentional acceptance failure, separate
from passing software tests.

Measurements are from imported GLB geometry, in metres; W/L include external
fittings and the forward gun, H excludes the antenna. No texture bitmaps are
used. Only the provisional LOD0 exists; LOD1/LOD2/LOD3 are not implemented.

|Target variant|Measured W × L × H (m)|LOD0 triangles|References and checks|
|---|---|---:|---|
|IS-2 Model 1944, straightened upper glacis|3.350 × 9.150 × 3.157|3848|[references](../references/is2_1944/references.md), [checklist](is2_1944/variant_check.md), [renders](is2_1944/front_3q.png)|
|Jagdpanther G1, 1944|3.470 × 10.611 × 2.890|3960|[references](../references/jagdpanther/references.md), [checklist](jagdpanther/variant_check.md), [renders](jagdpanther/front_3q.png)|
|Panther Ausf. G, late 1944|3.470 × 9.000 × 3.157|4020|[references](../references/panther_g/references.md), [checklist](panther_g/variant_check.md), [renders](panther_g/front_3q.png)|
|SU-100, wartime 1944/45|3.280 × 9.055 × 2.890|3300|[references](../references/su100/references.md), [checklist](su100/variant_check.md), [renders](su100/front_3q.png)|
|T-34-85 Model 1944, Factory 183 (target; not yet verified)|3.280 × 7.525 × 3.157|3572|[references](../references/t34_85/references.md), [checklist](t34_85/variant_check.md), [renders](t34_85/front_3q.png)|
|Tiger I, late production 1944|3.900 × 8.225 × 3.157|4020|[references](../references/tiger_i/references.md), [checklist](tiger_i/variant_check.md), [renders](tiger_i/front_3q.png)|

## Implemented versus missing

- Panther: sloped hull, rotating turret and long gun exist; exact late-G
  proportions, chin mantlet, wheel overlap, deck/exhaust details remain unverified.
- Tiger: turret, hull and barrel articulation exist; rounded asymmetric turret,
  late steel-wheel layout, hull width and external fittings are not validated.
- Jagdpanther: Panther-family blockout with fixed casemate and long gun exists;
  G1 gun collar, exact casemate angles, running gear/deck details are not validated.
- T-34-85: five-wheel blockout and rotating rounded turret exist; Factory 183
  casting shape, wheel spacing, hatch and deck layout are not validated.
- IS-2: six-wheel blockout and large gun exist; Model 1944 glacis, cast turret,
  mantlet, brake and wheel spacing are not validated.
- SU-100: five-wheel chassis and fixed casemate exist; wartime commander cupola,
  offset gun/mantlet and roof/rear details are not validated.

Historical dimensions *used*: none of the geometry inputs currently passes the
independent variant-specific reference gate. Do not reinterpret the measurements
above as historical target values. Available museum references establish only
selected mass/speed/gun fields, not a full geometry specification.

Every vehicle directory contains front, rear, left, right, top, front_3q,
rear_3q neutral Blender renders. `godot/` contains front/side/front_3q screenshots
at one orthographic scale for all six models. These images expose the current
state; rendering them does not constitute human recognition acceptance.

Reproduce (requires Blender installed):

```sh
/Applications/Blender.app/Contents/MacOS/Blender -b --python-exit-code 2 \
  --python tools/blender/validate_vehicle_dimensions.py -- --strict
```

Do not proceed to cosmetic weathering to mask these geometry failures. The next
modelling pass must first complete legal, exact-variant orthographic reference
packs and independent dimensions, then correct silhouettes before detail/LOD.
