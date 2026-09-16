# Armour and ballistics

Spheres/tracers represent finite-speed projectiles. Each physics tick integrates
gravity and exponential drag exp(-drag_per_m*speed*dt), then sweeps a ray over
only the travelled segment. This prevents tunnelling and is not weapon hitscan.
The projectile starts at the articulated muzzle, including hull pitch and gun
elevation. Intersections use terrain/building layer 1 and armour layer 4.
Shooter colliders are excluded; friendly hits can occur. Visuals are lightweight.

Armour panels are independent collision shapes with zone IDs and normals.
Upper/lower front, hull sides/rear/roof, turret or casemate faces and mantlet
use JSON nominal thickness. Incidence = acos(-direction dot normal).
Effective thickness = thickness / cos(max(0, incidence - normalization)), with
cosine floor 0.05; grazing shots ricochet at the ammo threshold. Penetration is
linear interpolation of the distance table, clamped to its endpoints.

IMPORTANT: the supplied penetration tables, normalization and ricochet limits
are provisional simulation curves, NOT sourced test-standard-equivalent data.
They must not be used to claim historical penetration capability. Mantlet
curvature is coarse and overlapping armour layers are not accumulated.
Projectile APHE labelling denotes intended family, not a validated explosive
filler/fuze implementation. Filler is null; only penetrator/spall is simulated.

After penetration, a local penetrator ray plus expanding analytical cone visits
module volumes. Disabled modules change motion, aiming or reload; ammo rack or
critical crew loss destroys the vehicle. No common vehicle HP pool. Internal
positions and cone width are explicitly approximate. Repair, fire propagation,
fragment energy accounting, and crew substitution are not implemented.

Godot validation tests normal/grazing impact, interpolation, all six actors'
module destruction and projectile spawn. Vacuum time/drop checks are analytical
checks, not validation of historical dispersion or drag tables.
