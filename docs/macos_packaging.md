# macOS packaging

`./run.sh` is the working repository application launcher. It locates Godot,
sets repository/Python paths, prepares the import cache if absent and starts
Bootstrap/MainMenu. Godot owns optional backend processes; jobs supervise their
own children. Missing Python does not prevent Rule AI or the manual range.

`frontend/godot/export_presets.cfg` provides a universal macOS frontend preset.
`python tools/package_macos.py` prepares an isolated export staging directory,
including only small vehicle/gun/armour/scenario JSON and original GLBs. It
excludes MaleCNS data, caches and local references. `--export` additionally runs
Godot's exporter, requiring matching macOS export templates. Output is an
unsigned frontend archive in build/FlySwarm.zip; signing/notarization is not done.

No finished standalone distributable is claimed. Python, scipy/numpy/flybrain
and the MaleCNS dataset are NOT bundled. Exported Rule AI/range can read embedded
JSON; neural modes need a configured external FLYSWARM_ROOT and FLYSWARM_PYTHON.
Exported user sessions/settings go to user://, not into the application bundle.
A future signed release needs a relocatable backend runtime, dependency licenses,
dataset provisioning UX and native package testing.
