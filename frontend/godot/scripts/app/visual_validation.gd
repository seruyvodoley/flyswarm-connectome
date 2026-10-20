extends SceneTree
var app
var failures=0
var screenshot_dir := ""
func check(condition: bool,message: String):
	if not condition:failures+=1;push_error(message)
func _initialize():call_deferred("run")
func capture(name):
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(screenshot_dir.path_join(name+".png"))
func run():
	app=root.get_node("AppState")
	screenshot_dir=OS.get_environment("FLYSWARM_QA_OUT")
	if screenshot_dir=="":screenshot_dir=ProjectSettings.globalize_path("res://../../artifacts/visual_validation")
	DirAccess.make_dir_recursive_absolute(screenshot_dir)
	for language in ["en","ru"]:
		app.settings.language=language
		for page in ["MainMenu","HistoricalBattleSetup","Settings","ResearchLab","TrainingMenu","TestRangeSetup","ReplayBrowser"]:
			app.show_page(page)
			await capture(language+"-"+page)
	for appearance in ["dark","light"]:
		app.settings.appearance=appearance
		for page in ["MainMenu","Settings","OpenDayMain","MarlLaboratory"]:
			app.show_page(page)
			await capture(appearance+"-"+page)
			if page=="MarlLaboratory":
				var tab_list=app.view.find_children("*","TabContainer",true,false)
				if not tab_list.is_empty():
					var tabs=tab_list[0] as TabContainer
					tabs.current_tab=1
					await capture(appearance+"-MarlPython")
	app.settings.appearance="dark"
	app.configure("battle");app.session.seconds=60;app.launch()
	for frame in range(20):await process_frame
	app.battle.set_physics_process(false)
	for size in [Vector2i(1280,720),Vector2i(1280,800),Vector2i(1440,900),Vector2i(1920,1080),Vector2i(2560,1440)]:
		DisplayServer.window_set_size(size)
		await capture("overhead-"+str(size.x))
	for mode in [1,2,3,0]:
		app.battle.cycle_camera()
		await process_frame
		await capture("camera-"+str(mode))
		check(app.battle.gunner_reticle.visible==(app.battle.camera_mode in [1,2]),"Shared battle reticle appears only in third-person, gunner and sniper camera modes")
	app.battle.audio_mode="team_audio"
	app.battle.replay_mode=true
	app.battle.ingest_communication({"sample":1,"events":[{"sender":0,"receiver":1,"raw":2.0,"received":.1,"distance_m":20.0},{"sender":8,"receiver":9,"raw":1.0,"received":.06,"distance_m":20.0}]})
	for mode in [1,2,3,0]:
		app.battle.cycle_comms()
		await capture("comms-"+str(mode))
	for mode in [0,3]:
		app.battle.comm_view=mode
		var start=Time.get_ticks_usec()
		for i in range(100):app.battle.refresh_comm_panel()
		print("COMM UI mean ms mode=",mode," ",(Time.get_ticks_usec()-start)/100000.0)
	app.stop_session();app.clear_view();await process_frame
	print("VISUAL VALIDATION failures=",failures)
	quit(0 if failures==0 else 1)
