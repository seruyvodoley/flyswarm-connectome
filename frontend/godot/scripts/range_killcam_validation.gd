extends SceneTree

var failures=0
var app

func check(condition: bool,message: String):
	if not condition:
		failures+=1
		push_error(message)


func _initialize():
	call_deferred("run")


func wait_battle() -> bool:
	for attempt in range(300):
		if is_instance_valid(app.battle):
			return true
		await create_timer(.05).timeout

	return false


func run():
	app=root.get_node("AppState")

	app.configure("range")
	app.session.training_vehicle="tiger_i"
	app.session.target_vehicle="t34_85"
	app.session.range_distance=500
	app.session.target_angle=0
	app.session.range_mode="gunnery"
	app.session.seconds=30

	app.launch()

	check(
		await wait_battle(),
		"Test Range starts"
	)

	if not is_instance_valid(app.battle):
		quit(1)
		return

	var battle=app.battle

	check(
		battle.is_range,
		"Range mode active"
	)

	check(
		battle.vehicles.size()==16,
		"Range keeps normal vehicle array"
	)

	var target=battle.vehicles[8]

	check(
		target.alive,
		"Target starts alive"
	)

	check(
		is_instance_valid(
			battle.range_feedback
		),
		"Hit feedback UI exists"
	)

	check(
		is_instance_valid(
			battle.range_killcam_panel
		),
		"Killcam panel exists"
	)

	# Synthetic UI event only; this validation does not alter penetration
	# physics or claim to reproduce a real penetration.
	target.last_impact={
		"penetrated":true,
		"ricochet":false,
		"capability":145.0,
		"effective":90.0,
		"zone":"upper_front",
		"distance":500.0,
		"damaged":["ammo_rack"],
		"shell":"validation_ap"
	}

	target.modules["ammo_rack"]=false
	target.alive=false

	var shell={
		"owner":0,
		"origin":battle.vehicles[0].muzzle.global_position,
		"ammo":{"id":"validation_ap"}
	}

	battle.on_range_target_impact(
		target,
		shell,
		target.global_position+Vector3(0,1,0)
	)

	check(
		battle.range_killcam_active,
		"Destroyed target starts Killcam"
	)

	check(
		battle.range_killcam_panel.visible,
		"Killcam summary visible"
	)

	check(
		battle.range_killcam_path.visible,
		"Projectile path visible"
	)

	battle.end_range_killcam()

	check(
		not battle.range_killcam_active,
		"Killcam can be skipped"
	)

	battle.reset_range_target()

	check(
		target.alive,
		"Target restored alive"
	)

	check(
		target.modules["ammo_rack"],
		"Ammo rack restored"
	)

	check(
		target.modules["driver"]
		and target.modules["gunner"]
		and target.modules["commander"],
		"Crew restored"
	)

	check(
		not battle.range_killcam_panel.visible,
		"Killcam panel closes after reset"
	)

	# Target death must no longer finish the Test Range.
	target.alive=false
	await physics_frame

	check(
		not battle.finished_report,
		"Target destruction does not end Test Range"
	)

	print(
		"RANGE KILLCAM VALIDATION failures=",
		failures
	)

	app.menu()

	await process_frame

	quit(
		0 if failures==0 else 1
	)
