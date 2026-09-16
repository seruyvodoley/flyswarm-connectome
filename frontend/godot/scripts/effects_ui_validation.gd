extends SceneTree

var failures=0

func check(condition: bool, message: String):
	if not condition:
		failures+=1
		push_error(message)


func _initialize():
	call_deferred("run")


func run():
	check(
		str(ProjectSettings.get_setting(
			"display/window/stretch/mode",
			""
		))=="canvas_items",
		"UI stretch mode must be canvas_items"
	)

	check(
		str(ProjectSettings.get_setting(
			"display/window/stretch/aspect",
			""
		))=="expand",
		"UI stretch aspect must be expand"
	)

	var scene=load(
		"res://scenes/Battle.tscn"
	).instantiate()

	root.add_child(scene)

	await process_frame
	await physics_frame

	scene.paused=true

	var before=scene.effects.size()

	scene.vehicle_destroyed_effect(
		Vector3.ZERO,
		true
	)

	check(
		scene.effects.size()>before,
		"vehicle destruction creates visual effects"
	)

	var maximum_visual_radius=0.0
	var maximum_expansion=0.0

	for fx in scene.effects:
		var node=fx.get("node",null)

		if not is_instance_valid(node):
			continue

		var sphere=node.mesh as SphereMesh

		if sphere==null:
			continue

		var expansion=float(
			fx.get("expansion",0.0)
		)

		maximum_expansion=maxf(
			maximum_expansion,
			expansion
		)

		var final_radius=(
			sphere.radius
			* (1.0+expansion)
		)

		maximum_visual_radius=maxf(
			maximum_visual_radius,
			final_radius
		)

	check(
		maximum_visual_radius<4.0,
		"individual explosion sphere must stay below 4 m radius"
	)

	check(
		maximum_expansion<=1.0,
		"effects must use bounded expansion"
	)

	print(
		"EFFECT/UI VALIDATION",
		" failures=",failures,
		" max_radius=",maximum_visual_radius,
		" max_expansion=",maximum_expansion,
		" stretch=",
		ProjectSettings.get_setting(
			"display/window/stretch/mode"
		),
		"/",
		ProjectSettings.get_setting(
			"display/window/stretch/aspect"
		)
	)

	scene.queue_free()

	await process_frame

	quit(0 if failures==0 else 1)
