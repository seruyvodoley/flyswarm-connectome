# macOS packaging

The supported release workflow builds the Godot app and its Python backend as
one arm64 bundle, then produces the DMG, ZIP and checksums from that exact app.
Do not publish `build/FlySwarm.zip`; that legacy file is a Godot-only export.

Build on Apple Silicon with Godot 4.7.2, its matching macOS export templates,
and the project's Python 3.11 virtual environment:

```sh
./tools/run run-tests
.venv/bin/python tools/package_macos.py --build --version 0.2.0-beta.1
```

For an installer-only iteration with an unchanged backend already built in that
version's output directory, `--reuse-backend` skips only PyInstaller; normal
release builds should use the full command above.

The build uses Godot's official macOS template and thins its universal engine
binary to arm64. PyInstaller creates an onedir runtime so NumPy, SciPy, Numba,
llvmlite, FlyBrain, PettingZoo and Gymnasium plus their native libraries and
runtime data files are relocatable within
`FlySwarm.app/Contents/Resources/backend/FlySwarmBackend`. The app also carries
the small Python research job runner and its runtime source modules. It does
not carry the developer virtual environment, project checkout, personal paths,
results or MaleCNS data. Third-party license texts are bundled in
`Contents/Resources/THIRD_PARTY_LICENSES.txt`.

Installed-app mode derives backend and support paths from the app bundle and
stores settings, sessions, logs and job output under Godot's per-user writable
data directory. It does not depend on the current working directory or
environment variables. Developer mode continues to use `.venv`, `src/` and the
local checkout. Research and training jobs run through the packaged backend
entry point and the bundled job supervisor.

MaleCNS `brain.npz` and `weights.npz` are not included by default. A release may
include a local dataset after its license and redistribution terms have been
verified by passing `--dataset <folder>` to the same packaging command. The
packager checks both files against FlyBrain's published SHA-256 values, copies
them into `Contents/Resources/MaleCNS`, and includes `MALECNS_DATA_NOTICE.txt`
with attribution and license information. MaleCNS v1.0 and the prebuilt derived
runtime files are CC BY 4.0. The app selects a bundled dataset by default when
present. In Settings, users can choose another folder containing both files
and press **Check MaleCNS data**. The app validates checksums, saves the path,
and supplies `FLY_DATA` to its child backend. Open Day waits for actual
FlyBrain(batch=1) initialization and warm-up before reporting the backend
ready.

The build ad-hoc signs the app bundle for internal consistency. It has no
Developer ID signature and is not notarized. macOS Gatekeeper may show an
unidentified-developer warning; users must follow Apple's normal per-app
approval flow. The build never changes system security settings.

Outputs are written to `build/releases/<version>/`:

- `FlySwarm.app`
- `FlySwarm-<version>-macos-arm64.dmg` with an Applications shortcut
- `FlySwarm-<version>-macos-arm64.zip`
- `SHA256SUMS.txt`

The release gate includes checking every Mach-O slice for arm64, verifying the
ad-hoc signature and archive checksums, mounting the DMG, copying the app to a
temporary location outside the checkout, and launching the copied app. Release
is blocked if the standalone backend, dataset selection, Open Day, research
job flow, or installed-app smoke fails.
