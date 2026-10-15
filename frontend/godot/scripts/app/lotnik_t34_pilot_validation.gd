extends SceneTree

const Appearance = preload("res://scripts/vehicles/vehicle_appearance.gd")

var failures := 0

func _initialize() -> void:
	call_deferred("_run")

func _run() -> void:
	var packed := load("res://assets/vehicles/t34_85.glb") as PackedScene
	_check(packed != null, "candidate GLB imports as a PackedScene")
	if packed == null:
		quit(1)
		return
	var model := packed.instantiate() as Node3D
	root.add_child(model)
	await process_frame
	var hull := model.find_child("HullPivot", true, false) as Node3D
	var turret := model.find_child("TurretPivot", true, false) as Node3D
	var gun := model.find_child("GunElevationPivot", true, false) as Node3D
	var muzzle := model.find_child("Muzzle", true, false) as Node3D
	var left_track := model.find_child("TrackLeft", true, false)
	var right_track := model.find_child("TrackRight", true, false)
	_check(hull != null, "hull group is present")
	_check(turret != null, "turret is a separate pivot")
	_check(gun != null, "gun is a separate elevation pivot")
	_check(muzzle != null, "muzzle marker is present")
	_check(left_track != null and right_track != null, "left and right track loops remain separate")
	var meshes := model.find_children("*", "MeshInstance3D", true, false)
	_check(meshes.size() == 55, "41 source meshes and 14 wheel rollers are present (%d found)" % meshes.size())
	var wheel_nodes := model.find_children("WheelGeometry*", "MeshInstance3D", true, false)
	_check(wheel_nodes.size() == 14, "14 separate wheel rollers can use the existing spin animation")
	var surfaces := Appearance.apply(model, "t34_85")
	_check(surfaces > 0, "existing T-34/85 livery shader applies (%d surfaces)" % surfaces)
	if turret and gun and muzzle:
		var before_turret: Vector3 = muzzle.global_position
		turret.rotation.y += 0.25
		await process_frame
		var after_turret: Vector3 = muzzle.global_position
		_check(before_turret.distance_to(after_turret) > 0.15, "turret traverse moves the muzzle")
		var before_gun: Vector3 = muzzle.global_position
		gun.rotation.x += 0.10
		await process_frame
		_check(before_gun.distance_to(muzzle.global_position) > 0.02, "gun elevation moves the muzzle")
	print("LOTNIK_T34_PILOT_VALIDATION failures=%d meshes=%d livery_surfaces=%d" % [failures, meshes.size(), surfaces])
	quit(0 if failures == 0 else 1)

func _check(ok: bool, label: String) -> void:
	if ok:
		print("PASS ", label)
	else:
		failures += 1
		push_error("FAIL " + label)
