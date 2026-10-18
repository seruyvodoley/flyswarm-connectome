"""Render six orthographic/angled views and an articulated rig pose from a GLB."""
import bpy,sys,math
from pathlib import Path
from mathutils import Vector
src,out=sys.argv[sys.argv.index('--')+1:];out=Path(out);out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=src)
scene=bpy.context.scene;scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=1200;scene.render.resolution_y=800;scene.render.resolution_percentage=100
sh=scene.display.shading;sh.light='STUDIO';sh.studio_light='paint.sl';sh.color_type='MATERIAL';sh.show_cavity=True;sh.cavity_type='BOTH';sh.show_shadows=True
scene.world=bpy.data.worlds.new('World');scene.world.color=(.075,.085,.09)
c=bpy.data.cameras.new('ReviewCamera');cam=bpy.data.objects.new('ReviewCamera',c);scene.collection.objects.link(cam);scene.camera=cam;c.type='ORTHO'
pts=[o.matrix_world@Vector(p) for o in scene.objects if o.type=='MESH' for p in o.bound_box];lo=Vector([min(p[i] for p in pts) for i in range(3)]);hi=Vector([max(p[i] for p in pts) for i in range(3)]);center=(lo+hi)/2;dim=hi-lo
views={'front':(0,-1,0),'side':(1,0,0),'top':(0,0,1),'rear':(0,1,0),'front-three-quarter':(1,-1,.65),'rear-three-quarter':(-1,1,.65)}
for name,d in views.items():
    cam.location=center+Vector(d)*18;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();c.ortho_scale=max(dim.x,dim.z*1.5)*1.15 if name in ['front','rear'] else max(dim)*1.15*(1.5 if name=='top' else 1.0)
    scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
for o in scene.objects:
    if o.type=='MESH' and not o.name.startswith(('Wheel','TrackLeft','TrackRight')):o.hide_render=True
cam.location=Vector((18,0,.65));cam.rotation_euler=(Vector((0,0,.65))-cam.location).to_track_quat('-Z','Y').to_euler();c.ortho_scale=7.2;scene.render.filepath=str(out/'running-gear.png');bpy.ops.render.render(write_still=True)
for o in scene.objects:o.hide_render=False
bpy.data.objects['TurretPivot'].rotation_mode='XYZ';bpy.data.objects['GunElevationPivot'].rotation_mode='XYZ'
bpy.data.objects['TurretPivot'].rotation_euler.z=math.radians(9 if Path(src).stem in ["jagdpanther","su100"] else 65);bpy.data.objects['GunElevationPivot'].rotation_euler.x=math.radians(-12)
cam.location=center+Vector((18,-18,14));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();c.ortho_scale=max(dim)*1.3;scene.render.filepath=str(out/'articulated.png');bpy.ops.render.render(write_still=True)
