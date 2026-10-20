extends SubViewportContainer

const Appearance = preload("res://scripts/vehicles/vehicle_appearance.gd")
const INITIAL_YAW_DEGREES := -22.0
const AUTO_ROTATION_SPEED := 0.075
const RESUME_DELAY := 4.0
const DRAG_YAW_SENSITIVITY := 0.34
const DRAG_PITCH_SENSITIVITY := 0.18
const MAX_PITCH_DEGREES := 18.0
const VEHICLE_PATHS := {
	"t34_85": "res://assets/vehicles/t34_85.glb",
	"panther_g": "res://assets/vehicles/panther_g.glb",
	"tiger_i": "res://assets/vehicles/tiger_i.glb",
	"is2_1944": "res://assets/vehicles/is2_1944.glb",
	"jagdpanther": "res://assets/vehicles/jagdpanther.glb",
	"su100": "res://assets/vehicles/su100.glb",
}

@export var vehicle_id := "t34_85"
@export_range(0.0, 60.0, 1.0) var preview_render_hz := 30.0
var viewport: SubViewport
var turntable: Node3D
var pitch_pivot: Node3D
var preview_model: Node3D
var camera: Camera3D
var rotation_speed := AUTO_ROTATION_SPEED
var load_generation := 0
var target := Vector3.ZERO
var model_size := Vector3.ONE
var yaw_degrees := INITIAL_YAW_DEGREES
var pitch_degrees := 0.0
var mouse_dragging := false
var user_rotated := false
var idle_elapsed := 0.0
var render_elapsed := 0.0
var render_pending := true
var was_visible := false

func _ready() -> void:
	stretch = true
	focus_mode = Control.FOCUS_NONE
	mouse_filter = Control.MOUSE_FILTER_STOP
	if custom_minimum_size.x <= 0.0 or custom_minimum_size.y <= 0.0:
		custom_minimum_size = Vector2(340, 130)
	viewport = SubViewport.new()
	viewport.size = Vector2i(512, 256)
	viewport.transparent_bg = false
	viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
	viewport.world_3d = World3D.new()
	add_child(viewport)
	resized.connect(_sync_viewport_size)
	visibility_changed.connect(_on_visibility_changed)

	var environment_node := WorldEnvironment.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color("303840")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color("bdc5cc")
	environment.ambient_light_energy = 0.70
	environment_node.environment = environment
	viewport.add_child(environment_node)
	_add_directional_light(Vector3(-38.0, -32.0, 0.0), Color("fff2dc"), 1.35)
	_add_directional_light(Vector3(-12.0, 145.0, 0.0), Color("d5e0e8"), 0.68)
	_add_directional_light(Vector3(-8.0, 165.0, 0.0), Color("e8d1ad"), 0.76)
	camera = Camera3D.new()
	camera.fov = 36.0
	viewport.add_child(camera)
	turntable = Node3D.new()
	turntable.name = "VehicleVisualCentreYawPivot"
	viewport.add_child(turntable)
	turntable.rotation.y = deg_to_rad(INITIAL_YAW_DEGREES)
	pitch_pivot = Node3D.new()
	pitch_pivot.name = "VehiclePitchPivot"
	turntable.add_child(pitch_pivot)
	set_vehicle(vehicle_id)

func _add_directional_light(rotation: Vector3, color: Color, energy: float) -> void:
	var light := DirectionalLight3D.new()
	light.rotation_degrees = rotation
	light.light_color = color
	light.light_energy = energy
	light.shadow_enabled = false
	viewport.add_child(light)

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
		pitch_pivot.remove_child(preview_model)
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
	pitch_pivot.add_child(preview_model)
	await get_tree().process_frame
	if not is_instance_valid(preview_model) or generation != load_generation or not is_inside_tree():
		return
	var overrides := Appearance.apply(preview_model, vehicle_id)
	if overrides == 0:
		push_error("No livery surfaces were applied to %s" % vehicle_id)
	_fit_camera(preview_model)
	_request_viewport_frame()

func _fit_camera(model: Node3D) -> void:
	if not is_instance_valid(camera) or not camera.is_inside_tree():
		return
	var bounds := AABB()
	var found := false
	for node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh_node := node as MeshInstance3D
		if mesh_node.mesh == null:
			continue
		var model_to_mesh := Appearance.relative_transform(model, mesh_node)
		for corner in _corners(mesh_node.get_aabb()):
			var point := model_to_mesh * corner
			if not found:
				bounds = AABB(point, Vector3.ZERO)
				found = true
			else:
				bounds = bounds.expand(point)
	if not found:
		return
	var center := bounds.get_center()
	model.position = -center
	model_size = bounds.size
	target = Vector3.ZERO
	# Rotate around the full visual centre, then frame the complete horizontal
	# envelope. This keeps long barrels inside the viewport at every azimuth.
	var aspect := maxf(0.25, float(viewport.size.x) / maxf(1.0, float(viewport.size.y)))
	var tan_vertical := tan(deg_to_rad(camera.fov * 0.5))
	var tan_horizontal := tan_vertical * aspect
	var half_height := bounds.size.y * 0.5
	var horizontal_radius := maxf(bounds.size.x, bounds.size.z) * 0.5
	var camera_angle := atan(0.16)
	var projected_vertical_radius := half_height * cos(camera_angle) + horizontal_radius * sin(camera_angle)
	var depth_margin := maxf(0.20, bounds.size.length() * 0.08)
	var distance := maxf(projected_vertical_radius / tan_vertical, horizontal_radius / tan_horizontal) * 1.15 + depth_margin
	camera.position = target + Vector3(distance * 0.10, distance * 0.16, distance)
	camera.look_at(target, Vector3.UP)

func _sync_viewport_size() -> void:
	if not is_instance_valid(viewport):
		return
	if is_instance_valid(preview_model):
		_fit_camera(preview_model)
	_request_viewport_frame()

func _request_viewport_frame() -> void:
	if is_instance_valid(viewport):
		render_pending = true

func _corners(box: AABB) -> Array[Vector3]:
	var p := box.position
	var e := box.end
	return [p, Vector3(e.x, p.y, p.z), Vector3(p.x, e.y, p.z), Vector3(p.x, p.y, e.z), Vector3(e.x, e.y, p.z), Vector3(e.x, p.y, e.z), Vector3(p.x, e.y, e.z), e]

func reset_view() -> void:
	yaw_degrees = INITIAL_YAW_DEGREES
	pitch_degrees = 0.0
	idle_elapsed = 0.0
	user_rotated = false
	_apply_manual_rotation()

func _apply_manual_rotation() -> void:
	if is_instance_valid(turntable):
		turntable.rotation.y = deg_to_rad(yaw_degrees)
	if is_instance_valid(pitch_pivot):
		pitch_pivot.rotation.x = deg_to_rad(pitch_degrees)
	_request_viewport_frame()

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed and event.double_click:
			reset_view()
			accept_event()
			return
		mouse_dragging = event.pressed
		idle_elapsed = 0.0
		accept_event()

func _input(event: InputEvent) -> void:
	if mouse_dragging and event is InputEventMouseMotion:
		yaw_degrees -= event.relative.x * DRAG_YAW_SENSITIVITY
		pitch_degrees = clampf(pitch_degrees + event.relative.y * DRAG_PITCH_SENSITIVITY, -MAX_PITCH_DEGREES, MAX_PITCH_DEGREES)
		idle_elapsed = 0.0
		user_rotated = true
		_apply_manual_rotation()
		get_viewport().set_input_as_handled()

func _on_visibility_changed() -> void:
	if is_visible_in_tree():
		_request_viewport_frame()
	else:
		mouse_dragging = false
		if is_instance_valid(viewport):
			viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED

func _process(delta: float) -> void:
	if not is_instance_valid(viewport):
		return
	if not is_visible_in_tree():
		was_visible = false
		viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
		return
	if not was_visible:
		was_visible = true
		render_pending = true
	if not mouse_dragging:
		idle_elapsed += delta
		if not user_rotated or idle_elapsed >= RESUME_DELAY:
			yaw_degrees = wrapf(yaw_degrees + delta * rad_to_deg(rotation_speed), -180.0, 180.0)
			if is_instance_valid(turntable):
				turntable.rotation.y = deg_to_rad(yaw_degrees)
			render_pending = true
	if preview_render_hz <= 0.0:
		viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		return
	render_elapsed += delta
	if render_pending and render_elapsed >= 1.0 / preview_render_hz:
		render_elapsed = fmod(render_elapsed, 1.0 / preview_render_hz)
		render_pending = false
		viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
