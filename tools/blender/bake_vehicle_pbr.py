"""Deterministic rest-space paint rasterized into a shared UV atlas per vehicle.
No geometry/pivot changes. PNG albedo (sRGB), roughness/metallic (data), tangent
normal (OpenGL). Low-frequency paint bands are shared across component seams.
"""
import bpy,sys,math,json,time
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
IDS=['t34_85','is2_1944','panther_g','tiger_i','jagdpanther','su100']
SIZE=2048
PALETTES={'t34_85':(.32,.37,.23),'is2_1944':(.30,.35,.22),'su100':(.33,.38,.25)}

def surface(p,n,kind,cast,seed):
    x,y,z=p.T
    a=seed*.73
    grain=np.sin(x*79+a)*np.sin(y*91-a)*np.sin(z*83+.4)
    broad=np.sin(x*2.3+a)*np.sin(y*1.8+.5)*np.cos(z*2.7-a)
    base=np.array(PALETTES.get(ID,(.62,.55,.37)))
    c=np.tile(base,(len(p),1))
    if ID not in PALETTES and kind=='paint':
        # Broad swept spray bands, per-vehicle phase/orientation, never mesh-local.
        f=np.sin(y*(1.65 if ID=='jagdpanther' else 2.15)+x*.8+z*1.3+a+np.sin(x*1.7+z)*.55)
        h=np.sin(y*1.4-x*1.6+z*2.2-a+np.sin(y+z)*.4)
        green=np.clip((f-.12)/.13,0,1);brown=np.clip((h-.49)/.11,0,1)
        c=c*(1-green[:,None])+np.array([.32,.37,.25])*green[:,None]
        c=c*(1-brown[:,None])+np.array([.40,.28,.20])*brown[:,None]
    rough=np.full(len(p),.78);metal=np.zeros(len(p))
    if kind=='rubber':c[:]=(.075,.08,.073);rough[:]=.94
    elif kind=='steel':c[:]=(.22,.23,.21);rough[:]=.62;metal[:]=.8
    elif kind=='recess':c[:]=(.07,.075,.065);rough[:]=.9
    c*=1+(broad*.055+grain*.012)[:,None]
    # Dust follows low running surfaces and upward-facing ledges, not random blotches.
    low=np.clip((1.1-z)/.9,0,1)
    dust=(low*.22+np.maximum(n[:,2],0)*.055)*(1+broad*.2)
    if kind=='recess':dust*=.2
    c=c*(1-dust[:,None])+np.array([.43,.38,.28])*dust[:,None]
    rough=np.clip(rough+broad*.045+grain*.02+dust*.15,.42,.98)
    metal*=1-dust
    # Submillimeter cast relief; milder rolled-steel / rubber surface.
    strength=.065 if cast else (.018 if kind=='paint' else .026)
    grad=np.column_stack((79*np.cos(x*79+a)*np.sin(y*91-a)*np.sin(z*83+.4),91*np.sin(x*79+a)*np.cos(y*91-a)*np.sin(z*83+.4),83*np.sin(x*79+a)*np.sin(y*91-a)*np.cos(z*83+.4)))*strength/90
    return np.clip(c,0,1),rough,metal,grad

def image(name,data,colorspace,path):
    im=bpy.data.images.new(name,width=SIZE,height=SIZE,alpha=True)
    im.colorspace_settings.name=colorspace
    rgba=np.concatenate((data,np.ones((SIZE,SIZE,1),dtype=np.float32)),axis=2).astype(np.float32)
    im.pixels.foreach_set(rgba.ravel());im.filepath_raw=str(path);im.file_format='PNG';im.save();im.pack();return im

def run(id):
    global ID
    ID=id;seed=IDS.index(id)+19;start=time.time()
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/models/rebuilt_1944'/f'{id}.blend'))
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.003,area_weight=.1,correct_aspect=True,scale_to_bounds=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    # Short-range structural occlusion, independent of scene lights.  Split by
    # moving assembly so hull shadows cannot become baked onto a rotating turret.
    trees={}
    for obj in objects:
        obj.data.calc_loop_triangles()
        trees[obj.name]=BVHTree.FromPolygons([obj.matrix_world@v.co for v in obj.data.vertices],[tuple(t.vertices) for t in obj.data.loop_triangles],all_triangles=True)
    albedo=np.zeros((SIZE,SIZE,3),np.float32);orm=np.zeros_like(albedo);normal=np.zeros_like(albedo);normal[:]=(.5,.5,1)
    valid=np.zeros((SIZE,SIZE),bool)
    for o in objects:
        mesh=o.data;mesh.calc_loop_triangles()
        pos=np.array([o.matrix_world@v.co for v in mesh.vertices]);nm=np.array(o.matrix_world.to_3x3().inverted().transposed())
        for tri in mesh.loop_triangles:
            uv=np.array([mesh.uv_layers.active.data[i].uv[:] for i in tri.loops])*SIZE-.5
            lo=np.maximum(np.floor(uv.min(0)).astype(int),0);hi=np.minimum(np.ceil(uv.max(0)).astype(int),SIZE-1)
            if np.any(hi<lo):continue
            xx,yy=np.meshgrid(np.arange(lo[0],hi[0]+1),np.arange(lo[1],hi[1]+1));q=np.stack([xx.ravel(),yy.ravel()],axis=1)
            m=np.column_stack((uv[1]-uv[0],uv[2]-uv[0]));det=np.linalg.det(m)
            if abs(det)<1e-8:continue
            b=(q-uv[0])@np.linalg.inv(m).T;w=np.column_stack((1-b.sum(1),b));keep=np.all(w>=-1e-6,axis=1)
            if not keep.any():continue
            w=w[keep];q=q[keep];p=w@pos[list(tri.vertices)]
            normals=np.array([mesh.corner_normals[i].vector[:] for i in tri.loops])@nm.T
            n=w@normals;n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-8)
            mat=mesh.materials[tri.material_index];name=mat.name.lower() if mat else ''
            kind='rubber' if 'rubber' in name else ('recess' if 'recess' in name else ('steel' if 'steel' in name else 'paint'))
            cast=('TurretGeometry' in o.name and id in ['t34_85','is2_1944']) or any(t in o.name for t in ['Mantlet','Saukopf'])
            c,r,metal,grad=surface(p,n,kind,cast,seed)
            if kind=='paint' and any(label in o.name for label in ['Hatch','Fender','Cupola']):
                # Sparse scuffing at exposed access/foot-contact edges only.
                bounds=np.array([o.matrix_world@Vector(v) for v in o.bound_box]);mn=bounds.min(0);mx=bounds.max(0)
                edge=np.minimum(p[:,:2]-mn[:2],mx[:2]-p[:,:2]).min(1)
                fleck=np.sin(p[:,0]*127+seed)*np.sin(p[:,1]*109-seed)
                wear=np.clip((.018-edge)/.018,0,1)*np.clip((fleck-.65)/.35,0,1)*.65
                c=c*(1-wear[:,None])+np.array([.26,.27,.25])*wear[:,None];metal=np.maximum(metal,wear*.8);r-=wear*.15
            if 'Exhaust' in o.name:
                c*=.68;r=np.maximum(r,.82)
            corners=pos[list(tri.vertices)];deriv=np.column_stack((corners[1]-corners[0],corners[2]-corners[0]))@np.linalg.inv(m)
            t=deriv[:,0];t/=max(np.linalg.norm(t),1e-8)
            bit=np.cross(n,t)*np.sign(np.dot(np.cross(n[0],t),deriv[:,1]))
            tangent=np.column_stack((-grad@t,-np.sum(grad*bit,axis=1),np.ones(len(p))));tangent/=np.linalg.norm(tangent,axis=1)[:,None]
            center=Vector(p.mean(0));nn=Vector(n.mean(0)).normalized();tt=nn.orthogonal().normalized();bb=nn.cross(tt)
            blocked=0
            for angle in [0,math.pi/2,math.pi,math.pi*1.5]:
                direction=(nn*.65+(tt*math.cos(angle)+bb*math.sin(angle))*.76).normalized()
                if trees[o.name].ray_cast(center+nn*.004,direction,.18)[0] is not None:blocked+=1
            ao=1-blocked*.045
            X,Y=q.T;albedo[Y,X]=c;orm[Y,X]=np.column_stack((np.full(len(r),ao),r,metal));normal[Y,X]=tangent*.5+.5;valid[Y,X]=True
    # Six texels of padding prevent dark UV seams under mip filtering.
    for _ in range(6):
        old=valid.copy()
        for dy,dx in [(0,1),(0,-1),(1,0),(-1,0)]:
            take=~valid & np.roll(old,(dy,dx),(0,1))
            for data in [albedo,orm,normal]:data[take]=np.roll(data,(dy,dx),(0,1))[take]
            valid[take]=True
    out=ROOT/'assets/models/pbr_1944'/id;out.mkdir(parents=True,exist_ok=True)
    # Image buffer is encoded sRGB here; PNG save preserves these samples.
    ai=image(id+'_albedo',albedo,'sRGB',out/'albedo.png');oi=image(id+'_orm',orm,'Non-Color',out/'orm.png');ni=image(id+'_normal',normal,'Non-Color',out/'normal.png')
    mat=bpy.data.materials.new('FlySwarmPBR_'+id);mat.use_nodes=True;n=mat.node_tree.nodes;l=mat.node_tree.links;p=n.get('Principled BSDF')
    a=n.new('ShaderNodeTexImage');a.image=ai;l.new(a.outputs['Color'],p.inputs['Base Color'])
    o=n.new('ShaderNodeTexImage');o.image=oi;sep=n.new('ShaderNodeSeparateColor');l.new(o.outputs['Color'],sep.inputs['Color']);l.new(sep.outputs['Green'],p.inputs['Roughness']);l.new(sep.outputs['Blue'],p.inputs['Metallic'])
    group=bpy.data.node_groups.new('glTF Material Output','ShaderNodeTree');group.interface.new_socket(name='Occlusion',in_out='INPUT',socket_type='NodeSocketFloat');gn=n.new('ShaderNodeGroup');gn.node_tree=group
    # The exporter expects the packed image node directly on this socket and
    # takes AO from its red channel in the glTF ORM texture.
    l.new(o.outputs['Color'],gn.inputs['Occlusion'])
    tex=n.new('ShaderNodeTexImage');tex.image=ni;normalnode=n.new('ShaderNodeNormalMap');l.new(tex.outputs['Color'],normalnode.inputs['Color']);l.new(normalnode.outputs['Normal'],p.inputs['Normal'])
    for obj in objects:
        obj.data.materials.clear();obj.data.materials.append(mat)
        for face in obj.data.polygons:face.material_index=0
    bpy.ops.wm.save_as_mainfile(filepath=str(out/f'{id}.blend'))
    bpy.ops.export_scene.gltf(filepath=str(out/f'{id}.glb'),export_format='GLB',export_yup=True,export_animations=False)
    (out/'manifest.json').write_text(json.dumps(dict(id=id,seed=seed,resolution=SIZE,seconds=time.time()-start,ao='four-ray short-range per-mesh structural occlusion; no directional light baked',geometry='unchanged',textures=['albedo.png','orm.png','normal.png']),indent=2))
    print('PBR_COMPLETE',id,time.time()-start,flush=True)
for id in (sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else IDS):run(id)
