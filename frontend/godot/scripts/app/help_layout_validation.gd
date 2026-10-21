extends SceneTree
var failures := 0
func _initialize():
	call_deferred("run")
func run():
	var page = load("res://scripts/app/marl_laboratory.gd").new()
	root.add_child(page)
	for viewport_size in [Vector2i(1280,720),Vector2i(1920,1080),Vector2i(2880,860),Vector2i(800,480)]:
		get_root().size=viewport_size
		await process_frame
		page._show_code_help()
		await process_frame
		var dialog=page.find_child("PythonApiHelp",true,false) as Window
		if dialog==null:
			push_error("Help dialog was not created")
			failures+=1
			continue
		var label=dialog.find_child("HelpText",true,false) as Label
		if label==null or label.autowrap_mode!=TextServer.AUTOWRAP_WORD_SMART:
			push_error("Help text is missing or does not wrap")
			failures+=1
		print("HELP_LAYOUT viewport=",viewport_size," dialog=",dialog.size," position=",dialog.position)
		if dialog.size.x>viewport_size.x or dialog.size.y>viewport_size.y:
			push_error("Help dialog exceeds viewport "+str(viewport_size))
			failures+=1
		dialog.queue_free()
		await process_frame
	quit(1 if failures else 0)
