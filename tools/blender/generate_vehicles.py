"""Original low-poly recognition models. Blender --background --python this_file.
Blender +Z up, -Y forward. GLB converts to Godot +Y up, +Z forward.
"""
import bpy, math, json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'frontend/godot/assets/vehicles'

def mat(name,c):
 m=bpy.data.materials.new(name);m.diffuse_color=(*c,1);m.use_nodes=True
 m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*c,1)
 m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.85
 return m

def finish(o,name,material,parent=None):
 o.name=name;o.data.materials.append(material)
 if parent: o.parent=parent
 return o

def box(name,loc,size,material,parent=None):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.scale=size
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 return finish(o,name,material,parent)

def cyl(name,loc,r,depth,material,parent=None,axis='Z',vertices=16):
 bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=depth,location=loc)
 o=bpy.context.object
 if axis=='X':o.rotation_euler[1]=math.pi/2
 if axis=='Y':o.rotation_euler[0]=math.pi/2
 return finish(o,name,material,parent)

def wedge(name,loc,bottom,top,height,material,parent=None):
 w,l=bottom;tw,tl=top
 verts=[(-w/2,-l/2,0),(w/2,-l/2,0),(w/2,l/2,0),(-w/2,l/2,0),(-tw/2,-tl/2,height),(tw/2,-tl/2,height),(tw/2,tl/2,height),(-tw/2,tl/2,height)]
 mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]);mesh.update()
 o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o);o.location=loc
 return finish(o,name,material,parent)

def empty(name,loc,parent=None):
 o=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(o);o.location=loc;o.parent=parent;return o

for p in sorted((ROOT/'data/vehicles').glob('*/*.json')):
 if p.name.startswith('._'):continue
 d=json.loads(p.read_text());v=d['parameters'];id=d['id']
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 body=mat('paint',(.38,.37,.22) if d['nation']=='germany' else (.22,.29,.16))
 dark=mat('track steel',(.09,.105,.095));rubber=mat('rubber',(.045,.05,.043));metal=mat('steel',(.24,.25,.22));light=mat('hatch',(.42,.43,.31))
 root=empty('VehicleModel',(0,0,0))
 w=v['width_m'];l=v['length_m']
 wedge('LowerHull',(0,0,.5),(w-.8,l-1),(w-.65,l-.4),.65,body,root)
 wedge('Hull',(0,0,1.05),(w-.3,l),(w-.7,l-1.4),.9,body,root)
 for side in [-1,1]:
  x=side*(w/2-.3)
  box('Fender',(x,0,1.55),(.8,l+.15,.08),body,root)
  for j in range(v['wheel_count']):
   y=-l*.36+j*l*.72/(v['wheel_count']-1)
   cyl('Wheel', (x,y,.72),.48 if v['wheel_count']<7 else .43,.32,rubber,root,'X')
   cyl('WheelHub',(x+side*.18,y,.72),.30,.08,body,root,'X')
  for j in range(56):
   a=j*2*math.pi/56
   y=math.cos(a)*(l*.43);z=.74+math.sin(a)*.61
   o=box('TrackLink',(x,y,z),(.65,.24,.10),dark,root)
   o.rotation_euler[0]=math.atan2(-math.sin(a)*l*.43,math.cos(a)*.61)
  for j in range(4):box('EngineGrille',(side*.65,l*.30+j*.12,2),(.65,.06,.035),dark,root)
 if v['turreted']:
  pivot=empty('TurretPivot',(0,-.4,1.96),root)
  if id in ['t34_85','is2_1944']:
   bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=1,location=(0,0,.35));o=bpy.context.object;o.scale=(1.30,1.45,.70);finish(o,'Turret',body,pivot)
  else: wedge('Turret',(0,0,0),(2.5,2.8),(2.05,2.15),.95,body,pivot)
  cyl('Cupola',(-.65,.45,1.02),.34,.27,body,pivot)
  cyl('CupolaHatch',(-.65,.45,1.18),.31,.035,light,pivot)
  gun=empty('GunElevationPivot',(0,-1.25,.43),pivot)
 else:
  wedge('Casemate',(0,-.8,1.8),(w-.2,l*.65),(w-1.15,l*.43),.90,body,root)
  cyl('CommanderCupola',(.65,-.1,2.8),.30,.18,body,root)
  pivot=empty('TurretPivot',(0,-l*.30,2.18),root)
  gun=empty('GunElevationPivot',(0,0,0),pivot)
 gunlen={'panther_g':3.6,'tiger_i':3.1,'jagdpanther':4.8,'t34_85':2.8,'is2_1944':3.8,'su100':4.1}[id]
 cyl('Mantlet',(0,-.12,0),.38,.50,body,gun,'Y')
 cyl('Gun',(0,-gunlen/2,0),.075 if id!='is2_1944' else .11,gunlen,body,gun,'Y')
 if id in ['panther_g','tiger_i','jagdpanther','is2_1944']:
  box('MuzzleBrake',(0,-gunlen,0),(.32,.48,.25),body,gun)
  for side in [-1,1]:box('BrakePort',(side*.164,-gunlen,0),(.01,.26,.12),dark,gun)
 empty('Muzzle',(0,-gunlen-.25,0),gun)
 for side in [-1,1]:
  cyl('Exhaust',(side*.65,l*.48,1.65),.13,.8,dark,root)
  if d['nation']=='ussr':cyl('ExternalFuel',(side*(w/2-.1),l*.26,1.85),.24,1.25,body,root,'Y')
  else:box('Stowage',(side*.9,l*.45,1.72),(.65,.35,.55),body,root)
 for j in [-1,1]:cyl('Headlamp',(j*.85,-l*.40,1.82),.13,.15,metal,root,'Y')
 cyl('Antenna',(-.8,.4,3.8),.01,2.2,dark,root)
 bpy.ops.export_scene.gltf(filepath=str(OUT/(id+'.glb')),export_format='GLB',export_yup=True)
 print('EXPORTED',id)
