from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "package_windows.py"
SPEC = importlib.util.spec_from_file_location("package_windows", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
package_windows = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package_windows)


class WindowsPackagingPathTests(unittest.TestCase):
    def test_pyinstaller_uses_ascii_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as ascii_temp:
            expected = Path(ascii_temp).resolve()
            with patch.object(package_windows.Path, "cwd", return_value=expected):
                cwd = package_windows.pyinstaller_working_directory()
            self.assertTrue(cwd.is_dir())
            self.assertEqual(cwd, expected)

    def test_godot_exports_to_ascii_staging_then_moves_to_unicode_path(self) -> None:
        with tempfile.TemporaryDirectory() as ascii_temp:
            expected = Path(ascii_temp).resolve()
            output = Path(ascii_temp) / "практическая работа" / "FlySwarm.exe"
            exported: list[Path] = []
            working_directories: list[Path] = []

            def fake_run(args: list[str], *, cwd: Path = package_windows.ROOT) -> None:
                target = Path(args[-1])
                self.assertTrue(str(target).isascii())
                self.assertTrue(str(cwd).isascii())
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"MZ test executable")
                exported.append(target)
                working_directories.append(cwd)

            with patch.object(package_windows.tempfile, "gettempdir", return_value=ascii_temp):
                with patch.object(package_windows, "run", side_effect=fake_run):
                    package_windows.export_windows_app(
                        Path("C:/Godot/Godot.exe"), Path("E:/исходники/project"), output
                    )

            self.assertEqual(len(exported), 1)
            self.assertEqual(len(working_directories), 1)
            self.assertEqual(working_directories[0].parent.resolve(), expected.resolve())
            self.assertFalse(exported[0].exists())
            self.assertEqual(output.read_bytes(), b"MZ test executable")


if __name__ == "__main__":
    unittest.main()
