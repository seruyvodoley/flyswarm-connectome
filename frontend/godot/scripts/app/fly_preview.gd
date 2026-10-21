extends SubViewportContainer

const INITIAL_YAW_DEGREES := 26.0
const AUTO_ROTATION_SPEED := 0.11
const RESUME_DELAY := 4.0
const DRAG_YAW_SENSITIVITY := 0.34
const DRAG_PITCH_SENSITIVITY := 0.20
const MAX_PITCH_DEGREES := 24.0

var fly_root: Node3D
var fly_tilt: Node3D
var orientation_correction: Node3D
var fly_model: Node3D
var preview_camera: Camera3D
var floor_stage: MeshInstance3D
var fit_bounds := AABB()
var viewport: SubViewport
var wing_pivots: Array[Node3D] = []
var fly_skeleton: Skeleton3D
var wing_bone_indices: Array[int] = []
var wing_bone_rest_rotations: Array[Quaternion] = []
var wing_bone_local_axes: Array[Vector3] = []
var preview_elapsed := 0.0
var yaw_degrees := INITIAL_YAW_DEGREES
var pitch_degrees := 0.0
var mouse_dragging := false
var user_rotated := false
var idle_elapsed := 0.0
var render_elapsed := 0.0
var render_pending := true
var was_visible := false
@export_range(0.0, 60.0, 1.0) var preview_render_hz := 30.0
## Main-menu brand mark: render a single still frame and ignore pointer input.
@export var static_watermark := false

func _ready() -> void:
	stretch = true
	focus_mode = Control.FOCUS_NONE
	mouse_filter = Control.MOUSE_FILTER_IGNORE if static_watermark else Control.MOUSE_FILTER_STOP
	if custom_minimum_size.x <= 0.0 or custom_minimum_size.y <= 0.0:
		custom_minimum_size = Vector2(300, 120)
	viewport = SubViewport.new()
	viewport.size = Vector2i(512, 288)
	viewport.transparent_bg = static_watermark
	viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
	viewport.world_3d = World3D.new()
	add_child(viewport)
	resized.connect(_sync_viewport_size)
	visibility_changed.connect(_on_visibility_changed)

	var environment_node := WorldEnvironment.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.0, 0.0, 0.0, 0.0) if static_watermark else Color("303840")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color("b9c3cb")
	environment.ambient_light_energy = 0.62
	environment_node.environment = environment
	viewport.add_child(environment_node)
	_add_directional_light(Vector3(-38, -32, 0), Color("fff0d8"), 1.18, true)
	_add_directional_light(Vector3(-12, 145, 0), Color("d3e0e8"), 0.38)
	_add_directional_light(Vector3(-8, 165, 0), Color("e1c8a4"), 0.48)
	floor_stage = MeshInstance3D.new()
	floor_stage.name = "NeutralStudioFloor"
	var floor_mesh := PlaneMesh.new()
	floor_mesh.size = Vector2(3.6, 3.6)
	floor_stage.mesh = floor_mesh
	floor_stage.visible = not static_watermark
	var floor_material := StandardMaterial3D.new()
	floor_material.albedo_color = Color("3b444a")
	floor_material.roughness = 0.92
	floor_stage.material_override = floor_material
	floor_stage.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	viewport.add_child(floor_stage)

	preview_camera = Camera3D.new()
	preview_camera.fov = 34.0
	viewport.add_child(preview_camera)
	fly_root = Node3D.new()
	fly_root.name = "FlyWorldYawPivot"
	viewport.add_child(fly_root)
	fly_tilt = Node3D.new()
	fly_tilt.name = "FlyPitchPivot"
	fly_root.add_child(fly_tilt)
	orientation_correction = Node3D.new()
	orientation_correction.name = "FlyImportAxisCorrection"
	# glTF export has already converted the Blender Z-up model to Godot Y-up.
	orientation_correction.rotation = Vector3.ZERO
	fly_tilt.add_child(orientation_correction)

	var fly_scene := load("res://assets/environment/fly/fly.glb") as PackedScene
	if fly_scene == null:
		push_error("Missing FlySwarm Drosophila preview model: fly.glb")
		return
	fly_model = fly_scene.instantiate() as Node3D
	fly_model.name = "DrosophilaModel"
	orientation_correction.add_child(fly_model)
	_apply_preview_wing_material(fly_model)
	_setup_wing_animation(fly_model)
	_center_and_fit_model(fly_root, fly_model, 3.2)
	yaw_degrees = INITIAL_YAW_DEGREES
	fly_root.rotation.y = deg_to_rad(yaw_degrees)
	_sync_viewport_size()
	_request_viewport_frame()

func _apply_preview_wing_material(model: Node3D) -> void:
	var wing_material := StandardMaterial3D.new()
	# Keep the user-requested pale-blue wing membrane opaque: the CT mesh has
	# many fine gaps, and alpha blending let the dark thorax show through as a
	# black wing in the small preview window.
	wing_material.albedo_color = Color(0.66, 0.84, 1.0)
	wing_material.transparency = BaseMaterial3D.TRANSPARENCY_DISABLED
	wing_material.roughness = 0.54
	wing_material.metallic = 0.0
	wing_material.emission_enabled = true
	wing_material.emission = Color(0.48, 0.72, 0.92)
	wing_material.emission_energy_multiplier = 0.24
	wing_material.cull_mode = BaseMaterial3D.CULL_DISABLED
	wing_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	wing_material.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_OPAQUE_ONLY
	wing_material.vertex_color_use_as_albedo = false
	var body_material := StandardMaterial3D.new()
	body_material.albedo_color = Color("56645e") if static_watermark else Color(0.018, 0.027, 0.038)
	body_material.roughness = 0.62
	body_material.metallic = 0.04
	body_material.vertex_color_use_as_albedo = false
	var eye_material := StandardMaterial3D.new()
	eye_material.albedo_color = Color(0.54, 0.018, 0.045)
	eye_material.roughness = 0.30
	eye_material.metallic = 0.02
	eye_material.vertex_color_use_as_albedo = false
	for node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh_node := node as MeshInstance3D
		var node_name := mesh_node.name.to_lower()
		var selected_material := wing_material if "wing" in node_name else eye_material if "compound_eye" in node_name else body_material
		mesh_node.material_override = selected_material
		if mesh_node.mesh != null:
			for surface_index in mesh_node.mesh.get_surface_count():
				mesh_node.set_surface_override_material(surface_index, selected_material)

func _setup_wing_animation(model: Node3D) -> void:
	var skeleton_nodes := model.find_children("*", "Skeleton3D", true, false)
	fly_skeleton = skeleton_nodes[0] as Skeleton3D if not skeleton_nodes.is_empty() else null
	if is_instance_valid(fly_skeleton):
		for bone_name in ["wing_left", "wing_right"]:
			var bone_index := fly_skeleton.find_bone(bone_name)
			if bone_index < 0:
				continue
			wing_bone_indices.append(bone_index)
			wing_bone_rest_rotations.append(fly_skeleton.get_bone_pose_rotation(bone_index))
			# The fly's thorax-to-abdomen axis runs along local X. Rotating around
			# camera depth only folds the membranes and makes the flap hard to see.
			var body_axis_local := fly_skeleton.get_bone_global_rest(bone_index).basis.inverse() * Vector3.RIGHT
			wing_bone_local_axes.append(body_axis_local.normalized())
		if not wing_bone_indices.is_empty():
			return
	for pivot_name in ["WingPivot_L", "WingPivot_R"]:
		var pivot := model.find_child(pivot_name, true, false) as Node3D
		if is_instance_valid(pivot):
			wing_pivots.append(pivot)

func _add_directional_light(rotation: Vector3, color: Color, energy: float, cast_shadows := false) -> void:
	var light := DirectionalLight3D.new()
	light.rotation_degrees = rotation
	light.light_color = color
	light.light_energy = energy
	light.shadow_enabled = cast_shadows
	viewport.add_child(light)

func _center_and_fit_model(pivot: Node3D, model: Node3D, target_length: float) -> void:
	var bounds := AABB()
	var found := false
	var pivot_inverse := pivot.global_transform.affine_inverse()
	for node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh_node := node as MeshInstance3D
		if mesh_node.mesh == null:
			continue
		var to_pivot := pivot_inverse * mesh_node.global_transform
		for corner in _corners(mesh_node.get_aabb()):
			var point := to_pivot * corner
			if not found:
				bounds = AABB(point, Vector3.ZERO)
				found = true
			else:
				bounds = bounds.expand(point)
	if not found:
		return
	var largest := maxf(bounds.size.x, maxf(bounds.size.y, bounds.size.z))
	if largest <= 0.0:
		return
	var scale_factor := target_length / largest
	fit_bounds = AABB(Vector3.ZERO, bounds.size * scale_factor)
	# The correction node translates the imported, rotated model by its visual
	# centre. FlyWorldYawPivot therefore stays at the centre of the fly.
	orientation_correction.scale = Vector3.ONE * scale_factor
	orientation_correction.position = -bounds.get_center() * scale_factor
	if is_instance_valid(floor_stage):
		floor_stage.position.y = -fit_bounds.size.y * 0.5 - 0.012

func _corners(box: AABB) -> Array[Vector3]:
	var p := box.position
	var e := box.end
	return [p, Vector3(e.x, p.y, p.z), Vector3(p.x, e.y, p.z), Vector3(p.x, p.y, e.z), Vector3(e.x, e.y, p.z), Vector3(e.x, p.y, e.z), Vector3(p.x, e.y, e.z), e]

func _sync_viewport_size() -> void:
	if not is_instance_valid(viewport):
		return
	if not is_instance_valid(preview_camera) or fit_bounds.size.length() <= 0.0:
		return
	var aspect := maxf(0.25, float(viewport.size.x) / float(viewport.size.y))
	var tan_vertical := tan(deg_to_rad(preview_camera.fov * 0.5))
	var tan_horizontal := tan_vertical * aspect
	var camera_angle := atan(0.18)
	var camera_up := Vector3(0.0, cos(camera_angle), -sin(camera_angle))
	var toward_camera := Vector3(0.0, sin(camera_angle), cos(camera_angle))
	var model_rotation := Basis(Vector3.UP, deg_to_rad(yaw_degrees)) * Basis(Vector3.RIGHT, deg_to_rad(pitch_degrees))
	var look_target := Vector3(0.0, -fit_bounds.size.y * 0.15, 0.0)
	var distance := 0.0
	# Fit the actual rotated bounds so inspection from every side and the full
	# allowed pitch keep the legs and wing tips inside the viewport.
	for corner in _corners(fit_bounds):
		var point: Vector3 = model_rotation * corner - look_target
		var depth := point.dot(toward_camera)
		distance = maxf(distance, depth + absf(point.x) / tan_horizontal)
		distance = maxf(distance, depth + absf(point.dot(camera_up)) / tan_vertical)
	# Bounds corners are conservative for this long, narrow insect model; use an
	# angle-dependent fit so wings and legs stay inside during inspection.
	var yaw_radians := deg_to_rad(yaw_degrees)
	var side_view_adjustment := absf(sin(yaw_radians))
	var rear_view_adjustment := clampf(-cos(yaw_radians), 0.0, 1.0)
	var pitch_adjustment := clampf(absf(pitch_degrees) / MAX_PITCH_DEGREES, 0.0, 1.0)
	# `distance` already accounts for the projected width and height of every
	# transformed bounds corner. Multipliers below 1.0 zoomed inside that fit,
	# clipping the wing tips when the user rotated the model. Keep a small safety
	# margin for the low-poly scan's sparse points and the animated wing bones.
	var inspection_margin := 1.06 + 0.08 * side_view_adjustment + 0.02 * rear_view_adjustment + 0.02 * pitch_adjustment
	# The Open Day fly is a hero object, so use the spare margins in its preview
	# frame while retaining the full angle-aware fit. Lowering the camera target
	# moves the complete stage upward in the window without changing the model.
	distance = (distance * inspection_margin + 0.08) * 0.95
	if static_watermark:
		# Make the isolated silhouette legible at logo size without cropping it.
		distance *= 0.88
	preview_camera.position = look_target + Vector3(0.0, distance * 0.18, distance)
	preview_camera.look_at(look_target, Vector3.UP)
	_request_viewport_frame()

func set_yaw_degrees(angle: float) -> void:
	yaw_degrees = angle
	if is_instance_valid(fly_root):
		fly_root.rotation.y = deg_to_rad(yaw_degrees)
	_sync_viewport_size()
	_request_viewport_frame()

func get_yaw_axis() -> Vector3:
	return fly_root.global_basis.y.normalized() if is_instance_valid(fly_root) else Vector3.ZERO

func reset_view() -> void:
	yaw_degrees = INITIAL_YAW_DEGREES
	pitch_degrees = 0.0
	idle_elapsed = 0.0
	user_rotated = false
	_apply_manual_rotation()

func _apply_manual_rotation() -> void:
	if is_instance_valid(fly_root):
		fly_root.rotation.y = deg_to_rad(yaw_degrees)
	if is_instance_valid(fly_tilt):
		fly_tilt.rotation.x = deg_to_rad(pitch_degrees)
	_sync_viewport_size()
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

func _request_viewport_frame() -> void:
	if is_instance_valid(viewport):
		render_pending = true

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
	if not static_watermark and not mouse_dragging:
		idle_elapsed += delta
		if not user_rotated or idle_elapsed >= RESUME_DELAY:
			yaw_degrees = wrapf(yaw_degrees + delta * rad_to_deg(AUTO_ROTATION_SPEED), -180.0, 180.0)
			fly_root.rotation.y = deg_to_rad(yaw_degrees)
			_sync_viewport_size()
			preview_elapsed += delta
			var flap := sin(preview_elapsed * 69.0) * 0.62
			if is_instance_valid(fly_skeleton) and not wing_bone_indices.is_empty():
				for index in wing_bone_indices.size():
					var side := 1.0 if index == 0 else -1.0
					var flutter := Quaternion(wing_bone_local_axes[index], flap * side)
					fly_skeleton.set_bone_pose_rotation(wing_bone_indices[index], wing_bone_rest_rotations[index] * flutter)
			else:
				for index in wing_pivots.size():
					var pivot := wing_pivots[index]
					if is_instance_valid(pivot):
						pivot.rotation.x = flap * (1.0 if index == 0 else -1.0)
			render_pending = true
	if preview_render_hz <= 0.0:
		viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		return
	render_elapsed += delta
	if render_pending and render_elapsed >= 1.0 / preview_render_hz:
		render_elapsed = fmod(render_elapsed, 1.0 / preview_render_hz)
		render_pending = false
		viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
		if static_watermark:
			set_process(false)
