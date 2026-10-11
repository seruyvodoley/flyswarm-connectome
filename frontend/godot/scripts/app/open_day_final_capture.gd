extends SceneTree

const OUTPUT := "res://../../artifacts/open_day_final_validation"
var app
var failures := 0
var menu_fps := 0.0
var battle_fps := 0.0

func _initialize() -> void:
	call_deferred("run")

func _capture(name: String) -> void:
	for _frame in 8:
		await process_frame
	var image := root.get_texture().get_image()
	var error := image.save_png(ProjectSettings.globalize_path(OUTPUT.path_join(name)))
	if error != OK:
		failures += 1
		push_error("Could not save final validation capture: " + name)

func _sample_fps(frame_count: int) -> float:
	var total := 0.0
	for _frame in frame_count:
		await process_frame
		total += Engine.get_frames_per_second()
	return total / maxf(1.0, float(frame_count))

func run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUTPUT))
	DisplayServer.window_set_size(Vector2i(1280, 720))
	app = root.get_node("AppState")
	app.settings.language = "en"
	app.show_page("OpenDayMain")
	await _sample_fps(30)
	menu_fps = await _sample_fps(60)
	for id in ["t34_85", "panther_g", "tiger_i"]:
		app.stop_session()
		app.clear_view()
		app.configure_demo(id)
		app.launch()
		var battle = null
		for _attempt in 900:
			if is_instance_valid(app.battle):
				battle = app.battle
				break
			if app.backend_state == "ERROR":
				break
			await create_timer(0.1).timeout
		if battle == null:
			failures += 1
			push_error("Real MaleCNS battle did not start for " + id)
			continue
		battle.demo_intro_left = 0.0
		battle.demo_intro.visible = false
		var has_live_traces := false
		for _attempt in 150:
			if battle.bridge.connected() and battle.bridge.last_reply.has("traces"):
				has_live_traces = true
				break
			await create_timer(0.1).timeout
		if not has_live_traces:
			failures += 1
			push_error("Live MaleCNS telemetry missing for " + id)
			app.stop_session()
			continue
		if id == "t34_85":
			battle_fps = await _sample_fps(60)
		await _capture("battle-%s.png" % id)
		battle.finish(false)
		app.stop_session()
		app.clear_view()
		await process_frame

	for destroyed_id in [8, 0]:
		app.stop_session()
		app.clear_view()
		app.configure_demo("t34_85")
		app.session.seconds = 90.0
		app.launch()
		var battle = null
		for _attempt in 900:
			if is_instance_valid(app.battle):
				battle = app.battle
				break
			if app.backend_state == "ERROR":
				break
			await create_timer(0.1).timeout
		if battle == null:
			failures += 1
			push_error("Real MaleCNS battle did not start for result capture")
			continue
		battle.demo_intro_left = 0.0
		battle.demo_intro.visible = false
		for _attempt in 150:
			if battle.bridge.connected() and battle.bridge.last_reply.has("traces"):
				break
			await create_timer(0.1).timeout
		if not battle.bridge.connected():
			failures += 1
			push_error("Real MaleCNS did not connect for result capture")
			app.stop_session()
			continue
		battle.vehicles[destroyed_id].destroy_vehicle(8 if destroyed_id == 0 else 0)
		battle.finish()
		var human_won: bool = destroyed_id == 8
		var target_phrase := "YOU DEFEATED THE FLY" if human_won else "THE FLY WON"
		await process_frame
		var labels: Array[Node] = app.view.find_children("*", "Label", true, false)
		var found := false
		for label in labels:
			found = found or (label as Label).text == target_phrase
		if not found:
			failures += 1
			push_error("Expected production result title missing: " + target_phrase)
		await _capture("result-%s.png" % ("human-win" if human_won else "fly-win"))
		app.stop_session()
		app.clear_view()
		await process_frame

	print("PERFORMANCE GUI avg_fps menu=", round_to_tenth(menu_fps), " battle=", round_to_tenth(battle_fps))
	print("OPEN DAY FINAL CAPTURE failures=", failures)
	quit(0 if failures == 0 else 1)

func round_to_tenth(value: float) -> float:
	return snappedf(value, 0.1)
