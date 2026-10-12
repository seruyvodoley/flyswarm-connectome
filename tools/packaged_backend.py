"""PyInstaller entry point for the relocatable FlySwarm Python runtime."""

import runpy
import sys
from pathlib import Path

from flyswarm.bridge.server import main


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--marl":
        from flyswarm.marl.cli import main as marl_main
        raise SystemExit(marl_main(sys.argv[2:]))
    if len(sys.argv) == 3 and sys.argv[1] == "--job-config":
        job_config = str(sys.argv[2])
        job_script = Path(sys.executable).resolve().parent.parent.parent / "support/tools/app_job.py"
        sys.argv = [str(job_script), job_config]
        runpy.run_path(str(job_script), run_name="__main__")
        raise SystemExit(0)
    raise SystemExit(main() or 0)
