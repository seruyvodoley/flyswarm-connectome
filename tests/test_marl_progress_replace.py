import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from flyswarm.marl.experiments import write_json


def test_write_json_retries_transient_windows_replace_lock(tmp_path, monkeypatch):
    target = tmp_path / "progress.json"
    target.write_text('{"old": true}\n', encoding="utf-8")
    original_replace = Path.replace
    failed_attempts = 0

    def replace_with_temporary_lock(path, destination):
        nonlocal failed_attempts
        if path.name == "progress.json.tmp" and failed_attempts < 3:
            failed_attempts += 1
            raise PermissionError(5, "temporarily locked by a concurrent reader")
        return original_replace(path, destination)

    monkeypatch.setattr(Path, "replace", replace_with_temporary_lock)

    write_json(target, {"step": 64})

    assert failed_attempts == 3
    assert json.loads(target.read_text(encoding="utf-8")) == {"step": 64}
    assert not target.with_suffix(".json.tmp").exists()
