extends SceneTree
const Appearance=preload("res://scripts/vehicles/vehicle_appearance.gd")
const IDS=["t34_85","is2_1944","panther_g","tiger_i","jagdpanther","su100"]
var failures=0
var viewport: SubViewport
var stage: Node3D
var camera: Camera3D
var sun: DirectionalLight3D
var env: Environment
var output="res://../../artifacts/vehicle_materials"
func _initialize():call_deferred("run")
func check(ok,message):
	if not ok:
		failures+=1
		push_error(message)
func capture(path):
	for i in 3:await process_frame
	RenderingServer.force_draw(false)
	var image=viewport.get_texture().get_image()
	check(not image.is_empty(),"Empty capture "+path)
	image.save_png(output+"/"+path+".png")
func run():
	if DisplayServer.get_name()=="headless":
		quit(1)
		return
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps=0
	viewport=SubViewport.new();viewport.size=Vector2i(1200,800);viewport.own_world_3d=true;viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS;root.add_child(viewport)
	stage=Node3D.new();viewport.add_child(stage)
	sun=DirectionalLight3D.new();sun.rotation_degrees=Vector3(-42,-28,0);sun.light_energy=1.55;sun.light_color=Color(1,.92,.77);sun.shadow_enabled=true;stage.add_child(sun)
	var world=WorldEnvironment.new();env=Environment.new();env.background_mode=Environment.BG_COLOR;env.background_color=Color("53636a");env.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;env.ambient_light_color=Color(.62,.69,.75);env.ambient_light_energy=.62;env.tonemap_mode=Environment.TONE_MAPPER_FILMIC;world.environment=env;stage.add_child(world)
	var ground=MeshInstance3D.new();ground.mesh=PlaneMesh.new();ground.mesh.size=Vector2(100,100);var gm=StandardMaterial3D.new();gm.albedo_color=Color(.35,.34,.25);gm.roughness=1;ground.material_override=gm;stage.add_child(ground)
	camera=Camera3D.new();camera.projection=Camera3D.PROJECTION_ORTHOGONAL;camera.current=true;stage.add_child(camera)
	var results={"renderer":RenderingServer.get_current_rendering_method(),"device":RenderingServer.get_video_adapter_name(),"viewport":"1200x800","timing":"CPU-observed frame intervals; not isolated GPU timing","scenarios":{}}
	for phase in ["before","after"]:
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(output+"/"+phase))
		var models=[]
		for id in IDS:
			var path="res://assets/vehicle_pbr_baseline/%s.glb"%id if phase=="before" else "res://assets/vehicles/%s.glb"%id
			var model=load(path).instantiate();stage.add_child(model);Appearance.apply(model,id);models.append(model)
			if phase=="after":
				for part in model.find_children("*","MeshInstance3D",true,false):
					for s in part.mesh.get_surface_count():
						var mat=part.get_surface_override_material(s)
						check(mat is StandardMaterial3D,"Preserve glTF material: "+id)
						if mat is StandardMaterial3D:
							check(mat.albedo_texture!=null and mat.normal_enabled and mat.normal_texture!=null and mat.roughness_texture!=null and mat.metallic_texture!=null and mat.ao_enabled and mat.ao_texture!=null,"PBR maps enabled: "+id)
			var views={"front":Vector3(0,2,12),"side":Vector3(12,2,0),"top":Vector3(.01,15,0),"quarter":Vector3(9,7,11),"turret":Vector3(4,3.7,4),"running-gear":Vector3(5,1.2,1)}
			for view in views:
				camera.size=4.2 if view=="turret" else (4.8 if view=="running-gear" else (14.0 if view=="top" else 9.5))
				camera.position=views[view];camera.look_at(Vector3(0,1.5 if view=="turret" else 1.0,0))
				await capture(phase+"/"+id+"-"+view)
			if phase=="after":
				camera.size=9.5;camera.position=Vector3(9,7,11);camera.look_at(Vector3(0,1.2,0))
				for angle in [-120,90,0]:
					sun.rotation_degrees.y=angle;await capture(phase+"/"+id+"-light-"+str(angle))
				sun.visible=false;await capture(phase+"/"+id+"-shade");sun.visible=true;sun.rotation_degrees.y=-28
				camera.size=25;await capture(phase+"/"+id+"-distance")
			model.visible=false
		for i in models.size():
			models[i].visible=true;models[i].position=Vector3((i%3-1)*7,0,(i/3)*10)
		camera.size=29;camera.position=Vector3(25,24,31);camera.look_at(Vector3(0,0,5))
		await capture(phase+"/all-six")
		for i in 30:await process_frame
		var times=[];var last=Time.get_ticks_usec()
		for i in 120:
			await process_frame
			var now=Time.get_ticks_usec();times.append((now-last)/1000.0);last=now
		times.sort()
		results.scenarios[phase]={"median_ms":times[60],"p99_ms":times[118],"draw_calls":Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),"texture_bytes":Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED)}
		for model in models:model.queue_free()
		await process_frame
	results["failures"]=failures
	var f=FileAccess.open(output+"/validation.json",FileAccess.WRITE);f.store_string(JSON.stringify(results,"\t"));f.close()
	print("MATERIAL_VALIDATION ",JSON.stringify(results))
	quit(1 if failures else 0)
