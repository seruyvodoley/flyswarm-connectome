# Vehicle and track-ground approximation

Units: metres, seconds, kg, kW. Heading zero is world +Z, +Y up.
Longitudinal acceleration is limited by both traction and P/(mass*speed), with
an efficiency factor 0.7 and low-speed denominator floor 2 m/s. Rolling drag,
slope gravity, braking, reverse limits and turn speed loss act separately.
Ground category chooses road/cross-country cap. Automatic gear display is
currently diagnostic; individual gearbox torque curves are NOT modelled.
German neutral steering and slower low-speed Soviet steering are provisional
approximations, not detailed transmission models. Damage affects mobility.

Godot CharacterBody3D handles world collision; sampled terrain gradients tilt
the visual chassis. Suspension links are not simulated individually. Terrain
height is deterministic from scenario seed. There is a dry riverbed crossing,
not water hydrodynamics. All meshes use metres without Godot rescaling.

## Track marks / ruts

tracks.gd is a bounded 6000-segment MultiMesh ring buffer (no link rigid bodies).
Left and right contact points follow chassis transforms. Belt travel includes
left = v + yaw_rate*track_spacing/2; right = v - yaw_rate*track_spacing/2, so pivot turns generate curved marks. Marks appear
only at ground contact and accumulated travel; stationary vehicles do not draw
continuous trails. Each strip follows the local terrain normal and configured
track width. Marks wrap through the ring buffer instead of growing indefinitely.

Pressure = mass*g*terrain_normal.y / (2*track_width*0.72*hull_length). A deliberately simple
soil-compliance law estimates rut depth from pressure/stiffness and slip, capped
at 0.18 m. Road, soil and riverbed use separate stiffness/grip/resistance.
Slip is an effort-versus-grip proxy, not measured track angular velocity.
The sparse 1.5 m rut grid accumulates irreversible settlement with each pass,
using d_next = max(d_old, d_old + (d_limit-d_old)*(1-exp(-travel/1.2))).
The slip-dependent limit is capped at 0.18 m. This law is independent of how
a fixed travel distance is split into steps. Swept strips deposit samples at
0.5 m intervals; both track cells feed resistance, not the empty chassis centre.
Airborne motion clears contact history to avoid bridging jumps with trails.
Existing ruts increase
rolling resistance for subsequent traffic. This is an uncalibrated terramechanics
approximation. It does NOT solve Bekker/Wong equations or material failure.

The visual marks and traction/resistance effects work; the terrain collision
mesh is NOT plastically deformed. The depth estimate is logged, not presented
as a measured trench depth. Contact samples use chassis tracks, not suspension
raycasts per road wheel. Dust and mud ejection are still TODO.
