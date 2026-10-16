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
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(output_dir))
	var app = root.get_node("AppState")
	app.show_page("OpenDayMain")
	await _frames(8)
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
	await _validate_open_day_vehicle_choices(app.view)
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
	for degrees in [0, 90, 180, 270, 360]:
		fly.set_yaw_degrees(float(degrees))
		await _frames(3)
		var axis: Vector3 = fly.get_yaw_axis()
		if absf(axis.dot(Vector3.UP)) < 0.999:
			_fail("Fly yaw pivot is not rotating about world Y at %d degrees" % degrees)
		if not capture_enabled:continue
		var viewport := fly.get_child(0) as SubViewport
		_save_viewport(viewport, "fly-%03d.png" % degrees)
		if not _has_foreground(viewport.get_texture().get_image(), Color("101817")):
			_fail("Fly preview rendered no visible model at %d degrees" % degrees)

func _capture_vehicle_switches(preview: VehiclePreview) -> void:
	for index in 30:
		var id: String = PREVIEW_IDS[index % PREVIEW_IDS.size()]
		preview.set_vehicle(id)
		await _frames(3)
		if not is_instance_valid(preview.preview_model) or preview.preview_model.name != "Preview_%s" % id:
			_fail("VehiclePreview did not load requested model %s on switch %d" % [id, index + 1])
		if preview.turntable.get_child_count() != 1:
			_fail("VehiclePreview leaked model nodes after switch %d" % (index + 1))
		if capture_enabled and index in [27, 28, 29]:
			var viewport := preview.get_child(0) as SubViewport
			await _frames(15)
			preview._request_viewport_frame()
			await RenderingServer.frame_post_draw
			_save_viewport(viewport, "vehicle-%s.png" % id)
			if not _has_foreground(viewport.get_texture().get_image(), Color("101817")):
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
			turret.rotation.y += 0.25
			turret.force_update_transform()
			muzzle.force_update_transform()
			if muzzle.global_position.distance_to(muzzle_before) < 0.05:
				_fail("Turret does not move the muzzle on %s" % id)
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
				_fail("Separate track loops are missing on the T-34/85 pilot")
			if model.find_children("WheelGeometry*", "MeshInstance3D", true, false).size() < 12:
				_fail("Individual T-34/85 wheel rollers are missing")
		if id in ["tiger_i", "is2_1944", "panther_g"]:
			for part_name in ["HullGeometry", "GunBarrel", "TrackLeft", "TrackRight"]:
				if model.find_child(part_name, true, false) == null:
					_fail("Required mechanical mesh %s is missing on %s" % [part_name, id])
		if id == "tiger_i" and model.find_children("Wheel*", "MeshInstance3D", true, false).size() < 12:
			_fail("Individual Tiger I wheel meshes are missing")
		if id in ["is2_1944", "panther_g"] and (model.find_child("RoadWheelsLeft", true, false) == null or model.find_child("RoadWheelsRight", true, false) == null):
			_fail("Separate left and right running gear is missing on %s" % id)
		var materials := {}
		for node in model.find_children("*", "MeshInstance3D", true, false):
			var mesh := node as MeshInstance3D
			for surface in mesh.mesh.get_surface_count():
				var material := mesh.get_surface_override_material(surface)
				if material is ShaderMaterial:
					materials[material.get_instance_id()] = true
		if materials.size() < 2:
			_fail("Materials are shared instead of per-surface on %s" % id)
		Appearance.set_destroyed(model, id, true)
		var destroyed_mat := _first_override(model)
		if destroyed_mat == null or not destroyed_mat.get_shader_parameter("charred"):
			_fail("Destroyed appearance missing for %s" % id)
		Appearance.set_destroyed(model, id, false)
		var restored_mat := _first_override(model)
		if restored_mat == null or restored_mat.get_shader_parameter("charred"):
			_fail("Livery did not restore after reset for %s" % id)
		model.queue_free()
	await process_frame

func _first_override(model: Node3D) -> ShaderMaterial:
	for node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh := node as MeshInstance3D
		for surface in mesh.mesh.get_surface_count():
			var material := mesh.get_surface_override_material(surface)
			if material is ShaderMaterial:
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
