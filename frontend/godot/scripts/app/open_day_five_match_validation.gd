extends SceneTree
func _initialize():call_deferred("run")
func run():root.add_child(load("res://scripts/app/open_day_match_checks.gd").new())
