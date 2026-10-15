"""Compatibility entry point for the current five-vehicle builder. Tiger is separate."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name("rebuild_vehicle_families.py")),run_name="__main__")
