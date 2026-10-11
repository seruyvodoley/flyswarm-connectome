# Open Day visual validation captures

Captured from Godot 4.7.2 running the real scene on Apple M2 with the Metal renderer.

- `vehicle-*`: selected GLB in the menu's actual VehiclePreview viewport.
- `battle-*`: each selected vehicle in the 1v1 arena after a real MaleCNS backend connection and live traces.
- `fly-000.png`, `fly-090.png`, `fly-180.png`, `fly-270.png`: real fly viewport at those yaw angles; `fly-360.png` checks the full turn cycle.
- `result-human-win.png` and `result-fly-win.png`: production DemoResult page captures after a test vehicle elimination, one for each outcome. The eliminations are scripted validation inputs, not claims of human-played matches.

`open_day_vehicle_validation.gd` checks six livery profiles, preserved mechanical pivots, destroyed/reset appearance, 30 preview switches, visible rendered frames, and world-Y fly rotation. `open_day_final_capture.gd` checks live MaleCNS telemetry and both result routes while writing the battle and result captures.
