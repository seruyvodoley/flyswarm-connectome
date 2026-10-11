# macOS packaging

`./run.sh` is the working repository application launcher. It locates Godot,
sets repository/Python paths, prepares the import cache if absent and starts
Bootstrap/MainMenu. Godot owns optional backend processes; jobs supervise their
own children. Missing Python does not prevent Rule AI or the manual range.

`frontend/godot/export_presets.cfg` provides a universal macOS frontend preset.
`python tools/package_macos.py` prepares an isolated export staging directory,
including only small vehicle/gun/armour/scenario JSON and original GLBs. It
excludes MaleCNS data, caches and local references. `--export` runs Godot's
exporter and writes `build/FlySwarm.zip`; matching macOS export templates must
be installed. The archive currently contains only an unsigned universal Godot
frontend app with the FlySwarm icon.

This archive is not a standalone distributable. Python, scipy/numpy/flybrain,
the research job runner and MaleCNS dataset are not bundled. Neural modes rely
on repository-relative paths and a configured external `FLYSWARM_ROOT` and
`FLYSWARM_PYTHON`; a moved exported app cannot start them. Exported user
sessions/settings go to `user://`, not into the application bundle. A release
still requires a relocatable backend runtime, a user-facing dataset setup flow,
an arm64 DMG and ZIP, checksums, and a clean installed-app test. The current
local export is unsigned and not notarized.
