extends SceneTree

var app
var results=[]
var failures=0
var match_count=5
var match_seconds=120.0

func check(ok: bool,message: String):
	if not ok:
		failures+=1
		push_error(message)

func _initialize():call_deferred("run")

func run():
	var output_override=""
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--matches="):match_count=clampi(int(argument.trim_prefix("--matches=")),1,5)
		if argument.begins_with("--seconds="):match_seconds=clampf(float(argument.trim_prefix("--seconds=")),20.0,120.0)
		if argument.begins_with("--output="):output_override=argument.trim_prefix("--output=")
	app=root.get_node("AppState")
	for match_index in range(match_count):
		app.configure_demo("t34_85")
		app.session.seconds=match_seconds
		app.session.record=false
		app.session.battle_seed=204+match_index
		app.session.map_seed=1944+match_index
		await app.launch()
		var wait_start=Time.get_ticks_msec()
		while not is_instance_valid(app.battle) and Time.get_ticks_msec()-wait_start<120000:
			await create_timer(.1).timeout
		check(is_instance_valid(app.battle),"Match %d starts with the real backend" % (match_index+1))
		if not is_instance_valid(app.battle):break
		var battle=app.battle
		check(battle.is_demo and battle.requires_brain,"Match %d is a live Open Day MaleCNS battle" % (match_index+1))
		battle.demo_intro_left=0.0
		battle.demo_intro.visible=false
		var first_response=false
		var connection_held=true
		var timeout_at=Time.get_ticks_msec()+900000
		while not battle.finished_report and Time.get_ticks_msec()<timeout_at:
			await create_timer(.2).timeout
			if battle.bridge.responses_received>0:first_response=true
			if battle.bridge.responses_received>0 and not battle.bridge.connected() and not battle.finished_report:connection_held=false
			if battle.vehicles[0].weapon_block_reason() in ["gunner","breech"]:check(false,"Match %d player lost weapon control to a disabled module" % (match_index+1))
			if not battle.vehicles[0].modules.get("engine",true) or not battle.vehicles[0].modules.get("track_left",true) or not battle.vehicles[0].modules.get("track_right",true):check(false,"Match %d player mobility module was disabled" % (match_index+1))
		check(battle.finished_report,"Match %d reached a completed battle result" % (match_index+1))
		var report=battle.report_cache.duplicate(true)
		var fly=report.get("vehicles",[])[8] if report.get("vehicles",[]).size()>8 else {}
		var player=report.get("vehicles",[])[0] if report.get("vehicles",[]).size()>0 else {}
		var metrics=fly.get("metrics",{})
		var summary={
			"match":match_index+1,
			"seconds":report.get("time",0.0),
			"wall_seconds":report.get("wall_seconds",0.0),
			"realtime_factor":report.get("realtime_factor",0.0),
			"male_cns_tick_ms":report.get("brain_tick_ms"),
			"male_cns_tick_stats":report.get("male_cns_tick_ms",{}),
			"ipc_stats":report.get("ipc_latency_ms",{}),
			"opponent_distance_m":metrics.get("distance_travelled",0.0),
			"opponent_target_visible_s":metrics.get("target_visible_s",0.0),
			"opponent_final_position":fly.get("position",[]),
			"opponent_moving_fraction":1.0-float(metrics.get("stationary_s",0.0))/maxf(1.0,float(report.get("time",0.0))),
			"opponent_stuck_recoveries":metrics.get("stuck_recoveries",0),
			"opponent_shots":metrics.get("shots",0),
			"opponent_penetrations":metrics.get("penetrations",0),
			"player_shots":player.get("metrics",{}).get("shots",0),
			"neural_responses":report.get("neural_steps",0),
			"backend_disconnects":report.get("backend_disconnects",0),
			"male_cns_trace_summary":report.get("demo_male_cns_trace_summary",{}),
			"navigation_intervention_mean":report.get("demo_navigation_intervention_mean",0.0),
			"male_cns_connected":connection_held,
			"real_neural_response_seen":first_response,
			"completion":report.get("completion","missing")
		}
		results.append(summary)
		check(float(summary.seconds)>=minf(60.0,match_seconds*.85),"Match %d lasted for the configured validation interval" % (match_index+1))
		check(float(summary.opponent_distance_m)>=20.0,"Match %d MaleCNS opponent moved at least 20 metres" % (match_index+1))
		check(float(summary.opponent_moving_fraction)>=.20,"Match %d MaleCNS moved during at least 20%% of the battle" % (match_index+1))
		check(bool(summary.real_neural_response_seen) and int(summary.neural_responses)>5,"Match %d used repeated real neural responses" % (match_index+1))
		check(bool(summary.male_cns_connected),"Match %d kept its real MaleCNS connection alive" % (match_index+1))
		check(report.get("backend_metadata",{}).get("neuron_count",0)==166700,"Match %d used the full MaleCNS population" % (match_index+1))
		print("OPEN DAY MATCH ",JSON.stringify(summary))
		app.stop_session()
		await process_frame
	var output_path=output_override if output_override!="" else ProjectSettings.globalize_path("res://../../artifacts/performance/open_day_five_match_validation.json")
	DirAccess.make_dir_recursive_absolute(output_path.get_base_dir())
	FileAccess.open(output_path,FileAccess.WRITE).store_string(JSON.stringify({"matches":results,"failures":failures},"  "))
	print("OPEN DAY FIVE MATCH VALIDATION failures=",failures," results=",JSON.stringify(results))
	quit(0 if failures==0 and results.size()==match_count else 1)
