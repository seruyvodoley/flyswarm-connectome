"""Second family pass. Original Newc42 Tiger armour retained; new independent running gear.
Jagdpanther G2 and SU-100 use newly constructed section hulls and compatible chassis parts.
"""
import bpy,bmesh,sys,math,json
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).parent))
import rebuild_1944 as g
ROOT=g.ROOT
original_wheel=g.wheel

def wheel(name,x,y,z,r,kind,side,parent,width=.15):
    if kind!='tiger':return original_wheel(name,x,y,z,r,kind,side,parent,width)
    before=set(bpy.data.objects)
    g.radial('SteelWheelDisc',[(-.05,r*.18),(-.05,r*.76),(-.07,r*.9),(-.07,r),(.05,r),(.05,r*.9),(.015,r*.77),(.015,r*.25),(.08,r*.21)],parent,g.paint,(x,y,z))
    for i in range(10):
        a=i*math.tau/10;g.cylinder('WheelFastener',(x+side*.045,y+r*.58*math.cos(a),z+r*.58*math.sin(a)),.018,.035,parent,g.steel,'X')
    return g.combine(list(set(bpy.data.objects)-before),name,parent,(x,y,z))
g.wheel=wheel

def tiger():
    bpy.ops.import_scene.gltf(filepath=str(ROOT/'assets/models/imported/tiger_i/newc42/tiger_i_pre_rebuild.glb'))
    root=bpy.data.objects['VehicleModel'];hull=bpy.data.objects['HullPivot']
    # Original track geometry only had one wheel per axle and faceted continuous belts.
    for o in list(bpy.data.objects):
        if o.type=='MESH' and (o.name.startswith('Wheel') or o.name in ['TrackLeft','TrackRight']):bpy.data.objects.remove(o,do_unlink=True)
    # Bake the retained source transforms, preserving its designed plate/turret shapes.
    bpy.context.view_layer.update()
    for o in list(bpy.data.objects):
        if o.type=='MESH':
            o.data.materials.clear();o.data.materials.append(g.paint)
            for p in o.data.polygons:p.material_index=0
    mesh=bpy.data.objects['HullGeometry'];inv=mesh.matrix_world.inverted()
    for v in mesh.data.vertices:
        p=mesh.matrix_world@v.co
        if abs(p.x)>1.65:p.x=math.copysign(1.65+(abs(p.x)-1.65)*.49,p.x)
        v.co=inv@p
    # Late steel-wheel configuration omits the source's early smoke-launcher clusters.
    turret_mesh=bpy.data.objects['TurretGeometry']
    bm=bmesh.new();bm.from_mesh(turret_mesh.data)
    unseen=set(bm.verts);remove=[]
    while unseen:
        seed=unseen.pop();component={seed};pending=[seed]
        while pending:
            for edge in pending.pop().link_edges:
                for vertex in edge.verts:
                    if vertex in unseen:unseen.remove(vertex);component.add(vertex);pending.append(vertex)
        points=[turret_mesh.matrix_world@v.co for v in component]
        if all(-.95<p.y<-.70 and 2.14<p.z<2.54 and abs(p.x)>.65 for p in points):remove.extend(component)
    if remove:bmesh.ops.delete(bm,geom=remove,context='VERTS')
    bm.to_mesh(turret_mesh.data);bm.free()
    # Keep the source mantlet; replace the faceted barrel and closed muzzle.
    gunpivot=bpy.data.objects['GunElevationPivot'];oldgun=bpy.data.objects['GunBarrel']
    bm=bmesh.new();bm.from_mesh(oldgun.data)
    doomed=[v for v in bm.verts if (oldgun.matrix_world@v.co).y < -1.78]
    bmesh.ops.delete(bm,geom=doomed,context='VERTS');bm.to_mesh(oldgun.data);bm.free();oldgun.name='OriginalGunMantlet'
    bpy.data.objects.remove(bpy.data.objects['Muzzle'],do_unlink=True)
    g.gun(gunpivot,3.98,.088,True)
    spec=dict(family='tiger',centers=[-1.79+i*.514 for i in range(8)],r=.40,track_x=1.40,track_w=.725,ends=[(-2.45,.69,.36),(2.45,.65,.32)],pitch=.13)
    g.running_gear(spec,hull)
    return root,spec

def setup():
    global root,hull
    root=g.node('VehicleModel');hull=g.node('HullPivot',root);return root,hull

def jagdpanther():
    root,hull=setup()
    # G2: continuous sloping front, shorter fighting-compartment roof and longer deck.
    g.body_sections('HullGeometry',[
        (-3.30,.86,1.10,1.11,.91,1.56,1.55),
        (-1.30,.48,1.17,2.55,.91,1.56,1.02),
        (1.02,.48,1.17,2.62,.91,1.56,1.02),
        (1.55,.48,1.17,1.90,.91,1.56,1.23),
        (2.95,.48,1.17,1.90,.91,1.56,1.23),
        (3.30,.82,1.14,1.70,.91,1.48,1.22)],hull)
    for side in [-1,1]:
        g.box('Fender',(side*1.43,0,1.34),(.38,6.45,.035),hull,g.paint)
        for y in [-.95,.55]:g.cylinder('RoofHatch',(side*.65,y,2.59 if y<0 else 2.64),.25,.04,hull,g.paint)
        g.box('RoofPeriscope',(side*.77,-.64,2.65),(.15,.16,.10),hull,g.dark)
        g.cylinder('CoolingFan',(side*.72,2.05,1.94),.34,.055,hull,g.dark)
        for j in range(8):g.box('DeckLouvre',(side*.72,2.48+j*.055,1.94),(.65,.025,.035),hull,g.paint)
        g.radial('Exhaust',[(0,.12),(.8,.12),(.8,.09),(.67,.09)],hull,g.steel,(side*.58,3.35,1.25),'Z')
    g.cylinder('HullMachineGun',(-.76,-2.54,1.66),.16,.15,hull,g.paint,'Y')
    pivot=g.node('TurretPivot',root,(.15,-2.18,1.95))
    gunpivot=g.node('GunElevationPivot',pivot)
    # Bolted G2 collar stays on hull; only the cast inner shield follows gun traverse.
    rings=[]
    for offset in [-.055,.055]:
        rings.append([(.15+x,-2.18+z*1.34+offset,1.95+z) for x,z in [(-.55,-.46),(.55,-.46),(.55,.46),(-.55,.46)]])
    g.loft('FixedGunCollar',rings,hull,g.paint)
    for x in [-.46,.46]:
        for z in [-.36,0,.36]:g.cylinder('CollarBolt',(.15+x,-2.25+z*1.34,1.95+z),.035,.05,hull,g.steel,'Y')
    g.loft('CastSaukopf', [[(math.cos(a)*w,y,math.sin(a)*h+shift) for a in [i*math.tau/40 for i in range(40)]] for y,w,h,shift in [(-.69,.17,.20,0),(-.53,.25,.28,0),(-.12,.43,.40,.04),(.14,.45,.42,.08)]],gunpivot,g.paint,True)
    g.gun(gunpivot,4.38,.088,True)
    spec=dict(family='panther',centers=[-1.95+i*.557 for i in range(8)],r=.43,track_x=1.30,track_w=.66,ends=[(-2.79,.82,.43),(2.77,.77,.34)],pitch=.153)
    g.running_gear(spec,hull);return root,spec

def su100():
    root,hull=setup()
    g.body_sections('HullGeometry',[
        (-3.05,.89,.94,.95,.83,1.43,1.41),
        (-1.55,.45,1.13,1.98,.82,1.43,1.06),
        (.36,.45,1.13,1.98,.82,1.43,1.07),
        (.55,.45,1.13,1.65,.82,1.43,1.05),
        (2.08,.45,1.13,1.65,.82,1.43,1.05),
        (3.05,.88,1.12,1.38,.90,1.34,1.14)],hull)
    for side in [-1,1]:
        g.box('Fender',(side*1.27,0,1.18),(.53,6.10,.04),hull,g.paint)
        for y in [1.04,2.13]:g.cylinder('FuelDrum',(side*1.27,y,1.55),.18,.95,hull,g.paint,'Y')
        g.radial('RearExhaust',[(0,.11),(.20,.11),(.20,.075),(.08,.075)],hull,g.steel,(side*.71,3.02,1.18),'Y')
    g.deck(hull,1.05,1.68)
    # The right-hand commander's bay is an actual projecting armoured volume.
    outline=[(.73,-.48),(1.12,-.48),(1.32,-.31),(1.36,.10),(1.18,.38),(.73,.38)]
    g.loft('CommanderSponson',[[(x,y,1.40) for x,y in outline],[(x,y,1.99) for x,y in outline]],hull,g.paint)
    g.cupola(hull,(1.02,-.05,2.00),.30)
    g.cylinder('RoofLoaderHatch',(-.53,-.13,2.01),.27,.035,hull,g.paint)
    g.box('RoofPeriscope',(-.35,-1.17,2.03),(.13,.16,.10),hull,g.dark)
    # Driver's hatch sits on the sloped glacis left of the gun.
    rings=[]
    for offset in [-.03,.03]:rings.append([(-.63+x,-2.10+z*1.45+offset,1.61+z) for x,z in [(-.25,-.20),(.25,-.20),(.25,.20),(-.25,.20)]])
    g.loft('DriverHatch',rings,hull,g.paint)
    pivot=g.node('TurretPivot',root,(.15,-2.20,1.68));gunpivot=g.node('GunElevationPivot',pivot)
    g.loft('D10SCastMantlet', [[(math.copysign(abs(math.cos(a))**.65,math.cos(a))*w,y,math.sin(a)*h) for a in [i*math.tau/40 for i in range(40)]] for y,w,h in [(-.63,.24,.26),(-.47,.40,.36),(-.12,.50,.42),(.20,.50,.43)]],gunpivot,g.paint,True)
    g.gun(gunpivot,4.20,.100)
    spec=dict(family='t34',centers=[-1.88,-.95,-.02,.91,1.84],r=.415,track_x=1.225,track_w=.55,ends=[(-2.64,.64,.29),(2.60,.65,.32)],pitch=.172)
    g.running_gear(spec,hull);return root,spec

def main():
    kind=sys.argv[sys.argv.index('--')+1]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    g.paint=g.material('Armour',(.23,.29,.14) if kind=='su100' else (.46,.40,.24));g.steel=g.material('TrackSteel',(.19,.20,.18),.6);g.rubber=g.material('Rubber',(.045,.05,.045));g.dark=g.material('Recess',(.035,.04,.032))
    root,spec={'tiger_i':tiger,'jagdpanther':jagdpanther,'su100':su100}[kind]()
    out=ROOT/'assets/models/rebuilt_1944';bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(out/(kind+'.blend')))
    bpy.ops.export_scene.gltf(filepath=str(out/(kind+'.glb')),export_format='GLB',export_yup=True,export_cameras=False,export_lights=False)
    (out/(kind+'.json')).write_text(json.dumps({'model':kind,'running_gear':spec,'triangles':sum(len(p.vertices)-2 for o in bpy.context.scene.objects if o.type=='MESH' for p in o.data.polygons)},indent=2))
if __name__=='__main__':main()
