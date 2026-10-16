# Local map integration captures

These PNG files are captures of the running Godot scenes, not concept art.

- `open-day-village.png` — Open Day arena after the initial smoke curtain; camera placed toward its farmhouse lane.
- `open-day-battle.png` — short Open Day battle from the normal follow camera.
- `historical-battle-overview.png` — overhead view around the central capture sector, showing the map lanes and sector placement.
- `historical-battle-village.png` — close view of a Historical Battle farmstead, fence line, and woodland edge.

The map geometry and screenshot framing were validated on this macOS arm64
development machine with Godot 4.7.2. The captures do not represent packaged-app
or Windows GUI verification.

The 10-second Open Day Rule AI render sample is recorded at
`../performance/battle-rule-2026-10-16T22-53-04.json`. It averaged 59.8 FPS,
16.72 ms/frame, and 20.36 ms p99 at 1280 × 800 on Apple M2. Godot did not
expose GPU time. This sample is not directly comparable to the older full
8v8 Historical Battle profile.
