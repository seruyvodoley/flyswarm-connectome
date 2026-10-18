extends SceneTree

const TerrainScript = preload("res://scripts/terrain.gd")
const FieldEnvironment = preload("res://scripts/battlefield_environment.gd")
var output_dir := ""

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	output_dir = ProjectSettings.globalize_path("res://../.." ).path_join("artifacts/environment_maps")
	DirAccess.make_dir_recursive_absolute(output_dir)
	DisplayServer.window_set_size(Vector2i(1440,900))
	await capture_krasny("before","legacy")
	await capture_krasny("after","enhanced_visual")
	await capture_range("before","legacy")
	await capture_range("after","enhanced_visual")
	print("ENVIRONMENT_GALLERY display=",DisplayServer.get_name()," output=",output_dir)
	quit()

func capture_krasny(label: String, profile: String) -> void:
	var world := make_world(profile,false,1500.0)
	await save_view(world,label,"krasny-overhead",Vector3(0,1260,0),Vector3.ZERO,Vector3.FORWARD,1600.0)
	await save_view(world,label,"krasny-hull",Vector3(63,5,-138),Vector3(140,3,-187),Vector3.UP,68.0)
	await save_view(world,label,"krasny-gunner",Vector3(0,0,-94),Vector3(0,0,-245),Vector3.UP,68.0)
	await save_view(world,label,"krasny-village",Vector3(132,7,-127),Vector3(168,3,-185),Vector3.UP,72.0)
	await save_view(world,label,"krasny-forest",Vector3(-330,6,-12),Vector3(-418,4,-25),Vector3.UP,72.0)
	await save_view(world,label,"krasny-road",Vector3(0,5,-14),Vector3(0,1,-100),Vector3.UP,66.0)
	world.queue_free()
	await process_frame

func capture_range(label: String, profile: String) -> void:
	var world := make_world(profile,true,2200.0)
	await save_view(world,label,"range-overhead",Vector3(0,1240,0),Vector3.ZERO,Vector3.FORWARD,1470.0)
	await save_view(world,label,"range-hull",Vector3(0,5,175),Vector3(0,1,-30),Vector3.UP,62.0)
	await save_view(world,label,"range-gunner",Vector3(0,0,-32),Vector3(0,0,-190),Vector3.UP,62.0)
	await save_view(world,label,"range-margin",Vector3(156,5,128),Vector3(205,1,0),Vector3.UP,68.0)
	world.queue_free()
	await process_frame


func make_world(profile: String, is_range: bool, size: float) -> Node3D:
	var world := Node3D.new()
	root.add_child(world)
	var terrain = TerrainScript.new()
	terrain.range_flat = is_range
	terrain.environment_profile = profile
	world.add_child(terrain)
	terrain.build(is_range,1944,size)
	if profile != "legacy":
		var environment = FieldEnvironment.new()
		environment.configure_world(terrain,1.0,profile,is_range)
		world.add_child(environment)
	var world_environment := WorldEnvironment.new()
	var environment_resource := Environment.new()
	environment_resource.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var sky_material := ProceduralSkyMaterial.new()
	sky_material.sky_top_color = Color(.24,.39,.53)
	sky_material.sky_horizon_color = Color(.78,.77,.65)
	sky_material.ground_bottom_color = Color(.31,.35,.29)
	sky_material.ground_horizon_color = Color(.63,.66,.56)
	sky.sky_material = sky_material
	environment_resource.sky = sky
	environment_resource.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment_resource.ambient_light_color = Color(.62,.69,.75)
	environment_resource.ambient_light_energy = .62
	environment_resource.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	world_environment.environment = environment_resource
	world.add_child(world_environment)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-43.0,-34.0,0.0)
	sun.light_energy = 1.18
	sun.shadow_enabled = true
	world.add_child(sun)
	var camera := Camera3D.new()
	camera.name = "GalleryCamera"
	camera.current = true
	camera.fov = 54.0
	world.add_child(camera)
	world.set_meta("gallery_camera",camera)
	world.set_meta("gallery_terrain",terrain)
	world.set_meta("training_range",is_range)
	var vehicle_scene := load("res://assets/vehicles/t34_85.glb") as PackedScene
	if vehicle_scene != null:
		var tank := vehicle_scene.instantiate() as Node3D
		if tank != null:
			tank.name = "ReferenceT34ForViewScale"
			var tank_z := -30.0 if is_range else -92.0
			tank.position = Vector3(0.0,terrain.height_at(0.0,tank_z)+.1,tank_z)
			world.add_child(tank)
			world.set_meta("gallery_tank",tank)
	return world

func save_view(world: Node3D,label: String,name: String,position: Vector3,target: Vector3,up: Vector3,orthogonal_size: float) -> void:
	var camera: Camera3D = world.get_meta("gallery_camera")
	var camera_position := position
	if name.ends_with("-hull"):
		var terrain = world.get_meta("gallery_terrain")
		var is_range: bool = world.get_meta("training_range")
		var tank_z := -30.0 if is_range else -92.0
		camera_position = Vector3(0.0,terrain.height_at(0.0,tank_z)+5.2,tank_z+14.0)
		target = Vector3(0.0,terrain.height_at(0.0,tank_z)+1.5,tank_z-8.0)
	elif name.ends_with("-gunner"):
		var terrain = world.get_meta("gallery_terrain")
		var is_range: bool = world.get_meta("training_range")
		var tank_z := -30.0 if is_range else -92.0
		var eye_height: float = terrain.height_at(0.0,tank_z)+2.5
		camera_position = Vector3(0.0,eye_height,tank_z-1.2)
		target = Vector3(0.0,eye_height-1.0,tank_z-160.0)
	if name.ends_with("overhead"):
		camera.projection = Camera3D.PROJECTION_ORTHOGONAL
		camera.size = orthogonal_size
	else:
		camera.projection = Camera3D.PROJECTION_PERSPECTIVE
	camera.global_position = camera_position
	camera.look_at(target,up)
	await process_frame
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	image.save_png(output_dir.path_join(label + "-" + name + ".png"))
