extends SceneTree
const Combat=preload("res://scripts/combat.gd")
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
	check(battle.vehicles[0].demo_health==6 and battle.vehicles[8].demo_health==3,"Open Day has isolated six-point player and three-point opponent durability")
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
	var fly=battle.vehicles[8];var fly_cmd=battle.apply_demo_tactical_aux(fly,[0.0,0.0,0.0,0.0,0.0,0.0])
	check(fly_cmd[0]>=.36 and is_finite(float(fly_cmd[2])),"MaleCNS navigation assistance prevents the low-throttle stop while retaining a bounded steering command")
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
	check(not battle.camera_button.visible and is_instance_valid(battle.demo_controls) and (battle.demo_controls.text.contains("LMB") or battle.demo_controls.text.contains("ЛКМ")) and (battle.demo_controls.text.contains("RMB") or battle.demo_controls.text.contains("ПКМ")),"Open Day uses the simple mouse-only guide without a camera selector")
	check(is_instance_valid(battle.impact_killcam),"Non-blocking hit camera is available in the otherwise unused corner")
	battle.gunner_reticle.set_aim_screen_position(Vector2(-25.0,420.0))
	check(battle.gunner_reticle.has_aim_screen_position and battle.gunner_reticle.aim_screen_position.x<0.0,"Sight preserves offscreen impact coordinates instead of snapping to screen centre")
	battle.camera_mode=0;await process_frame
	check(not battle.gunner_reticle.visible,"Battlefield observer view hides the gun sight")
	battle.camera_mode=3;await process_frame
	check(not battle.gunner_reticle.visible,"Free tactical view hides the gun sight")
	battle.camera_mode=1;await process_frame
	check(battle.gunner_reticle.visible,"Shared gun sight is visible in third-person battle view")
	var vehicle=battle.vehicles[0];var original_yaw=vehicle.rotation.y;var original_turret=vehicle.turret_angle;var original_gun=vehicle.gun_angle
	battle.paused=false;battle.camera_mode=1
	var right_click=InputEventMouseButton.new();right_click.button_index=MOUSE_BUTTON_RIGHT;right_click.pressed=true
	battle._unhandled_input(right_click)
	check(battle.demo_sniper_mode and battle.camera_mode==1,"RMB temporarily zooms while retaining the third-person camera")
	battle._unhandled_input(right_click)
	check(battle.demo_sniper_mode,"Holding RMB keeps the zoom active until release")
	right_click.pressed=false;battle._unhandled_input(right_click)
	check(not battle.demo_sniper_mode and battle.camera_mode==1,"Releasing RMB smoothly returns to the third-person view")
	battle.demo_apply_mouse_motion(Vector2(900,360),false)
	check(vehicle.manual_aim and battle.gunner_reticle.aim_screen_position==Vector2(900,360) and vehicle.rotation.y==original_yaw and vehicle.turret_angle==original_turret and vehicle.gun_angle==original_gun,"Screen cursor positions the reticle and sets smooth turret/gun targets")
	vehicle.cmd=battle.demo_command(false)
	vehicle.step(.1)
	check(absf(vehicle.manual_turret_target-vehicle.turret_angle)<absf(original_turret-vehicle.manual_turret_target) and absf(vehicle.manual_gun_target-vehicle.gun_angle)<absf(original_gun-vehicle.manual_gun_target),"Turret and gun slew toward the selected cursor target at bounded speed")
	battle._process(.1)
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
	check(battle.gunner_reticle.aim_screen_position.x>=0.0 and battle.gunner_reticle.aim_screen_position.y>=0.0,"Open Day keeps the reticle at the active cursor position")
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
	check(battle.impact_killcam.offset_left>=battle.vehicle_status_panel.offset_right and battle.impact_killcam.offset_right<870 and battle.impact_killcam.offset_bottom<battle.demo_controls.offset_top,"Impact report clears status, telemetry and control guide")
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
	battle.queue_free();await process_frame
	print("OPEN DAY VALIDATION failures=",failures)
	quit(0 if failures==0 else 1)
