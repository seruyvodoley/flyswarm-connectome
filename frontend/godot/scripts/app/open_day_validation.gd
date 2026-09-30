extends SceneTree
var app
var failures=0

func check(condition: bool,message: String):
	if not condition:failures+=1;push_error(message)
func _initialize():call_deferred("run")
func capture(name: String):
	await process_frame;await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("/tmp/flyswarm-open-day-"+name+".png")

func run():
	app=root.get_node("AppState")
	var original_language=app.settings.language
	for language in ["ru","en"]:
		app.settings.language=language
		for page in ["OpenDayMain","HowItWorks"]:
			app.show_page(page);await process_frame
			check(is_instance_valid(app.view),"Open Day page loads: "+page+" "+language)
			check(not app.view.find_children("*","SubViewportContainer",true,false).is_empty(),"Fly viewport visible: "+page)
	for size in [Vector2i(1280,720),Vector2i(1440,900),Vector2i(1920,1080),Vector2i(2560,1440)]:
		DisplayServer.window_set_size(size);app.show_page("OpenDayMain");await capture(str(size.x)+"x"+str(size.y))
		var buttons=app.view.find_children("*","Button",true,false)
		check(buttons.size()>=10,"Complete Open Day controls at "+str(size))
	app.settings.language=original_language
	app.clear_view();DisplayServer.window_set_size(Vector2i(1280,720));await process_frame
	app.configure_demo("t34_85")
	var battle=load("res://scenes/Battle.tscn").instantiate();battle.session_config=app.session;root.add_child(battle);await process_frame;battle.paused=true
	check(battle.is_demo,"Demo runtime enabled")
	check(battle.alive_count(0)==1 and battle.alive_count(1)==1,"Demo is isolated 1v1")
	check(not battle.objectives[0].marker.visible,"Domination UI hidden")
	var forward=battle.demo_command_for_point(battle.vehicles[0].position+Vector3(0,0,100),false,false)
	var right=battle.demo_command_for_point(battle.vehicles[0].position+Vector3(100,0,0),false,true)
	battle.vehicles[0].speed=0
	var reverse=battle.demo_command_for_point(battle.vehicles[0].position+Vector3(0,0,100),true,false)
	check(forward[0]>0 and absf(forward[2])<.01,"Mouse aim inside dead zone keeps forward drive")
	check(absf(right[2])>.1 and right[5]>0,"Aim outside dead zone turns hull and LMB fires")
	check(reverse[0]<0,"RMB at rest selects reverse")
	var original_turreted=battle.vehicles[0].cfg.turreted;var original_limit=battle.vehicles[0].cfg.traverse_limit_deg;battle.vehicles[0].cfg.turreted=false;battle.vehicles[0].cfg.traverse_limit_deg=10
	var casemate=battle.demo_command_for_point(battle.vehicles[0].position+Vector3(100,0,0),false,false)
	battle.vehicles[0].cfg.turreted=original_turreted;battle.vehicles[0].cfg.traverse_limit_deg=original_limit
	check(absf(casemate[2])>.1,"Casemate falls back to hull traverse")
	check(is_instance_valid(battle.demo_brain_panel) and battle.hud.visible==false,"Presentation HUD replaces research HUD")
	battle.demo_intro_left=0;battle.demo_intro.visible=false;battle.update_demo_hud();await capture("battle-1280x720")
	battle.queue_free();await process_frame
	print("OPEN DAY VALIDATION failures=",failures)
	quit(0 if failures==0 else 1)
