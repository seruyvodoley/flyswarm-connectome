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

The battle HUD uses the same reticle in third-person and gunner views. It hides
the reticle in overhead and free-camera views. It distinguishes a ready gun
from reloading, empty ammunition, a disabled breech, and an incapacitated gunner.
Only a shot fired by the currently selected tank at an opposing tank opens
the hit report in any battle mode; incoming hits and other agents' shots cannot
be mistaken for damage dealt. The report identifies the shooter and target,
uses the target's own 3D model, and closes after four seconds or when the
selected tank or camera changes. Each such impact opens a compact report with a translucent
X-ray-style shell, the incoming path, and colored module markers: amber for
damaged and red for disabled. The report lists cumulative module damage and
crew remaining. The final Open Day result retains the same shot history and
damage state.

A separate lower-left status panel follows the selected tank. It lists the
surviving crew, ammunition, weapon readiness, disabled modules, and cumulative
partial damage. Both the status panel and impact report are hidden in overhead
and free-camera views. Open Day projects the pointer into the 3D scene, solves
a low-arc ballistic aim point, and slews the turret and gun toward it while the
camera follows the hull. Left-click fires; holding right-click smoothly zooms
the third-person camera and releasing it restores the normal view. The player's
tank moves under a separate automatic navigation controller. In Open Day only,
penetrating hits reduce six player or three opponent health points; they do not
disable crew or mobility modules. The opponent has an eight-second safe opening
and a twelve-second demo-only reload. Historical Battle and every other mode retain
the module and crew damage model above. The click that dismisses the opening
card does not also fire a shell.

## Mode audit

Open Day and Test Range send mouse fire through the same `Vehicle.step` gate as
the autonomous battle's AI actions. A short click is retained across the next
physics tick. Firing requires an alive vehicle, available ammunition, a loaded
gun, a functioning breech, and a living gunner. A blocked shot consumes neither
ammunition nor reload time. Damage from every actual projectile hit persists in
`module_damage`; no crew member or module silently recovers. Range target reset
is an explicit exception that restores the target for another trial.

The 3D battle, Open Day, and Test Range use the same projectile, armour,
fragment-cone, module and crew logic. A penetrating shot may miss internal
modules, damage one or more modules, or destroy the vehicle when the ammunition
rack is disabled or no more than one crew member survives. A non-penetration or
ricochet leaves internal modules unchanged. The X-ray report follows the
target's actual turret angle; hits on existing wrecks do not replay the previous
damage report. The Test Range destruction explanation uses the recorded lethal
reason, including crew losses outside the driver/gunner/commander trio.

In the shared battle view, a selected tank has a top-down 2D damage schematic:
green marks are intact, amber marks are damaged, and red marks are disabled.
Crew positions use circles and mechanical modules use squares. The hit view
shows only shots from that selected tank, loads the struck vehicle's own mesh,
and replays the recorded entry point and projectile direction through the
armour. Bright markers identify modules touched by that shot; branch lines
illustrate the fragment cone toward those modules, rather than individual
simulated fragments. Both overlays are hidden in overhead and free camera
modes. The hit view closes after four seconds and sits above tank-switch
controls.

The PettingZoo MARL Laboratory runs a separate analytical training environment
with scalar vehicle health and abstract shot damage. Its battle visualizations
must not be interpreted as measurements of the 3D armour/module solver. Replays
restore recorded positions and module states but do not re-simulate projectile
collisions or reconstruct every transient hit-camera event. Crew substitution,
repairs, fire propagation and individual fragment trajectories are not modeled.

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
