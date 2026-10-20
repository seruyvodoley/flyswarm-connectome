extends SceneTree

## Repeatable local frame-time sampler. Run with --mode=menu or --mode=battle-rule
	## and optionally --seconds=30. battle-rule is a render/control baseline;
	## battle-brain is a separate real MaleCNS measurement.
const OUTPUT_DIR := "res://../../artifacts/performance"
const WARMUP_SECONDS := 5.0

var frame_ms: Array[float] = []
var shot_frame_ms: Array[float] = []
var impact_frame_ms: Array[float] = []
var process_ms: Array[float] = []
var physics_ms: Array[float] = []
var draw_calls: Array[float] = []
var rendered_objects: Array[float] = []
var primitives: Array[float] = []
var video_memory: Array[float] = []
var static_memory: Array[float] = []
var brain_tick_ms: Array[float] = []
var ipc_latency_ms: Array[float] = []
var disabled_previews: Array[String] = []
var graphics_overrides := {}
var last_brain_response := -1
var preview_rate_override := -1.0
var exercise_fire := false
var camera_override := -1

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var mode := "menu"
	var seconds := 30.0
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--mode="):
			mode = arg.trim_prefix("--mode=")
		elif arg.begins_with("--seconds="):
			seconds = maxf(5.0, float(arg.trim_prefix("--seconds=")))
		elif arg.begins_with("--disable-preview="):
			for name in arg.trim_prefix("--disable-preview=").split(",", false):
				disabled_previews.append(name)
		elif arg.begins_with("--vegetation="):
			graphics_overrides["vegetation"] = clampf(float(arg.trim_prefix("--vegetation=")), 0.25, 1.0)
		elif arg.begins_with("--shadows="):
			graphics_overrides["shadows"] = arg.trim_prefix("--shadows=") != "off"
		elif arg.begins_with("--preview-rate="):
			preview_rate_override = maxf(0.0, float(arg.trim_prefix("--preview-rate=")))
		elif arg == "--exercise-fire":
			exercise_fire = true
		elif arg.begins_with("--camera="):
			camera_override = clampi(int(arg.trim_prefix("--camera=")), 0, 3)
	if mode not in ["menu", "battle-rule", "battle-brain"]:
		push_error("Unsupported profile mode: %s" % mode)
		quit(2)
		return
	var app = root.get_node("AppState")
	app.settings.fullscreen = false
	app.settings.resolution = 0
	for key in graphics_overrides:
		app.settings[key] = graphics_overrides[key]
	app.apply_settings()
	if mode == "menu":
		app.show_page("OpenDayMain")
		for preview in app.view.find_children("*", "SubViewportContainer", true, false):
			if preview_rate_override >= 0.0 and preview.get("preview_render_hz") != null:
				preview.preview_render_hz = preview_rate_override
			var kind := "fly" if preview.has_method("set_yaw_degrees") else "vehicle" if preview.has_method("set_vehicle") else ""
			if kind in disabled_previews:
				preview.set_process(false)
				var subviewport := preview.get_child(0) as SubViewport
				subviewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
	elif mode == "battle-rule":
		app.configure_demo("t34_85")
		# This measures the same battle scene without the external brain process;
		# it is a render/control baseline only, not a MaleCNS performance claim.
		app.session.red_controller = "rule"
		app.session.blue_controller = "rule"
		app.launch()
	else:
		app.configure_demo("t34_85")
		app.launch()
		var wait_started := Time.get_ticks_msec()
		while not is_instance_valid(app.battle) and app.backend_state != "ERROR" and Time.get_ticks_msec() - wait_started < 120000:
			await process_frame
		if not is_instance_valid(app.battle):
			push_error("Real MaleCNS battle did not start: %s" % app.loading_message)
			quit(1)
			return
	await _wait_seconds(WARMUP_SECONDS)
	if camera_override >= 0 and is_instance_valid(app.battle):
		app.battle.camera_mode = camera_override
		app.battle.last_camera_mode = -1
	frame_ms.clear()
	shot_frame_ms.clear()
	impact_frame_ms.clear()
	process_ms.clear()
	physics_ms.clear()
	draw_calls.clear()
	rendered_objects.clear()
	primitives.clear()
	video_memory.clear()
	static_memory.clear()
	brain_tick_ms.clear()
	ipc_latency_ms.clear()
	if is_instance_valid(app.battle):
		app.battle.bridge.tick_ms_samples.clear()
		app.battle.bridge.latency_ms_samples.clear()
		last_brain_response=app.battle.bridge.responses_received
		_sample_start_responses=app.battle.bridge.responses_received
		_sample_start_match_wall=maxf(0.0,float(Time.get_ticks_usec()-app.battle.start_wall)/1000000.0)
	else:
		last_brain_response=-1
		_sample_start_responses=0
		_sample_start_match_wall=0.0
	_sample_start_sim=app.battle.sim_time if is_instance_valid(app.battle) else 0.0
	_sample_start_frame=app.battle.frame if is_instance_valid(app.battle) else 0
	_sample_started_usec = Time.get_ticks_usec()
	var started := _sample_started_usec
	while float(Time.get_ticks_usec() - started) / 1000000.0 < seconds:
		if exercise_fire and mode == "battle-rule" and is_instance_valid(app.battle) and app.battle.sim_time > 4.0:
			# Synthetic fire input exercises the same fire -> projectile -> hit path;
			# it is a repeatable profiling stimulus, not a controller test.
			app.battle.mouse_fire_pending = true
		var shots_before := _combat_event_count(app.battle, "shots") if is_instance_valid(app.battle) else 0
		var impacts_before := _combat_event_count(app.battle, "impacts") if is_instance_valid(app.battle) else 0
		var frame_started := Time.get_ticks_usec()
		await process_frame
		if mode.begins_with("battle") and is_instance_valid(app.battle) and app.battle.finished_report:
			break
		var elapsed_frame_ms := float(Time.get_ticks_usec() - frame_started) / 1000.0
		frame_ms.append(elapsed_frame_ms)
		if is_instance_valid(app.battle):
			if _combat_event_count(app.battle, "shots") > shots_before:shot_frame_ms.append(elapsed_frame_ms)
			if _combat_event_count(app.battle, "impacts") > impacts_before:impact_frame_ms.append(elapsed_frame_ms)
		if is_instance_valid(app.battle) and app.battle.bridge.responses_received != last_brain_response:
			last_brain_response = app.battle.bridge.responses_received
			var tick_ms = app.battle.bridge.last_reply.get("tick_ms", null)
			if tick_ms != null:
				brain_tick_ms.append(float(tick_ms))
			ipc_latency_ms.append(float(app.battle.bridge.latency_ms))
		_sample(Performance.TIME_PROCESS, process_ms)
		_sample(Performance.TIME_PHYSICS_PROCESS, physics_ms)
		_sample(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME, draw_calls)
		_sample(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME, rendered_objects)
		_sample(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME, primitives)
		_sample(Performance.RENDER_VIDEO_MEM_USED, video_memory)
		_sample(Performance.MEMORY_STATIC, static_memory)
	var report := _report(mode, seconds, app)
	var output_root := OS.get_environment("FLYSWARM_QA_OUT")
	if output_root == "": output_root = ProjectSettings.globalize_path(OUTPUT_DIR)
	DirAccess.make_dir_recursive_absolute(output_root)
	var path := output_root.path_join("%s-%s.json" % [mode, Time.get_datetime_string_from_system().replace(":", "-")])
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "  "))
	file.close()
	print("PERFORMANCE_PROFILE ", JSON.stringify(report))
	print("PERFORMANCE_PROFILE_FILE ", path)
	if mode != "menu":
		app.stop_session()
	quit(0)

func _wait_seconds(seconds: float) -> void:
	var started := Time.get_ticks_usec()
	while float(Time.get_ticks_usec() - started) / 1000000.0 < seconds:
		await process_frame

func _sample(monitor: int, target: Array[float]) -> void:
	target.append(float(Performance.get_monitor(monitor)))

func _combat_event_count(battle: Node, event_kind: String) -> int:
	var count := 0
	for vehicle in battle.vehicles:
		count += int(vehicle.metrics.get("shots", 0)) if event_kind == "shots" else vehicle.impact_history.size()
	return count

func _summary(values: Array[float]) -> Dictionary:
	if values.is_empty():
		return {"available": false}
	var ordered := values.duplicate()
	ordered.sort()
	var total := 0.0
	for value in values:
		total += value
	var p99_index := clampi(int(ceil(float(ordered.size()) * 0.99)) - 1, 0, ordered.size() - 1)
	return {"mean": total / values.size(), "p99": ordered[p99_index], "max": ordered[-1]}

func _report(mode: String, seconds: float, app: Node) -> Dictionary:
	var size := DisplayServer.window_get_size()
	var root_viewport := get_root().get_viewport()
	var presentation_hz := float(frame_ms.size()) / maxf(0.001, float(Time.get_ticks_usec() - int(_sample_started_usec)) / 1000000.0) if _sample_started_usec > 0 else 0.0
	var wall_elapsed := maxf(0.001,float(Time.get_ticks_usec()-int(_sample_started_usec))/1000000.0)
	if is_instance_valid(app.battle) and app.battle.finished_report:
		wall_elapsed=maxf(0.001,float(app.battle.report_cache.wall_seconds)-_sample_start_match_wall)
	var sim_elapsed: float = app.battle.sim_time-_sample_start_sim if is_instance_valid(app.battle) else 0.0
	var physics_steps: int = app.battle.frame-_sample_start_frame if is_instance_valid(app.battle) else 0
	var neural_responses: int = app.battle.bridge.responses_received-_sample_start_responses if is_instance_valid(app.battle) else 0
	return {
		"mode": mode,
		"requested_sample_seconds": seconds,
		"sampled_frames": frame_ms.size(),
		"presentation_fps": presentation_hz,
		"frame_ms": _summary(frame_ms),
		"shot_frame_count": shot_frame_ms.size(),
		"shot_frame_ms": _summary(shot_frame_ms),
		"impact_frame_count": impact_frame_ms.size(),
		"impact_frame_ms": _summary(impact_frame_ms),
		"synthetic_fire_input": exercise_fire,
		"camera_override": camera_override,
		"process_ms": _summary(_to_milliseconds(process_ms)),
		"physics_ms": _summary(_to_milliseconds(physics_ms)),
		"draw_calls": _summary(draw_calls),
		"rendered_objects": _summary(rendered_objects),
		"rendered_primitives": _summary(primitives),
		"video_memory_bytes": _summary(video_memory),
		"static_memory_bytes": _summary(static_memory),
		"male_cns_tick_ms_series": _summary(brain_tick_ms),
		"ipc_latency_ms_series": _summary(ipc_latency_ms),
		"sample_wall_elapsed_seconds": wall_elapsed,
		"sample_simulation_elapsed_seconds": sim_elapsed,
		"sample_realtime_factor": sim_elapsed/wall_elapsed,
		"sample_physics_steps": physics_steps,
		"sample_neural_responses": neural_responses,
		"sample_neural_response_rate_hz": neural_responses/wall_elapsed,
		"battle_simulation_seconds": app.battle.sim_time if is_instance_valid(app.battle) else null,
		"window_logical_px": [size.x, size.y],
		"screen_pixels": [DisplayServer.screen_get_size().x, DisplayServer.screen_get_size().y],
		"root_viewport_px": [root_viewport.size.x, root_viewport.size.y],
		"screen_scale": DisplayServer.screen_get_scale(),
		"vsync_mode": DisplayServer.window_get_vsync_mode(),
		"renderer": RenderingServer.get_video_adapter_name(),
		"display_backend": DisplayServer.get_name(),
		"godot_version": Engine.get_version_info(),
		"gpu_time": "not exposed by the active Godot renderer/API",
		"cpu_gpu_load": "not sampled by Godot; use Activity Monitor for a separate OS-level capture",
		"backend_state": app.backend_state,
		"male_cns_tick_ms": app.battle.bridge.last_reply.get("tick_ms", null) if is_instance_valid(app.battle) else null,
		"male_cns_request_count": app.battle.bridge.tick if is_instance_valid(app.battle) else null,
		"male_cns_response_count": app.battle.bridge.responses_received if is_instance_valid(app.battle) else null,
		"male_cns": "real FlyBrain(batch=1)" if mode == "battle-brain" else "not used" if mode == "battle-rule" else "not applicable",
		"subviewport_count": app.view.find_children("*", "SubViewport", true, false).size() if is_instance_valid(app.view) else 0,
		"disabled_previews": disabled_previews,
		"graphics_overrides": graphics_overrides,
		"preview_rate_hz": "always" if preview_rate_override == 0.0 else preview_rate_override if preview_rate_override > 0.0 else 30.0,
	}

func _to_milliseconds(values: Array[float]) -> Array[float]:
	var result: Array[float] = []
	for value in values:
		result.append(value * 1000.0)
	return result

var _sample_started_usec := 0
var _sample_start_sim := 0.0
var _sample_start_frame := 0
var _sample_start_responses := 0
var _sample_start_match_wall := 0.0
