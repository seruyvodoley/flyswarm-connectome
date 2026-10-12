"""Build FlySwarm's relocatable Windows x64 application and installer on Windows."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str], *, cwd: Path = ROOT) -> None:
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)


def licenses(destination: Path) -> None:
    names = ["flybrain", "numpy", "scipy", "numba", "llvmlite", "pettingzoo", "gymnasium", "stable-baselines3", "torch"]
    sections = []
    for package in names:
        dist = importlib.metadata.distribution(package)
        sections.append(f"{package} {dist.version}")
        for item in dist.files or []:
            if any(word in Path(str(item)).name.lower() for word in ("license", "copying", "notice")):
                path = Path(dist.locate_file(item))
                if path.is_file() and path.stat().st_size < 2_000_000:
                    sections.append(f"--- {path.name} ---\n{path.read_text(errors='replace')}")
    destination.write_text("\n\n".join(sections), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "build/windows")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("Windows packaging must run on a Windows x64 host.")
    out = args.output.resolve()
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    godot_project = ROOT / "frontend/godot"
    run([str(args.godot), "--headless", "--editor", "--path", str(godot_project), "--import"])
    run([str(args.godot), "--headless", "--path", str(godot_project), "--export-release", "Windows Desktop", str(out / "FlySwarm.exe")])

    backend_out = out / "FlySwarm/Resources/backend"
    backend_out.mkdir(parents=True)
    work = out / "pyinstaller-work"
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--name", "FlySwarmBackend",
         "--distpath", str(backend_out), "--workpath", str(work), "--specpath", str(out / "pyinstaller-spec"),
         "--paths", str(ROOT / "src"), "--collect-all", "flybrain", "--collect-all", "pettingzoo",
         "--collect-all", "gymnasium", "--collect-all", "stable_baselines3", "--collect-all", "matplotlib",
         "--collect-binaries", "llvmlite", "--collect-binaries", "scipy", "--exclude-module", "pygame",
         "--hidden-import", "flybrain.brain", "--hidden-import", "flybrain.data", "--hidden-import", "flyswarm.marl.cli",
         str(ROOT / "tools/packaged_backend.py")])
    backend_exe = backend_out / "FlySwarmBackend/FlySwarmBackend.exe"
    if not backend_exe.is_file():
        raise RuntimeError(f"PyInstaller backend missing: {backend_exe}")
    shutil.copytree(ROOT / "data", backend_out / "FlySwarmBackend/data",
                    ignore=shutil.ignore_patterns("local", "._*"))

    packaged = out / "FlySwarm"
    shutil.copytree(ROOT / "src", packaged / "Resources/support/src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (packaged / "Resources/support/tools").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "tools/app_job.py", packaged / "Resources/support/tools/app_job.py")
    shutil.copy2(ROOT / "docs/windows_packaging.md", packaged / "Resources/INSTALLATION.txt")
    licenses(packaged / "Resources/THIRD_PARTY_LICENSES.txt")
    (packaged / "VERSION.txt").write_text(args.version + "\n", encoding="utf-8")
    # The Godot executable and its embedded PCK sit side by side with Resources.
    shutil.move(str(out / "FlySwarm.exe"), packaged / "FlySwarm.exe")

    app = packaged / "FlySwarm.exe"
    run([str(app), "--headless", "--quit-after", "3"], cwd=packaged)
    smoke = out / "smoke-results"
    run([str(backend_exe), "--marl", "--output-root", str(smoke), "baseline", "--episodes", "1", "--max-steps", "16"], cwd=packaged)
    training = smoke / "ppo-training-seed-7"
    run([str(backend_exe), "--marl", "--output-root", str(smoke), "--experiment-dir", str(training),
         "train", "--steps", "64", "--seed", "7", "--max-steps", "16"], cwd=packaged)
    checkpoint = training / "checkpoint/ppo_team.zip"
    run([str(backend_exe), "--marl", "--output-root", str(smoke), "evaluate", str(checkpoint), "--episodes", "1", "--seed", "21", "--max-steps", "16"], cwd=packaged)
    run([str(backend_exe), "--marl", "--output-root", str(smoke), "compare", str(checkpoint), "--episodes", "1", "--seed", "31", "--max-steps", "16"], cwd=packaged)

    (out / "FlySwarm.iss").write_text(
        f'''[Setup]\nAppId=FlySwarm-Research-Platform\nAppName=FlySwarm\nAppVersion={args.version}\nDefaultDirName={{autopf}}\\FlySwarm\nDefaultGroupName=FlySwarm\nOutputDir={out.as_posix()}\nOutputBaseFilename=FlySwarm-{args.version}-windows-x64-setup\nArchitecturesInstallIn64BitMode=x64\nCompression=lzma2\nSolidCompression=yes\nPrivilegesRequired=lowest\n\n[Files]\nSource: "{(packaged / '*').as_posix()}"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs\n\n[Icons]\nName: "{{group}}\\FlySwarm"; Filename: "{{app}}\\FlySwarm.exe"\nName: "{{autodesktop}}\\FlySwarm"; Filename: "{{app}}\\FlySwarm.exe"; Tasks: desktopicon\n\n[Tasks]\nName: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked\n''', encoding="utf-8")
    run(["iscc", str(out / "FlySwarm.iss")])
    installer = out / f"FlySwarm-{args.version}-windows-x64-setup.exe"
    digest = hashlib.sha256(installer.read_bytes()).hexdigest()
    (out / "SHA256SUMS-windows.txt").write_text(f"{digest}  {installer.name}\n", encoding="utf-8")
    with zipfile.ZipFile(out / f"FlySwarm-{args.version}-windows-x64.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in packaged.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(out))
    print(f"WINDOWS_INSTALLER {installer}")


if __name__ == "__main__":
    main()
