# Windows x64 build

The Windows package is built on a Windows x64 GitHub Actions runner. The workflow
exports the Godot project, builds a relocatable Python onedir runtime with
PyInstaller, creates an Inno Setup installer, installs it into a clean runner
directory, then smoke-tests the installed executable and MARL CLI. On a version
tag it produces downloadable GitHub Actions artifacts and adds the installer,
portable ZIP and checksums to a draft prerelease. Publish that release only after
the matching macOS DMG, ZIP and checksum have also been attached and validated.

The package contains no MaleCNS research dataset. The Windows automated checks
exercise the application and the self-contained MARL baseline backend. They are
headless runner checks; they do not verify the interactive GUI, graphics driver,
screen scaling, accessibility, or the MaleCNS dependency stack on physical
Windows hardware. Those checks require a manual run on a supported Windows x64
computer before claiming full Windows GUI or MaleCNS support.

Before claiming physical Windows DualSense support, install the package on a
Windows x64 computer, connect a DualSense by USB and Bluetooth in separate runs,
then verify Open Day menu focus/confirm/back, analog left-stick drive, independent
right-stick camera and turret aim, L2 zoom, single-shot R2, OPTIONS pause/resume,
and safe pause plus reconnection after removing the controller while moving.
The CI runner cannot certify any of these physical-controller checks.

The MARL implementation uses portable Python paths and Godot's process APIs.
Developer mode selects `.venv/Scripts/python.exe` on Windows and `.venv/bin/python`
on Unix-like systems. Packaged mode resolves the backend next to the exported
application. Outputs are written to the user's Godot data directory in packaged
mode and remain ordinary CSV, JSON, PNG and JSONL files.

Windows release files are named `FlySwarm-<version>-windows-x64-setup.exe`,
`FlySwarm-<version>-windows-x64.zip` and `SHA256SUMS-windows.txt`.
