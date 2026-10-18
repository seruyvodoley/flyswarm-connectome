extends SceneTree
const Appearance = preload("res://scripts/vehicles/vehicle_appearance.gd")
func _initialize() -> void:call_deferred("run")
func run() -> void:
	if DisplayServer.get_name()=="headless":
		push_error("Rendered validation requires a graphical renderer")
		quit(1)
		return
	var viewport=SubViewport.new()
	viewport.size=Vector2i(1200,800)
	viewport.own_world_3d=true
	viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS
	root.add_child(viewport)
	var stage=Node3D.new()
	viewport.add_child(stage)
	var light=DirectionalLight3D.new()
	light.rotation_degrees=Vector3(-45,-35,0)
	light.light_energy=1.2
	stage.add_child(light)
	var env=WorldEnvironment.new()
	env.environment=Environment.new()
	env.environment.background_mode=Environment.BG_COLOR
	env.environment.background_color=Color("303b3b")
	env.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_color=Color.WHITE
	env.environment.ambient_light_energy=.6
	stage.add_child(env)
	var camera=Camera3D.new()
	camera.projection=Camera3D.PROJECTION_ORTHOGONAL
	camera.size=8.4
	stage.add_child(camera)
	camera.current=true
	var output="res://../../artifacts/vehicle_rebuild_1944/godot"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(output))
	for id in ["t34_85","is2_1944","panther_g","tiger_i","jagdpanther","su100"]:
		var model=load("res://assets/vehicles/%s.glb" % id).instantiate()
		stage.add_child(model)
		Appearance.apply(model,id)
		for pose in ["neutral","traverse","elevation"]:
			model.find_child("TurretPivot",true,false).rotation.y=0 if pose=="neutral" else (.16 if id in ["jagdpanther","su100"] else 1.1)
			model.find_child("GunElevationPivot",true,false).rotation.x=-.22 if pose=="elevation" else 0
			camera.position=Vector3(9,7,11)
			camera.look_at(Vector3(0,1.3,0))
			for i in 4:await process_frame
			RenderingServer.force_draw(false)
			var image=viewport.get_texture().get_image()
			if image.is_empty():
				push_error("Empty viewport for "+id)
				quit(1)
				return
			image.save_png(output+"/"+id+"-"+pose+".png")
		model.queue_free()
		await process_frame
	print("REBUILT_RENDERED_VALIDATION captured=18")
	quit()
