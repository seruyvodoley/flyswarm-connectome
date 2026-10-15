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

func command_for_key(battle,keycode: Key) -> Array:
	var event=InputEventKey.new()
	event.physical_keycode=keycode
	event.pressed=true
	Input.parse_input_event(event)
	await process_frame
	var command=battle.manual_commands()
	var release=event.duplicate()
	release.pressed=false
	Input.parse_input_event(release)
	await process_frame
	return command


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
	battle.camera_mode=1
	battle.update_vehicle_status()
	check(battle.vehicle_status_panel.visible and battle.vehicle_status_map.vehicle==battle.vehicles[battle.selected],"Range shows the selected tank's 2D module map")
	check(battle.impact_killcam.offset_bottom<battle.previous_vehicle_button.offset_top and battle.impact_killcam.offset_bottom<battle.next_vehicle_button.offset_top,"Impact camera clears tank selection buttons")
	var forward=await command_for_key(battle,KEY_W);var reverse=await command_for_key(battle,KEY_S)
	check(forward[0]>0.0 and reverse[0]<0.0,"Range forward and reverse controls work")
	var left=await command_for_key(battle,KEY_A);var right=await command_for_key(battle,KEY_D)
	check(left[2]<0.0 and right[2]>0.0,"Range left and right hull steering work")
	var traverse_left=await command_for_key(battle,KEY_Q);var traverse_right=await command_for_key(battle,KEY_E)
	check(traverse_left[3]<0.0 and traverse_right[3]>0.0,"Range turret left and right controls work")
	var lower=await command_for_key(battle,KEY_F);var raise=await command_for_key(battle,KEY_R)
	check(lower[4]<0.0 and raise[4]>0.0,"Range gun depression and elevation work")
	var keyboard_fire=await command_for_key(battle,KEY_SPACE)
	check(keyboard_fire[5]>0.0,"Range keyboard fire works alongside LMB")
	var range_tank=battle.vehicles[0]
	var old_turret_target=range_tank.turret_angle
	var old_gun_target=range_tank.gun_angle
	var right_button=InputEventMouseButton.new()
	right_button.button_index=MOUSE_BUTTON_RIGHT
	right_button.pressed=true
	right_button.position=Vector2(640,360)
	Input.parse_input_event(right_button)
	await process_frame
	var mouse_motion=InputEventMouseMotion.new()
	mouse_motion.position=Vector2(670,340)
	mouse_motion.relative=Vector2(30,-20)
	Input.parse_input_event(mouse_motion)
	await process_frame
	check(range_tank.manual_turret_target>old_turret_target and range_tank.manual_gun_target>old_gun_target,"Range RMB drag aims turret right and gun up")
	var right_release=right_button.duplicate()
	right_release.pressed=false
	Input.parse_input_event(right_release)
	await process_frame

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
	check(not battle.range_killcam_panel.visible,"Range impact summary closes with the timed camera")
	battle.camera_mode=0
	battle.start_range_killcam(target,shell,target.global_position)
	check(not battle.range_killcam_active and not battle.range_killcam_panel.visible,"Overview never opens a damage camera")
	battle.camera_mode=1

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
