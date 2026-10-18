extends SceneTree
var failures := 0
func _initialize() -> void:
	call_deferred("run")
func check(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error(message)
func run() -> void:
	var ids = OS.get_cmdline_user_args()
	if ids.is_empty(): ids = ["t34_85", "is2_1944", "panther_g", "tiger_i", "jagdpanther", "su100"]
	for id in ids:
		var model = load("res://assets/vehicles/%s.glb" % id).instantiate()
		root.add_child(model)
		await process_frame
		var hull = model.find_child("HullGeometry", true, false)
		var turret = model.find_child("TurretPivot", true, false)
		var casemate = id in ["jagdpanther", "su100"]
		var shell = hull if casemate else model.find_child("TurretGeometry", true, false)
		var gun = model.find_child("GunElevationPivot", true, false)
		var muzzle = model.find_child("Muzzle", true, false)
		check(hull != null and shell != null and turret != null and gun != null and muzzle != null, id+" required parts")
		if hull == null or shell == null or turret == null or gun == null or muzzle == null: continue
		check(casemate or shell.mesh.get_aabb().size.z < 3.6, id+" turret geometry excludes hull-length pieces")
		check(casemate or shell.mesh.get_aabb().size.y < 1.4, id+" turret geometry excludes running gear")
		check(gun.get_parent() == turret and muzzle.get_parent() == gun, id+" mechanical hierarchy")
		var fixed := {}
		for part in model.find_children("*", "MeshInstance3D", true, false):
			if not turret.is_ancestor_of(part): fixed[part] = part.global_transform
		check(muzzle.global_basis.z.normalized().dot((muzzle.global_position-gun.global_position).normalized()) > .999, id+" muzzle points along barrel")
		var start: Vector3 = muzzle.global_position
		turret.rotation.y = .16 if casemate else PI/2
		await process_frame
		check(start.distance_to(muzzle.global_position)>(.3 if casemate else 2.0),id+" muzzle traverses")
		for part in fixed: check(part.global_transform.is_equal_approx(fixed[part]),id+" fixed hull/track/wheel "+part.name)
		var yaw_position: Vector3 = muzzle.global_position
		gun.rotation.x = -.2
		await process_frame
		check(muzzle.global_position.y > yaw_position.y+.3,id+" positive elevation raises muzzle")
		var wheels = model.find_children("Wheel*", "MeshInstance3D", true, false)
		var expected = {"t34_85":24,"is2_1944":34,"panther_g":36,"tiger_i":36,"jagdpanther":36,"su100":24}
		check(wheels.size()==expected[id], id+" wheel count: "+str(wheels.size()))
		for wheel in wheels:
			var before: Vector3 = wheel.global_position
			wheel.rotate_x(.7)
			check(wheel.global_position.is_equal_approx(before), id+" wheel rotates on its axle")
		check(model.find_child("TrackLeft",true,false)!=null and model.find_child("TrackRight",true,false)!=null,id+" both tracks")
		print("REBUILT_MODEL ",id," wheels=",wheels.size()," fixed_meshes=",fixed.size())
		model.queue_free()
		await process_frame
	print("REBUILT_VEHICLE_VALIDATION failures=",failures)
	quit(1 if failures else 0)
