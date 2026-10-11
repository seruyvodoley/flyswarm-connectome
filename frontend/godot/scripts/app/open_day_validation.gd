extends SceneTree
var app
var failures=0
var screenshot_dir=""
var capture_enabled=false

func check(condition: bool,message: String):
	if not condition:failures+=1;push_error(message)
func _initialize():call_deferred("run")
func capture(name: String):
	for _i in 6:await process_frame
	if not capture_enabled:return
	var image=root.get_texture().get_image()
	image.save_png(screenshot_dir.path_join(name+".png"))

func run():
	capture_enabled=DisplayServer.get_name()!="headless"
	screenshot_dir=ProjectSettings.globalize_path("res://../../artifacts/performance/open_day_validation")
	DirAccess.make_dir_recursive_absolute(screenshot_dir)
	app=root.get_node("AppState")
	var original_language=app.settings.language
	for language in ["ru","en"]:
		app.settings.language=language
		for page in ["OpenDayMain","HowItWorks","Settings"]:
			app.show_page(page);await process_frame
			check(is_instance_valid(app.view),"Open Day page loads: "+page+" "+language)
			if page!="Settings":check(not app.view.find_children("*","SubViewportContainer",true,false).is_empty(),"Fly viewport visible: "+page)
			else:check(app.view.find_child("MaleCNSDatasetPath",true,false)!=null,"Dataset folder setting is available: "+language)
			if language=="ru":await capture("main-ru" if page=="OpenDayMain" else "how-it-works-ru")
	for size in [Vector2i(1280,720),Vector2i(1440,900),Vector2i(1920,1080),Vector2i(2560,1440)]:
		DisplayServer.window_set_size(size);app.show_page("OpenDayMain");await capture(str(size.x)+"x"+str(size.y))
		var buttons=app.view.find_children("*","Button",true,false)
		check(buttons.size()>=12,"Complete Open Day controls at "+str(size))
		var left=app.view.find_child("OpenDayLeft",true,false) as Control
		var center=app.view.find_child("OpenDayCenter",true,false) as Control
		var right=app.view.find_child("OpenDayRight",true,false) as Control
		check(left!=null and center!=null and right!=null,"Three Open Day columns exist at "+str(size))
		if left and center and right:
			check(not left.get_global_rect().intersects(center.get_global_rect()) and not center.get_global_rect().intersects(right.get_global_rect()),"Open Day columns do not overlap at "+str(size))
	app.settings.language=original_language
	app.clear_view();DisplayServer.window_set_size(Vector2i(1280,720));await process_frame
	print("OPEN DAY validation: initializing demo arena")
	app.configure_demo("t34_85")
	var battle=load("res://scenes/Battle.tscn").instantiate();battle.session_config=app.session;root.add_child(battle)
	for _frame in range(8):await process_frame
	battle.paused=true
	check(battle.is_demo,"Demo runtime enabled")
	check(battle.alive_count(0)==1 and battle.alive_count(1)==1,"Demo is isolated 1v1")
	var only_active_models=0
	for i in battle.vehicles.size():
		if battle.vehicles[i].model.get_child_count()>0:only_active_models+=1
	check(only_active_models==2,"Demo loads and renders only its two active tank models")
	check(battle.vehicles[0].find_child("OpenDayParticipantMark",true,false)!=null and battle.vehicles[8].find_child("OpenDayParticipantMark",true,false)!=null,"Player and MaleCNS receive project identity marks")
	check(not battle.objectives[0].marker.visible,"Domination UI hidden")
	var idle_command=battle.demo_command(false);var firing_command=battle.demo_command(true)
	check(idle_command[0]>.5 and idle_command.slice(1,5)==[0.0,0.0,0.0,0.0],"Open Day drives forward without autonomous hull or turret steering")
	check(firing_command[5]==1.0,"Right mouse button maps to fire action")
	check(battle.camera_button.visible and is_instance_valid(battle.demo_controls),"Mouse-accessible camera selector and control guide are visible")
	var vehicle=battle.vehicles[0];var original_yaw=vehicle.rotation.y;var original_turret=vehicle.turret_angle;var original_gun=vehicle.gun_angle
	battle.paused=false;battle.camera_mode=2
	battle.demo_apply_mouse_motion(Vector2(80,-40),false)
	check(vehicle.rotation.y==original_yaw and vehicle.turret_angle>original_turret and vehicle.gun_angle>original_gun,"Mouse movement aims the turret and raises the gun independently")
	var aimed_turret=vehicle.turret_angle;var aimed_gun=vehicle.gun_angle
	battle.demo_apply_mouse_motion(Vector2(30,0),true)
	check(vehicle.rotation.y!=original_yaw and vehicle.turret_angle==aimed_turret and vehicle.gun_angle==aimed_gun,"Middle-button drag rotates the hull without changing gun aim")
	battle.demo_intro_left=0;battle.demo_intro.visible=false;battle.update_camera_button();battle.demo_set_sniper_mode(true);await process_frame
	check(battle.demo_sniper_mode and battle.gunner_reticle.visible and battle.gunner_reticle.scoped and battle.camera.fov<30.0,"Gunner view shows the reticle, sniper grid and optical zoom")
	check(battle.camera_button.text.contains(battle.camera_name()),"Camera selector names the current first-person view")
	await capture("battle-gunner-scope-1280x720")
	battle.demo_set_sniper_mode(false);vehicle.rotation.y=original_yaw;vehicle.turret_angle=original_turret;vehicle.gun_angle=original_gun;battle.camera_mode=1;battle.paused=true
	check(is_instance_valid(battle.demo_brain_panel) and battle.hud.visible==false,"Presentation HUD replaces research HUD")
	battle.demo_intro_left=0;battle.demo_intro.visible=false;battle.update_demo_hud();await capture("battle-1280x720")
	# Exercise the Open Day scheduler with no live socket: fixed physics must
	# advance on neutral startup and continue using a last accepted command.
	var test_bridge=load("res://scripts/bridge.gd").new()
	battle.bridge=test_bridge;battle.requires_brain=true;battle.session_config=null;battle.paused=false
	var before_sim=battle.sim_time;var before_frame=battle.frame
	for _step in 26:await physics_frame
	battle.paused=true
	var neutral_steps=battle.frame-before_frame
	check(neutral_steps>=24 and neutral_steps<=26,"Open Day physics advances each fixed tick before the first neural reply")
	check(absf((battle.sim_time-before_sim)-float(neutral_steps)*.02)<.001,"Simulation time advances by the configured 0.02 seconds per fixed step")
	var accepted_actions=[]
	for _agent in 16:accepted_actions.append([.25,0.0,0.0,0.0,0.0,0.0])
	test_bridge.last_valid_commands=accepted_actions
	test_bridge.responses_received=1
	test_bridge.last_response_at_usec=Time.get_ticks_usec()
	before_sim=battle.sim_time;before_frame=battle.frame
	battle.paused=false
	for _step in 26:await physics_frame
	battle.paused=true
	check(battle.frame-before_frame>=24 and battle.frame-before_frame<=26 and absf((battle.sim_time-before_sim)-float(battle.frame-before_frame)*.02)<.001,"Open Day physics keeps advancing under zero-order hold (steps=%d, sim=%.3f)" % [battle.frame-before_frame,battle.sim_time-before_sim])
	check(test_bridge.repeated_command_steps==battle.frame-before_frame and test_bridge.responses_received==1,"Held motor commands do not fabricate fresh neural responses (repeats=%d, physics=%d, responses=%d)" % [test_bridge.repeated_command_steps,battle.frame-before_frame,test_bridge.responses_received])
	battle.queue_free();await process_frame
	print("OPEN DAY VALIDATION failures=",failures)
	quit(0 if failures==0 else 1)
