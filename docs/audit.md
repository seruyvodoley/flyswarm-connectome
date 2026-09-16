# Cleanup audit — 2026-09-16

Project: `/Volumes/RisingSail/основы программирования/flytank`.
Source attachment: `/Users/serg/Downloads/flyswarm_05_two_brains_8v8.py`.
Initial repository: no Git history; only src/, results/, .venv/.

Preserved 22 historical Python scripts and 25 result/config/model files.
`file_manifest.json` records every original path, destination, size and SHA-256.
All 47 hashes verified after relocation; all 25 legacy result symlinks resolve
and return the original bytes. New attachment copied byte-for-byte (SHA-256:
`84eead725dcdef129aed979633d3ed0ae9a8cae3c7cf98b056af4926dc4ee115`).

Historical scripts contain no imports from adjacent experiment files or
__file__-relative data paths. Their results paths are relative to working
directory, so all launches must use the repository root. No historical source
was edited. Experiments 003 and 008 are causal controls and were classified
alongside 010a/010b. brain_smoke_test.py remains in single_agent/.

Exact duplicate script groups:
- experiments/single_agent/experiment_002_tracking.py, archive/prototypes/experiment_002_tracking_WORKING.py
- experiments/swarm/flyswarm_01_batch.py, archive/prototypes/flyswarm_01_batch_WORKING.py
- experiments/swarm/flyswarm_02_battle.py, archive/prototypes/flyswarm_02_battle_WORKING.py

All three *_WORKING.py files retained in archive/prototypes/. No scientific
files deleted. Initial inspection found no temp/backup/cache files in src or
results; macOS AppleDouble ._* files appeared during filesystem operations and
are ignored, as are generated Python caches and .DS_Store.

MaleCNS is configured at /Users/serg/fly-data outside the repository; no download
was needed. .venv and optional local data directories are ignored. Large raw
artifacts remain on disk and are ignored. Small summaries, JSON configs and
three NPZ research artifacts (largest ~1.55 MB) are intentionally versioned.

Validation:
- py_compile of FlySwarm 0.5: passed.
- Plain compileall encountered macOS AppleDouble ._*.py metadata (null bytes).
  Re-run with -x '/\._' over experiments src archive tests tools: passed.
- unittest: 10 tests passed; no brain loaded by unit tests.
- pytest not installed; optional requirements-dev.txt added.
- Real shortened temporary-copy import: passed; independent CPU brains, each
  batch=8, distinct weight and voltage arrays; all three conditions exercised.
- Temporary raw CSV: 6 rows; summary CSV: 3 rows. No smoke output retained as
  scientific results. Original 45-second experiment was not run.

Importing the untouched 0.5 source directly runs the full experiment. Import
validation was therefore performed on a temporary AST-patched copy, changing
only duration/seed-count/rest parameters. This is not a full-duration validation.

segment_circle_t returns the closest-point projection and ignores zero-length
segments, rather than computing first contact. Tests document this existing
behavior; any physics change belongs in a separately assessed Phase 2 commit.

GitHub CLI is absent. No remote repository created and no authentication bypass
attempted. Local repository is ready for a private GitHub push after gh setup.
