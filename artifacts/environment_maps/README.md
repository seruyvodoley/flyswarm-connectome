# Battlefield map visual checks

These are real screenshots captured from the FlySwarm Godot project on the
Apple M2 Metal renderer at 1440×900. `before` and `after` use the same camera
positions, seed (1944), lighting, and renderer. `before` means the preserved
`legacy` map profile; `after` means the default `enhanced_visual` profile.
The images were not generated or retouched.

## Krasny Valley

| View | Legacy | Enhanced |
| --- | --- | --- |
| Overhead | ![Legacy overhead](before-krasny-overhead.png) | ![Enhanced overhead](after-krasny-overhead.png) |
| Third person / vehicle scale | ![Legacy tank view](before-krasny-hull.png) | ![Enhanced tank view](after-krasny-hull.png) |
| Gunner sight line | ![Legacy gunner view](before-krasny-gunner.png) | ![Enhanced gunner view](after-krasny-gunner.png) |
| Farm settlement | ![Legacy settlement](before-krasny-village.png) | ![Enhanced settlement](after-krasny-village.png) |
| Woodland edge | ![Legacy woodland](before-krasny-forest.png) | ![Enhanced woodland](after-krasny-forest.png) |
| Road surface | ![Legacy road](before-krasny-road.png) | ![Enhanced road](after-krasny-road.png) |

## Training Range

| View | Legacy | Enhanced |
| --- | --- | --- |
| Overhead / firing lanes | ![Legacy range overhead](before-range-overhead.png) | ![Enhanced range overhead](after-range-overhead.png) |
| Tank and target corridor | ![Legacy range tank view](before-range-hull.png) | ![Enhanced range tank view](after-range-hull.png) |
| Gunner sight line | ![Legacy gunner view](before-range-gunner.png) | ![Enhanced gunner view](after-range-gunner.png) |
| Range margin | ![Legacy range edge](before-range-margin.png) | ![Enhanced range edge](after-range-margin.png) |

Training Range scenery stays outside the configured target axis. Open Day
continues to use its existing arena scene and destruction components; it is
covered by `open_day_validation.gd` and `environment_physics_validation.gd`.

## Limits visible in the images

The shared CC0 trees and rural buildings are stylized low-poly assets. They
provide distinct 3D forms and licensed geometry, but are not historically exact
Eastern European architecture. The default visual profile keeps legacy terrain
height, collision, and forest visibility behavior. `enhanced_physical` is a
separate research condition with changed relief, visibility, and destructible
obstacle collision. See `docs/environment_profiles.md` for the distinction.
