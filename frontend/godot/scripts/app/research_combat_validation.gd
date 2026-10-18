extends Node

const SessionConfig = preload("res://scripts/app/session_config.gd")
const BattleScene = preload("res://scenes/Battle.tscn")

var failures := 0
var test_results: Array[Dictionary] = []

func _ready() -> void:
	call_deferred("run")

func check(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error(message)

func run() -> void:
	var config = SessionConfig.new()
	config.mode = "range"
	config.map = "test_range"
	config.range_mode = "armour"
	config.range_distance = 80
	config.training_vehicle = "t34_85"
	config.target_vehicle = "t34_85"
	config.seconds = 20.0
	var battle = BattleScene.instantiate()
	battle.session_config = config
	get_tree().root.add_child(battle)
	await get_tree().process_frame
	await get_tree().process_frame
	battle.paused = true
	check(battle.vehicles.size() >= 9, "range scene must spawn the real shooter and target")
	if battle.vehicles.size() < 9:
		get_tree().quit(1)
		return
	var shooter = battle.vehicles[0]
	var target = battle.vehicles[8]
	await test_shot(battle, shooter, target, "A_stationary_vs_stationary", false, false)
	await test_shot(battle, shooter, target, "B_stationary_vs_moving_target", true, false)
	await test_shot(battle, shooter, target, "C_moving_shooter_vs_stationary", false, true)
	await test_mutual_engagement(battle, shooter, target)
	print("RESEARCH_COMBAT_VALIDATION failures=", failures)
	write_report()
	battle.queue_free()
	await get_tree().process_frame
	get_tree().quit(1 if failures else 0)

func test_shot(battle: Node, shooter: Node, target: Node, label: String,
		move_target: bool, move_shooter: bool) -> void:
	if not target.alive:
		target.reset_destroyed_state()
	for key in target.modules:
		target.modules[key] = true
		target.module_damage[key] = 0.0
	target.impact_history.clear()
	target.last_impact = {}
	target.position = Vector3(0.0, 0.1, 40.0)
	target.rotation.y = PI
	target.velocity = Vector3.ZERO
	target.speed = 0.0
	target.turret_angle = 0.0
	target.gun_angle = 0.0
	target.turret.rotation.y = 0.0
	target.gun.rotation.x = 0.0
	shooter.position = Vector3(0.0, 0.1, -40.0)
	shooter.rotation.y = 0.0
	shooter.velocity = Vector3.ZERO
	shooter.speed = 0.0
	shooter.turret_angle = 0.0
	shooter.turret.rotation.y = 0.0
	shooter.gun_angle = 0.0
	shooter.gun.rotation.x = 0.0
	shooter.reload_left = 0.0
	shooter.ammo_left = 1
	shooter.velocity = Vector3(0.0, 0.0, 4.0) if move_shooter else Vector3.ZERO
	await get_tree().physics_frame
	var aim_point: Vector3 = target.global_position + Vector3(0.0, 1.5, 0.0)
	var delta: Vector3 = aim_point - shooter.muzzle.global_position
	shooter.gun_angle = atan2(delta.y, Vector2(delta.x, delta.z).length())
	shooter.gun.rotation.x = -shooter.gun_angle
	await get_tree().physics_frame
	var initial_position: Vector3 = shooter.muzzle.global_position
	var direction: Vector3 = shooter.muzzle.global_basis.z.normalized()
	print("COMBAT_TEST_SETUP case=", label, " distance_m=", initial_position.distance_to(aim_point),
		" angle_error_deg=", rad_to_deg(acos(clampf(direction.dot((aim_point-initial_position).normalized()), -1.0, 1.0))))
	battle.fire(shooter)
	if move_shooter:
		var fired_speed: float = battle.shells.back().velocity.length()
		var nominal_speed: float = float(shooter.cfg.ammo_data.muzzle_velocity_m_s)
		check(fired_speed > nominal_speed + 0.005,
			"moving-platform shot must inherit vehicle velocity")
	var max_steps := 40
	while not battle.shells.is_empty() and max_steps > 0:
		await get_tree().physics_frame
		if move_target:
			target.velocity = Vector3(4.0, 0.0, 0.0)
			target.move_and_slide()
		if move_shooter:
			shooter.velocity = Vector3(0.0, 0.0, 4.0)
			shooter.move_and_slide()
		battle.step_shells(0.02)
		max_steps -= 1
	var impact: Dictionary = target.last_impact
	var hit_vehicle = str(impact.get("shot_id", "")) != ""
	var damaged_module := false
	check(hit_vehicle, "%s must collide with the actual vehicle armor" % label)
	if hit_vehicle:
		check(impact.has("penetrated") and impact.has("zone"), "%s must register armor outcome and zone" % label)
		for value in target.module_damage.values():
			damaged_module = damaged_module or float(value) > 0.0
		check(not bool(impact.get("penetrated", false)) or damaged_module or not target.alive,
			"%s penetrating hit must damage a module or destroy target" % label)
		print("COMBAT_TEST_HIT case=", label, " outcome=", impact.get("outcome"),
			" zone=", impact.get("zone"), " penetrated=", impact.get("penetrated"),
			" damage=", target.module_damage, " alive=", target.alive)
	else:
		print("COMBAT_TEST_MISS case=", label, " shells_remaining=", battle.shells.size())
	test_results.append({"case": label, "passed": hit_vehicle and (not bool(impact.get("penetrated", false)) or damaged_module or not target.alive),
		"distance_m": initial_position.distance_to(aim_point), "angle_error_deg": rad_to_deg(acos(clampf(direction.dot((aim_point-initial_position).normalized()), -1.0, 1.0))),
		"impact": impact.duplicate(true), "module_damage": target.module_damage.duplicate(true), "target_alive": target.alive,
		"moving_target": move_target, "moving_shooter": move_shooter})

func test_mutual_engagement(battle: Node, first: Node, second: Node) -> void:
	for tank in [first, second]:
		if not tank.alive:
			tank.reset_destroyed_state()
		for key in tank.modules:
			tank.modules[key] = true
			tank.module_damage[key] = 0.0
		tank.impact_history.clear()
		tank.last_impact = {}
		tank.speed = 0.0
		tank.velocity = Vector3.ZERO
		tank.reload_left = 0.0
		tank.ammo_left = 1
		for key in tank.modules: tank.modules[key] = true
	first.position = Vector3(0.0, 0.1, -40.0)
	first.rotation.y = 0.0
	second.position = Vector3(0.0, 0.1, 40.0)
	second.rotation.y = PI
	first.turret_angle = 0.0
	second.turret_angle = 0.0
	first.turret.rotation.y = 0.0
	second.turret.rotation.y = 0.0
	await get_tree().physics_frame
	for tank in [first, second]:
		var aim_point: Vector3 = (second if tank == first else first).global_position + Vector3(0.0, 1.5, 0.0)
		var delta: Vector3 = aim_point - tank.muzzle.global_position
		tank.gun_angle = atan2(delta.y, Vector2(delta.x, delta.z).length())
		tank.gun.rotation.x = -tank.gun_angle
	await get_tree().physics_frame
	var verified_range: float = first.muzzle.global_position.distance_to(second.global_position + Vector3(0.0, 1.5, 0.0))
	print("COMBAT_TEST_SETUP case=D_mutual_engagement range_m=", verified_range)
	battle.fire(first)
	battle.fire(second)
	var max_steps := 40
	while not battle.shells.is_empty() and max_steps > 0:
		await get_tree().physics_frame
		battle.step_shells(0.02)
		max_steps -= 1
	check(str(first.last_impact.get("shot_id", "")) != "", "D engagement: second tank shell must hit first tank")
	check(str(second.last_impact.get("shot_id", "")) != "", "D engagement: first tank shell must hit second tank")
	print("COMBAT_TEST_MUTUAL range_m=", verified_range,
		" first_hit=", not str(first.last_impact.get("shot_id", "")).is_empty(),
		" second_hit=", not str(second.last_impact.get("shot_id", "")).is_empty())
	test_results.append({"case": "D_mutual_engagement", "passed": not str(first.last_impact.get("shot_id", "")).is_empty() and not str(second.last_impact.get("shot_id", "")).is_empty(),
		"distance_m": verified_range, "first_impact": first.last_impact.duplicate(true),
		"second_impact": second.last_impact.duplicate(true), "first_alive": first.alive, "second_alive": second.alive})

func write_report() -> void:
	var root_path := ProjectSettings.globalize_path("res://../../results/research")
	DirAccess.make_dir_recursive_absolute(root_path)
	var output_path := root_path.path_join("controlled-combat-validation-%d.json" % int(Time.get_unix_time_from_system()))
	var report := {"schema": "flyswarm.controlled_combat_validation.v1", "technical_test_only": true,
		"scientific_sample": false, "synthetic_hits": false, "model": "t34_85", "range_mode": "flat 80 m armour range",
		"physics_ticks_per_second": 50, "overall_passed": failures == 0, "cases": test_results}
	var file := FileAccess.open(output_path, FileAccess.WRITE)
	if file == null:
		push_error("Could not write controlled combat test report: " + output_path)
		return
	file.store_string(JSON.stringify(report, "\t") + "\n")
	file.close()
	print("CONTROLLED_COMBAT_REPORT ", output_path)
