extends SceneTree

var frame_dir=""
var frame_index=0

func _initialize():
	call_deferred("run")

func record(seconds: float):
	for _frame in range(ceili(seconds*12.0)):
		await process_frame
		await RenderingServer.frame_post_draw
		var image=root.get_texture().get_image()
		image.save_jpg(frame_dir.path_join("frame%05d.jpg" % frame_index),.88)
		frame_index+=1
		await create_timer(1.0/12.0).timeout

func run():
	var app=root.get_node("AppState")
	frame_dir=ProjectSettings.globalize_path("res://../../artifacts/open_day_graphics/video_frames")
	DirAccess.make_dir_recursive_absolute(frame_dir)
	app.settings.language="ru"
	DisplayServer.window_set_size(Vector2i(1280,720))
	app.show_page("OpenDayMain")
	await record(3.0)
	app.show_page("HowItWorks")
	await record(3.0)
	app.open_day_menu()
	await record(2.0)
	app.configure_demo("t34_85")
	app.session.seconds=90.0
	app.launch()
	for _attempt in range(300):
		if is_instance_valid(app.battle) or app.backend_state=="ERROR":break
		await record(.1)
	if is_instance_valid(app.battle):
		app.battle.demo_intro_left=0.0
		app.battle.demo_intro.visible=false
		for _attempt in range(150):
			if app.battle.bridge.connected():break
			await record(.1)
		await record(10.0)
		if is_instance_valid(app.battle):app.battle.finish()
	for _attempt in range(80):
		if app.current_page=="DemoResult":break
		await record(.1)
	await record(4.0)
	app.stop_session()
	quit()
