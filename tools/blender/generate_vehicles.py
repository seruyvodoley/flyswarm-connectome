"""Intermediate recognition models; component dimensions remain provisional. Blender --background --python this_file.
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

def cyl(name,loc,r,depth,material,parent=None,axis='Z',vertices=32):
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

def cast_turret(name,parent,wide,long,roof):
 # Ring-built cast shell: broad cheeks, tapering roof and rear bustle.
 verts=[];faces=[];n=40
 for z,scale,shift in [(0,.80,0),(.18,1,0),(.55,.97,.08),(roof,.72,.16)]:
  for i in range(n):
   a=2*math.pi*i/n
   verts.append((wide*scale*math.cos(a),long*scale*math.sin(a)+shift,z))
 for k in range(3):
  for i in range(n):a=k*n+i;b=k*n+(i+1)%n;faces.append((a,b,b+n,a+n))
 faces += [tuple(reversed(range(n))),tuple(range(3*n,4*n))]
 mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
 o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o);finish(o,name,body,parent)
 for f in mesh.polygons:f.use_smooth=len(f.vertices)==4
 return o

def track_loop(x,l,radius,root):
 # Straight ground contact, rounded ends, lightly sagging upper return.
 end=l*.36;z=radius+.13;r=radius+.06
 points=[]
 for j in range(24):points.append((-end+2*end*j/24,.07))
 for j in range(18):
  a=-math.pi/2+math.pi*j/18;points.append((end+r*math.cos(a),z+r*math.sin(a)))
 for j in range(24):
  t=j/24;points.append((end-2*end*t,z+r-.07*math.sin(math.pi*t)))
 for j in range(18):
  a=math.pi/2+math.pi*j/18;points.append((-end+r*math.cos(a),z+r*math.sin(a)))
 for i,(y,h) in enumerate(points):
  yy,hh=points[(i+1)%len(points)];pitch=math.hypot(yy-y,hh-h)
  o=box('TrackShoe',(x,(y+yy)/2,(h+hh)/2),(.58,pitch*.96,.07),dark,root)
  o.rotation_euler.x=math.atan2(hh-h,yy-y)
  o=box('TrackCleat',(x,(y+yy)/2,(h+hh)/2-.035),(.60,.035,.035),metal,root);o.rotation_euler.x=math.atan2(hh-h,yy-y)

for p in sorted((ROOT/'data/vehicles').glob('*/*.json')):
 if p.name.startswith('._'):continue
 d=json.loads(p.read_text());v=d['parameters'];id=d['id']
 if id=='tiger_i':continue # Dedicated source: build_tiger_late.py; never overwrite with a generic model.
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 body=mat('paint',(.38,.37,.22) if d['nation']=='germany' else (.22,.29,.16))
 dark=mat('track steel',(.09,.105,.095));rubber=mat('rubber',(.045,.05,.043));metal=mat('steel',(.24,.25,.22));light=mat('hatch',(.42,.43,.31))
 root=empty('VehicleModel',(0,0,0));w=v['width_m'];l=v['length_m'];german=d['nation']=='germany'
 wedge('LowerHull',(0,0,.4),(w-1,l-.6),(w-.75,l-.4),.70,body,root)
 wedge('SlopedUpperHull',(0,0,1.05),(w-.35,l),(w-.8,l-1.65),.82 if id!='is2_1944' else .70,body,root)
 count=8 if german else (6 if id=='is2_1944' else 5)
 radius=.43 if german else (.35 if id=='is2_1944' else .415)
 for side in [-1,1]:
  x=side*(w/2-.29);z=radius+.13
  box('Fender',(x,0,1.38),(.65,l+.05,.055),body,root)
  for j in range(count):
   y=-l*.30+j*l*.60/(count-1)
   wx=x+side*(.075 if j%2 else -.075) if german else x
   cyl('Wheel',(wx,y,z),radius,.26,rubber,root,'X')
   cyl('WheelDish',(wx+side*.145,y,z),radius*.83,.045,body,root,'X')
   cyl('WheelHub',(wx+side*.19,y,z),radius*.26,.09,metal,root,'X')
   for k in range(8):
    a=k*math.pi/4;cyl('WheelBolt',(wx+side*.18,y+radius*.52*math.cos(a),z+radius*.52*math.sin(a)),.022,.02,metal,root,'X',8)
  for sy in [-1,1]:
   cyl('DriveSprocket' if sy<0 else 'Idler',(x,sy*l*.36,z),radius*.87,.28,metal,root,'X')
   cyl('EndHub',(x+side*.16,sy*l*.36,z),radius*.3,.08,body,root,'X')
  track_loop(x,l,radius,root)
  for j in range(10):box('EngineGrille',(side*.6,l*.29+j*.055,1.90),(.72,.026,.025),dark,root)
  cyl('CoolingFan',(side*.64,l*.23,1.9),.30,.04,dark,root)
 if v['turreted']:
  pivot=empty('TurretPivot',(0,-.45,1.88 if id!='is2_1944' else 1.76),root)
  if id=='t34_85':cast_turret('T34CastTurret',pivot,1.06,1.29,.89)
  elif id=='is2_1944':cast_turret('IS2CastTurret',pivot,1.20,1.42,.83)
  else:
   wedge('PantherWeldedTurret',(0,0,0),(2.30,2.95),(1.70,2.28),.88,body,pivot)
   box('RearTurretHatch',(0,1.43,.40),(.62,.045,.49),body,pivot)
  cyl('Cupola',(-.58,.44,.94),.31,.22,body,pivot)
  cyl('CupolaHatch',(-.58,.44,1.06),.29,.035,light,pivot)
  box('LoaderHatch',(.46,.35,.91),(.48,.54,.04),body,pivot)
  for k in range(6):
   a=k*math.pi/3;box('CupolaPeriscope',(-.58+.28*math.cos(a),.44+.28*math.sin(a),1.01),(.085,.075,.08),dark,pivot)
  gun=empty('GunElevationPivot',(0,-1.16,.43),pivot)
 else:
  # Jagdpanther: tall integrated sloping fighting compartment; SU: lower forward casemate.
  tall=id=='jagdpanther';height=1.22 if tall else 1.02
  wedge('IntegratedCasemate',(0,-.56,1.2),(w-.32,l*.76),(w-1.03,l*.53),height,body,root)
  if not tall:cyl('SUCommanderCupola',(.85,-.1,2.33),.33,.25,body,root)
  else:
   for side in [-1,1]:box('RoofHatch',(side*.53,-.3,2.44),(.53,.60,.035),body,root)
  pivot=empty('TurretPivot',(.23 if not tall else .10,-l*.28,1.98),root)
  gun=empty('GunElevationPivot',(0,0,0),pivot)
 gunlen={'panther_g':3.6,'jagdpanther':4.8,'t34_85':2.8,'is2_1944':3.8,'su100':4.1}[id]
 if id=='panther_g':cyl('CurvedMantlet',(0,-.12,0),.36,1.24,body,gun,'X')
 elif id in ['jagdpanther','su100']:
  bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,location=(0,-.13,0));o=bpy.context.object;o.scale=(.43,.50,.39);finish(o,'CastGunMantlet',body,gun)
 else:box('GunShield',(0,-.1,0),(.93,.32,.54),body,gun)
 cyl('BarrelCollar',(0,-.40,0),.16,.65,body,gun,'Y')
 cyl('Gun',(0,-gunlen/2,0),.075 if id!='is2_1944' else .105,gunlen,body,gun,'Y')
 if id in ['panther_g','jagdpanther','is2_1944']:
  # Open two-chamber brake with real side gaps, not painted rectangles.
  for k in [0,1,2]:cyl('BrakeBaffle',(0,-gunlen-.14*k,0),.18,.045,body,gun,'Y')
  for sz in [-1,1]:box('BrakeBridge',(0,-gunlen-.14,sz*.145),(.19,.30,.055),body,gun)
  cyl('MuzzleBore',(0,-gunlen-.305,0),.075,.012,dark,gun,'Y')
  muzzle=gunlen+.32
 else:
  cyl('MuzzleBore',(0,-gunlen-.005,0),.055,.012,dark,gun,'Y');muzzle=gunlen+.02
 empty('Muzzle',(0,-muzzle,0),gun)
 for side in [-1,1]:
  if german:
   cyl('Exhaust',(side*.65,l*.44,1.60),.12,.65,dark,root)
   box('RearStowage',(side*.98,l*.43,1.50),(.48,.32,.47),body,root)
  else:
   for j in [0,1]:cyl('ExternalFuel',(side*(w/2-.12),l*(.20+j*.16),1.76),.22,.78,body,root,'Y')
  box('TowLug',(side*.69,-l*.43,.83),(.12,.22,.14),metal,root)
 cyl('Headlamp',(-.85,-l*.32,1.88),.12,.13,metal,root,'Y')
 box('DriverHatch',(-.48,-l*.24,1.89),(.58,.45,.05),body,root)
 # Merge static details by articulation group; retain wheel meshes for animation.
 for parent in [root,pivot,gun]:
  items=[o for o in list(bpy.context.scene.objects) if o.type=='MESH' and o.parent==parent and not o.name.startswith('Wheel')]
  if items:
   bpy.ops.object.select_all(action='DESELECT')
   for o in items:o.select_set(True)
   bpy.context.view_layer.objects.active=items[0];bpy.ops.object.join();items[0].name=parent.name+'Geometry'
 bpy.ops.object.select_all(action='SELECT')
 bpy.ops.export_scene.gltf(filepath=str(OUT/(id+'.glb')),export_format='GLB',export_yup=True)
 print('EXPORTED',id)
