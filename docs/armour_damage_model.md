# Armour and internal damage model

FlySwarm uses a deliberately bounded tank damage model, not War Thunder's
proprietary damage solver. The result of every projectile collision is recorded
in `last_impact` and shown by the hit camera: stopped or ricochet, penetration
with minor internal damage, critical module/crew damage, or destruction.

## Shot resolution

The projectile ray intersects a hull, turret, casemate, mantlet or roof collider.
Each collider uses the nominal plate thickness from `data/armour/`; inclined
front plates are inclined in the collision geometry. Impact obliquity comes
from the actual surface normal. The current APHE penetration curve is
interpolated by distance; normalization and calibre overmatch adjust obliquity.
A shell must have more penetration than the effective thickness and must not
ricochet. On penetration, the remaining penetration controls how far the
projectile and fragments can travel into the tank.

Crew, ammunition, breech, turret drive, engine, transmission, fuel and tracks
are spatial damage volumes. A penetrating shot travels along its measured
local direction and sheds a widening 12-degree fragment cone. Cone reach is
bounded by residual penetration; fragment severity falls across the cone and
along the path. Direct and fragment damage add to each module's persistent
damage until it is disabled. The fighting-compartment volumes rotate with a
turret. Ammunition-rack damage also accumulates and disables the rack at its
critical threshold. A vehicle is destroyed only when that rack detonates or
no more than one crew member remains. Thus multiple shots can disable the
breech and one crew member, then another crew member, before the fatal hit.
Lesser module failures leave the vehicle alive but impair the corresponding
function.

The battle HUD uses the same reticle in every camera mode. Each enemy impact
opens a compact damage report with the actual 3D vehicle, a translucent
X-ray-style shell, the incoming path, and colored module markers: amber for
damaged and red for disabled. The report lists cumulative module damage and
crew remaining. The final Open Day result retains the same shot history and
damage state.

## Historical scope and limitations

Crew counts now follow the documented five-person Tiger I, Panther,
Jagdpanther and T-34/85, and four-person IS-2 and SU-100. German and T-34/85
hull crew include a radio operator. The collider layout follows each asset's
actual fighting-compartment pivot, including the forward casemates of the
Jagdpanther and SU-100. The Jagdpanther and SU-100 casemate fronts use the
inclined geometry recorded in their armour data. The remaining armour figures,
projectile curves, module coordinates and fragment sizes are still simulation
approximations, not surveyed engineering plans. The fragment cone is
deterministic and does not trace individual fragments or conserve their energy
physically. In particular, this model does not yet simulate cast-armour
variation, ballistic caps, fuze delay, individual round stowage,
material-quality variation, projectile shatter or internal bulkheads. It must
not be used for quantitative historical claims.

Reference points: [The Tank Museum's Tiger I](https://tankmuseum.org/tank-nuts/tank-collection/tiger-i/),
[Panther](https://tankmuseum.org/tank-nuts/tank-collection/panther/),
[Jagdpanther](https://tankmuseum.org/tank-nuts/tank-collection/jagdpanther/) and
[T-34/85](https://tankmuseum.org/tank-nuts/tank-collection/t-34-85/) collection
records; [US Army ODIN's SU-100 record](https://odin.t2com.army.mil/WEG/Asset/3542e205d88502994ba3ea1771494ec6);
and the official War Thunder descriptions of
[ground vehicle modules](https://wiki.warthunder.com/mechanics/4775-ground-vehicle-modules)
and [post-penetration effects](https://wiki.warthunder.com/mechanics/4236-the-mechanics-of-high-explosive-effect-and-overpressure).
