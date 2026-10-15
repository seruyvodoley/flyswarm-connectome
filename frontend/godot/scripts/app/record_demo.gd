# Deterministic capture of the actual running interface, no fabricated UI.
extends SceneTree
var app
func _initialize():call_deferred("run")
func hold(seconds):
	for frame in range(int(seconds*24)):await process_frame
func run():
	app=root.get_node("AppState")
	app.settings.language="ru"
	app.show_page("MainMenu");await hold(3)
	app.configure("battle");await hold(3)
	app.session.seconds=120;app.session.record=false;app.launch()
	while not is_instance_valid(app.battle):await process_frame
	await hold(4)
	app.battle.cycle_camera();await hold(4)
	app.pause_menu();await hold(2)
	app.menu();app.configure("range");app.session.training_vehicle="t34_85";await hold(2)
	app.launch()
	while not is_instance_valid(app.battle):await process_frame
	var key=InputEventKey.new();key.physical_keycode=KEY_W;key.pressed=true;Input.parse_input_event(key)
	await hold(3)
	key.pressed=false;Input.parse_input_event(key);await hold(2)
	app.menu();app.configure("research");await hold(3)
	app.menu();app.configure("training");await hold(3)
	app.menu();app.show_page("Settings");await hold(3)
	app.menu();app.show_page("ReplayBrowser");await hold(2)
	app.menu();await hold(2)
	app.stop_session();app.clear_view();await process_frame
	quit()
