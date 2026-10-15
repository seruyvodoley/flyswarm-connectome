# Vehicle motion and gun guidance

The six vehicles share one deterministic tracked-vehicle model, but have separate
mass, engine power, speed limits, neutral-steering capability, maximum hull turn
rate, turret/casemate traverse rate, and gun elevation limits. The vehicle JSON
files in `data/vehicles/` are authoritative for the values used by the game.

Commands request movement; they never write an angle or speed directly. Engine
power, mass, soil grip and slope determine acceleration, capped by the tuned
drivetrain response. Steering changes yaw rate with a finite angular
acceleration. Turret traverse and gun elevation have independent rate and
acceleration limits. Mouse input accumulates desired hull/turret/gun angles;
each mechanism slews toward its target and brakes before reaching it. A damaged
turret drive reduces traverse and elevation to one tenth of nominal rate; a
disabled gunner cannot aim. The fixed simulation tick makes the behaviour
independent of input event frequency.

| Vehicle | Main-gun traverse | Gun elevation rate | Hull turn cap |
| --- | ---: | ---: | ---: |
| Panther G | 14°/s | 2.8°/s | 24°/s |
| Tiger I (H1 reference) | 8.4°/s | 2.8°/s | 18°/s |
| Jagdpanther G1 | 5.6°/s, ±11° arc | 2.8°/s | 22°/s |
| T-34-85 | 17.5°/s | 2.8°/s | 27°/s |
| IS-2 (1944) | 9.8°/s | 2.8°/s | 17°/s |
| SU-100 | 4.9°/s, ±8° arc | 2.8°/s | 25°/s |

The gun guidance rates use the **basic-crew reference figures** on the official
War Thunder Wiki pages for [Panther G](https://wiki.warthunder.com/unit/germ_pzkpfw_V_ausf_g_panther),
[Tiger H1](https://wiki.warthunder.com/unit/germ_pzkpfw_VI_ausf_h1_tiger),
[Jagdpanther G1](https://wiki.warthunder.com/unit/germ_panzerjager_panther),
[T-34-85](https://wiki.warthunder.com/unit/ussr_t_34_85_zis_53),
[IS-2 (1944)](https://wiki.warthunder.com/unit/ussr_is_2_1944), and
[SU-100](https://wiki.warthunder.com/unit/ussr_su_100_1945). These are game
reference figures, not measured mechanical test curves. The hull turn caps,
angular accelerations, throttle response and drive acceleration caps are
deliberately marked as approximations in each vehicle's provenance. Terrain,
transmission state and track damage further affect observed movement. This
model improves pacing and distinction between vehicles; it does not claim to
reproduce exact historical gear ratios or hydraulic traverse behaviour.
