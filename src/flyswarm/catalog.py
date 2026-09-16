"""Data definitions shared by research tools; Godot owns world dynamics."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'data'

def vehicle(identifier):
    paths=[p for p in (DATA/'vehicles').glob(f'*/{identifier}.json') if not p.name.startswith('._')]
    if len(paths)!=1: raise ValueError(f'Unknown vehicle: {identifier}')
    obj=json.loads(paths[0].read_text())
    params=obj['parameters']
    for key in params:
        if key not in obj['provenance']: raise ValueError(f'Missing provenance: {key}')
    for key in ['mass_kg','engine_kw','max_speed_kph','reload_s']:
        if params[key]<=0:raise ValueError(key)
    return obj

def ammunition(identifier):
    obj=json.loads((DATA/'ammunition'/f'{identifier}.json').read_text())
    curve=obj['penetration_mm']
    if len(curve)<2 or any(a[0]>=b[0] for a,b in zip(curve,curve[1:])):raise ValueError('Curve must be sorted')
    return obj
