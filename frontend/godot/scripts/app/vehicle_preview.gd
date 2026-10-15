extends SubViewportContainer

const Appearance = preload("res://scripts/vehicles/vehicle_appearance.gd")
const VEHICLE_PATHS = {
	"t34_85": "res://assets/vehicles/t34_85.glb",
	"panther_g": "res://assets/vehicles/panther_g.glb",
	"tiger_i": "res://assets/vehicles/tiger_i.glb",
}

@export var vehicle_id := "t34_85"
var viewport: SubViewport
var turntable: Node3D
var preview_model: Node3D
var camera: Camera3D
var rotation_speed := 0.16
var load_generation := 0
var target := Vector3.ZERO
var model_size := Vector3.ONE
@export_range(0.0, 60.0, 1.0) var preview_render_hz := 30.0
var render_elapsed := 0.0

func _ready() -> void:
	stretch = true
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	custom_minimum_size = Vector2(340, 180)
	viewport = SubViewport.new()
	viewport.size = Vector2i(512, 256)
	viewport.transparent_bg = false
	# UPDATE_ONCE is re-armed at 30 Hz below, which limits the extra preview
	# render without tying vehicle rotation or the simulation to this cadence.
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS if preview_render_hz <= 0.0 else SubViewport.UPDATE_ONCE
	viewport.world_3d = World3D.new()
	add_child(viewport)
	resized.connect(_sync_viewport_size)
	var environment_node := WorldEnvironment.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color("101817")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color("aeb9aa")
	environment.ambient_light_energy = 0.38
	environment_node.environment = environment
	viewport.add_child(environment_node)
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-38, -32, 0)
	key.light_color = Color.WHITE
	key.light_energy = 0.92
	viewport.add_child(key)
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-12, 145, 0)
	fill.light_color = Color("8ba9b2")
	fill.light_energy = 0.32
	viewport.add_child(fill)
	camera = Camera3D.new()
	camera.fov = 36.0
	viewport.add_child(camera)
	turntable = Node3D.new()
	turntable.name = "VehicleYawPivot"
	viewport.add_child(turntable)
	set_vehicle(vehicle_id)

func set_vehicle(next_vehicle: String) -> void:
	if not VEHICLE_PATHS.has(next_vehicle):
		push_warning("VehiclePreview does not support %s" % next_vehicle)
		return
	vehicle_id = next_vehicle
	load_generation += 1
	var generation := load_generation
	_replace_deferred(generation)

func _replace_deferred(generation: int) -> void:
	if is_instance_valid(preview_model):
		turntable.remove_child(preview_model)
		preview_model.queue_free()
		preview_model = null
	await get_tree().process_frame
	if not is_inside_tree() or generation != load_generation:
		return
	var packed := load(VEHICLE_PATHS[vehicle_id]) as PackedScene
	if packed == null:
		push_error("Cannot load vehicle preview model: %s" % VEHICLE_PATHS[vehicle_id])
		return
	preview_model = packed.instantiate() as Node3D
	preview_model.name = "Preview_%s" % vehicle_id
	turntable.add_child(preview_model)
	await get_tree().process_frame
	if not is_instance_valid(preview_model) or generation != load_generation:
		return
	var overrides := Appearance.apply(preview_model, vehicle_id)
	if overrides == 0:
		push_error("No livery surfaces were applied to %s" % vehicle_id)
	_fit_camera(preview_model)
	_request_viewport_frame()

func _fit_camera(model: Node3D) -> void:
	var bounds := AABB()
	var found := false
	for node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh_node := node as MeshInstance3D
		if mesh_node.mesh == null:
			continue
		var transform_to_model := Appearance.relative_transform(model, mesh_node)
		var box := mesh_node.get_aabb()
		for corner in _corners(box):
			var point := transform_to_model * corner
			if not found:
				bounds = AABB(point, Vector3.ZERO)
				found = true
			else:
				bounds = bounds.expand(point)
	if not found:
		return
	var center := bounds.get_center()
	model.position = Vector3(-center.x, -bounds.position.y, -center.z)
	model_size = bounds.size
	target = Vector3(0.0, bounds.size.y * 0.46, 0.0)
	var aspect := maxf(float(viewport.size.x) / maxf(1.0, float(viewport.size.y)), 1.0)
	var half_height := maxf(bounds.size.y, maxf(bounds.size.x / aspect, bounds.size.z / aspect)) * 0.53
	# Keep margin for the projecting gun barrel at every turntable angle.
	var distance := (half_height / tan(deg_to_rad(camera.fov * 0.5)) + maxf(0.5, bounds.size.z * 0.18)) * 1.18
	camera.position = target + Vector3(bounds.size.x * 0.24, bounds.size.y * 0.48, distance)
	camera.transform = Transform3D(Basis.looking_at(target - camera.position, Vector3.UP), camera.position)

func _sync_viewport_size() -> void:
	if not is_instance_valid(viewport):return
	if is_instance_valid(preview_model):_fit_camera(preview_model)
	_request_viewport_frame()

func _request_viewport_frame() -> void:
	if not is_instance_valid(viewport) or not is_visible_in_tree():return
	render_elapsed=0.0
	viewport.render_target_update_mode=SubViewport.UPDATE_ONCE

func _corners(box: AABB) -> Array[Vector3]:
	var p := box.position
	var e := box.end
	return [p, Vector3(e.x, p.y, p.z), Vector3(p.x, e.y, p.z), Vector3(p.x, p.y, e.z), Vector3(e.x, e.y, p.z), Vector3(e.x, p.y, e.z), Vector3(p.x, e.y, e.z), e]

func _process(delta: float) -> void:
	if is_instance_valid(turntable):
		turntable.rotate_y(delta * rotation_speed)
	if not is_instance_valid(viewport):
		return
	if not is_visible_in_tree():
		render_elapsed = 0.0
		viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
		return
	if preview_render_hz <= 0.0:
		viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		return
	render_elapsed += delta
	if render_elapsed >= 1.0 / preview_render_hz:
		render_elapsed = fmod(render_elapsed, 1.0 / preview_render_hz)
		viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
