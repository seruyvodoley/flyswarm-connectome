extends SceneTree

const TerrainScript = preload("res://scripts/terrain.gd")
const FieldEnvironment = preload("res://scripts/battlefield_environment.gd")
const DestructibleSectionScript = preload("res://scripts/demo/destructible_section.gd")
const SessionConfigScript = preload("res://scripts/app/session_config.gd")
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)

func make_world(profile: String, training_range := false) -> Array:
	var started_usec := Time.get_ticks_usec()
	var world := Node3D.new()
	root.add_child(world)
	var terrain = TerrainScript.new()
	terrain.range_flat = training_range
	terrain.environment_profile = profile
	world.add_child(terrain)
	terrain.build(training_range,1944,1500.0 if not training_range else 2200.0)
	var environment = FieldEnvironment.new()
	environment.configure_world(terrain,.35,profile,training_range)
	world.add_child(environment)
	await process_frame
	var batches: Array = world.find_children("*","MultiMeshInstance3D",true,false)
	var instances := 0
	for batch in batches:
		if batch.multimesh != null:
			instances += batch.multimesh.instance_count
	print("FIELD_PROFILE_METRICS profile=",profile," range=",training_range," generation_ms=",(Time.get_ticks_usec()-started_usec)/1000.0," multimesh_batches=",batches.size()," instances=",instances," collision_shapes=",world.find_children("*","CollisionShape3D",true,false).size()," destructibles=",world.find_children("*","DestructibleSection",true,false).size())
	return [world,terrain,environment]

func run() -> void:
	var legacy := TerrainScript.new()
	legacy.build(false,1944,1500.0)
	var visual := await make_world("enhanced_visual")
	var visual_terrain = visual[1]
	var visual_environment = visual[2]
	for point in [Vector2(-620,-410),Vector2(0,0),Vector2(320,120),Vector2(640,530)]:
		check(is_equal_approx(legacy.height_at(point.x,point.y),visual_terrain.height_at(point.x,point.y)),"Enhanced visual terrain preserves legacy physical heights at %s" % str(point))
	check(not visual_terrain.forest_blocks(Vector3(-560,0,-520),Vector3(-560,0,-190)),"Enhanced visual profile preserves the legacy forest visibility boundary")
	check(visual_environment.find_children("*","CollisionShape3D",true,false).is_empty(),"Enhanced visual scene adds no new physical obstacle colliders")
	check(visual_environment.find_children("*","MultiMeshInstance3D",true,false).size() >= 8,"Enhanced battlefield batches tree, shrub, grass, building, rock and fence visuals")
	var collision_mesh := visual_terrain.get_node_or_null("LegacyResolutionTerrainCollision") as MeshInstance3D
	var visual_mesh := visual_terrain.get_node_or_null("FieldGround") as MeshInstance3D
	check(collision_mesh != null and not collision_mesh.visible,"Enhanced visual terrain keeps the exact legacy collision mesh hidden under the detailed render mesh")
	check(visual_mesh != null and visual_mesh.mesh != null and visual_mesh.mesh.get_faces().size() > collision_mesh.mesh.get_faces().size(),"Enhanced visual surface increases terrain tessellation without changing its legacy silhouette")
	visual[0].queue_free()
	await process_frame
	await physics_frame
	var physical := await make_world("enhanced_physical")
	var physical_terrain = physical[1]
	var physical_environment = physical[2]
	await physics_frame
	var ground_query := PhysicsRayQueryParameters3D.create(Vector3(17.0,80.0,-29.0),Vector3(17.0,-80.0,-29.0))
	var ground_hit: Dictionary = physical[0].get_world_3d().direct_space_state.intersect_ray(ground_query)
	check(not ground_hit.is_empty() and absf(float(ground_hit.position.y)-physical_terrain.height_at(17.0,-29.0)) < .35,"Rendered physical terrain height agrees with its active collision surface")
	check(not is_equal_approx(legacy.height_at(211.0,-175.0),physical_terrain.height_at(211.0,-175.0)),"Enhanced physical profile adds a deterministic relief layer")
	check(physical_terrain.forest_blocks(Vector3(-560,0,-520),Vector3(-560,0,-190)),"Enhanced physical profile aligns agent forest occlusion with added woodlots")
	check(physical_environment.find_children("*","CollisionShape3D",true,false).size() > 100,"Enhanced physical profile enables tree, building, fence and rock collision")
	check(physical_environment.find_children("*","DestructibleSection",true,false).size() > 50,"Enhanced physical profile registers destructible buildings and fences")
	var destructibles: Array = physical_environment.find_children("*","DestructibleSection",true,false)
	var ram_target: DestructibleSection = null
	var projectile_target: DestructibleSection = null
	for section in destructibles:
		if section is DestructibleTree and ram_target == null:
			ram_target = section
		elif not section is DestructibleTree and projectile_target == null:
			projectile_target = section
	check(ram_target != null and projectile_target != null,"Enhanced physical profile includes both destructible trees and structural sections")
	if ram_target != null:
		ram_target.damage_ram(91,45000.0,Vector3(0.0,0.0,-22.0),ram_target.global_position,Vector3.FORWARD)
		check(ram_target.falling or ram_target.broken,"A fast, direct heavy-vehicle ram starts felling a tree")
	if projectile_target != null:
		projectile_target.damage_projectile({"mass_kg":10.0},Vector3(0.0,0.0,-1100.0),Vector3.FORWARD,projectile_target.global_position)
		check(projectile_target.broken,"A high-energy projectile can break one structural section while leaving the rest intact")
	var cfg = SessionConfigScript.new()
	cfg.environment_profile = "enhanced_physical"
	var args: PackedStringArray = cfg.cli_args()
	check(args.has("--environment-profile") and args[args.find("--environment-profile") + 1] == "enhanced_physical","The settings profile propagates through every SessionConfig-launched battle")
	var range := await make_world("enhanced_visual",true)
	var range_environment = range[2]
	var range_trees: Array = range_environment.find_children("*","MultiMeshInstance3D",true,false)
	check(not range_trees.is_empty(),"Training Range retains its enhanced field dressing")
	for batch in range_trees:
		check(batch.multimesh.instance_count > 0,"Training Range scenery batch is populated")
	print("FIELD_ENVIRONMENT_VALIDATION failures=",failures)
	for world_state in [visual[0],physical[0],range[0]]:
		world_state.queue_free()
	legacy.queue_free()
	await process_frame
	quit(0 if failures == 0 else 1)
