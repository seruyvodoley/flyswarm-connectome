extends SubViewportContainer

var fly_root: Node3D
var rotation_speed=.28

func _ready():
	stretch=true
	mouse_filter=Control.MOUSE_FILTER_IGNORE
	var viewport=SubViewport.new()
	viewport.size=Vector2i(640,420)
	viewport.transparent_bg=false
	viewport.render_target_update_mode=SubViewport.UPDATE_WHEN_VISIBLE
	viewport.world_3d=World3D.new()
	add_child(viewport)
	var environment=WorldEnvironment.new()
	var env=Environment.new()
	env.background_mode=Environment.BG_COLOR
	env.background_color=Color("101817")
	env.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color=Color("9caf9d")
	env.ambient_light_energy=.82
	environment.environment=env
	viewport.add_child(environment)
	var key=DirectionalLight3D.new();key.rotation_degrees=Vector3(-38,-32,0);key.light_color=Color("f0d9ab");key.light_energy=2.0;viewport.add_child(key)
	var fill=OmniLight3D.new();fill.position=Vector3(-3,2,4);fill.light_color=Color("84b6a3");fill.omni_range=12;fill.light_energy=3.3;viewport.add_child(fill)
	var camera=Camera3D.new();camera.position=Vector3(0,.15,5.4);camera.fov=34;viewport.add_child(camera)
	fly_root=Node3D.new();fly_root.rotation_degrees=Vector3(-8,-24,0);viewport.add_child(fly_root)
	var fly_scene=load("res://assets/environment/fly/fly.glb") as PackedScene
	if fly_scene==null:
		push_error("Missing licensed FlyBody-derived GLB: fly.glb")
		return
	var fly_model=fly_scene.instantiate() as Node3D
	fly_root.add_child(fly_model)
	fit_model_to_preview(fly_model,3.2)
	camera.look_at(Vector3(0,0,0))

func fit_model_to_preview(model: Node3D,target_length: float):
	var bounds=AABB()
	var found=false
	for node in model.find_children("*","MeshInstance3D",true,false):
		if node.mesh==null:continue
		var local_transform=model.global_transform.affine_inverse()*node.global_transform
		var mesh_bounds=node.get_aabb()
		for corner in [mesh_bounds.position,mesh_bounds.position+Vector3(mesh_bounds.size.x,0,0),mesh_bounds.position+Vector3(0,mesh_bounds.size.y,0),mesh_bounds.position+Vector3(0,0,mesh_bounds.size.z),mesh_bounds.end,mesh_bounds.position+Vector3(mesh_bounds.size.x,mesh_bounds.size.y,0),mesh_bounds.position+Vector3(mesh_bounds.size.x,0,mesh_bounds.size.z),mesh_bounds.position+Vector3(0,mesh_bounds.size.y,mesh_bounds.size.z)]:
			var point=local_transform*corner
			if not found:bounds=AABB(point,Vector3.ZERO);found=true
			else:bounds=bounds.expand(point)
	if not found:return
	var largest=maxf(bounds.size.x,maxf(bounds.size.y,bounds.size.z))
	if largest<=0:return
	model.scale=Vector3.ONE*(target_length/largest)
	model.position=-bounds.get_center()*target_length/largest

func _process(delta):
	if is_instance_valid(fly_root):fly_root.rotate_y(delta*rotation_speed)
