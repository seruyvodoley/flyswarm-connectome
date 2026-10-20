extends SceneTree

const Appearance = preload("res://scripts/vehicles/vehicle_appearance.gd")
const VehiclePreview = preload("res://scripts/app/vehicle_preview.gd")
const FlyPreview = preload("res://scripts/app/fly_preview.gd")
const SessionConfig = preload("res://scripts/app/session_config.gd")
const IDS = ["t34_85", "panther_g", "tiger_i", "is2_1944", "jagdpanther", "su100"]
const PREVIEW_IDS = IDS

var failures := 0
var capture_enabled := false
var output_dir := "res://../../artifacts/performance/open_day_vehicle_validation"

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	capture_enabled=DisplayServer.get_name()!="headless"
	var requested_output := OS.get_environment("FLYSWARM_QA_OUT")
	if not requested_output.is_empty():
		output_dir = requested_output
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(output_dir) if output_dir.begins_with("res://") else output_dir)
	var app = root.get_node("AppState")
	app.show_page("OpenDayMain")
	await _frames(8)
	if capture_enabled:
		DisplayServer.window_set_size(Vector2i(1280, 720))
		await _frames(3)
	var fly: Node
	var tank: Node
	for node in app.view.find_children("*", "SubViewportContainer", true, false):
		if node.has_method("set_yaw_degrees"):
			fly = node
		elif node.has_method("set_vehicle"):
			tank = node
	if fly == null or tank == null:
		_fail("Open Day main page must expose its real fly and vehicle previews")
		quit(1)
		return
	if not is_equal_approx(fly.custom_minimum_size.y, 155.0) or not is_equal_approx(tank.custom_minimum_size.y, 155.0):
		_fail("Fly and vehicle preview panes must share the same minimum height")
	if app.view.find_child("OpenDaySelectionControl", true, false) == null:
		_fail("Open Day vehicle caption and selector must remain in the center block")
	await _frames(2)
	var fly_stage := fly.get_parent().get_parent() as Control
	var tank_stage := tank.get_parent().get_parent() as Control
	if absf(fly_stage.size.y - tank_stage.size.y) > 1.0:
		_fail("Fly and vehicle preview windows must have equal heights")
	await _validate_open_day_vehicle_choices(app.view)
	if capture_enabled:
		await _frames(4)
		var page_image := root.get_texture().get_image()
		var page_path := ProjectSettings.globalize_path(output_dir) if output_dir.begins_with("res://") else output_dir
		var page_error := page_image.save_png(page_path.path_join("open-day-selection-su100.png"))
		if page_error != OK:
			_fail("Could not save complete Open Day selection screenshot")
		else:
			print("SCREENSHOT ", page_path.path_join("open-day-selection-su100.png"))
	await _validate_preview_interaction(fly, tank)
	await _validate_battle_vehicle_spawns()
	await _capture_fly_angles(fly)
	await _capture_vehicle_switches(tank)
	_validate_all_liveries()
	print("OPEN DAY VEHICLE VALIDATION failures=", failures)
	if not capture_enabled:print("VISUAL CAPTURES SKIPPED: headless rendering backend")
	quit(0 if failures == 0 else 1)

func _validate_open_day_vehicle_choices(page: Node) -> void:
	for id in IDS:
		if not page.vehicle_buttons.has(id):
			_fail("Open Day vehicle selector is missing %s" % id)
			continue
		page.select_vehicle(id)
		await _frames(3)
		if page.selected_vehicle != id or page.vehicle_preview.vehicle_id != id:
			_fail("Open Day selected %s / preview %s, requested %s" % [page.selected_vehicle, page.vehicle_preview.vehicle_id, id])
		var app = root.get_node("AppState")
		app.configure_demo(id)
		if app.session.demo_vehicle != id or app.session.vehicle_composition != id:
			_fail("Open Day battle setup did not carry vehicle selection %s" % id)

func _validate_battle_vehicle_spawns() -> void:
	for id in ["t34_85", "tiger_i", "is2_1944", "panther_g"]:
		var config = SessionConfig.new()
		config.mode = "demo"
		config.map = "demo_arena"
		config.seconds = 1.0
		config.vehicle_composition = id
		config.demo_vehicle = id
		config.demo_opponent = id
		config.blue_controller = "rule"
		config.red_controller = "rule"
		var battle = load("res://scenes/Battle.tscn").instantiate()
		battle.session_config = config
		root.add_child(battle)
		await process_frame
		if battle.vehicles.size() <= 8:
			_fail("Battle did not spawn the selected vehicle %s" % id)
		else:
			for index in [0, 8]:
				var tank = battle.vehicles[index]
				if tank.cfg.id != id or tank.model.find_child("Muzzle", true, false) == null:
					_fail("Battle slot %d did not load the selected %s model and gun rig" % [index, id])
		battle.queue_free()
		await process_frame

func _frames(count: int) -> void:
	for _i in count:
		await process_frame

func _capture_fly_angles(fly: FlyPreview) -> void:
	fly.set_yaw_degrees(26.0)
	await _frames(15)
	if capture_enabled:
		_save_viewport(fly.get_child(0) as SubViewport, "fly-initial-3q.png")
	for degrees in [0, 90, 180, 270, 360]:
		fly.set_yaw_degrees(float(degrees))
		await _frames(3)
		var axis: Vector3 = fly.get_yaw_axis()
		if absf(axis.dot(Vector3.UP)) < 0.999:
			_fail("Fly yaw pivot is not rotating about world Y at %d degrees" % degrees)
		if not capture_enabled:continue
		var viewport := fly.get_child(0) as SubViewport
		_save_viewport(viewport, "fly-%03d.png" % degrees)
		var fly_image := viewport.get_texture().get_image()
		if not _has_foreground(fly_image, Color("303840")):
			_fail("Fly preview rendered no visible model at %d degrees" % degrees)
		elif not _model_inside_frame(fly_image, Color("303840")):
			_fail("Fly model crossed the preview frame at %d degrees" % degrees)
	fly.yaw_degrees = 26.0
	fly.pitch_degrees = FlyPreview.MAX_PITCH_DEGREES
	fly._apply_manual_rotation()
	await _frames(15)
	if capture_enabled:
		var top_viewport := fly.get_child(0) as SubViewport
		_save_viewport(top_viewport, "fly-top-limited.png")
		if not _model_inside_frame(top_viewport.get_texture().get_image(), Color("303840")):
			_fail("Fly model crossed the preview frame at the maximum inspection pitch")
	fly.pitch_degrees = 0.0
	fly.set_yaw_degrees(90.0)
	await _frames(15)
	if capture_enabled:
		_save_viewport(fly.get_child(0) as SubViewport, "fly-side.png")
	fly.reset_view()

func _validate_preview_interaction(fly: FlyPreview, tank: VehiclePreview) -> void:
	if fly.floor_stage == null or not fly.floor_stage.mesh is PlaneMesh:
		_fail("Fly preview does not provide a visible neutral ground plane")
	if fly.orientation_correction.rotation.length() > 0.001:
		_fail("Fly import correction must preserve the glTF Y-up orientation")
	if absf(fly.floor_stage.position.y - (-fly.fit_bounds.size.y * 0.5 - 0.012)) > 0.01:
		_fail("Fly preview ground plane is not aligned below the model's feet")
	fly.reset_view()
	fly.mouse_dragging = true
	var fly_motion := InputEventMouseMotion.new()
	fly_motion.relative = Vector2(60.0, 500.0)
	fly._input(fly_motion)
	fly.mouse_dragging = false
	if not fly.user_rotated or absf(fly.yaw_degrees - FlyPreview.INITIAL_YAW_DEGREES) < 1.0:
		_fail("Fly mouse drag did not rotate the yaw pivot")
	if absf(fly.pitch_degrees - FlyPreview.MAX_PITCH_DEGREES) > 0.01:
		_fail("Fly preview pitch was not clamped to its safe limit")
	var fly_paused_yaw := fly.yaw_degrees
	fly._process(2.0)
	if absf(fly.yaw_degrees - fly_paused_yaw) > 0.01:
		_fail("Fly auto-rotation did not pause after manual inspection")
	fly._process(2.1)
	if is_equal_approx(fly.yaw_degrees, fly_paused_yaw):
		_fail("Fly auto-rotation did not resume after the idle delay")
	fly.reset_view()
	if absf(fly.pitch_degrees) > 0.01 or absf(fly.yaw_degrees - FlyPreview.INITIAL_YAW_DEGREES) > 0.01:
		_fail("Fly preview reset did not restore the initial view")

	tank.reset_view()
	tank.mouse_dragging = true
	var tank_motion := InputEventMouseMotion.new()
	tank_motion.relative = Vector2(-50.0, 500.0)
	tank._input(tank_motion)
	tank.mouse_dragging = false
	if not tank.user_rotated or absf(tank.yaw_degrees - VehiclePreview.INITIAL_YAW_DEGREES) < 1.0:
		_fail("Vehicle mouse drag did not rotate the yaw pivot")
	if absf(tank.pitch_degrees - VehiclePreview.MAX_PITCH_DEGREES) > 0.01:
		_fail("Vehicle preview pitch was not clamped to its safe limit")
	var tank_paused_yaw := tank.yaw_degrees
	tank._process(2.0)
	if absf(tank.yaw_degrees - tank_paused_yaw) > 0.01:
		_fail("Vehicle auto-rotation did not pause after manual inspection")
	tank._process(2.1)
	if is_equal_approx(tank.yaw_degrees, tank_paused_yaw):
		_fail("Vehicle auto-rotation did not resume after the idle delay")
	tank.reset_view()
	if absf(tank.pitch_degrees) > 0.01 or absf(tank.yaw_degrees - VehiclePreview.INITIAL_YAW_DEGREES) > 0.01:
		_fail("Vehicle preview reset did not restore the initial view")

func _capture_vehicle_switches(preview: VehiclePreview) -> void:
	for index in 30:
		var id: String = PREVIEW_IDS[index % PREVIEW_IDS.size()]
		preview.set_vehicle(id)
		await _frames(3)
		if not is_instance_valid(preview.preview_model) or preview.preview_model.name != "Preview_%s" % id:
			_fail("VehiclePreview did not load requested model %s on switch %d" % [id, index + 1])
		if preview.pitch_pivot.get_child_count() != 1:
			_fail("VehiclePreview leaked model nodes after switch %d" % (index + 1))
		if capture_enabled and index >= 24:
			var viewport := preview.get_child(0) as SubViewport
			await _frames(15)
			preview._request_viewport_frame()
			await RenderingServer.frame_post_draw
			_save_viewport(viewport, "vehicle-%s.png" % id)
			if not _has_foreground(viewport.get_texture().get_image(), Color("303840")):
				_fail("Vehicle preview rendered no visible model for %s" % id)

func _validate_all_liveries() -> void:
	for id in IDS:
		var packed := load("res://assets/vehicles/%s.glb" % id) as PackedScene
		if packed == null:
			_fail("Missing vehicle model %s" % id)
			continue
		var model := packed.instantiate() as Node3D
		root.add_child(model)
		var turret := model.find_child("TurretPivot", true, false)
		var gun := model.find_child("GunElevationPivot", true, false)
		var muzzle := model.find_child("Muzzle", true, false)
		var pivots := [turret.transform if turret else Transform3D.IDENTITY, gun.transform if gun else Transform3D.IDENTITY, muzzle.transform if muzzle else Transform3D.IDENTITY]
		var surface_count := Appearance.apply(model, id)
		if surface_count < 1:
			_fail("No livery materials applied to %s" % id)
		if not turret or not gun or not muzzle:
			_fail("Mechanical pivots missing on %s" % id)
		elif turret.transform != pivots[0] or gun.transform != pivots[1] or muzzle.transform != pivots[2]:
			_fail("Livery changed a mechanical pivot on %s" % id)
		elif id in ["t34_85", "tiger_i", "is2_1944", "panther_g"]:
			var muzzle_before: Vector3 = muzzle.global_position
			var hull_mesh := model.find_child("HullGeometry", true, false) as MeshInstance3D
			var hull_before: Vector3 = hull_mesh.global_position if hull_mesh else Vector3.ZERO
			turret.rotation.y += 0.25
			turret.force_update_transform()
			muzzle.force_update_transform()
			if muzzle.global_position.distance_to(muzzle_before) < 0.05:
				_fail("Turret does not move the muzzle on %s" % id)
			if hull_mesh and hull_mesh.global_position.distance_to(hull_before) > 0.001:
				_fail("Turret rotation moves the source hull on %s" % id)
			turret.transform = pivots[0]
			var before_elevation: Vector3 = muzzle.global_position
			gun.rotation.x += 0.12
			gun.force_update_transform()
			muzzle.force_update_transform()
			if muzzle.global_position.distance_to(before_elevation) < 0.01:
				_fail("Gun elevation does not move the muzzle on %s" % id)
			gun.transform = pivots[1]
		if id == "t34_85":
			if model.find_child("TrackLeft", true, false) == null or model.find_child("TrackRight", true, false) == null:
				_fail("T-34/85 track loops are missing")
		if id in ["tiger_i", "is2_1944", "panther_g"]:
			for part_name in ["HullGeometry", "GunBarrel", "TrackLeft", "TrackRight"]:
				if model.find_child(part_name, true, false) == null:
					_fail("Required mechanical mesh %s is missing on %s" % [part_name, id])
		if id == "tiger_i" and model.find_children("Wheel*", "MeshInstance3D", true, false).size() < 12:
			_fail("Individual Tiger I wheel meshes are missing")
		if id in ["t34_85", "is2_1944", "panther_g"]:
			var expected_wheels = {"t34_85":24, "is2_1944":34, "panther_g":36}
			if model.find_children("Wheel*", "MeshInstance3D", true, false).size() != expected_wheels[id]:
				_fail("Rebuilt running gear wheel count is incorrect on %s" % id)
		if id in ["is2_1944", "panther_g"]:
			var vehicle_root := model.find_child("VehicleModel", true, false)
			if turret.get_parent() != vehicle_root or gun.get_parent() != turret:
				_fail("%s source turret and gun pivots are not independent model nodes" % id)
		for node in model.find_children("*", "MeshInstance3D", true, false):
			for surface in node.mesh.get_surface_count():
				var material = node.get_surface_override_material(surface)
				if not material is StandardMaterial3D or material.albedo_texture == null or material.normal_texture == null or material.roughness_texture == null:
					_fail("Imported PBR maps missing on %s/%s" % [id,node.name])
		Appearance.set_destroyed(model, id, true)
		var destroyed_mat := _first_override(model)
		if destroyed_mat == null or destroyed_mat.albedo_color.r > .3:
			_fail("Destroyed appearance missing for %s" % id)
		Appearance.set_destroyed(model, id, false)
		var restored_mat := _first_override(model)
		if restored_mat == null or restored_mat.albedo_color.r < .95:
			_fail("PBR did not restore after reset for %s" % id)
		model.queue_free()
	await process_frame

func _first_override(model: Node3D) -> StandardMaterial3D:
	for node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh := node as MeshInstance3D
		for surface in mesh.mesh.get_surface_count():
			var material := mesh.get_surface_override_material(surface)
			if material is StandardMaterial3D:
				return material
	return null

func _has_foreground(image: Image, background: Color) -> bool:
	if image == null or image.is_empty():
		return false
	var different := 0
	for y in range(0, image.get_height(), 4):
		for x in range(0, image.get_width(), 4):
			var pixel := image.get_pixel(x, y)
			if maxf(absf(pixel.r-background.r), maxf(absf(pixel.g-background.g), absf(pixel.b-background.b))) > 0.045:
				different += 1
	return different > 30

func _model_inside_frame(image: Image, background: Color) -> bool:
	if image == null or image.is_empty():
		return false
	var bounds := Rect2i(image.get_width(), image.get_height(), -1, -1)
	for y in image.get_height():
		for x in image.get_width():
			var pixel := image.get_pixel(x, y)
			var difference := maxf(absf(pixel.r-background.r), maxf(absf(pixel.g-background.g), absf(pixel.b-background.b)))
			if difference <= 0.20:
				continue
			if bounds.size.x < 0:
				bounds.position = Vector2i(x, y)
				bounds.size = Vector2i(1, 1)
			else:
				var left := mini(bounds.position.x, x)
				var top := mini(bounds.position.y, y)
				var right := maxi(bounds.end.x, x + 1)
				var bottom := maxi(bounds.end.y, y + 1)
				bounds = Rect2i(left, top, right - left, bottom - top)
	return bounds.size.x > 0 and bounds.position.x >= 2 and bounds.position.y >= 2 and bounds.end.x <= image.get_width() - 2 and bounds.end.y <= image.get_height() - 2

func _save_viewport(viewport: SubViewport, filename: String) -> void:
	var image := viewport.get_texture().get_image()
	if image == null or image.is_empty():
		_fail("No rendered frame for %s" % filename)
		return
	var path := ProjectSettings.globalize_path(output_dir.path_join(filename))
	var error := image.save_png(path)
	if error != OK:
		_fail("Could not save %s" % filename)
	else:
		print("SCREENSHOT ", path)

func _fail(message: String) -> void:
	failures += 1
	push_error(message)
