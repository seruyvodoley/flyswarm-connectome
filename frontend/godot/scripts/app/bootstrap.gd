extends Node
func _ready():
	# Existing bounded command-line research entry points remain compatible.
	var args=OS.get_cmdline_user_args()
	if "--seconds" in args or "--legacy-battle" in args or "--connect" in args or "--replay" in args:
		var scene=load("res://scenes/Battle.tscn").instantiate()
		add_child(scene)
	else:AppState.show_page.call_deferred("MainMenu")
