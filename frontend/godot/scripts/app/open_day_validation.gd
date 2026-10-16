extends SceneTree
const Combat=preload("res://scripts/combat.gd")
const OpenDayController=preload("res://scripts/app/open_day_controller.gd")
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
	app.open_day_mode=false;app.show_page("MainMenu");await process_frame
	var main_buttons=app.view.find_children("*","Button",true,false)
	check(not main_buttons.is_empty(),"Main menu exposes focusable gamepad controls")
	if not main_buttons.is_empty():
		main_buttons[0].grab_focus()
		var main_cross=InputEventJoypadButton.new();main_cross.device=0;main_cross.button_index=JoyButton.JOY_BUTTON_A;main_cross.pressed=true;Input.parse_input_event(main_cross);await process_frame
		check(app.current_page=="OpenDayMain","Cross/A activates the focused main-menu action")
		main_cross.pressed=false;Input.parse_input_event(main_cross);await process_frame
	for page_name in ["Settings","ResearchLab","TrainingMenu","MarlLaboratory"]:
		app.open_day_mode=false;app.show_page(page_name);await process_frame
		var activated=[0]
		var probe=Button.new();probe.text="Controller input validation";probe.pressed.connect(func():activated[0]+=1);app.view.add_child(probe);probe.grab_focus()
		var window_cross=InputEventJoypadButton.new();window_cross.device=0;window_cross.button_index=JoyButton.JOY_BUTTON_A;window_cross.pressed=true;Input.parse_input_event(window_cross);await process_frame
		check(activated[0]==1,"Cross/A activates the focused control in "+page_name)
		window_cross.pressed=false;Input.parse_input_event(window_cross);await process_frame
	app.open_day_mode=false;app.show_page("TrainingMenu");await process_frame
	check(app.view.find_child("CombatCheckpoint",true,false)!=null,"Readout Training retains its policy field and exposes combat resume checkpoint selection")
	check(app.view.find_child("CombatRewardCurve",true,false)==null,"Training reward graph is created only while a combat-training job is running")
	var has_combat_training=false
	for node in app.view.find_children("*","Label",true,false):
		if node.text=="MALECNS COMBAT TRAINING":has_combat_training=true
	check(has_combat_training,"MaleCNS Combat Training is integrated into the existing Readout Training page")
	app.session.mode="combat_training";app.show_page("JobProgress");await process_frame
	var curve=app.view.find_child("CombatRewardCurve",true,false)
	check(curve!=null and app.view.find_child("PauseJob",true,false)!=null and app.view.find_child("SaveCheckpointNow",true,false)!=null,"Combat training progress includes a live reward chart, pause/resume and explicit checkpoint save")
	var reward_samples:Array[float]=[0.0,1.0,-.25]
	if curve!=null:curve.call("set_samples",reward_samples);await process_frame
	app.session.mode="training"
	for language in ["ru","en"]:
		app.settings.language=language
		for page in ["OpenDayMain","HowItWorks","Settings"]:
			app.show_page(page);await process_frame
			check(is_instance_valid(app.view),"Open Day page loads: "+page+" "+language)
			if page!="Settings":check(not app.view.find_children("*","SubViewportContainer",true,false).is_empty(),"Fly viewport visible: "+page)
			else:check(app.view.find_child("MaleCNSDatasetPath",true,false)!=null,"Dataset folder setting is available: "+language)
			if language=="ru":await capture("main-ru" if page=="OpenDayMain" else "how-it-works-ru")
			if page=="HowItWorks":
				var cards=app.view.find_child("HowItWorksCards",true,false) as GridContainer
				check(cards!=null and cards.columns==2 and cards.get_child_count()==4,"How It Works uses four readable cards in a two-column layout")
				if cards!=null:
					for card in cards.get_children():
						check(cards.get_global_rect().encloses(card.get_global_rect()),"How It Works card remains inside the page at "+language)
	var result_screen=load("res://scripts/app/open_day_page.gd").new()
	result_screen.page="DemoResult"
	root.add_child(result_screen)
	await process_frame
	check(result_screen.find_children("*","ImpactKillcam",true,false).is_empty(),"Round result screen does not create a hit camera outside active combat")
	result_screen.queue_free()
	await process_frame
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
	app.show_page("HowItWorks");await process_frame
	var how_page=app.view
	var how_buttons=how_page.controller_buttons()
	check(how_buttons.size()==2,"How It Works provides a compact controller focus order")
	if how_buttons.size()==2:
		how_buttons[0].grab_focus()
		var dpad=InputEventJoypadButton.new();dpad.device=0;dpad.button_index=JoyButton.JOY_BUTTON_DPAD_DOWN;dpad.pressed=true;Input.parse_input_event(dpad);await process_frame
		check(root.get_viewport().gui_get_focus_owner()==how_buttons[1],"D-pad advances exactly one focused Open Day menu button")
		dpad.pressed=false;Input.parse_input_event(dpad);await process_frame
		how_buttons[0].grab_focus()
		var nav_stick=InputEventJoypadMotion.new();nav_stick.device=0;nav_stick.axis=JoyAxis.JOY_AXIS_LEFT_Y;nav_stick.axis_value=.72;Input.parse_input_event(nav_stick);await process_frame
		var first_stick_focus=root.get_viewport().gui_get_focus_owner()
		nav_stick=InputEventJoypadMotion.new();nav_stick.device=0;nav_stick.axis=JoyAxis.JOY_AXIS_LEFT_Y;nav_stick.axis_value=.78;Input.parse_input_event(nav_stick);await process_frame
		check(first_stick_focus==how_buttons[1] and root.get_viewport().gui_get_focus_owner()==how_buttons[1],"Holding or gently varying the left stick advances only one menu item")
		nav_stick.axis_value=0.0;Input.parse_input_event(nav_stick);await process_frame
		nav_stick.axis_value=.76;Input.parse_input_event(nav_stick);await process_frame
		check(root.get_viewport().gui_get_focus_owner()==how_buttons[0],"Returning the stick to neutral rearms one next menu step")
		how_buttons[1].grab_focus()
		var cross=InputEventJoypadButton.new();cross.device=0;cross.button_index=JoyButton.JOY_BUTTON_A;cross.pressed=true;Input.parse_input_event(cross);await process_frame
		check(app.current_page=="OpenDayMain","Cross confirms one focused menu action without double activation")
		cross.pressed=false;Input.parse_input_event(cross);await process_frame
		for _frame in 4:await process_frame
	check(InputMap.has_action("od_move_forward") and InputMap.has_action("od_look_right") and InputMap.has_action("od_fire") and InputMap.has_action("od_zoom"),"Open Day registers named DualSense InputMap actions")
	check(InputMap.action_get_events("od_fire").size()==1 and InputMap.action_get_events("od_zoom").size()==1,"R2 and L2 use standard Joypad trigger-axis events")
	check(OpenDayController.shape_vector(Vector2(.1,.08))==Vector2.ZERO,"Radial stick deadzone suppresses small drift")
	var slow_stick=OpenDayController.drive_command(Vector2(0,-.35),false);var full_stick=OpenDayController.drive_command(Vector2(0,-1),false)
	check(slow_stick[0]>0.0 and slow_stick[0]<full_stick[0] and is_equal_approx(full_stick[0],1.0),"Physical left-stick up produces forward throttle while preserving analog scaling")
	var turn_right=OpenDayController.drive_command(Vector2(.8,0),true)
	check(turn_right[2]<0.0 and turn_right[5]==1.0 and OpenDayController.drive_command(Vector2.ZERO,false)==[0.0,0.0,0.0,0.0,0.0,0.0],"Inverted physical left-stick horizontal axis is normalized and one-shot fire remains independent")
	check(OpenDayController.normalize_trigger(-1.0,-1.0)==0.0 and is_equal_approx(OpenDayController.normalize_trigger(0.56,0.0),0.56) and OpenDayController.normalize_trigger(1.0,-1.0)==1.0,"Trigger normalization supports both -1..1 and 0..1 hardware ranges")
	var look_right=OpenDayController.advance_camera(0.0,0.0,Vector2(1,0),.1,false);var look_left=OpenDayController.advance_camera(0.0,0.0,Vector2(-1,0),.1,false)
	var look_up=OpenDayController.advance_camera(0.0,0.0,Vector2(0,-1),.1,false);var look_down=OpenDayController.advance_camera(0.0,0.0,Vector2(0,1),.1,false)
	check(look_right.x>0.0 and look_left.x<0.0 and look_up.y>0.0 and look_down.y<0.0,"Camera response preserves its standard semantic left/right and up/down directions")
	var right_axis=InputEventJoypadMotion.new();right_axis.device=0;right_axis.axis=JoyAxis.JOY_AXIS_RIGHT_X;right_axis.axis_value=.75;Input.parse_input_event(right_axis);await process_frame
	check(Input.get_action_strength("od_look_left")>.7 and Input.get_action_strength("od_look_right")<.1,"Physical right-stick right is mapped to look-left")
	right_axis.axis_value=-.75;Input.parse_input_event(right_axis);await process_frame
	check(Input.get_action_strength("od_look_right")>.7 and Input.get_action_strength("od_look_left")<.1,"Physical right-stick left is mapped to look-right")
	right_axis.axis_value=0.0;Input.parse_input_event(right_axis);await process_frame
	var scoped_look=OpenDayController.advance_camera(0.0,0.0,Vector2(1,0),.1,true)
	check(scoped_look.x>0.0 and scoped_look.x<look_right.x and OpenDayController.camera_forward(0.0,0.0).is_equal_approx(Vector3(0,0,1)),"ADS lowers camera sensitivity and camera ray points forward at neutral")
	app.settings.language=original_language
	app.clear_view();DisplayServer.window_set_size(Vector2i(1280,720));await process_frame
	var stick_event=InputEventJoypadMotion.new();stick_event.device=0;stick_event.axis=JoyAxis.JOY_AXIS_LEFT_Y;stick_event.axis_value=-.75;Input.parse_input_event(stick_event);await process_frame
	check(Input.get_action_strength("od_move_forward")>.7,"A standard negative left-stick Y event produces forward analog input")
	stick_event=InputEventJoypadMotion.new();stick_event.device=0;stick_event.axis=JoyAxis.JOY_AXIS_LEFT_Y;stick_event.axis_value=.75;Input.parse_input_event(stick_event);await process_frame
	check(Input.get_action_strength("od_move_reverse")>.7,"A standard positive left-stick Y event produces reverse analog input")
	stick_event=InputEventJoypadMotion.new();stick_event.device=0;stick_event.axis=JoyAxis.JOY_AXIS_LEFT_Y;stick_event.axis_value=0.0;Input.parse_input_event(stick_event);await process_frame
	var trigger_event=InputEventJoypadMotion.new();trigger_event.device=0;trigger_event.axis=JoyAxis.JOY_AXIS_TRIGGER_RIGHT;trigger_event.axis_value=.8;Input.parse_input_event(trigger_event);await process_frame
	check(Input.get_action_strength("od_fire")>.7,"Standard R2 trigger-axis input is registered by the fire InputMap action")
	trigger_event=InputEventJoypadMotion.new();trigger_event.device=0;trigger_event.axis=JoyAxis.JOY_AXIS_TRIGGER_RIGHT;trigger_event.axis_value=0.0;Input.parse_input_event(trigger_event);await process_frame
	trigger_event=InputEventJoypadMotion.new();trigger_event.device=0;trigger_event.axis=JoyAxis.JOY_AXIS_TRIGGER_LEFT;trigger_event.axis_value=.8;Input.parse_input_event(trigger_event);await process_frame
	check(Input.get_action_strength("od_zoom")>.7,"Standard L2 trigger-axis input is registered by the zoom InputMap action")
	trigger_event=InputEventJoypadMotion.new();trigger_event.device=0;trigger_event.axis=JoyAxis.JOY_AXIS_TRIGGER_LEFT;trigger_event.axis_value=0.0;Input.parse_input_event(trigger_event);await process_frame
	var pause_event=InputEventJoypadButton.new();pause_event.device=0;pause_event.button_index=JoyButton.JOY_BUTTON_START;pause_event.pressed=true;Input.parse_input_event(pause_event);await process_frame
	check(Input.is_action_pressed("od_pause"),"DualSense OPTIONS is mapped to the pause action")
	pause_event.pressed=false;Input.parse_input_event(pause_event);await process_frame
	print("OPEN DAY validation: initializing demo arena")
	app.configure_demo("t34_85")
	check(is_equal_approx(app.session.seconds,120.0),"Open Day starts with a two-minute battle limit")
	var battle=load("res://scenes/Battle.tscn").instantiate();battle.session_config=app.session;root.add_child(battle)
	for _frame in range(8):await process_frame
	check(is_equal_approx(battle.time_limit,120.0),"The live Open Day battle honors the two-minute limit")
	check(battle.demo_status.get_script()==load("res://scripts/app/demo_health_hud.gd"),"Open Day uses visual health bars instead of text hash meters")
	battle.paused=true
	var connected_controllers=Input.get_connected_joypads()
	check(battle.demo_gamepad_active==not connected_controllers.is_empty(),"Open Day automatically selects a connected joypad when present")
	print("OPENDAY CONTROLLER connected=",connected_controllers," active=",battle.demo_gamepad_active," name=",Input.get_joy_name(battle.demo_controller_device) if battle.demo_controller_device>=0 else "mouse fallback")
	if battle.demo_gamepad_active:
		var player_vehicle=battle.vehicles[0]
		var original_hull_yaw=player_vehicle.rotation.y
		battle.paused=false;battle.demo_intro_left=0.0
		Input.action_press("od_move_forward",.72)
		var analog_drive=battle.demo_gamepad_commands(false)
		check(analog_drive[0]>0.0 and analog_drive[0]<1.0 and analog_drive[2]==0.0 and not player_vehicle.manual_hull_aim,"Physical left-stick up advances the tank and preserves analog throttle without hull autopilot")
		Input.action_release("od_move_forward")
		Input.action_press("od_look_right",1.0)
		var original_camera_yaw=battle.demo_camera_yaw
		battle.update_demo_controller_input(.1)
		battle._process(.016)
		check(battle.demo_camera_yaw>original_camera_yaw and player_vehicle.rotation.y==original_hull_yaw and (-battle.camera.global_basis.z).angle_to(OpenDayController.camera_forward(battle.demo_camera_yaw,battle.demo_camera_pitch))<.01,"Right-stick look rotates the smooth camera and reticle aim independently of the hull")
		var aimed_point=battle.demo_aim_world_point
		var synthetic_mouse=InputEventMouseMotion.new();synthetic_mouse.position=Vector2(50,50);synthetic_mouse.relative=Vector2(40,40);battle._input(synthetic_mouse)
		check(battle.demo_aim_world_point==aimed_point,"Mouse motion cannot overwrite active DualSense camera aim")
		Input.action_release("od_look_right");battle.paused=true
		player_vehicle.speed=6.0;player_vehicle.drive_throttle=.7;player_vehicle.yaw_rate=.4;player_vehicle.cmd=[.7,0.0,.4,0.0,0.0,1.0]
		battle.demo_controller_safe_pause()
		check(battle.paused and player_vehicle.speed==0.0 and player_vehicle.drive_throttle==0.0 and player_vehicle.yaw_rate==0.0 and player_vehicle.cmd==[0.0,0.0,0.0,0.0,0.0,0.0],"Controller-loss pause clears throttle, steering and pending fire")
		battle.resume_active_clock()
	# Keep the existing mouse regression suite deterministic even when a physical
	# controller is paired with this Mac.
	battle.demo_gamepad_active=false
	battle.update_demo_control_hint()
	check(battle.is_demo,"Demo runtime enabled")
	check(battle.alive_count(0)==1 and battle.alive_count(1)==1,"Demo is isolated 1v1")
	check(battle.terrain.height_at(0.0,0.0)<1.0,"Open Day keeps the valley traversable after the opening screen clears")
	var demo_min=INF;var demo_max=-INF;var demo_grade=0.0
	for x in range(-180,181,20):
		for z in range(-160,161,20):
			var height=battle.terrain.height_at(float(x),float(z));demo_min=minf(demo_min,height);demo_max=maxf(demo_max,height)
			demo_grade=maxf(demo_grade,absf(battle.terrain.height_at(float(x)+5.0,float(z))-height)/5.0)
	check(demo_max-demo_min>2.0 and demo_grade<.18,"Open Day has drivable shallow hull-down shoulders and swales instead of a flat plane")
	check(battle.demo_smoke_screen!=null and battle.demo_smoke_screen.collision_layer==4 and battle.demo_smoke_screen.visible,"A visible collidable smoke curtain physically separates the teams at spawn")
	check(battle.demo_sight_locked(battle.vehicles[0],battle.vehicles[8]),"Open Day enemy sensing is locked during the first ten seconds")
	battle.sim_time=9.99
	check(battle.demo_sight_locked(battle.vehicles[0],battle.vehicles[8]),"The opening sight lock remains active until ten seconds")
	battle.sim_time=10.0
	battle.update_demo_smoke_screen()
	check(not battle.demo_sight_locked(battle.vehicles[0],battle.vehicles[8]),"Enemy sensing unlocks at ten seconds")
	check(battle.demo_smoke_screen.collision_layer==0,"The physical opening smoke curtain clears at ten seconds")
	battle.sim_time=0.0
	check(battle.vehicles[0].demo_health==battle.vehicles[8].demo_health and battle.vehicles[0].demo_health_max==battle.vehicles[8].demo_health_max and battle.vehicles[0].demo_health_max==6,"Open Day gives the player and MaleCNS equal six-point durability")
	var only_active_models=0
	for i in battle.vehicles.size():
		if battle.vehicles[i].model.get_child_count()>0:only_active_models+=1
	check(only_active_models==2,"Demo loads and renders only its two active tank models")
	check(battle.vehicles[0].find_child("OpenDayParticipantMark",true,false)!=null and battle.vehicles[8].find_child("OpenDayParticipantMark",true,false)!=null,"Player and MaleCNS receive project identity marks")
	check(not battle.objectives[0].marker.visible,"Domination UI hidden")
	var idle_command=battle.demo_command(false);var firing_command=battle.demo_command(true)
	check(idle_command[0]>.5 and idle_command.slice(1,5)==[0.0,0.0,0.0,0.0],"Open Day drives forward without autonomous hull or turret steering")
	check(firing_command[5]==1.0 and battle.demo_mouse_commands(true)[5]==1.0,"Left mouse button maps to fire action")
	check(battle.demo_mouse_commands(false)[0]>=.36,"Player autopilot keeps the tank moving while independently steering toward the engagement")
	var fly=battle.vehicles[8];var fly_cmd=battle.apply_demo_tactical_aux(fly,[0.0,0.0,0.0,0.0,0.0,1.0])
	check(fly_cmd[0]>=.42 and is_finite(float(fly_cmd[2])) and fly_cmd[5]==0.0,"Hard Open Day navigation maneuvers while hidden and rejects unsupported fire commands")
	var saved_sim_time=battle.sim_time;var saved_seen=fly.seen;var saved_target=fly.target;var saved_turret=fly.turret_angle
	battle.sim_time=12.0;fly.seen=true;fly.target=0;fly.turret_angle+=.45
	var hard_fly_cmd=battle.apply_demo_tactical_aux(fly,[.2,0.0,0.0,0.0,0.0,1.0])
	check(absf(hard_fly_cmd[2])>.05 and absf(hard_fly_cmd[3])>.1 and hard_fly_cmd[5]==0.0,"Hard gunnery predicts the visible target, improves traverse, and waits to fire until the ballistic solution is aligned")
	var saved_gun=fly.gun_angle;var player_for_aim=battle.vehicles[0];var hard_shell_speed=float(fly.cfg.ammo_data.muzzle_velocity_m_s)
	fly.turret_angle=0.0;fly.gun_angle=0.0;fly.rotation.y=PI
	for _aim_iteration in 4:
		var exact_aim=player_for_aim.global_position+Vector3(0,1.45,0)-fly.muzzle.global_position
		var exact_horizontal=Vector2(exact_aim.x,exact_aim.z).length()
		var exact_discriminant=hard_shell_speed**4-9.81*(9.81*exact_horizontal*exact_horizontal+2.0*exact_aim.y*hard_shell_speed*hard_shell_speed)
		if exact_discriminant>=0.0:fly.gun_angle=atan((hard_shell_speed*hard_shell_speed-sqrt(exact_discriminant))/(9.81*maxf(1.0,exact_horizontal)))
		fly.turret_angle=wrapf(atan2(exact_aim.x,exact_aim.z)-fly.rotation.y,-PI,PI)
	battle.demo_fly_velocity_valid=false;fly.reload_left=0.0
	var aligned_fire=battle.apply_demo_tactical_aux(fly,[.2,0.0,0.0,0.0,0.0,0.0])
	check(aligned_fire[5]==1.0,"Hard gunnery releases fire when its predicted ballistic aim is aligned")
	fly.gun_angle=saved_gun
	battle.sim_time=saved_sim_time;fly.seen=saved_seen;fly.target=saved_target;fly.turret_angle=saved_turret
	var fallback_source=FileAccess.get_file_as_string("res://scripts/battle.gd")
	check(fallback_source.contains("if is_demo and v.agent_id==8:v.cmd=apply_demo_tactical_aux(v,v.cmd,delta)"),"Hard tactical and gunnery assistance also runs in the no-backend Open Day fallback")
	var player=battle.vehicles[0];var saved_penetration=player.cfg.ammo_data.penetration_mm.duplicate(true)
	player.cfg.ammo_data.penetration_mm=[[0.0,10000.0],[3000.0,10000.0]]
	var health_before=fly.demo_health;var modules_before=fly.modules.duplicate(true)
	fly.hit({"ammo":player.cfg.ammo_data,"distance":30.0,"velocity":Vector3(0,0,-1000),"owner":0},fly.global_position+Vector3(0,1,1),Vector3(0,0,1),"upper_front")
	check(fly.demo_health==health_before-1 and fly.last_impact.get("outcome")=="demo_hit" and fly.modules==modules_before,"Penetrating Open Day hit reduces only arcade health and cannot disable crew or modules")
	player.cfg.ammo_data.penetration_mm=saved_penetration
	var result_page=load("res://scripts/app/open_day_page.gd").new()
	check(result_page.result_outcome(true,true)=="draw","Surviving vehicles are never scored as a win")
	check(result_page.result_outcome(true,false)=="human" and result_page.result_outcome(false,true)=="fly" and result_page.result_outcome(false,false)=="draw","A winner requires destruction of the opposing vehicle")
	result_page.free()
	check(not battle.camera_button.visible and is_instance_valid(battle.demo_controls) and (battle.demo_controls.text.contains("LMB") or battle.demo_controls.text.contains("ЛКМ")) and (battle.demo_controls.text.contains("RMB") or battle.demo_controls.text.contains("ПКМ")),"Mouse fallback controls remain available without a camera selector")
	check(is_instance_valid(battle.impact_killcam),"Non-blocking hit camera is available in the otherwise unused corner")
	battle.gunner_reticle.set_aim_screen_position(Vector2(-25.0,420.0))
	check(battle.gunner_reticle.has_aim_screen_position and battle.gunner_reticle.aim_screen_target.x<0.0,"Sight preserves offscreen impact coordinates instead of snapping to screen centre")
	battle.camera_mode=0;await process_frame
	check(not battle.gunner_reticle.visible,"Battlefield observer view hides the gun sight")
	battle.camera_mode=3;await process_frame
	check(not battle.gunner_reticle.visible,"Free tactical view hides the gun sight")
	battle.camera_mode=1;await process_frame
	check(battle.gunner_reticle.visible,"Shared gun sight is visible in third-person battle view")
	var vehicle=battle.vehicles[0];var original_yaw=vehicle.rotation.y;var original_turret=vehicle.turret_angle;var original_gun=vehicle.gun_angle
	check(battle.demo_opening_flank_sign in [-1.0,1.0],"Fly opening flank is selected from the match seed instead of always starting in the same direction")
	var fly_vehicle=battle.vehicles[8]
	var original_vehicle_position=vehicle.position;var original_fly_position=fly_vehicle.position;var original_fly_yaw=fly_vehicle.rotation.y
	fly_vehicle.position=Vector3(0.0,battle.terrain.height_at(0.0,0.0)+.1,0.0);fly_vehicle.rotation.y=0.0
	vehicle.position=Vector3(0.0,battle.terrain.height_at(0.0,-32.0)+.1,-32.0)
	battle.sim_time=11.0
	var rear_response=battle.apply_demo_tactical_aux(fly_vehicle,[0.0,0.0,0.0,0.0,0.0,0.0],.1)
	check(fly_vehicle.seen and rear_response[1]>.5 and absf(rear_response[2])>.5 and absf(rear_response[3])>.05,"Fly detects a visible rear approach, pivots its hull and traverses its turret to respond")
	battle.sim_time=0.0;vehicle.position=original_vehicle_position;fly_vehicle.position=original_fly_position;fly_vehicle.rotation.y=original_fly_yaw;fly_vehicle.target=-1;fly_vehicle.seen=false
	var battle_source=FileAccess.get_file_as_string("res://scripts/battle.gd")
	check(battle_source.contains("demo_update_aim_from_world_point(vehicles[0],demo_aim_world_point)") and not battle_source.contains("demo_apply_mouse_motion(get_viewport().get_mouse_position())"),"Per-frame Open Day aim updates reuse a stable world point instead of raycasting from the moving camera")
	battle.paused=false;battle.camera_mode=1
	var right_click=InputEventMouseButton.new();right_click.button_index=MOUSE_BUTTON_RIGHT;right_click.pressed=true
	battle._unhandled_input(right_click)
	check(battle.demo_sniper_mode and battle.camera_mode==1,"RMB temporarily zooms while retaining the third-person camera")
	battle._unhandled_input(right_click)
	check(battle.demo_sniper_mode,"Holding RMB keeps the zoom active until release")
	right_click.pressed=false;battle._unhandled_input(right_click)
	check(not battle.demo_sniper_mode and battle.camera_mode==1,"Releasing RMB smoothly returns to the third-person view")
	battle.demo_apply_mouse_motion(Vector2(900,360),false)
	check(vehicle.manual_aim and battle.gunner_reticle.camera_center_marker and vehicle.rotation.y==original_yaw and vehicle.turret_angle==original_turret and vehicle.gun_angle==original_gun,"Mouse selects a target while the camera centre marker remains distinct from the moving gun sight")
	var camera_forward_before=battle.demo_camera_forward(vehicle)
	var saved_manual_yaw=vehicle.manual_turret_target
	vehicle.manual_turret_target=wrapf(saved_manual_yaw+.55,-PI,PI)
	check(camera_forward_before.angle_to(battle.demo_camera_forward(vehicle))>.4,"Open Day follow camera direction tracks the sight target independently of hull heading")
	vehicle.manual_turret_target=saved_manual_yaw
	var left_cursor=Vector2(160,360);var center_cursor=Vector2(640,360);var right_cursor=Vector2(1120,360)
	battle.demo_apply_mouse_motion(left_cursor);var left_yaw=vehicle.manual_turret_target
	battle.demo_apply_mouse_motion(center_cursor);var center_yaw=vehicle.manual_turret_target
	battle.demo_apply_mouse_motion(right_cursor);var right_yaw=vehicle.manual_turret_target
	check(absf(wrapf(left_yaw-center_yaw,-PI,PI))>deg_to_rad(2.0) and absf(wrapf(right_yaw-center_yaw,-PI,PI))>deg_to_rad(2.0),"Synthetic left, center and right cursor positions produce distinct turret aim targets")
	check(battle.gunner_reticle.camera_center_marker and battle.demo_aim_world_valid,"The camera centre marker stays fixed while mouse movement updates the world aim point")
	var stable_aim_point=battle.demo_aim_world_point
	var stable_vehicle_local_aim=battle.demo_aim_vehicle_local_point
	var camera_cursor=Vector2(900,360)
	var aimed_basis=battle.demo_camera_basis_for_aim(camera_cursor,stable_aim_point)
	var aimed_ray=(aimed_basis*Vector3.FORWARD).normalized()
	check(aimed_ray.angle_to((stable_aim_point-battle.camera.global_position).normalized())<.001,"Camera centres the selected world point under the reticle without a moving-ray feedback loop")
	check(absf(aimed_basis.x.dot(Vector3.UP))<.001,"Open Day camera keeps the horizon level while aiming")
	for cursor_position in [Vector2(180,120),Vector2(640,360),Vector2(1100,620)]:
		var cursor_basis=battle.demo_camera_basis_for_aim(cursor_position,stable_aim_point)
		var center_ray=(cursor_basis*Vector3.FORWARD).normalized()
		check(center_ray.angle_to((stable_aim_point-battle.camera.global_position).normalized())<.001 and absf(cursor_basis.x.dot(Vector3.UP))<.001,"Open Day camera keeps the target centred and horizon level after mouse movement")
	vehicle.cmd=battle.demo_command(false)
	vehicle.step(.1)
	check(absf(vehicle.manual_turret_target-vehicle.turret_angle)<absf(original_turret-vehicle.manual_turret_target) and absf(vehicle.manual_gun_target-vehicle.gun_angle)<absf(original_gun-vehicle.manual_gun_target),"Turret and gun slew toward the selected cursor target at bounded speed")
	check(battle.demo_aim_vehicle_local_point==stable_vehicle_local_aim,"Aim input remains fixed in vehicle-local space while the tank moves")
	battle._process(.1)
	check(battle.demo_aim_world_point.distance_to(vehicle.to_global(stable_vehicle_local_aim))<.001,"Camera target follows the vehicle smoothly instead of lagging behind as a fixed world point")
	check(absf((-battle.camera.global_basis.z).x)<.99,"Third-person camera remains stable independently of turret traverse")
	var aimed_turret=vehicle.turret_angle;var aimed_gun=vehicle.gun_angle
	battle.demo_apply_mouse_motion(Vector2(360,360),false)
	check(vehicle.manual_hull_target==original_yaw and vehicle.turret_angle==aimed_turret and vehicle.gun_angle==aimed_gun,"Mouse aiming never steers the hull")
	battle.camera_mode=1
	var middle=InputEventMouseButton.new();middle.button_index=MOUSE_BUTTON_MIDDLE;middle.pressed=true;middle.position=Vector2(640,360)
	var hull_target_before=vehicle.manual_hull_target
	Input.parse_input_event(middle);await process_frame
	var drag=InputEventMouseMotion.new();drag.position=Vector2(660,360);drag.relative=Vector2(20,0)
	Input.parse_input_event(drag);await process_frame
	var middle_release=middle.duplicate();middle_release.pressed=false;Input.parse_input_event(middle_release);await process_frame
	check(vehicle.manual_hull_target==hull_target_before,"Middle-button input has no Open Day control binding")
	var routed_right=InputEventMouseButton.new();routed_right.button_index=MOUSE_BUTTON_RIGHT;routed_right.pressed=true;routed_right.position=Vector2(640,360)
	Input.parse_input_event(routed_right);await process_frame
	check(battle.demo_sniper_mode and battle.camera_mode==1,"Routed right-button press enables momentary zoom")
	var routed_right_release=routed_right.duplicate();routed_right_release.pressed=false;Input.parse_input_event(routed_right_release);await process_frame
	check(not battle.demo_sniper_mode and battle.camera_mode==1,"Routed right-button release returns to normal zoom")
	battle.demo_intro_left=0;battle.demo_intro.visible=false;battle.update_camera_button();battle.demo_set_sniper_mode(true);await process_frame
	check(battle.demo_sniper_mode and battle.gunner_reticle.visible and battle.gunner_reticle.scoped and battle.camera.fov>30.0 and battle.camera.fov<62.0,"Third-person reticle remains visible during moderate optical zoom")
	battle._process(.13)
	var predicted_aim=Combat.predict_impact(battle.get_world_3d().direct_space_state,vehicle.muzzle.global_position,vehicle.muzzle.global_basis.z,vehicle.cfg.ammo_data,vehicle.excluded())
	check(battle.gunner_reticle.camera_center_marker,"Open Day keeps a separate camera marker fixed at screen centre")
	await capture("battle-mouse-zoom-1280x720")
	battle.impact_killcam.show_impact({"source_id":0,"source_name":"B1 T-34-85","target_name":"R1 Panther G","vehicle":"Panther G","vehicle_id":"panther_g","turret_angle":.25,"shell":"test shell","shot_count":3,"module_positions":{"gunner":[0.0,1.0,1.0]},"destroyed_modules":["gunner"],"damaged_modules":["gunner","breech"],"fatal":true,"impact":{"penetrated":true,"zone":"turret_front","capability":180.0,"effective":90.0,"damaged":["gunner"],"crew_alive":1,"crew_total":5,"outcome":"lethal","point_local":[0.0,1.0,2.0],"incoming_local":[0.0,0.0,-1.0]}})
	check(battle.impact_killcam.visible and battle.impact_killcam.body.text.contains("gunner"),"Impact report shows cumulative crew and module damage")
	check(battle.impact_killcam.model_view.model!=null and not battle.impact_killcam.model_view.model.find_children("*","MeshInstance3D",true,false).is_empty(),"Impact report renders a 3D tank model for its X-ray damage view")
	check(str(battle.impact_killcam.model_view.model.scene_file_path).contains("panther_g"),"Impact report renders the actual target type")
	battle.impact_killcam.model_view.show_event({"vehicle_id":"tiger_i","impact":{}})
	check(str(battle.impact_killcam.model_view.model.scene_file_path).contains("tiger_i"),"A different victim replaces the X-ray tank model")
	battle.impact_killcam.model_view.show_event({"vehicle_id":"panther_g","turret_angle":.25,"module_positions":{"gunner":[0.0,1.0,1.0]},"destroyed_modules":["gunner"],"impact":{"penetrated":true,"damaged":["gunner"],"point_local":[0.0,1.0,2.0],"incoming_local":[0.0,0.0,-1.0]}})
	check(battle.impact_killcam.model_view.model.find_child("DamageMarker",true,false)!=null and battle.impact_killcam.model_view.model.find_child("ImpactPath",true,false)!=null,"X-ray markers and shell path follow the rotated tank model")
	check(battle.impact_killcam.model_view.projectile!=null and battle.impact_killcam.model_view.path_start.distance_to(battle.impact_killcam.model_view.path_end)>3.0,"Impact view has an entry-to-interior projectile path")
	battle.impact_killcam.model_view._process(.6)
	check(battle.impact_killcam.model_view.projectile.position.distance_to(battle.impact_killcam.model_view.path_start)>0.1,"Impact projectile animates along its path")
	check(is_equal_approx(float(battle.impact_killcam.model_view.model.find_child("TurretPivot",true,false).rotation.y),.25),"X-ray turret follows the target's actual traverse")
	check(battle.impact_killcam.title.text.contains("B1 T-34-85") and battle.impact_killcam.title.text.contains("R1 Panther G"),"Impact report names its actual shooter and target")
	battle.update_vehicle_status()
	check(battle.impact_killcam.anchor_left==battle.vehicle_status_panel.anchor_left and battle.impact_killcam.anchor_bottom==battle.vehicle_status_panel.anchor_bottom and battle.impact_killcam.offset_left==battle.vehicle_status_panel.offset_left and battle.impact_killcam.offset_top==battle.vehicle_status_panel.offset_top and battle.impact_killcam.offset_bottom<battle.demo_controls.offset_top and not battle.vehicle_status_panel.visible,"Open Day impact report temporarily replaces the lower-left vehicle-status card without covering controls")
	vehicle.module_damage["breech"]=.5;battle.update_vehicle_status()
	await capture("battle-impact-killcam-1280x720")
	battle.vehicle_status_panel.visible=true;battle.camera_mode=0;battle._process(.02)
	check(not battle.impact_killcam.visible and not battle.vehicle_status_panel.visible,"Overview hides impact and own-vehicle status")
	battle.camera_mode=3;battle.update_vehicle_status()
	check(not battle.vehicle_status_panel.visible and not battle.should_show_impact(battle.vehicles[0],battle.vehicles[8]),"Free camera has neither own-vehicle status nor impact report")
	battle.camera_mode=1;battle.impact_killcam.show_impact({"source_id":0,"source_name":"B1","target_name":"R1","vehicle_id":"t34_85","impact":{}})
	battle.impact_killcam._process(4.1)
	check(not battle.impact_killcam.visible,"Impact report expires within five seconds")
	battle.update_vehicle_status()
	check(battle.vehicle_status_panel.visible and battle.vehicle_status_map.vehicle==vehicle and (battle.vehicle_status_detail.text.contains("breech") or battle.vehicle_status_detail.text.contains("казённик")),"Own-vehicle 2D status shows cumulative module damage")
	battle.demo_set_sniper_mode(false);vehicle.rotation.y=original_yaw;vehicle.turret_angle=original_turret;vehicle.gun_angle=original_gun;vehicle.manual_aim=false;vehicle.manual_hull_aim=false;vehicle.turret_rate=0.0;vehicle.gun_rate=0.0;vehicle.yaw_rate=0.0;battle.camera_mode=1;battle.paused=true
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
	# A real press can begin and end between fixed physics ticks. It must still
	# produce one player shot, including when that first press dismisses the intro.
	vehicle.modules.gunner=true;vehicle.modules.breech=true;vehicle.ammo_left=20;vehicle.reload_left=0.0
	vehicle.rotation.y=original_yaw;vehicle.turret_angle=original_turret;vehicle.gun_angle=original_gun
	battle.requires_brain=false;battle.paused=false;battle.demo_intro_left=3.0;battle.mouse_fire_pending=false
	var shots_before=int(vehicle.metrics.shots)
	var lmb=InputEventMouseButton.new();lmb.button_index=MOUSE_BUTTON_LEFT;lmb.pressed=true;lmb.position=battle.get_viewport().get_visible_rect().size*.5
	Input.parse_input_event(lmb)
	var lmb_release=lmb.duplicate();lmb_release.pressed=false;Input.parse_input_event(lmb_release)
	for _tick in 4:await physics_frame
	check(battle.demo_intro_left==0.0 and int(vehicle.metrics.shots)==shots_before,"First routed Open Day click only dismisses intro")
	Input.parse_input_event(lmb);Input.parse_input_event(lmb_release)
	for _tick in 4:await physics_frame
	check(int(vehicle.metrics.shots)==shots_before+1 and not battle.mouse_fire_pending,"Next brief routed Open Day click fires exactly one round (before=%d, after=%d, reason=%s, alive=%s, pending=%s)" % [shots_before,int(vehicle.metrics.shots),vehicle.weapon_block_reason(),str(vehicle.alive),str(battle.mouse_fire_pending)])
	battle.impact_killcam.show_impact({"source_id":0,"source_name":"B1","target_name":"R1","vehicle_id":"t34_85","impact":{}})
	battle.finish(false)
	check(not battle.impact_killcam.visible and not battle.should_show_impact(battle.vehicles[0],battle.vehicles[8]),"Ending a round dismisses its hit camera before the result/menu screen appears")
	check(battle.demo_brain_panel.offset_right-battle.demo_brain_panel.offset_left==300 and battle.demo_brain_preview.custom_minimum_size.x<=280,"Open Day MaleCNS panel uses the compact layout")
	battle.queue_free();await process_frame
	print("OPEN DAY VALIDATION failures=",failures)
	quit(0 if failures==0 else 1)
