"""Reference-led Tiger I primary/secondary geometry, metres. Still under validation.
See docs/references/tiger_i/modelling_pass_02.md before editing parameters.
No third-party meshes/textures. Local reference images are NOT packed/exported.
"""
import bpy,math,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'frontend/godot/assets/vehicles/tiger_i.glb'
REF=ROOT/'data/local/visual_references/tiger_i'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
def material(name,color):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*color,1)
 m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.78
 return m
paint=material('Unpainted validation steel',(.39,.41,.39));steel=material('Track steel',(.17,.18,.17));dark=material('Recesses',(.07,.08,.075))
def empty(name,at,parent=None):
 o=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(o);o.location=at;o.parent=parent;return o
root=empty('VehicleModel',(0,0,0))
def mesh(name,verts,faces,parent=root,mat=paint):
 data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.update();o=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(o);o.parent=parent;o.data.materials.append(mat);return o
def bevel(o,width=.008,segments=2):
 mod=o.modifiers.new('Restrained armour edge','BEVEL');mod.width=width;mod.segments=segments
 mod=o.modifiers.new('Area weighted normals','WEIGHTED_NORMAL');mod.keep_sharp=True
 return o
def box(name,at,size,parent=root,mat=paint,edge=.006):
 bpy.ops.mesh.primitive_cube_add(size=1);o=bpy.context.object;o.name=name;o.location=at;o.scale=size
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.parent=parent;o.data.materials.append(mat)
 if edge:bevel(o,edge)
 return o
def cyl(name,at,r,depth,parent=root,mat=paint,axis='Z',n=48):
 bpy.ops.mesh.primitive_cylinder_add(vertices=n,radius=r,depth=depth);o=bpy.context.object;o.name=name;o.location=at;o.parent=parent;o.data.materials.append(mat)
 if axis=='X':o.rotation_euler.y=math.pi/2
 if axis=='Y':o.rotation_euler.x=math.pi/2
 for f in o.data.polygons:f.use_smooth=len(f.vertices)==4
 return bevel(o,.003)
def tube_profile(name,profile,parent,axis='Y',n=64,mat=paint):
 # profile is (axial position, radius), connected lathe shell; end caps explicit.
 verts=[]
 for pos,r in profile:
  for j in range(n):
   a=j*math.tau/n
   verts.append((r*math.cos(a),pos,r*math.sin(a)) if axis=='Y' else (pos,r*math.cos(a),r*math.sin(a)))
 faces=[]
 for k in range(len(profile)-1):
  for j in range(n):faces.append((k*n+j,k*n+(j+1)%n,(k+1)*n+(j+1)%n,(k+1)*n+j))
 faces += [tuple(range(n-1,-1,-1)),tuple((len(profile)-1)*n+j for j in range(n))]
 o=mesh(name,verts,faces,parent,mat)
 for p in o.data.polygons:p.use_smooth=len(p.vertices)==4
 return o
def hull_section(name,profile,width,mat=paint):
 verts=[(side*width/2,y,z) for side in [-1,1] for y,z in profile];n=len(profile)
 faces=[tuple(range(n-1,-1,-1)),tuple(range(n,n*2))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
 return bevel(mesh(name,verts,faces,root,mat))
# Plate angles: 9-degree driver's plate, 10-degree nose deck, 25-degree lower nose.
# Longitudinal placement remains provisional; lateral section is independently sourced.
hull_section('HullLower',[(-2.48,.485),(-3.0,.80),(-3.30,1.44),(-2.32,1.61),(2.91,1.815),(2.76,.57),(2.55,.485)],1.92)
hull_section('HullUpper',[(-3.30,1.44),(-2.32,1.61),(-2.288,1.815),(2.91,1.815),(2.83,1.31),(-2.60,1.29)],3.14)
# Actual shelf/vertical sponsons, never Panther-like tapered sides.
for side in [-1,1]:
 box('Fender',(side*1.61,-.05,1.365),(.26,5.82,.035),edge=.004)
 for j in range(4):
  panel=box('FenderSegment',(side*1.66,-2.15+j*1.43,1.28),(.18,1.40,.20),edge=.004)
  panel.rotation_euler.y=side*math.radians(18)
# Two wheels per each of eight stations; steel rims, alternating axial offsets.
for side in [-1,1]:
 for station in range(8):
  y=-1.8025+station*.515
  for pair in range(2):
   offset=.085 if station%2==0 else -.075
   x=side*(1.311+offset+(pair-.5)*.165)
   wheel=empty(f'WheelAssembly_{side}_{station}_{pair}',(x,y,.475),root)
   profile=[(-.038,.22),(-.031,.32),(-.038,.39),(-.027,.400),(.027,.400),(.038,.39),(.028,.32),(.050,.16),(.045,.08)]
   tube_profile('RoadWheel',profile,wheel,'X',64)
   cyl('WheelHub',(side*.055,0,0),.115,.050,wheel,paint,'X',32)
   for j in range(12):
    a=j*math.tau/12
    cyl('RimBolt',(side*.05,.26*math.cos(a),.26*math.sin(a)),.018,.018,wheel,paint,'X',6)
 # Sprocket front, smaller idler rear; teeth actually follow the sprocket circumference.
 for kind,y,z,r in [('DriveSprocket',-2.448,.91,.43),('Idler',2.337,.94,.34)]:
  axis=empty(kind+str(side),(side*1.311,y,z),root)
  cyl(kind,(0,0,0),r,.32,axis,paint,'X',64)
  cyl('Hub',(side*.18,0,0),r*.40,.06,axis,paint,'X',32)
  for j in range(20 if kind=='DriveSprocket' else 8):
   a=j*math.tau/(20 if kind=='DriveSprocket' else 8)
   if kind=='DriveSprocket':
    tooth=box('SprocketTooth',(0,math.cos(a)*r,math.sin(a)*r),(.36,.08,.07),axis,paint,.004);tooth.rotation_euler.x=a
   else:cyl('IdlerRecess',(side*.168,math.cos(a)*r*.65,math.sin(a)*r*.65),.055,.01,axis,dark,'X',16)
 # Analytic sampled belt around actual front/rear wheels, flat ground run and slight top sag.
 path=[(1.88,.055),(-1.84,.055),(-2.78,.59)]
 for j in range(25):
  a=math.radians(-140-j*130/24);path.append((-2.448+.455*math.cos(a),.91+.455*math.sin(a)))
 for j in range(1,35):
  t=j/34;path.append((-2.448+(2.337+2.448)*t,1.365-.075*math.sin(math.pi*t)))
 for j in range(1,25):
  a=math.radians(90-j*145/24);path.append((2.337+.385*math.cos(a),.98+.385*math.sin(a)))
 path.append((1.88,.055));lengths=[0]
 for a,b in zip(path,path[1:]):lengths.append(lengths[-1]+math.dist(a,b))
 for j in range(96):
  distance=(j+.5)*lengths[-1]/96
  index=next(i for i in range(len(lengths)-1) if lengths[i+1]>=distance)
  a,b=path[index],path[index+1];t=(distance-lengths[index])/(lengths[index+1]-lengths[index]);y=a[0]+t*(b[0]-a[0]);z=a[1]+t*(b[1]-a[1]);angle=math.atan2(b[1]-a[1],b[0]-a[0])
  link=empty('TrackLink', (side*1.311,y,z),root);link.rotation_euler.x=angle
  box('LinkShoe',(0,0,0),(.725,lengths[-1]/96*.88,.04),link,steel,.002)
  box('GroundCleat',(0,0,-.028),(.69,.032,.022),link,steel,.002)
  for toothx in [-.105,.105]:box('GuideHorn',(toothx,0,.065),(.027,.065,.085),link,steel,.002)
# Characteristic asymmetrical U-shaped turret: circular rear, tangent front walls.
pivot=empty('TurretPivot',(0,-.25,1.825),root)
outline=[(-.875,-1.18)]
# Left tangent from 14.5-degree wall; rear ring radius 1.160 m.
for j in range(81):
 a=math.pi+math.radians(14.5)-j*(math.pi+math.radians(34.5))/80
 outline.append((1.16*math.cos(a),1.16*math.sin(a)))
outline.append((.765,-1.18))
verts=[]
for top in [False,True]:
 for x,y in outline:
  height=.83-max(0,-y-.325)*math.tan(math.radians(9)) if top else (max(0,-y-.8)*.20)
  verts.append((x,y,height))
n=len(outline);faces=[tuple(range(n-1,-1,-1)),tuple(range(n,n*2))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
turret=bevel(mesh('TurretArmor',verts,faces,pivot),.006)
for poly in turret.data.polygons:
 if len(poly.vertices)==4:poly.use_smooth=True
# Roof fittings are clearly separate, with restrained geometry and no camouflage.
cyl('Cupola',(-.59,.30,.925),.36,.19,pivot,paint,n=64)
cyl('CupolaHatch',(-.59,.30,1.030),.335,.04,pivot,paint,n=64)
for j in range(7):
 a=j*math.tau/7
 box('CupolaPeriscope',(-.59+.30*math.cos(a),.30+.30*math.sin(a),.982),(.11,.09,.04),pivot,dark,.003)
box('LoaderHatch',(.50,.1,.85),(.51,.60,.035),pivot,paint,.06)
# Rear turret stowage and side escape hatch from museum rear view.
box('TurretStowage',(0,1.205,.48),(1.50,.36,.59),pivot,paint,.045)
box('StowageLid',(0,1.205,.79),(1.53,.39,.035),pivot,paint,.01)
cyl('EscapeHatch',(.99,.51,.45),.255,.025,pivot,paint,'X',48)
gun=empty('GunElevationPivot',(0,-1.18,.385),pivot)
# Broad asymmetrical mantlet; exposed barrel profile and brake remain provisional.
box('Mantlet',(-.055,-.10,.03),(1.58,.30,.55),gun,paint,.10)
cyl('GunSleeve',(0,-.38,0),.185,.45,gun,paint,'Y',64)
tube_profile('KwK36Barrel',[(0,.155),(-.50,.15),(-.57,.115),(-2.0,.10),(-3.48,.081),(-3.51,.094)],gun,'Y',64)
# Rounded two-chamber brake with open side windows and hollow muzzle.
brake=tube_profile('MuzzleBrake',[(-3.45,.105),(-3.51,.17),(-3.64,.20),(-3.79,.19),(-3.91,.125),(-3.91,.045),(-3.76,.045)],gun,'Y',64)
for y in [-3.59,-3.75]:
 cutter=box('BrakeWindowCutter',(0,y,0),(.60,.075,.16),gun,paint,0)
 mod=brake.modifiers.new('Open brake chamber','BOOLEAN');mod.operation='DIFFERENCE';mod.object=cutter
 bpy.context.view_layer.objects.active=brake;bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)
empty('Muzzle',(0,-3.94,0),gun)
# Clearly visible driver visor and hull MG in the near-vertical front plate.
box('DriverVisor',(-.76,-2.333,1.685),(.52,.035,.11),root,dark,.008)
cyl('HullMGMount',(.70,-2.345,1.66),.15,.07,root,paint,'Y',48)
cyl('HullMG',(.70,-2.47,1.66),.027,.27,root,steel,'Y',24)
for side in [-1,1]:
 cyl('ExhaustGuard',(side*.54,2.965,1.21),.20,.48,root,paint,n=48)
 cyl('ExhaustStack',(side*.54,2.98,1.67),.13,.46,root,steel,n=48)
 cyl('ExhaustOutlet',(side*.54,3.04,1.95),.07,.20,root,steel,'Y',32)
 box('RearMudguard',(side*1.32,2.96,1.12),(.69,.24,.15),root,paint,.009)
 box('EnginePanel',(side*.93,1.66,1.836),(.81,1.45,.035),root,paint,.004)
 for j in range(14):box('EngineLouvre',(side*.93,1.10+j*.085,1.865),(.70,.032,.018),root,dark,.002)
 for j in [-1,1]:
  bpy.ops.mesh.primitive_torus_add(major_radius=.105,minor_radius=.025,major_segments=24,minor_segments=8,location=(side*.99,j*2.93,.92));o=bpy.context.object;o.name='TowShackle';o.parent=root;o.rotation_euler.x=math.pi/2;o.data.materials.append(steel)
# Apply modifiers and join static pieces by parent, keeping wheel articulation.
for o in list(bpy.context.scene.objects):
 if o.type=='MESH':
  bpy.context.view_layer.objects.active=o
  for mod in list(o.modifiers):
   try:bpy.ops.object.modifier_apply(modifier=mod.name)
   except RuntimeError:pass
# Merge track-link/static meshes under root to keep draw calls bounded.
for o in list(bpy.context.scene.objects):
 if o.type=='MESH' and o.parent and o.parent.name.startswith('TrackLink'):
  matrix=o.matrix_world.copy();o.parent=root;o.matrix_world=matrix
for parent in [root,pivot,gun]+[o for o in bpy.context.scene.objects if o.name.startswith(('WheelAssembly','DriveSprocket','Idler')) and o.type=='EMPTY']:
 children=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.parent==parent]
 if not children:continue
 bpy.ops.object.select_all(action='DESELECT')
 for o in children:o.select_set(True)
 bpy.context.view_layer.objects.active=children[0];bpy.ops.object.join();bpy.context.object.name='WheelGeometry' if parent.name.startswith('WheelAssembly') else parent.name+'Geometry'
# Export only the model hierarchy, excluding reference image empties.
bpy.ops.object.select_all(action='DESELECT')
for o in bpy.context.scene.objects:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT),export_format='GLB',use_selection=True,export_yup=True)
# Aligned front/top reference planes, kept local and not packed into the source.
refs=bpy.data.collections.new('Reference planes — local only');bpy.context.scene.collection.children.link(refs)
for name,file,size,location,rotation in [('FRONT','Hull-dims-1.png',3.528,(.106,-3.7,.959),(math.pi/2,0,0)),('TOP','Turret-dims-1.png',3.036,(0,-.25,3.4),(math.pi,0,0)),('HEIGHT DATUM','Overall-height-late.png',3.50,(2.2,0,1.4),(math.pi/2,0,math.pi/2))]:
 if (REF/file).exists():
  o=bpy.data.objects.new(name,None);refs.objects.link(o);o.empty_display_type='IMAGE';o.data=bpy.data.images.load(str(REF/file));o.empty_display_size=size;o.location=location;o.rotation_euler=rotation;o.color[3]=.35;o.hide_render=True
bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=1
source=ROOT/'assets/models/tiger_i_late.blend';source.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(source))
print('TIGER PASS 02 EXPORTED',OUT)
