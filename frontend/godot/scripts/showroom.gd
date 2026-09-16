extends SceneTree
func _initialize():call_deferred("run")
func run():
	var stage=Node3D.new()
	root.add_child(stage)
	var camera=Camera3D.new()
	stage.add_child(camera)
	camera.projection=Camera3D.PROJECTION_ORTHOGONAL
	camera.size=12
	var sun=DirectionalLight3D.new()
	sun.rotation_degrees=Vector3(-40,-35,0)
	stage.add_child(sun)
	var environment=WorldEnvironment.new()
	var e=Environment.new()
	e.background_mode=Environment.BG_COLOR
	e.background_color=Color(.16,.17,.18)
	e.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color=Color.WHITE
	e.ambient_light_energy=.7
	environment.environment=e
	stage.add_child(environment)
	var grey=StandardMaterial3D.new()
	grey.albedo_color=Color(.52,.52,.52)
	var output=ProjectSettings.globalize_path("res://../../docs/model_validation/godot")
	DirAccess.make_dir_recursive_absolute(output)
	for id in ["panther_g","tiger_i","jagdpanther","t34_85","is2_1944","su100"]:
		var model=load("res://assets/vehicles/"+id+".glb").instantiate()
		stage.add_child(model)
		for mesh in model.find_children("*","MeshInstance3D",true,false):mesh.material_override=grey
		var angles={"side":Vector3(16,4,0),"front":Vector3(0,4,18),"front_3q":Vector3(13,10,16)}
		for view in angles:
			camera.position=angles[view]
			camera.look_at(Vector3(0,1.5,0))
			await process_frame
			await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png(output.path_join(id+"_"+view+".png"))
		model.queue_free()
		await process_frame
	print("SHOWROOM saved 18 neutral views")
	quit()
