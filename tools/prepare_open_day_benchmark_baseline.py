"""Extract Beta 4 source fixtures for render comparisons; no checkout or clone."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'build/validation/beta4-fixtures';base.mkdir(parents=True,exist_ok=True)
def old(path):return subprocess.check_output(['git','show','1ce6bda:'+path],cwd=ROOT,text=True)
(base/'tactics.gd').write_text(old('frontend/godot/scripts/app/open_day_tactics.gd'))
(base/'arena.gd').write_text(old('frontend/godot/scripts/demo/demo_arena.gd'))
(base/'ground.gdshader').write_text(old('frontend/godot/shaders/demo_ground.gdshader'))
(base/'terrain.gd').write_text(old('frontend/godot/scripts/terrain.gd').replace('res://shaders/demo_ground.gdshader',str(base/'ground.gdshader')))
(base/'arena.tscn').write_text('[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="'+str(base/'arena.gd')+'" id="1"]\n[node name="DemoArena" type="Node3D"]\nscript = ExtResource("1")\n')
s=old('frontend/godot/scripts/battle.gd').replace('res://scripts/terrain.gd',str(base/'terrain.gd')).replace('res://scripts/app/open_day_tactics.gd',str(base/'tactics.gd')).replace('res://scenes/demo/DemoArena.tscn',str(base/'arena.tscn'))
(base/'battle.gd').write_text(s)
