extends Node
func _ready():
	# Existing bounded command-line research entry points remain compatible.
	var args=OS.get_cmdline_user_args()
	if "--validate-open-day-map" in args:
		add_child(load("res://scripts/app/open_day_map_checks.gd").new())
		return
	if "--validate-open-day-matches" in args:
		add_child(load("res://scripts/app/open_day_match_checks.gd").new())
		return
	if "--validate-open-day-motion" in args:
		# Exported Godot templates do not support the editor's --script entry.
		# Run the same bounded checks through the packaged application's entry.
		add_child(load("res://scripts/app/open_day_motion_checks.gd").new())
		return
	if "--seconds" in args or "--legacy-battle" in args or "--connect" in args or "--replay" in args:
		var scene=load("res://scenes/Battle.tscn").instantiate()
		add_child(scene)
	elif "--open-day" in args:
		AppState.settings.language="ru"
		AppState.open_day_menu.call_deferred()
	else:AppState.show_page.call_deferred("MainMenu")
