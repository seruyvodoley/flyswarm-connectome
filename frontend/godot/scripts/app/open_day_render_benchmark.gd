extends SceneTree
var baseline=""
var samples:Array[float]=[]
var calls:Array[float]=[]
func _initialize():call_deferred("run")
func run():
	var out=""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--baseline-script="):baseline=arg.trim_prefix("--baseline-script=")
		if arg.begins_with("--output="):out=arg.trim_prefix("--output=")
	var app=root.get_node("AppState");app.clear_view();app.configure_demo("t34_85")
	app.session.red_controller="rule";app.session.blue_controller="rule";app.session.record=false;app.session.battle_seed=204
	app.settings.vegetation=.6;app.settings.shadows=true
	root.content_scale_mode=Window.CONTENT_SCALE_MODE_VIEWPORT;root.content_scale_size=Vector2i(1280,800)
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED);DisplayServer.window_set_size(Vector2i(1280,800))
	var started=Time.get_ticks_usec()
	var b=load(baseline).new() if baseline!="" else load("res://scenes/Battle.tscn").instantiate()
	b.session_config=app.session;root.add_child(b)
	var generation=(Time.get_ticks_usec()-started)/1000.0
	b.set_physics_process(false);b.set_process(false);b.demo_intro_left=0;b.demo_intro.hide();b.sim_time=12;b.update_demo_smoke_screen()
	b.vehicles[0].position=Vector3(105,b.terrain.height_at(105,0)+.1,0)
	b.vehicles[8].position=Vector3(105,b.terrain.height_at(105,180)+.1,180)
	b.camera.position=Vector3(105,b.terrain.height_at(105,0)+8,-18);b.camera.look_at(Vector3(50,3,160));b.camera.far=1050
	await create_timer(4).timeout
	started=Time.get_ticks_usec();var previous=started
	while Time.get_ticks_usec()-started<20000000:
		await process_frame
		var now=Time.get_ticks_usec();samples.append((now-previous)/1000.0);previous=now
		calls.append(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
	var result={"source":"beta4" if baseline!="" else "beta5","viewport_px":root.get_texture().get_size(),"renderer":RenderingServer.get_video_adapter_name(),"display":DisplayServer.get_name(),"map_and_scene_generation_ms":generation,"frame_ms":b.sample_statistics(samples),"draw_calls":b.sample_statistics(calls)}
	result["fps"]=1000.0/float(result.frame_ms.mean)
	print("OPEN_DAY_RENDER ",JSON.stringify(result))
	if out!="":FileAccess.open(out,FileAccess.WRITE).store_string(JSON.stringify(result,"  "))
	quit()
