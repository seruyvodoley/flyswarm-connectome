extends SceneTree

## Saves a genuine rendered overhead view of the integrated Historical Battle.
const OUTPUT_DIR="res://../../artifacts/map-integration"

func _initialize()->void:
	call_deferred("capture")

func capture()->void:
	var bootstrap=load("res://scenes/Bootstrap.tscn").instantiate()
	root.add_child(bootstrap)
	var battle:Node
	for _frame in 90:
		await process_frame
		for child in bootstrap.get_children():
			if child.get("vehicles") is Array:
				battle=child
				break
		if battle!=null:break
	if battle==null:
		push_error("Historical battle did not load for the map overview capture")
		quit(1)
		return
	var camera:=battle.get("camera") as Camera3D
	var environment:=battle.get("observer_environment") as Environment
	if "--demo" in OS.get_cmdline_user_args():
		battle.set("demo_intro_left",0.0)
		var intro:=battle.get("demo_intro") as Control
		if intro!=null:intro.hide()
		battle.set("sim_time",10.0)
		battle.call("update_demo_smoke_screen")
		var curtain:=battle.get("demo_smoke_screen") as StaticBody3D
		if curtain!=null:curtain.hide()
		if environment!=null:environment.fog_enabled=false
		battle.set("camera_mode",3)
		if environment!=null:environment.fog_enabled=false
		camera.position=Vector3(-70.0,17.0,-44.0)
		camera.look_at(Vector3(-48.0,2.0,-14.0),Vector3.UP)
		await _save_capture("open-day-village.png")
	else:
		battle.set("camera_mode",0)
		battle.set("battlefield_zoom",380.0)
		battle.set("battlefield_pan",Vector2(-35.0,-65.0))
		for _frame in 12:await process_frame
		if not await _save_capture("historical-battle-overview.png"):quit(1);return
		battle.set("camera_mode",3)
		camera.position=Vector3(-112.0,20.0,-132.0)
		camera.look_at(Vector3(-82.0,2.0,-92.0),Vector3.UP)
		await _save_capture("historical-battle-village.png")
	quit(0)

func _save_capture(filename:String)->bool:
	for _frame in 12:await process_frame
	var destination=ProjectSettings.globalize_path(OUTPUT_DIR.path_join(filename))
	DirAccess.make_dir_recursive_absolute(destination.get_base_dir())
	var error=root.get_viewport().get_texture().get_image().save_png(destination)
	if error!=OK:
		push_error("Could not save the rendered map image: "+str(error))
		return false
	print("MAP CAPTURE ",destination)
	return true
