# Application audit — 2026-09-16, before changes

Baseline: 46e00fb, branch feat/historical-3d-tank-simulator. Working tree clean.
No AGENTS.md was found. Existing research scripts/results are preserved.

|Subsystem|Existing entry points|Status|Decision|
|---|---|---|---|
|Godot project|frontend/godot/project.godot; main_scene = scenes/Battle.tscn|WORKING|Change entry point only; reuse battle|
|Battle scene|scenes/Battle.tscn (only existing tscn)|WORKING prototype|Reuse physics, combat, objectives, HUD/cameras|
|World|scripts/battle.gd, terrain.gd, vehicle.gd, tracks.gd, combat.gd, catalog.gd|WORKING approximations|Extend session configuration/manual input; no replacement|
|IPC|scripts/bridge.gd, src/flyswarm/bridge/{__init__,server}.py; localhost NDJSON|WORKING|Add lifecycle/status and mixed-team controllers|
|Brains|src/flyswarm/brain/__init__.py; two independent batch=8 objects|WORKING|Retain real network; add progress callbacks|
|CLI launchers|tools/run, tools/run_experiment.py, tools/training_smoke.py|WORKING|Retain; add normal run.sh app entry|
|Experiment runner|tools/run_experiment.py, paired Rule AI side-swap|PARTIAL|Expose only executable conditions; add asynchronous jobs|
|Replay|battle.gd recording and sampled world-state playback|PARTIAL|Add browser, manifest restoration, app return; no neural dependency|
|Training|training/fit.py + tools/training_smoke.py, real turret imitation|PARTIAL|Connect GUI to existing stage; disable unimplemented curriculum|
|Test range|--training scenario, no manual user controls|PARTIAL|Add manual drive/aim and range setup|
|Menus/router/settings/results/loading|none|MISSING|Add application shell and SessionConfig|
|Pause|SPACE; ESC immediately quits|PARTIAL|Add pause overlay and clean menu return|
|Backend supervision|manual separate terminal; timeout quits Godot|MISSING|Add managed local process lifecycle and recovery dialog|
|Application packaging|none|MISSING|Add macOS export preset, document local backend requirement|
|Vehicle assets|six ~4k triangle original procedural GLBs|PLACEHOLDER|Continue geometry work with references; never claim historical acceptance|
|Validation|scripts/validation.gd, showroom.gd, tests/test_simulator.py|WORKING|Retain and add application flow tests|

Existing .gd inventory: battle, bridge, catalog, combat, showroom, terrain,
tracks, validation, vehicle. No UI/menu scenes or Python GUI launcher existed.
Historical Python experiments under experiments/ are independent legacy work,
not safe GUI jobs because several execute on import and overwrite fixed outputs.
They will not be presented as enabled application experiments.
