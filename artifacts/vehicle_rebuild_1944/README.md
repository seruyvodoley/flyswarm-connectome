# Six-vehicle visual and mechanical review

Each vehicle directory contains front, side, top, rear, two three-quarter views, an isolated running-gear view and an articulated view. `*-review.jpg` combines these views. `godot/` contains actual Metal-rendered images with the game's appearance material in neutral, traverse and elevation poses.

## Validation

- `rebuilt_vehicle_validation.gd`: all six vehicles; fixed meshes remain fixed during traverse, muzzle direction and elevation, mechanical parentage, wheel counts/axle origins and both track meshes. Zero failures.
- `rebuilt_vehicle_visual_validation.gd`: 18 actual Godot Metal renders, all six vehicles with camouflage; this is not a headless rendering claim.
- Existing Python suite: 28 tests passed.
- Existing ballistics and environment-physics Godot validations: zero failures.
- Headless Open Day vehicle validation checks selection/preview switching and battle instantiation.

Limitation: the existing graphical Open Day preview validator stalled waiting for a rendered frame; it was terminated. The separate graphical model validation above succeeded. This is not a claim that every gameplay/UI path was manually re-tested, nor a dimensional certification against factory drawings.

Source/variant/provenance notes: `../../assets/models/rebuilt_1944/README.md`.
