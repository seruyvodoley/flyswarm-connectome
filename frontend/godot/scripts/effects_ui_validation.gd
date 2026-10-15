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

	var maximum_sprite_width=0.0
	var maximum_expansion=0.0
	var particle_bursts=0
	var radial_sprites=0

	for fx in scene.effects:
		var node=fx.get("node",null)

		if not is_instance_valid(node):
			continue

		if node is GPUParticles3D:
			particle_bursts+=1
			check(node.one_shot and node.amount>=12,"destruction uses a bounded one-shot particle burst")
			continue
		if not node is MeshInstance3D:continue
		var quad=node.mesh as QuadMesh
		if quad==null:continue
		radial_sprites+=1
		maximum_sprite_width=maxf(maximum_sprite_width,quad.size.x)
		check(node.material_override is ShaderMaterial,"effects use soft radial sprite materials")

		var expansion=float(
			fx.get("expansion",0.0)
		)

		maximum_expansion=maxf(
			maximum_expansion,
			expansion
		)

		check(expansion<=1.0,"effect sprite remains bounded")

	check(
		maximum_sprite_width<4.0,
		"impact and smoke sprites must remain compact"
	)
	check(radial_sprites>=4,"destruction contains flash/fire/smoke radial sprites")
	check(particle_bursts==1,"destruction contains a single particle burst")

	check(
		maximum_expansion<=1.0,
		"effects must use bounded expansion"
	)

	print(
		"EFFECT/UI VALIDATION",
		" failures=",failures,
		" max_sprite_width=",maximum_sprite_width,
		" max_expansion=",maximum_expansion,
		" sprites=",radial_sprites," particle_bursts=",particle_bursts,
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
