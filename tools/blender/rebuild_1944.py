"""Original section-built meshes. No imported or previous vehicle mesh is read.
Blender: metres, +Z up, -Y forward. glTF converts to Godot +Z forward.
Run Blender --background --python this_file -- t34_85 [--render].
"""
import bpy, bmesh, math, sys, json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
TAU=math.tau

def material(name,color,metal=0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=.72
    return m

def node(name,parent=None,at=(0,0,0)):
    o=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(o);o.parent=parent;o.location=at;return o

def mesh(name,v,f,parent,mat,smooth=False):
    data=bpy.data.meshes.new(name);data.from_pydata(v,[],f);data.update()
    bm=bmesh.new();bm.from_mesh(data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(data);bm.free()
    o=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(o);o.parent=parent;data.materials.append(mat)
    for p in data.polygons:p.use_smooth=smooth
    return o

def loft(name,rings,parent,mat,smooth=False,caps=True):
    n=len(rings[0]);v=sum(rings,[]);f=[]
    for k in range(len(rings)-1):
        for j in range(n):f.append((k*n+j,k*n+(j+1)%n,(k+1)*n+(j+1)%n,(k+1)*n+j))
    if caps:f.extend([tuple(range(n-1,-1,-1)),tuple(range((len(rings)-1)*n,len(rings)*n))])
    o=mesh(name,v,f,parent,mat,smooth)
    if caps:
        for p in list(o.data.polygons)[-2:]:p.use_smooth=False
    return o

def box(name,at,size,parent,mat):
    x,y,z=at;a,b,c=[t/2 for t in size]
    return mesh(name,[(x+i*a,y+j*b,z+k*c) for k in [-1,1] for j in [-1,1] for i in [-1,1]],[(0,2,3,1),(4,5,7,6),(0,1,5,4),(1,3,7,5),(3,2,6,7),(2,0,4,6)],parent,mat)

def radial(name,profile,parent,mat,at=(0,0,0),axis='X',n=40):
    rings=[]
    for p,r in profile:
        ring=[]
        for i in range(n):
            a=TAU*i/n
            q=(p,r*math.cos(a),r*math.sin(a)) if axis=='X' else ((r*math.cos(a),p,r*math.sin(a)) if axis=='Y' else (r*math.cos(a),r*math.sin(a),p))
            ring.append(tuple(q[j]+at[j] for j in range(3)))
        rings.append(ring)
    return loft(name,rings,parent,mat,True,caps=profile[0]!=profile[-1])

def cylinder(name,at,r,d,parent,mat,axis='Z'):
    return radial(name,[(-d/2,r),(d/2,r)],parent,mat,at,axis)

def combine(objects,name,parent,origin=(0,0,0)):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();o=objects[0];o.name=name
    bpy.context.scene.cursor.location=origin;bpy.ops.object.origin_set(type='ORIGIN_CURSOR');o.parent=parent
    return o

def convex(points):
    points=sorted(set(points))
    def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    low=[];high=[]
    for p in points:
        while len(low)>1 and cross(low[-2],low[-1],p)<=0:low.pop()
        low.append(p)
    for p in reversed(points):
        while len(high)>1 and cross(high[-2],high[-1],p)<=0:high.pop()
        high.append(p)
    return low[:-1]+high[:-1]

def wheel(name,x,y,z,r,kind,side,parent,width=.15):
    before=set(bpy.data.objects)
    # Deep annular dished rim, hub and individual radial webs; openings are geometry.
    if kind=='t34':
        rim=[(-width/2,r*.73),(-width/2,r*.94),(width/2,r*.94),(width/2,r*.73),(-width/2,r*.73)]
        spokes=10;hub=.24;web=.065
    elif kind=='is':
        rim=[(-width/2,r*.74),(-width/2,r),(width/2,r),(width/2,r*.76),(-width/2,r*.74)]
        spokes=8;hub=.30;web=.055
    elif kind=='panther':
        rim=[(-width/2,r*.72),(-width/2,r*.94),(width/2,r*.94),(width/2,r*.72),(-width/2,r*.72)]
        spokes=8;hub=.32;web=.06
    else:
        rim=[(-width/2,r*.74),(-width/2,r),(width/2,r),(width/2,r*.74),(-width/2,r*.74)]
        spokes=6;hub=.3;web=.05
    radial('Rim',rim,parent,paint,(x,y,z))
    if kind in ('t34','panther'):
        radial('Rubber',[( -width/2,r*.93),(-width/2,r),(width/2,r),(width/2,r*.93),(-width/2,r*.93)],parent,rubber,(x,y,z))
    cylinder('Hub',(x,y,z),r*hub,width*1.5,parent,paint,'X')
    # Perforated pressed/cast web: closed circular apertures, not wagon spokes.
    for i in range(spokes):
        angle=i*TAU/spokes; half=math.pi/spokes
        ri=r*hub*.94; ro=r*.82; rc=(ri+ro)/2; hole=min((ro-ri)*.34,rc*math.sin(half)*.60)
        perimeter=[]
        for j in range(4):
            a=angle-half+2*half*j/4;perimeter.append((ro*math.cos(a),ro*math.sin(a)))
        for j in range(4):
            rr=ro+(ri-ro)*j/4;a=angle+half;perimeter.append((rr*math.cos(a),rr*math.sin(a)))
        for j in range(4):
            a=angle+half-2*half*j/4;perimeter.append((ri*math.cos(a),ri*math.sin(a)))
        for j in range(4):
            rr=ri+(ro-ri)*j/4;a=angle-half;perimeter.append((rr*math.cos(a),rr*math.sin(a)))
        cy,cz=rc*math.cos(angle),rc*math.sin(angle)
        inner=[]
        for yy,zz in perimeter:
            a=math.atan2(zz-cz,yy-cy);inner.append((cy+hole*math.cos(a),cz+hole*math.sin(a)))
        vv=[(x+dx,y+yy,z+zz) for dx in [-width*.2,width*.2] for loop in [perimeter,inner] for yy,zz in loop];ff=[]
        for j in range(16):
            k=(j+1)%16
            ff.extend([(j,k,16+k,16+j),(32+j,48+j,48+k,32+k),(16+j,16+k,48+k,48+j)])
        mesh('PerforatedWeb',vv,ff,parent,paint)
    if kind=='drive':
        for i in range(14):
            a=i*TAU/14
            tooth=box('SprocketTooth',(x,y+(r+.017)*math.cos(a),z+(r+.017)*math.sin(a)),(width,.065,.06),parent,steel)
            # radial tooth facets remain deliberately simple at this scale.
    parts=list(set(bpy.data.objects)-before)
    return combine(parts,name,parent,(x,y,z))

def running_gear(spec,parent):
    centers=spec['centers'];r=spec['r'];x=spec['track_x'];w=spec['track_w'];ends=spec['ends'];family=spec['family']
    for side in [-1,1]:
        for i,y in enumerate(centers):
            if family in ('panther','tiger'):
                # Four separate transverse planes. Adjacent overlapping wheels occupy disjoint planes.
                offsets=(-.23,.07) if i%2==0 else (-.07,.23)
                for j,offset in enumerate(offsets):wheel(f'Wheel_{side}_{i}_{j}',side*(x+offset),y,r+.065,r,family,side,parent,.105)
            else:
                for j,offset in enumerate([-.105,.105]):wheel(f'Wheel_{side}_{i}_{j}',side*(x+offset),y,r+.065,r,family,side,parent,.13)
        for i,(y,z,rr) in enumerate(ends):
            drive=(i==0 if family in ('panther','tiger') else i==1)
            wheel(f'Wheel_{"Drive" if drive else "Idler"}_{side}',side*x,y,z,rr,'drive' if drive else 'idler',side,parent,.26)
        if family=='is':
            for i,y in enumerate([-1.5,0,1.5]):wheel(f'Wheel_Return_{side}_{i}',side*x,y,.90,.13,'idler',side,parent,.25)
        circles=[(y,r+.065,r+.034) for y in centers]+[(y,z,rr+.04) for y,z,rr in ends]
        path=convex([(y+rr*math.cos(i*TAU/96),z+rr*math.sin(i*TAU/96)) for y,z,rr in circles for i in range(96)])
        path.append(path[0]);lens=[0]
        for a,b in zip(path,path[1:]):lens.append(lens[-1]+math.dist(a,b))
        count=round(lens[-1]/spec['pitch']);verts=[];faces=[]
        def shoe_box(cx,cy,cz,sx,sy,sz,angle):
            base=len(verts)
            for k in [-1,1]:
                for j in [-1,1]:
                    for i in [-1,1]:
                        yy=j*sy/2;zz=k*sz/2
                        verts.append((cx+i*sx/2,cy+yy*math.cos(angle)-zz*math.sin(angle),cz+yy*math.sin(angle)+zz*math.cos(angle)))
            faces.extend([tuple(base+a for a in f) for f in [(0,2,3,1),(4,5,7,6),(0,1,5,4),(1,3,7,5),(3,2,6,7),(2,0,4,6)]])
        for j in range(count):
            d=j*lens[-1]/count;k=next(k for k in range(len(lens)-1) if lens[k+1]>=d);t=(d-lens[k])/(lens[k+1]-lens[k]);a,b=path[k:k+2];y=a[0]+t*(b[0]-a[0]);z=a[1]+t*(b[1]-a[1]);angle=math.atan2(b[1]-a[1],b[0]-a[0]);pitch=lens[-1]/count
            shoe_box(side*x,y,z,w,pitch*.92,.044,angle)
            shoe_box(side*x,y+.032*math.sin(angle),z-.032*math.cos(angle),w*.92,.025,.025,angle)
            # Narrow guide tooth points inward between the paired wheel discs.
            shoe_box(side*x,y-.055*math.sin(angle),z+.055*math.cos(angle),.035,.045,.075,angle)
        mesh('TrackLeft' if side<0 else 'TrackRight',verts,faces,parent,steel)
    return circles

def body_sections(name,sections,parent):
    # Six points per section: lower hull, sponson shoulder, sloping upper sides.
    rings=[]
    for y,zb,zs,zt,wb,ws,wt in sections:
        rings.append([(-wb,y,zb),(wb,y,zb),(ws,y,zs),(wt,y,zt),(-wt,y,zt),(-ws,y,zs)])
    return loft(name,rings,parent,paint)

def cast_shell(name,outline,layers,parent):
    # Smooth plan curve from explicit front cheeks, shoulders, bustle and rear stations.
    def cat(a,b,c,d,t):return tuple(.5*((2*b[j])+(-a[j]+c[j])*t+(2*a[j]-5*b[j]+4*c[j]-d[j])*t*t+(-a[j]+3*b[j]-3*c[j]+d[j])*t*t*t) for j in range(2))
    plan=[]
    for i in range(len(outline)):
        for k in range(4):plan.append(cat(outline[(i-1)%len(outline)],outline[i],outline[(i+1)%len(outline)],outline[(i+2)%len(outline)],k/4))
    rings=[[(x*sx,y*sy+shift,z) for x,y in plan] for z,sx,sy,shift in layers]
    return loft(name,rings,parent,paint,True)

def cupola(parent,at,r):
    x,y,z=at
    radial('CommanderCupola',[(0,r*.93),(.04,r),(.19,r),(.23,r*.92)],parent,paint,at,'Z')
    cylinder('CupolaHatch',(x,y,z+.25),r*.9,.035,parent,paint)
    for i in range(5):
        a=i*TAU/5;o=box('VisionSlit',(x+r*math.cos(a),y+r*math.sin(a),z+.12),(.10,.035,.04),parent,dark)

def deck(parent,y,z,width=1.65):
    box('EngineAccessPanel',(0,y,z),(width,.80,.035),parent,paint)
    for side in [-1,1]:
        box('VentRecess',(side*width*.36,y+.65,z),(.48,.65,.025),parent,dark)
        for j in range(8):box('EngineLouvre',(side*width*.36,y+.37+j*.08,z+.025),(.48,.025,.035),parent,paint)

def gun(parent,length,caliber,brake=False):
    # Closed-wall tube with open muzzle bore; the last rings turn inside the barrel.
    radial('GunBarrel',[(0,.135),(-.30,.13),(-.38,.095),(-length+.12,caliber*.70),(-length,caliber*.70),(-length,caliber/2),(-length+.18,caliber/2)],parent,paint,axis='Y')
    cylinder('BoreShadow',(0,-length+.185,0),caliber/2,.005,parent,dark,'Y')
    if brake:
        # Two open lateral chambers, three transverse diaphragms and a bored front face.
        for z in [-.125,.125]:box('BrakeRoof',(0,-length+.25,z),(.25,.56,.045),parent,paint)
        for y in [-length,-length+.25,-length+.50]:
            radial('BrakeDiaphragm',[(y-.025,.15),(y+.025,.15),(y+.025,caliber*.52),(y-.025,caliber*.52),(y-.025,.15)],parent,paint,axis='Y',n=32)
    node('Muzzle',parent,(0,-length,0))

def t34(root,hull):
    body_sections('HullGeometry',[(-2.98,.91,.94,.96,.83,1.43,1.42),(-2.0,.48,1.13,1.67,.82,1.43,1.05),(1.95,.48,1.13,1.66,.82,1.43,1.05),(2.98,.88,1.12,1.39,.90,1.34,1.15)],hull)
    for s in [-1,1]:box('Fender',(s*1.29,-.02,1.18),(.51,5.92,.045),hull,paint)
    hatch=box('DriverHatch',(-.52,-2.36,1.39),(.66,.085,.46),hull,paint);hatch.location=(-.52,-2.36,1.39);
    for v in hatch.data.vertices:v.co-=Vector(hatch.location)
    hatch.rotation_euler.x=math.radians(-55)
    cylinder('HullMachineGunBall',(.62,-2.36,1.39),.14,.14,hull,paint,'Y')
    deck(hull,1.02,1.69)
    for x in [-.71,.71]:radial('RearExhaust',[(0,.11),(.20,.11),(.20,.075),(.08,.075)],hull,steel,(x,2.98,1.20),'Y')
    for s in [-1,1]:
        cylinder('FuelDrum',(s*1.26,1.49,1.57),.18,1.18,hull,paint,'Y')
    tur=node('TurretPivot',root,(0,-.62,1.68))
    outline=[(-.48,-1.12),(.48,-1.12),(.89,-.78),(1.08,-.05),(.95,.81),(.67,1.30),(-.67,1.30),(-.95,.81),(-1.08,-.05),(-.89,-.78)]
    cast_shell('TurretGeometry',outline,[(0,.78,.82,0),(.09,.95,.96,0),(.25,1,1,0),(.69,.93,.98,.015),(.87,.84,.93,.02),(.93,.77,.87,.025)],tur)
    cupola(tur,(-.48,.56,.94),.29);cylinder('LoaderHatch',(.43,.44,.945),.25,.035,tur,paint)
    for x in [-.24,.24]:cylinder('Ventilator',(x,.93,.97),.14,.09,tur,paint)
    g=node('GunElevationPivot',tur,(0,-1.08,.44))
    loft('GunMantlet', [[(math.copysign(abs(math.cos(a))**.45,math.cos(a))*w,y,math.copysign(abs(math.sin(a))**.45,math.sin(a))*h) for a in [i*TAU/32 for i in range(32)]] for y,w,h in [(-.40,.25,.27),(-.30,.32,.33),(.04,.33,.34)]],g,paint,True)
    gun(g,3.47,.085)
    spec=dict(family='t34',centers=[-1.88,-.95,-.02,.91,1.84],r=.415,track_x=1.25,track_w=.50,ends=[(-2.64,.64,.29),(2.60,.65,.32)],pitch=.172)
    running_gear(spec,hull);return spec

def is2(root,hull):
    body_sections('HullGeometry',[
        (-3.38,.85,.91,.95,.92,1.24,1.20),
        (-2.90,.48,1.10,1.24,.86,1.30,1.17),
        (-2.10,.45,1.14,1.64,.86,1.31,1.08),
        (2.46,.45,1.17,1.64,.89,1.31,1.15),
        (3.38,.78,1.12,1.27,.98,1.28,1.18)],hull)
    # The entire glacis is a continuous slope, with no early-IS driver's step.
    for side in [-1,1]:
        box('Fender',(side*1.27,0,1.15),(.58,6.44,.045),hull,paint)
        for y in [1.05,2.18]:cylinder('ExternalFuelDrum',(side*1.30,y,1.54),.19,.97,hull,paint,'Y')
    deck(hull,1.30,1.665,1.82)
    box('DriverVisionArmour',(0,-2.75,1.35),(.36,.12,.13),hull,paint)
    box('DriverVisionSlot',(0,-2.82,1.36),(.25,.02,.035),hull,dark)
    for x in [-.55,.55]:
        cylinder('RearAccessCover',(x,3.39,1.01),.25,.09,hull,paint,'Y')
    tur=node('TurretPivot',root,(0,-.66,1.66))
    outline=[(-.48,-1.29),(.48,-1.29),(.84,-.94),(1.12,-.20),(1.15,.49),(.95,1.12),(.55,1.39),(-.55,1.39),(-.95,1.12),(-1.15,.49),(-1.12,-.20),(-.84,-.94)]
    cast_shell('TurretGeometry',outline,[(0,.87,.91,0),(.09,.98,.99,0),(.25,1,1,0),(.58,.92,.95,0),(.78,.83,.91,-.02),(.86,.77,.87,-.02)],tur)
    cupola(tur,(-.53,.62,.87),.30);cylinder('LoaderHatch',(.43,.51,.87),.25,.035,tur,paint)
    cylinder('RearTurretMG',(-.32,1.31,.40),.14,.20,tur,paint,'Y')
    g=node('GunElevationPivot',tur,(0,-1.24,.40))
    loft('HeavyGunMantlet', [[(math.copysign(abs(math.cos(a))**.65,math.cos(a))*w,y,math.copysign(abs(math.sin(a))**.65,math.sin(a))*h) for a in [i*TAU/40 for i in range(40)]] for y,w,h in [(-.49,.31,.32),(-.35,.47,.39),(-.02,.52,.40),(.11,.48,.37)]],g,paint,True)
    gun(g,4.47,.122,True)
    spec=dict(family='is',centers=[-2.02,-1.23,-.44,.35,1.14,1.93],r=.275,track_x=1.22,track_w=.65,ends=[(-2.79,.68,.33),(2.76,.69,.36)],pitch=.16)
    running_gear(spec,hull);return spec

def panther(root,hull):
    body_sections('HullGeometry',[
        (-3.43,.88,1.05,1.06,.91,1.55,1.55),
        (-2.16,.48,1.16,1.94,.91,1.55,1.23),
        (2.91,.48,1.17,1.94,.91,1.55,1.23),
        (3.43,.81,1.14,1.77,.91,1.48,1.24)],hull)
    for side in [-1,1]:
        box('TrackGuard',(side*1.44,0,1.34),(.36,6.43,.035),hull,paint)
        cylinder('DriverRoofHatch',(side*.65,-1.84,1.97),.27,.055,hull,paint)
        box('DriverPeriscope',(side*.66,-2.06,2.00),(.14,.16,.06),hull,dark)
        cylinder('ExhaustBase',(side*.58,3.32,1.41),.17,.54,hull,paint)
        radial('ExhaustPipe',[(0,.065),(.67,.065),(.67,.045),(.58,.045)],hull,steel,(side*.58,3.48,1.43),'Z')
        cylinder('EngineFan',(side*.72,2.06,1.97),.38,.06,hull,dark)
        for i in range(10):
            a=i*TAU/10
            box('FanGrille',(side*.72+.25*math.cos(a),2.06+.25*math.sin(a),2.01),(.08,.08,.03),hull,paint)
        for j in range(7):box('EngineVent',(side*.76,2.55+j*.055,1.98),(.64,.028,.025),hull,paint)
    cylinder('GlacisBallMount',(.66,-2.94,1.42),.19,.15,hull,paint,'Y')
    # Plan/side silhouette review: move the complete ring assembly 0.44 m aft.
    tur=node('TurretPivot',root,(0,-.15,1.96))
    lower=[(-.87,-1.14),(.87,-1.14),(1.12,.49),(.71,1.30),(-.71,1.30),(-1.12,.49)]
    upper=[(-.72,-.97),(.72,-.97),(.83,.38),(.55,.92),(-.55,.92),(-.83,.38)]
    loft('TurretGeometry',[[(x,y,0) for x,y in lower],[(x,y,.87) for x,y in upper]],tur,paint)
    cupola(tur,(-.47,.42,.89),.28)
    cylinder('LoaderHatch',(.39,-.18,.90),.23,.035,tur,paint)
    cylinder('RearTurretHatch',(0,1.09,.44),.28,.045,tur,paint,'Y')
    g=node('GunElevationPivot',tur,(0,-1.13,.43))
    # Extruded curved front mask with a downward chin; flat rear fits the turret face.
    profile=[(.10,-.38),(-.16,-.43),(-.34,-.43),(-.35,-.27),(-.43,-.08),(-.42,.15),(-.30,.34),(-.08,.40),(.10,.35)]
    loft('ChinMantlet', [[(x,y,z) for y,z in profile] for x in [-.76,.76]],g,paint)
    gun(g,3.74,.075,True)
    spec=dict(family='panther',centers=[-1.95+i*.557 for i in range(8)],r=.43,track_x=1.30,track_w=.66,ends=[(-2.79,.82,.43),(2.77,.77,.34)],pitch=.153)
    running_gear(spec,hull);return spec

def main():
    global paint,steel,rubber,dark
    args=sys.argv[sys.argv.index('--')+1:];kind=args[0]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    paint=material('Armour',(.23,.29,.14) if kind!='panther_g' else (.46,.40,.24));steel=material('TrackSteel',(.19,.20,.18),.6);rubber=material('Rubber',(.045,.05,.045));dark=material('Recess',(.035,.04,.032))
    root=node('VehicleModel');h=node('HullPivot',root)
    spec={'t34_85':t34,'is2_1944':is2,'panther_g':panther}[kind](root,h)
    bpy.context.view_layer.update()
    out=ROOT/'assets/models/rebuilt_1944';out.mkdir(exist_ok=True,parents=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/(kind+'.blend')))
    bpy.ops.export_scene.gltf(filepath=str(out/(kind+'.glb')),export_format='GLB',export_yup=True,export_cameras=False,export_lights=False)
    tris=sum(len(p.vertices)-2 for o in bpy.context.scene.objects if o.type=='MESH' for p in o.data.polygons)
    (out/(kind+'.json')).write_text(json.dumps({'model':kind,'source':'new section-built geometry, no imported meshes','triangles':tris,'running_gear':spec},indent=2))
    print('CREATED',kind,tris)
if __name__=='__main__':main()
