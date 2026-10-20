extends SubViewportContainer

var fly_root: Node3D
var rotation_speed=.28
var orientation_correction: Node3D
var preview_camera: Camera3D
var fit_bounds=AABB()
var viewport: SubViewport
var wing_pivots: Array[Node3D] = []
var preview_elapsed := 0.0
@export_range(0.0, 60.0, 1.0) var preview_render_hz := 30.0
var render_elapsed := 0.0

func _ready():
	stretch=true
	mouse_filter=Control.MOUSE_FILTER_IGNORE
	viewport=SubViewport.new()
	viewport.size=Vector2i(512,288)
	viewport.transparent_bg=false
	# Keep the imported model's animation smooth in the UI while avoiding a
	# second full scene render on every game frame. UPDATE_ONCE is re-armed by
	# _process() at a fixed 30 Hz and hidden menus do no offscreen work.
	viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS if preview_render_hz<=0.0 else SubViewport.UPDATE_ONCE
	viewport.world_3d=World3D.new()
	add_child(viewport)
	resized.connect(_sync_viewport_size)
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
	preview_camera=Camera3D.new();preview_camera.fov=34;viewport.add_child(preview_camera)
	fly_root=Node3D.new();fly_root.name="FlyYawPivot";viewport.add_child(fly_root)
	orientation_correction=Node3D.new();orientation_correction.name="FlyOrientationCorrection";orientation_correction.rotation_degrees=Vector3(-90,0,0);fly_root.add_child(orientation_correction)
	var fly_scene=load("res://assets/environment/fly/fly.glb") as PackedScene
	if fly_scene==null:
		push_error("Missing licensed FlyBody-derived GLB: fly.glb")
		return
	var fly_model=fly_scene.instantiate() as Node3D
	orientation_correction.add_child(fly_model)
	for pivot_name in ["WingPivot_L", "WingPivot_R"]:
		var pivot=fly_model.find_child(pivot_name,true,false) as Node3D
		if is_instance_valid(pivot):wing_pivots.append(pivot)
	fit_model_to_preview(fly_model,3.2,orientation_correction.transform)
	_request_viewport_frame()
	_sync_viewport_size()

func fit_model_to_preview(model: Node3D,target_length: float,orientation: Transform3D=Transform3D.IDENTITY):
	var bounds=AABB()
	var found=false
	for node in model.find_children("*","MeshInstance3D",true,false):
		if node.mesh==null:continue
		var local_transform=model.global_transform.affine_inverse()*node.global_transform
		var mesh_bounds=node.get_aabb()
		for corner in [mesh_bounds.position,mesh_bounds.position+Vector3(mesh_bounds.size.x,0,0),mesh_bounds.position+Vector3(0,mesh_bounds.size.y,0),mesh_bounds.position+Vector3(0,0,mesh_bounds.size.z),mesh_bounds.end,mesh_bounds.position+Vector3(mesh_bounds.size.x,mesh_bounds.size.y,0),mesh_bounds.position+Vector3(mesh_bounds.size.x,0,mesh_bounds.size.z),mesh_bounds.position+Vector3(0,mesh_bounds.size.y,mesh_bounds.size.z)]:
			var point=orientation*(local_transform*corner)
			if not found:bounds=AABB(point,Vector3.ZERO);found=true
			else:bounds=bounds.expand(point)
	if not found:return
	var largest=maxf(bounds.size.x,maxf(bounds.size.y,bounds.size.z))
	if largest<=0:return
	fit_bounds=bounds
	model.scale=Vector3.ONE*(target_length/largest)
	model.position=-(orientation.affine_inverse()*bounds.get_center())*target_length/largest

func _sync_viewport_size() -> void:
	if not is_instance_valid(viewport):return
	var target_size=Vector2i(maxi(128,roundi(size.x)),maxi(72,roundi(size.y)))
	if is_instance_valid(preview_camera) and fit_bounds.size.length()>0.0:
		var scale_factor=3.2/maxf(fit_bounds.size.x,maxf(fit_bounds.size.y,fit_bounds.size.z))
		var half_width=fit_bounds.size.x*scale_factor*.5
		var half_height=fit_bounds.size.y*scale_factor*.5
		var half_depth=fit_bounds.size.z*scale_factor*.5
		var aspect=maxf(.25,float(target_size.x)/float(target_size.y))
		var tangent=tan(deg_to_rad(preview_camera.fov*.5))
		# Fit the model's projected width and height to the actual card shape,
		# with room for the wing tips and a small perspective safety margin.
		var camera_distance=(maxf(half_height/tangent,half_width/(tangent*aspect))+half_depth*.55)*1.10
		preview_camera.position=Vector3(camera_distance*.10,camera_distance*.12,camera_distance)
		preview_camera.look_at(Vector3.ZERO)

func set_yaw_degrees(angle: float) -> void:
	if is_instance_valid(fly_root):fly_root.rotation=Vector3(0,deg_to_rad(angle),0)

func get_yaw_axis() -> Vector3:
	return fly_root.global_basis.y.normalized() if is_instance_valid(fly_root) else Vector3.ZERO

func _request_viewport_frame() -> void:
	if not is_instance_valid(viewport) or not is_visible_in_tree():return
	render_elapsed=0.0
	viewport.render_target_update_mode=SubViewport.UPDATE_ONCE

func _process(delta):
	if not is_instance_valid(viewport):return
	if not is_visible_in_tree():
		render_elapsed=0.0
		viewport.render_target_update_mode=SubViewport.UPDATE_DISABLED
		return
	if is_instance_valid(fly_root):fly_root.rotate_y(delta*rotation_speed)
	preview_elapsed+=delta
	var flap=sin(preview_elapsed*47.0)*0.22
	for index in wing_pivots.size():
		var pivot=wing_pivots[index]
		if is_instance_valid(pivot):pivot.rotation.x=flap*(1.0 if index==0 else -1.0)
	if preview_render_hz<=0.0:
		viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS
		return
	render_elapsed+=delta
	if render_elapsed>=1.0/preview_render_hz:
		render_elapsed=fmod(render_elapsed,1.0/preview_render_hz)
		viewport.render_target_update_mode=SubViewport.UPDATE_ONCE
