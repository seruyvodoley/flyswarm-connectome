"""Blender: inspect shipped GLB, export seven neutral-grey validation views.
No historical PASS is inferred from comparing a model with its own inputs.
"""
import bpy,json,math,sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/model_validation'
strict="--strict" in sys.argv
failed=False
views={'front':(0,-18,1.5),'rear':(0,18,1.5),'left':(-18,0,1.5),'right':(18,0,1.5),'top':(0,0,22),'front_3q':(-13,-16,10),'rear_3q':(13,16,10)}
for file in sorted((ROOT/'frontend/godot/assets/vehicles').glob('*.glb')):
 if file.name.startswith('._'):continue
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 bpy.ops.import_scene.gltf(filepath=str(file))
 meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
 bpy.context.view_layer.update()
 coords=[o.matrix_world@Vector(v) for o in meshes for v in o.bound_box]
 dims=[max(p[i] for p in coords)-min(p[i] for p in coords) for i in range(3)]
 tris=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)
 grey=bpy.data.materials.new('NeutralGrey');grey.diffuse_color=(.45,.45,.45,1)
 for o in meshes:o.data.materials.clear();o.data.materials.append(grey)
 out=OUT/file.stem;out.mkdir(parents=True,exist_ok=True)
 report={'asset':file.name,'dimensions_xyz_m':dims,'triangles_lod0':tris,'lod1':None,'lod2':None,'texture_sizes':[],'status':'BLOCKOUT / HISTORICAL VALIDATION NOT PASSED','historical_tolerance_check':'NOT RUN: complete independently sourced dimension sheet absent','axis':'Blender x width, y overall length, z height incl antenna'}
 sheet=json.loads((ROOT/'docs/references'/file.stem/'dimension_sheet.json').read_text())
 targets=sheet['dimensions']
 checks={}
 for field,target in targets.items():
  if not target['verified'] or target['value'] is None:
   checks[field]={'status':'FAIL','reason':'independent variant-specific reference not verified'}
   failed=True
 for axis,field in enumerate(['overall_width','overall_length_gun_forward']):
  target=targets[field]
  if target['verified'] and target['value'] is not None:
   relative=abs(dims[axis]-target['value'])/target['value']
   checks[field]={'status':'PASS' if relative<=.03 else 'FAIL','measured_m':dims[axis],'target_m':target['value'],'relative_error':relative}
   failed=failed or relative>.03
 # Antennas are excluded from the historical roof/cupola height check.
 solid=[o for o in meshes if 'antenna' not in o.name.lower()]
 roof=max((o.matrix_world@Vector(v)).z for o in solid for v in o.bound_box)
 target=targets['height_without_antenna']
 if target['verified'] and target['value'] is not None:
  relative=abs(roof-target['value'])/target['value']
  checks['height_without_antenna']={'status':'PASS' if relative<=.03 else 'FAIL','measured_m':roof,'target_m':target['value'],'relative_error':relative}
  failed=failed or relative>.03
 report['height_without_antenna_m']=roof
 report['dimension_checks']=checks
 report['historical_tolerance_check']='FAIL / incomplete reference sheet or tolerance exceeded' if any(c['status']=='FAIL' for c in checks.values()) else 'MAJOR DIMENSIONS ONLY; component validation pending'
 (out/'dimensions.json').write_text(json.dumps(report,indent=2)+'\n')
 bpy.ops.object.camera_add();camera=bpy.context.object;bpy.context.scene.camera=camera
 camera.data.type='ORTHO';camera.data.ortho_scale=12
 scene=bpy.context.scene;scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=800;scene.render.resolution_y=600;scene.render.resolution_percentage=100
 scene.display.shading.light='STUDIO';scene.display.shading.color_type='SINGLE';scene.display.shading.single_color=(.6,.6,.6);scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True
 scene.display.shading.background_type='WORLD';scene.world.color=(.12,.12,.12)
 for name,at in views.items():
  camera.location=at;camera.rotation_euler=(Vector((0,0,1.5))-camera.location).to_track_quat('-Z','Y').to_euler()
  scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
 print('MEASURED',file.stem,json.dumps(report))

if strict and failed: raise SystemExit(2)
