"""Create a compact, auditable student practical ZIP from existing outputs."""
from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

RESULT_SUFFIXES={".csv",".json",".jsonl",".png",".zip",".log",".py"}
SKIP_NAMES={"cancel","pause","progress.json"}


def export_practical(workspace: Path, sessions_root: Path, destination: Path) -> dict:
    workspace=Path(workspace).expanduser().resolve()
    sessions_root=Path(sessions_root).expanduser().resolve()
    destination=Path(destination).expanduser().resolve()
    destination.parent.mkdir(parents=True,exist_ok=True)
    included=[]
    for source_name in ("agent.py","reward.py"):
        source=workspace/source_name
        if source.is_file():included.append((source,f"FlySwarm_Practical/{source_name}"))
    sessions=[]
    if sessions_root.is_dir():
        for session in sorted(sessions_root.iterdir(),key=lambda p:p.name):
            if not session.is_dir() or not (session/"manifest.json").is_file():continue
            try:manifest=json.loads((session/"manifest.json").read_text(encoding="utf-8"))
            except (OSError,json.JSONDecodeError):continue
            if manifest.get("kind") in {"student_code_check","practical_export"}:continue
            sessions.append({"id":session.name,"manifest":manifest})
            for path in sorted(session.rglob("*")):
                if not path.is_file() or path.is_symlink() or path.name in SKIP_NAMES or path.name.startswith("._"):continue
                if path.suffix.lower() not in RESULT_SUFFIXES:continue
                if any(part in {"__pycache__","research","data"} for part in path.parts):continue
                relative=path.relative_to(session)
                included.append((path,f"FlySwarm_Practical/results/{session.name}/{relative.as_posix()}"))
    config={"exported_utc":datetime.now(timezone.utc).isoformat(),"sessions":[x["id"] for x in sessions]}
    manifest={"schema":"flyswarm.practical-export.v1","sessions":sessions,
              "included_files":[],"excluded":"MaleCNS data, research archives and unrelated user files"}
    with zipfile.ZipFile(destination,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        archive.writestr("FlySwarm_Practical/experiment_config.json",json.dumps(config,indent=2)+"\n")
        for source,archive_path in included:
            archive.write(source,archive_path)
            manifest["included_files"].append({"path":archive_path,"size":source.stat().st_size,
                "sha256":hashlib.sha256(source.read_bytes()).hexdigest()})
        archive.writestr("FlySwarm_Practical/manifest.json",json.dumps(manifest,indent=2,allow_nan=False)+"\n")
    return {"archive":str(destination),"included_files":len(included),
            "sessions":len(sessions),"bytes":destination.stat().st_size}
