"""Pass 03 original family-specific geometry. Blender metres; see reference audit.
Does not overwrite Tiger. Photo-interpreted component placements remain provisional.
"""
import bpy,math,json,sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'frontend/godot/assets/vehicles'
TAU=math.tau

def mat(name,c):
 m=bpy.data.materials.new(name);m.diffuse_color=(*c,1);m.use_nodes=True
 m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*c,1)
 m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.78
 return m

def empty(name,at=(0,0,0),parent=None):
 o=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(o);o.location=at;o.parent=parent;return o

def mesh(name,verts,faces,parent=None,material=None,smooth=False):
 m=bpy.data.meshes.new(name);m.from_pydata(verts,[],faces);m.update();o=bpy.data.objects.new(name,m);bpy.context.collection.objects.link(o);o.parent=parent or root;o.data.materials.append(material or paint)
 for p in m.polygons:p.use_smooth=smooth and len(p.vertices)==4
 return o

def box(name,at,size,parent=None,material=None):
 x,y,z=at;a,b,c=[v/2 for v in size]
 return mesh(name,[(x+i*a,y+j*b,z+k*c) for k in [-1,1] for j in [-1,1] for i in [-1,1]],[(0,2,3,1),(4,5,7,6),(0,1,5,4),(1,3,7,5),(3,2,6,7),(2,0,4,6)],parent,material)

def lathe(name,profile,at=(0,0,0),axis='Y',parent=None,material=None,n=48):
 v=[]
 for pos,r in profile:
  for i in range(n):
   a=i*TAU/n;p=(r*math.cos(a),pos,r*math.sin(a)) if axis=='Y' else ((pos,r*math.cos(a),r*math.sin(a)) if axis=='X' else (r*math.cos(a),r*math.sin(a),pos))
   v.append(tuple(p[j]+at[j] for j in range(3)))
 f=[]
 for k in range(len(profile)-1):
  for i in range(n):f.append((k*n+i,k*n+(i+1)%n,(k+1)*n+(i+1)%n,(k+1)*n+i))
 f += [tuple(range(n-1,-1,-1)),tuple(range((len(profile)-1)*n,len(profile)*n))]
 return mesh(name,v,f,parent,material,True)

def cyl(name,at,r,depth,axis='Z',parent=None,material=None,n=32):
 return lathe(name,[(-depth/2,r),(depth/2,r)],at,axis,parent,material,n)

def loft(name,rings,parent=None,material=None,smooth=False):
 n=len(rings[0]);v=sum(rings,[]);f=[]
 for k in range(len(rings)-1):
  for i in range(n):f.append((k*n+i,k*n+(i+1)%n,(k+1)*n+(i+1)%n,(k+1)*n+i))
 f += [tuple(range(n-1,-1,-1)),tuple(range((len(rings)-1)*n,len(rings)*n))]
 return mesh(name,v,f,parent,material,smooth)

def hull(name,stations):
 # y, bottom z, top z, lower half-width, upper half-width; independent cross-sections.
 return loft(name,[[(-wb,y,zb),(wb,y,zb),(wt,y,zt),(-wt,y,zt)] for y,zb,zt,wb,wt in stations])

def curve(name,points,r=.012,parent=None,material=None):
 c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.bevel_depth=r;c.bevel_resolution=1;c.resolution_u=1
 sp=c.splines.new('POLY');sp.points.add(len(points)-1)
 for p,v in zip(sp.points,points):p.co=(*v,1)
 o=bpy.data.objects.new(name,c);bpy.context.collection.objects.link(o);o.parent=parent or root;c.materials.append(material or steel);return o

def wheel(side,y,r,x,style,index):
 par=empty('RunningWheel', (side*x,y,r+.065),root)
 # Deep dish, rim shoulder, recessed web and central cap.
 profile=[(-.105,r*.79),(-.10,r),(-.035,r),(-.027,r*.84),(.045,r*.72),(.068,r*.29),(.1,r*.24)]
 lathe('WheelDish',profile,axis='X',parent=par,material=paint,n=48)
 if style!='steel':lathe('Tyre',[(-.105,r*.91),(-.105,r),(-.025,r),(-.025,r*.91)],axis='X',parent=par,material=rubber,n=48)
 cyl('Hub',(.085,0,0),r*.23,.075,'X',par,paint)
 for j in range(10 if style=='panther' else 6):
  a=j*TAU/(10 if style=='panther' else 6)
  cyl('HubFastener',(.077,math.cos(a)*r*.32,math.sin(a)*r*.32),.018,.026,'X',par,steel,6)
 if style=='is':
  for j in range(8):
   a=j*TAU/8;cyl('WebRecess',(.048,math.cos(a)*r*.6,math.sin(a)*r*.6),r*.1,.012,'X',par,dark,12)
 # Place disk faces outwards with mirrored local x.
 par.scale.x=side
 wheel_parents.append(par)

def running_gear(family):
 if family=='panther':r=.43;track=.66;spacing=2.61;centres=[-1.949+i*.557 for i in range(8)];ends=[(-2.58,.84,.43),(2.58,.80,.34)];count=86
 elif family=='t34':r=.415;track=.50;spacing=2.50;centres=[-1.85,-.95,-.02,.89,1.80];ends=[(-2.49,.65,.30),(2.48,.66,.32)];count=74
 else:r=.275;track=.65;spacing=2.42;centres=[-1.70,-1.02,-.34,.34,1.02,1.70];ends=[(-2.32,.63,.35),(2.39,.66,.37)];count=86
 for side in [-1,1]:
  for i,y in enumerate(centres):
   if family=='panther':
    for pair in [-1,1]:wheel(side,y,r,spacing/2+(.075 if i%2 else -.075)+pair*.09,'panther',i)
   else:wheel(side,y,r,spacing/2,family,i)
  if family=='is':
   for y in [-1.40,0,1.40]:cyl('ReturnRoller',(side*spacing/2,y,1.02),.14,.25,'X',material=steel)
  for j,(y,z,rad) in enumerate(ends):
   drive=(j==0 if family=='panther' else j==1)
   par=empty('DriveSprocket' if drive else 'Idler',(side*spacing/2,y,z),root)
   lathe('EndWheel',[(-.13,rad*.75),(-.11,rad),(.11,rad),(.13,rad*.75)],axis='X',parent=par)
   cyl('EndHub',(side*.16,0,0),rad*.3,.09,'X',par)
   for k in range(16 if drive else 8):
    a=k*TAU/(16 if drive else 8)
    if drive:box('DriveTooth',(0,math.cos(a)*rad,math.sin(a)*rad),(.29,.07,.07),par,steel)
    else:cyl('IdlerHole',(side*.135,math.cos(a)*rad*.59,math.sin(a)*rad*.59),.048,.012,'X',par,dark,16)
  # Belt follows convex end wheels and straight contact run, with upper sag.
  front,rear=ends;fy,fz,fr=front;ry,rz,rr=rear;path=[(centres[0]-.15,.025),(centres[-1]+.15,.025)]
  for i in range(19):
   a=-math.pi/2+i*math.pi/18;path.append((ry+(rr+.035)*math.cos(a),rz+(rr+.035)*math.sin(a)))
  for i in range(1,29):
   t=i/28;path.append((ry+(fy-ry)*t,rz+rr+.035+(fz+fr-rz-rr)*t-.06*math.sin(math.pi*t)))
  for i in range(1,19):
   a=math.pi/2+i*math.pi/18;path.append((fy+(fr+.035)*math.cos(a),fz+(fr+.035)*math.sin(a)))
  path.append(path[0]);lens=[0]
  for a,b in zip(path,path[1:]):lens.append(lens[-1]+math.dist(a,b))
  for j in range(count):
   distance=(j+.5)*lens[-1]/count;k=next(k for k in range(len(lens)-1) if lens[k+1]>=distance);a,b=path[k],path[k+1];t=(distance-lens[k])/(lens[k+1]-lens[k]);y=a[0]+t*(b[0]-a[0]);z=a[1]+t*(b[1]-a[1]);angle=math.atan2(b[1]-a[1],b[0]-a[0]);length=lens[-1]/count*.94
   par=empty('TrackLink',(side*spacing/2,y,z),root);par.rotation_euler.x=angle
   box('TrackShoe',(0,0,0),(track,length,.038),par,steel)
   for x in [-track*.30,0,track*.30]:box('ShoeRib',(x,0,-.026),(.028,length*.8,.023),par,steel)
   for yy in [-length*.33,length*.33]:box('CrossRib',(0,yy,-.026),(track*.9,.024,.023),par,steel)
   for x in [-.06,.06]:box('GuideHorn',(x,0,.060),(.025,.04,.09),par,steel)
 return spacing,track

def cupola(parent,x,y,z,r=.31):
 lathe('Cupola',[(z,r*.95),(z+.04,r),(z+.19,r),(z+.22,r*.9)],(x,y,0),'Z',parent)
 cyl('CupolaLid',(x,y,z+.23),r*.9,.045,parent=parent)
 for i in range(7):
  a=i*TAU/7;box('Periscope',(x+(r-.015)*math.cos(a),y+(r-.015)*math.sin(a),z+.14),(.085,.085,.06),parent,dark)
 curve('HatchHandle',[(x-.08,y,z+.26),(x-.08,y,z+.31),(x+.08,y,z+.31),(x+.08,y,z+.26)],.015,parent)

def cast_turret(kind,parent):
 # Different measured-photo profiles, not a scaled sphere; narrower gun cheeks,
 # widest shoulder near ring, full bustle, flattened crown.
 if kind=='t34':stations=[(0,.86,1.18,.08),(.13,1.03,1.42,.12),(.34,1.08,1.40,.13),(.73,.99,1.27,.22),(.89,.78,1.04,.22)]
 else:stations=[(0,.90,1.25,.12),(.16,1.10,1.53,.17),(.42,1.12,1.52,.17),(.79,.98,1.31,.23),(.96,.75,1.07,.27)]
 rings=[];n=48
 for z,w,l,shift in stations:
  ring=[]
  for i in range(n):
   a=TAU*i/n;x=w*math.cos(a);y=l*math.sin(a)+shift
   if y<-.45:x*=.78 if kind=='t34' else .88
   ring.append((x,y,z))
  rings.append(ring)
 o=loft('CastTurret_'+kind,rings,parent,smooth=True)
 mod=o.modifiers.new('Cast contour subdivision','SUBSURF');mod.levels=1
 cupola(parent,-.52,.51,.90 if kind=='t34' else .97,.30)
 cyl('LoaderHatch',(.42,.48,.92 if kind=='t34' else .98),.26,.04,parent=parent)
 for side in [-1,1]:
  curve('TurretGrabRail',[(side*1.02,.0,.49),(side*1.13,.0,.52),(side*1.13,.65,.52),(side*1.02,.65,.49)],.018,parent)
  cyl('PistolPort',(side*1.02,.10,.48),.07,.05,'X',parent)
 for y in [.76,1.08]:cyl('Ventilator',(0,y,.92),.12,.09,parent=parent)
 return o

def gun_model(id,parent):
 # Collars/tapers are separate gun family profiles. Muzzle length from chosen envelope.
 gunlen={'panther_g':3.45,'jagdpanther':4.17,'t34_85':2.64,'is2_1944':3.65,'su100':3.90}[id]
 caliber={'panther_g':.075,'jagdpanther':.088,'t34_85':.085,'is2_1944':.122,'su100':.100}[id]
 if id=='panther_g':
  lathe('WalzenMantlet',[(-.72,.31),(-.60,.40),(.60,.40),(.72,.31)],(0,-.13,0),'X',parent)
  box('MantletChin',(0,-.22,-.30),(1.20,.29,.18),parent)
 elif id in ['jagdpanther','su100']:
  lathe('CastSaukopf',[(-.72,.18),(-.62,.24),(-.39,.43),(-.08,.55),(.12,.51)],axis='Y',parent=parent,n=64)
  for side in [-1,1]:cyl('MantletFastener',(side*.30,-.46,.18),.035,.035,'Y',parent,steel,8)
 else:
  lathe('CastGunShield',[(-.34,.34),(-.23,.42),(.16,.44)],axis='Y',parent=parent,n=48)
  if id=='is2_1944':box('HeavyMantletFlange',(0,.05,0),(1.02,.16,.73),parent)
  for side in [-1,1]:cyl('ShieldFastener',(side*.28,-.33,.20),.026,.035,'Y',parent,steel,8)
 r=caliber*.88
 lathe('Barrel',[(-.20,.145 if id!='is2_1944' else .20),(-.85,.14 if id!='is2_1944' else .19),(-.87,r*1.25),(-gunlen+.25,r),(-gunlen,r*.85)],axis='Y',parent=parent,n=48)
 if id in ['panther_g','jagdpanther','is2_1944']:
  radius=.16 if id!='is2_1944' else .22
  for i in range(3):lathe('BrakeBaffle',[(-gunlen-i*.16,radius),(-gunlen-i*.16-.045,radius*.97)],axis='Y',parent=parent,n=40)
  for z in [-radius*.8,radius*.8]:box('BrakeBridge',(0,-gunlen-.17,z),(radius*1.3,.34,.05),parent)
  muzzle=gunlen+.37
 else:muzzle=gunlen+.015
 cyl('Bore',(0,-muzzle,0),caliber*.5,.012,'Y',parent,dark)
 empty('Muzzle',(0,-muzzle-.015,0),parent)

def deck(family,length,deck_z):
 for side in [-1,1]:
  if family=='panther':
   cyl('CoolingFanGrille',(side*.64,2.06,deck_z+.015),.39,.04,material=dark)
   for j in range(12):box('FanGuard',(side*.64-.35+j*.064,2.06,deck_z+.041),(.022,.66,.014),material=paint)
   for yy in [1.40,2.70]:
    box('LouvreFrame',(side*.60,yy,deck_z+.02),(.88,.43,.03))
    for j in range(8):box('AirLouvre',(side*.60,yy-.18+j*.05,deck_z+.044),(.80,.022,.018),material=dark)
  else:
   for j in range(17):box('EngineLouvre',(side*.55,1.60+j*.053,deck_z+.035),(.82,.025,.025),material=dark)
  curve('TowCable',[(side*1.17,-1.5,deck_z-.10),(side*1.32,-.6,deck_z-.03),(side*1.32,.6,deck_z-.03),(side*1.17,1.25,deck_z-.06)],.024)
  if family!='panther':
   # Three external cylinders total, brackets follow the hull, no turret attachment.
   for yy in ([1.55,2.43] if side==1 else [2.05]):
    cyl('FuelDrum',(side*1.28,yy,deck_z+.20),.215,.78,'Y')
    for off in [-.27,.27]:
     lathe('FuelStrap',[(-.022,.222),(.022,.222)],(side*1.28,yy+off,deck_z+.20),'Y',material=steel,n=32)
  else:
   box('RearBin',(side*.99,length/2-.10,1.30),(.53,.32,.66))
   cyl('ExhaustGuard',(side*.47,length/2+.025,1.11),.20,.45)
   cyl('ExhaustPipe',(side*.47,length/2+.07,1.57),.085,.55,material=dark)
 if family!='panther':
  for side in [-1,1]:cyl('RearExhaust',(side*.70,length/2-.03,1.35),.135,.28,'Y',material=dark)
 box('EngineAccessPanel',(0,1.38,deck_z+.012),(.67,.95,.025))

SPECS={
 'panther_g':dict(family='panther',length=6.87,deck=1.89),
 'jagdpanther':dict(family='panther',length=6.87,deck=1.89),
 't34_85':dict(family='t34',length=6.10,deck=1.69),
 'is2_1944':dict(family='is',length=6.77,deck=1.70),
 'su100':dict(family='t34',length=6.10,deck=1.69)}
for id,cfg in SPECS.items():
 if '--vehicle' in sys.argv and id!=sys.argv[sys.argv.index('--vehicle')+1]:continue
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 paint=mat('Neutral armour steel',(.36,.39,.36));steel=mat('Track steel',(.17,.19,.18));dark=mat('Mechanical recess',(.065,.075,.07));rubber=mat('Rubber tyre',(.075,.082,.075))
 root=empty('VehicleModel');wheel_parents=[];family=cfg['family'];l=cfg['length'];deck_z=cfg['deck']
 if family=='panther':
  hull('PantherLowerHull',[(-3.24,.92,.96,.92,.92),(-2.69,.48,1.23,.92,.92),(2.93,.48,1.23,.92,.92),(3.25,1.02,1.06,.92,.92)])
  if id=='panther_g':hull('AusfGUpperHull',[(-3.24,.96,.98,1.49,1.49),(-1.93,1.09,1.89,1.49,1.14),(3.20,1.12,1.89,1.49,1.14),(3.31,1.16,1.18,1.47,1.47)])
  else:
   hull('ContinuousJagdpantherCasemate',[(-3.24,.96,.98,1.49,1.49),(-1.06,1.11,2.49,1.49,1.00),(1.43,1.11,2.49,1.49,1.00),(2.10,1.11,1.90,1.49,1.15),(3.26,1.14,1.88,1.48,1.14)])
 elif family=='t34':
  hull('T34LowerHull',[(-3.03,.95,.97,1.10,1.10),(-2.45,.40,1.04,1.0,1.13),(2.55,.40,1.05,1.0,1.13),(3.02,1.25,1.29,1.1,1.1)])
  if id=='t34_85':hull('T34RakedHull',[(-3.03,.96,.98,1.38,1.38),(-1.75,1.05,1.69,1.40,1.03),(2.58,1.07,1.69,1.40,1.04),(3.02,1.27,1.30,1.34,1.31)])
  else:hull('SU100ContinuousCasemate',[(-3.03,.96,.98,1.38,1.38),(-1.48,1.04,2.17,1.40,1.01),(.86,1.05,2.17,1.40,1.01),(1.18,1.05,1.69,1.40,1.03),(2.58,1.07,1.69,1.40,1.04),(3.02,1.27,1.30,1.34,1.31)])
 else:
  hull('IS2LowerHull',[(-3.32,.97,1.02,.79,.91),(-2.70,.42,1.07,.89,1.03),(2.68,.42,1.08,.89,1.03),(3.33,1.1,1.2,.94,1.09)])
  hull('IS2StraightenedGlacis',[(-3.32,1.0,1.02,.91,1.12),(-2.04,1.02,1.72,1.24,1.00),(-1.07,1.03,1.91,1.33,.98),(.82,1.03,1.91,1.33,1.05),(1.23,1.03,1.70,1.33,1.13),(3.33,1.10,1.70,1.28,1.08)])
 spacing,track=running_gear(family)
 for side in [-1,1]:
  box('Fender',(side*spacing/2,.03,1.24 if family=='panther' else 1.08),(track+.12,l-.42,.035))
  if family=='panther':
   # Segmented removable skirts leave the lower interleaved wheels readable.
   for j in range(5):box('Schurzen',(side*1.70,-1.85+j*.92,1.10),(.022,.89,.38))
  for yy in [-l*.43,l*.43]:
   curve('TowEye',[(side*.79,yy,1.04),(side*.79,yy-.10,.91),(side*.79,yy+.05,.85),(side*.79,yy+.12,.99)],.035)
 deck(family,l,deck_z)
 if id=='panther_g':
  pivot=empty('TurretPivot',(0,-.38,1.92),root)
  # Hexagonal plan: broad mantlet cheeks, narrowing sides and short rear bustle.
  low=[(-.81,-1.30,0),(.81,-1.30,0),(1.16,-.52,0),(1.07,1.35,0),(-1.07,1.35,0),(-1.16,-.52,0)]
  high=[(-.76,-1.20,.80),(.76,-1.20,.80),(.83,-.49,.84),(.78,1.02,.84),(-.78,1.02,.84),(-.83,-.49,.84)]
  loft('PantherGTurret',[low,high],pivot)
  cupola(pivot,-.51,.45,.85,.32)
  cyl('RearEscapeHatch',(0,1.35,.38),.30,.07,'Y',pivot)
  box('LoaderRoofHatch',(.39,.35,.855),(.48,.54,.035),pivot)
  gun=empty('GunElevationPivot',(0,-1.31,.40),pivot)
 elif id in ['t34_85','is2_1944']:
  pivot=empty('TurretPivot',(0,-.53 if id=='t34_85' else -.33,1.76 if id=='t34_85' else 1.94),root)
  cast_turret('t34' if id=='t34_85' else 'is',pivot)
  gun=empty('GunElevationPivot',(0,-1.13 if id=='t34_85' else -1.22,.42),pivot)
 else:
  pivot=empty('TurretPivot',(.18 if id=='jagdpanther' else .39,-1.72 if id=='jagdpanther' else -2.02,1.95 if id=='jagdpanther' else 1.78),root)
  gun=empty('GunElevationPivot',parent=pivot)
  if id=='su100':cupola(root,.83,.40,2.15,.33)
  for side in [-1,1]:
   box('CasemateRoofHatch',(side*.47,-.22,2.51 if id=='jagdpanther' else 2.19),(.48,.49,.025))
   box('RoofPeriscope',(side*.43,-.65,2.54 if id=='jagdpanther' else 2.21),(.16,.10,.06),material=dark)
 gun_model(id,gun)
 # Glacis details follow the sloping surface rather than sitting horizontally.
 if id in ['t34_85','su100']:
  hatch=empty('DriverHatchFrame',(-.64,-2.08,1.51 if id=='t34_85' else 1.76),root);hatch.rotation_euler.x=math.radians(33 if id=='t34_85' else 38)
  box('DriverHatch',(0,0,0),(.60,.08,.43),hatch)
  for x in [-.15,.15]:box('VisionCover',(x,-.065,.08),(.19,.055,.10),hatch)
 if id in ['panther_g','t34_85']:
  p=(.69,-2.48,1.48) if id=='panther_g' else (.70,-2.29,1.44)
  cyl('BowMGBall',p,.145,.08,'Y');cyl('BowMG',(p[0],p[1]-.19,p[2]),.023,.36,'Y',material=dark)
 for side in [-1,1]:
  curve('ToolRail',[(side*1.31,-.95,1.36),(side*1.39,-.95,1.42),(side*1.39,.55,1.42),(side*1.31,.55,1.36)],.018)
 cyl('Headlamp',(-1.18,-1.90,1.55),.11,.14,'Y')
 # Convert curves and apply only contour subdivision, then merge by moving assembly.
 for o in list(bpy.context.scene.objects):
  if o.type=='CURVE':
   bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.convert(target='MESH')
  if o.type=='MESH':
   bpy.context.view_layer.objects.active=o
   for mod in list(o.modifiers):bpy.ops.object.modifier_apply(modifier=mod.name)
 # Collapse nested static meshes while keeping true wheel origins, turret and gun.
 groups=[root,pivot,gun]+wheel_parents
 for par in groups:
  members=[]
  for o in list(bpy.context.scene.objects):
   if o.type!='MESH':continue
   ancestor=o.parent
   while ancestor and ancestor not in groups:ancestor=ancestor.parent
   if ancestor==par:members.append(o)
  if not members:continue
  bpy.ops.object.select_all(action='DESELECT')
  for o in members:o.select_set(True)
  bpy.context.view_layer.objects.active=members[0];bpy.ops.object.join();o=members[0]
  world=o.matrix_world.copy();o.parent=par;o.matrix_world=world
  # Set origin to assembly pivot so wheels and barrels animate about correct axes.
  bpy.context.scene.cursor.location=par.matrix_world.translation;bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
  o.name='WheelGeometry' if par in wheel_parents else par.name+'Geometry'
  if par in [root,pivot]:
   mod=o.modifiers.new('Small steel edge bevel','BEVEL');mod.width=.004;mod.segments=2;mod.limit_method='ANGLE'
   bpy.ops.object.modifier_apply(modifier=mod.name)
 bpy.ops.object.select_all(action='SELECT')
 bpy.ops.export_scene.gltf(filepath=str(OUT/(id+'.glb')),export_format='GLB',export_yup=True)
 bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/models'/(id+'_pass03.blend')))
 print('PASS03 EXPORTED',id,flush=True)
