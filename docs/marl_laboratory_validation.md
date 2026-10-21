# FlySwarm validation report

Updated: 2026-10-21

## Student editor and terminal

- Kept a runnable `agent.py` starter example directly in the editor. It returns
  the six continuous action values expected by the environment and steers
  toward the objective.
- Moved the API explanation and action/reward contracts into the Help dialog;
  removed explanatory copy from the editor breadcrumb.
- Replaced simulated per-command execution with a persistent interactive shell.
  Commands such as `cd`, Python, and virtual-environment activation keep their
  shell state between submissions. Up/Down recall command history, Ctrl+C sends
  an interrupt, and output is capped to avoid unbounded UI growth.
- Checked the macOS shell transport with `pwd`, a directory change, and a
  Python command in the same shell process. Full interactive GUI entry and
  editor keyboard shortcuts were not manually exercised in the packaged app.

## Automated checks

- `PYTHONPATH=src .venv/bin/pytest -q`: 74 passed; two PettingZoo deprecation
  warnings.
- `./tools/run run-tests`: 66 Python tests passed. Godot ballistics, environment
  physics, field generation, bridge protocol, research combat, and Open Day
  validations each reported zero validation failures.
- Godot editor import completed successfully.
- `git diff --check` passed.
- CUA captured the packaged app's main menu from the mounted-DMG copy. Further
  click-driven GUI checks could not be completed because the native app window
  was not available to the UI automation after capture.

## macOS arm64 build

- Build: `0.2.0-beta.54`, using `tools/package_macos.py` with the available
  `/Users/serg/fly-data` dataset.
- App bundle: `build/releases/0.2.0-beta.54/FlySwarm.app` (1.6 GB).
- Install image: `FlySwarm-0.2.0-beta.54-macos-arm64.dmg` (450 MB).
- ZIP: `FlySwarm-0.2.0-beta.54-macos-arm64.zip` (418 MB).
- The DMG mounted, passed `hdiutil verify`, and its app copy was tested outside
  the checkout. The app's signature verifies, and the executable is arm64.
- Backend `--check-data` reported ready for both bundled files. Bundled file
  sizes and SHA-256 values matched the source dataset:
  - `brain.npz`: 53,396,978 bytes; `cc9bd1ecd00bd703a6fa648bc6ad145c93c7c1ee53debdcc9ce0d1f4305e6aca`
  - `weights.npz`: 205,331,565 bytes; `c29919aa44069a271b1ee978abe05fa9bf6e45e4ba3e436e92b624ef1b5be40c`
- `MALECNS_DATA_NOTICE.txt` is included in the app bundle.
- Signing is ad-hoc; the app is not notarized. Optional dependency warnings
  appeared during PyInstaller packaging, but the backend build and packaged
  data check succeeded.
- SHA-256:
  - DMG: `410a4bbb2cd0e73082fc366c4b8cf67211eb8703e7b9e115da4b224d41760447`
  - ZIP: `52adc7754612ef44d66914f55be6b7020438d677a2efa2413237028c69fbacf6`

## Remaining verification

- The packaged GUI's MARL editing/help flow, full PPO training/evaluation,
  custom reward, export, MaleCNS folder picker, Open Day battle, window-size
  behavior, and physical DualSense operation were not manually verified here.
- This report contains no old validation screenshots: the existing visual
  snapshot files predate the current editor and must not be presented as this
  build's appearance.
- No before/after performance measurements were collected in this pass.
- No GitHub Release was created, in accordance with the user's instruction.

## Responsive Help and reward starter — beta55

- Updated the Python API Help window to wrap long explanations and stay within
  the application window. A Godot layout validation script checked 1280×720,
  1920×1080, 2880×860, and 800×480 viewports; all four sizes passed.
- Replaced the one-line reward placeholder with a commented, runnable example
  covering objective capture, damage, and own-vehicle losses. The Python
  backend template and Godot editor starter use the same example. The existing
  default reward weights and calculation remain unchanged.
- Updated the user's saved `reward.py` starter in the MARL workspace so an
  already-created workspace receives the same example. A backup of the prior
  starter was retained in the user's Trash.
- Python contract checks: 36 passed (`tests/test_marl.py` and
  `tests/test_marl_student_contracts.py`); two PettingZoo deprecation warnings.
- Godot headless Help layout validation passed with zero failures. Godot editor
  import also passed. The Help dialog was not manually click-tested in the
  packaged GUI because UI automation could not attach to its separate native
  window.

### beta55 package

- Built `0.2.0-beta.55` from commit `05adbe0` for macOS arm64. The installed
  copy at `/Applications/FlySwarm.app` opens; signature verification succeeds
  (ad-hoc), and the bundled MaleCNS data check reports both files ready.
- DMG verification and ZIP integrity checks passed. The mounted-DMG app copy
  was launched outside the checkout. Notarization was not performed.
- DMG SHA-256: `cfd0522a5c2cdfee1c552da8dd16e275b3644b7a954866e9b724cf964cfa0b9b`
- ZIP SHA-256: `80fc9943e09124c99265d471b2abf8fc670cb672d64979e17c0baf3b92ae17cc`
- No GitHub Release was published, per the user's instruction.
