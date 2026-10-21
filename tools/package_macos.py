"""Build the complete arm64 macOS app, drag-and-drop DMG, ZIP and checksums."""

from __future__ import annotations

import argparse
import importlib.metadata
import os
import plistlib
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GODOT = Path.home() / "Applications/Godot.app/Contents/MacOS/Godot"
VERSION_DEFAULT = "0.2.0-beta.1"


def run(args: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)


def thin_arm64(path: Path) -> None:
    description = subprocess.run(["file", "-b", str(path)], check=True, capture_output=True, text=True).stdout
    if "Mach-O" not in description:
        return
    result = subprocess.run(["lipo", "-archs", str(path)], check=True, capture_output=True, text=True)
    architectures = result.stdout.split()
    if "arm64" not in architectures:
        raise RuntimeError(f"Native file is not arm64: {path}: {architectures}")
    if len(architectures) > 1:
        thin = path.with_name(path.name + ".arm64")
        run(["lipo", str(path), "-thin", "arm64", "-output", str(thin)])
        # lipo creates the output with regular-file permissions; preserve the
        # executable bit (and any other mode bits) from the original bundle file.
        thin.chmod(stat.S_IMODE(path.stat().st_mode))
        thin.replace(path)


def make_arm64(app: Path) -> None:
    candidates = [
        app / "Contents/MacOS/FlySwarm",
        app / "Contents/Resources/backend/FlySwarmBackend/FlySwarmBackend",
    ]
    for folder, _dirs, files in os.walk(app):
        for name in files:
            path = Path(folder) / name
            if path.suffix in {".dylib", ".so", ".bundle"}:
                if path not in candidates:
                    candidates.append(path)
    for candidate in candidates:
        if candidate.is_file():
            thin_arm64(candidate)
    # zipfile extraction does not restore Unix permissions from the Godot
    # export archive, so set both launched entry points executable explicitly.
    for launcher in candidates[:2]:
        if launcher.is_file():
            launcher.chmod(0o755)


def remove_macos_metadata(root: Path) -> None:
    for folder, dirs, files in os.walk(root, topdown=False):
        for name in files:
            if name == ".DS_Store" or name.startswith("._"):
                (Path(folder) / name).unlink(missing_ok=True)
        for name in dirs:
            if name == ".DS_Store" or name.startswith("._"):
                shutil.rmtree(Path(folder) / name, ignore_errors=True)


def add_third_party_licenses(destination: Path) -> None:
    packages = ["flybrain", "numpy", "scipy", "numba", "llvmlite", "pettingzoo", "gymnasium", "stable-baselines3", "torch", "matplotlib"]
    sections: list[str] = []
    for package in packages:
        distribution = importlib.metadata.distribution(package)
        sections.append(f"{package} {distribution.version}")
        license_files = []
        for relative in distribution.files or []:
            name = Path(str(relative)).name.lower()
            if any(marker in name for marker in ("license", "copying", "notice")):
                candidate = Path(distribution.locate_file(relative))
                if candidate.is_file() and candidate.stat().st_size < 2_000_000:
                    license_files.append(candidate)
        if not license_files:
            sections.append("No standalone license file was present in the installed distribution.")
        for license_path in sorted(set(license_files)):
            sections.append(f"--- {license_path.name} ---\n{license_path.read_text(errors='replace')}")
    (destination / "THIRD_PARTY_LICENSES.txt").write_text("\n\n".join(sections), encoding="utf-8")


def add_malecns_dataset(source: Path, resources: Path) -> None:
    """Bundle the validated MaleCNS runtime data with its required attribution."""
    from flybrain.data import FILES
    import hashlib

    source = source.expanduser().resolve()
    dataset = resources / "MaleCNS"
    dataset.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        path = source / name
        if not path.is_file():
            raise RuntimeError(f"MaleCNS dataset file is missing: {path}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1 << 20), b""):
                digest.update(block)
        if digest.hexdigest() != expected:
            raise RuntimeError(f"MaleCNS dataset checksum does not match FlyBrain: {path}")
        shutil.copy2(path, dataset / name)
    notice = """MaleCNS v1.0 connectome data notice

The bundled brain.npz and weights.npz are prebuilt derived runtime files for
the MaleCNS v1.0 connectome. The dataset is from FlyEM at HHMI Janelia, in
collaboration with the University of Cambridge, the MRC Laboratory of Molecular
Biology, and Google Research.

Source and dataset information: https://male-cns.janelia.org/download/
License: Creative Commons Attribution 4.0 International (CC BY 4.0)
License text: https://creativecommons.org/licenses/by/4.0/
Scientific reference: Berg et al., Sexual dimorphism in the complete connectome
of the Drosophila male central nervous system, Cell (2026).

The two prebuilt files are distributed by the FlyBrain package and are derived
from the CC BY 4.0 connectome. FlyBrain documents these derived files as covered
by the source dataset's CC BY 4.0 terms:
https://github.com/alextitonis/fly.ai

The bundled data files are unchanged. Their SHA-256 checksums are validated by
FlyBrain and by FlySwarm before the neural backend starts.
"""
    (resources / "MALECNS_DATA_NOTICE.txt").write_text(notice, encoding="utf-8")


def build_backend(python: Path, build_root: Path, output: Path) -> Path:
    dist = output / "FlySwarmBackend"
    shutil.rmtree(dist, ignore_errors=True)
    work = build_root / "pyinstaller-work"
    specs = build_root / "pyinstaller-spec"
    for path in (work, specs):
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True)
    command = [
        str(python), "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
        "--name", "FlySwarmBackend", "--distpath", str(output), "--workpath", str(work),
        "--specpath", str(specs), "--paths", str(ROOT / "src"),
        "--collect-all", "flybrain", "--collect-all", "pettingzoo", "--collect-all", "gymnasium",
        "--collect-all", "stable_baselines3", "--collect-binaries", "torch", "--collect-all", "matplotlib",
        "--collect-binaries", "llvmlite",
        "--exclude-module", "pygame",
        "--collect-binaries", "scipy", "--hidden-import", "flybrain.brain",
        "--hidden-import", "flybrain.data", "--hidden-import", "flyswarm.marl.cli",
        str(ROOT / "tools/packaged_backend.py"),
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    print("Building relocatable Python runtime with PyInstaller (onedir).", flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    executable = dist / "FlySwarmBackend"
    if not executable.is_file():
        raise RuntimeError(f"PyInstaller executable missing: {executable}")
    # Collect Torch's native runtime libraries without its package data. The
    # full package collector stages multi-gigabyte C/C++ headers and test
    # fixtures that this precompiled CPU application never uses. PyInstaller's
    # normal module analysis still follows the imported Python runtime modules.
    return dist


def update_plist(app: Path, version: str) -> None:
    plist_path = app / "Contents/Info.plist"
    with plist_path.open("rb") as source:
        info = plistlib.load(source)
    info["CFBundleDisplayName"] = "FlySwarm"
    info["CFBundleName"] = "FlySwarm"
    info["CFBundleIdentifier"] = "org.flyswarm.connectome"
    info["CFBundleShortVersionString"] = version
    info["CFBundleVersion"] = version.split("-")[0]
    info["LSArchitecturePriority"] = ["arm64"]
    info["LSMinimumSystemVersion"] = "13.0"
    info["NSHighResolutionCapable"] = True
    with plist_path.open("wb") as destination:
        plistlib.dump(info, destination, sort_keys=False)


def package(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    if sys_platform() != "darwin":
        raise RuntimeError("The native macOS package must be built on macOS.")
    if os.uname().machine != "arm64":
        raise RuntimeError("Build this release on an Apple Silicon host so bundled native libraries are arm64.")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", args.version):
        raise RuntimeError(f"Invalid SemVer version: {args.version}")
    godot = Path(args.godot).expanduser().resolve()
    # Keep the venv launcher symlink intact: resolving it points at the base
    # Homebrew interpreter and drops the virtualenv's site-packages.
    python = Path(os.path.abspath(Path(args.python).expanduser()))
    if not godot.is_file():
        raise RuntimeError(f"Godot executable not found: {godot}")
    if not python.is_file():
        raise RuntimeError(f"Python environment not found: {python}")
    output = Path(args.output).expanduser().resolve() / args.version
    output.mkdir(parents=True, exist_ok=True)
    # Keep large PyInstaller, Godot staging, DMG and ZIP intermediates on the
    # local APFS temp volume. The project may live on a slower removable
    # filesystem (for example ExFAT); staging multi-gigabyte app copies there
    # repeatedly triggers indexing and security scans and makes the machine
    # sluggish. The caller can copy the finished release artifacts to the
    # project volume once packaging and validation succeed.
    build_root = Path(tempfile.mkdtemp(prefix=f"flyswarm-package-work-{args.version}-"))

    backend_dist = output / "FlySwarmBackend"
    if not args.reuse_backend or not (backend_dist / "FlySwarmBackend").is_file():
        backend_dist = build_backend(python, build_root, output)
    # The frozen catalog resolves checked-in vehicle and ammunition JSON next
    # to the onedir executable. Include these small public definitions, but
    # never copy local research data or results into the app.
    backend_data = backend_dist / "data"
    shutil.rmtree(backend_data, ignore_errors=True)
    shutil.copytree(ROOT / "data", backend_data, ignore=shutil.ignore_patterns("local", "._*"))
    stage_root = Path(tempfile.mkdtemp(prefix="flyswarm-godot-stage-"))
    try:
        project = stage_root / "godot"
        shutil.copytree(ROOT / "frontend/godot", project, ignore=shutil.ignore_patterns(".godot", "._*"))
        shutil.copytree(ROOT / "data", project / "data", ignore=shutil.ignore_patterns("local", "._*"))
        run([godot, "--headless", "--editor", "--path", project, "--import"])
        frontend_zip = build_root / "FlySwarm-frontend.zip"
        run([godot, "--headless", "--path", project, "--export-release", "macOS Local Frontend", frontend_zip])
        exported = build_root / "exported"
        exported.mkdir()
        with zipfile.ZipFile(frontend_zip) as archive:
            archive.extractall(exported)
        apps = [path for path in exported.glob("*.app") if not path.name.startswith("._")]
        if len(apps) != 1:
            raise RuntimeError(f"Expected one exported app bundle, found {apps}")
        app = output / "FlySwarm.app"
        shutil.rmtree(app, ignore_errors=True)
        shutil.move(str(apps[0]), app)
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)

    resources = app / "Contents/Resources"
    shutil.rmtree(resources / "backend", ignore_errors=True)
    (resources / "backend").mkdir()
    shutil.copytree(backend_dist, resources / "backend/FlySwarmBackend", symlinks=True)
    support = resources / "support"
    shutil.copytree(ROOT / "src", support / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (support / "tools").mkdir(parents=True)
    shutil.copy2(ROOT / "tools/app_job.py", support / "tools/app_job.py")
    add_third_party_licenses(resources)
    if args.dataset:
        add_malecns_dataset(Path(args.dataset), resources)
    shutil.copy2(ROOT / "docs/macos_packaging.md", resources / "INSTALLATION.txt")
    update_plist(app, args.version)
    remove_macos_metadata(app)
    make_arm64(app)
    remove_macos_metadata(app)
    subprocess.run(["xattr", "-cr", app], check=True)
    run(["codesign", "--force", "--deep", "--sign", "-", app])
    remove_macos_metadata(app)
    run(["codesign", "--verify", "--deep", "--strict", app])

    dmg_path = output / f"FlySwarm-{args.version}-macos-arm64.dmg"
    zip_path = output / f"FlySwarm-{args.version}-macos-arm64.zip"
    checksum_path = output / "SHA256SUMS.txt"
    disk_contents = build_root / "dmg"
    disk_contents.mkdir()
    shutil.copytree(app, disk_contents / "FlySwarm.app", symlinks=True)
    (disk_contents / "Applications").symlink_to("/Applications")
    remove_macos_metadata(disk_contents)
    run(["hdiutil", "create", "-ov", "-format", "UDZO", "-imagekey", "zlib-level=9", "-volname", "FlySwarm", "-srcfolder", disk_contents, dmg_path])
    run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app, zip_path])
    with zipfile.ZipFile(zip_path) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"ZIP integrity check failed at {bad}")
    run(["hdiutil", "verify", dmg_path])
    import hashlib

    checksum_lines = []
    for artifact in (dmg_path, zip_path):
        digest = hashlib.sha256()
        with artifact.open("rb") as source:
            for block in iter(lambda: source.read(1 << 20), b""):
                digest.update(block)
        checksum_lines.append(f"{digest.hexdigest()}  {artifact.name}")
    checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    return app, dmg_path, zip_path


def sys_platform() -> str:
    import sys

    return sys.platform


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="Build the complete arm64 application and installers")
    parser.add_argument("--godot", default=str(DEFAULT_GODOT))
    parser.add_argument("--python", default=str(ROOT / ".venv/bin/python"))
    parser.add_argument("--version", default=VERSION_DEFAULT)
    parser.add_argument("--output", default=str(ROOT / "build/releases"))
    parser.add_argument("--reuse-backend", action="store_true", help="Reuse an already-built backend in this version's output directory")
    parser.add_argument("--dataset", help="Bundle a MaleCNS data folder after validating the official FlyBrain SHA-256 checksums")
    args = parser.parse_args()
    if not args.build:
        parser.error("Use --build; frontend-only exports are not distributable releases.")
    app, dmg, archive = package(args)
    print(f"APP {app}")
    print(f"DMG {dmg}")
    print(f"ZIP {archive}")
    print(f"SHA256 {dmg.parent / 'SHA256SUMS.txt'}")


if __name__ == "__main__":
    main()
