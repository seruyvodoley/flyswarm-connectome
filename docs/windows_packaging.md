# Windows x64 build

The Windows package is built on a Windows x64 GitHub Actions runner. The workflow
exports the Godot project, builds a relocatable Python onedir runtime with
PyInstaller, creates an Inno Setup installer, installs it into a clean runner
directory, then smoke-tests the installed executable and MARL CLI. On a version
tag it produces downloadable GitHub Actions artifacts. Attach those validated
installer files to the same GitHub Release as the macOS artifacts only after the
Windows job succeeds.

The package contains no MaleCNS research dataset. The Windows automated checks
exercise the application and the self-contained MARL baseline backend. They are
headless runner checks; they do not verify the interactive GUI, graphics driver,
screen scaling, accessibility, or the MaleCNS dependency stack on physical
Windows hardware. Those checks require a manual run on a supported Windows x64
computer before claiming full Windows GUI or MaleCNS support.

The MARL implementation uses portable Python paths and Godot's process APIs.
Developer mode selects `.venv/Scripts/python.exe` on Windows and `.venv/bin/python`
on Unix-like systems. Packaged mode resolves the backend next to the exported
application. Outputs are written to the user's Godot data directory in packaged
mode and remain ordinary CSV, JSON, PNG and JSONL files.

Windows release files are named `FlySwarm-<version>-windows-x64-setup.exe`,
`FlySwarm-<version>-windows-x64.zip` and `SHA256SUMS-windows.txt`.
